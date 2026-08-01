"""Conversation and intent engine.

Deterministic and rule-based on purpose. The thing that decides *what the
operator asked for* is the highest-leverage attack surface in a voice system, so
it does not itself route to a language model. A model may later enrich a plan;
it never decides whether the request was "explain the hold" or "remove it".

Two defences live here:

* **Quoted-content separation.** Text that arrives inside a document quotation is
  segmented out and marked ``QUOTED_DOCUMENT``. Imperatives found there are
  reported as detected injection attempts and carry no authority.
* **Ambiguity stops consequential work.** A request that is consequential but
  under-specified returns ``requires_clarification`` rather than a best guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .policy import AuthoritySource, RiskLevel


class IntentKind(str, Enum):
    STATUS_QUERY = "STATUS_QUERY"
    BLOCKER_QUERY = "BLOCKER_QUERY"
    APPROVAL_QUEUE_QUERY = "APPROVAL_QUEUE_QUERY"
    EVIDENCE_QUERY = "EVIDENCE_QUERY"
    EXPLAIN = "EXPLAIN"
    RUN_TOURNAMENT = "RUN_TOURNAMENT"
    COMPARE_RUNSHEET = "COMPARE_RUNSHEET"
    SHOW_DISAGREEMENTS = "SHOW_DISAGREEMENTS"
    IMPROVEMENT_LOOP = "IMPROVEMENT_LOOP"
    DRAFT_REPAIR_TASK = "DRAFT_REPAIR_TASK"
    DISPATCH_CODE_AGENT = "DISPATCH_CODE_AGENT"
    REQUEST_REVIEW = "REQUEST_REVIEW"
    SET_MODE = "SET_MODE"
    PROHIBIT_TARGET = "PROHIBIT_TARGET"
    STOP_ALL = "STOP_ALL"
    QUARANTINE = "QUARANTINE"
    CORRECTION = "CORRECTION"
    UNKNOWN = "UNKNOWN"


#: Intents that change or start work. Everything else is a question.
CONSEQUENTIAL = frozenset(
    {
        IntentKind.RUN_TOURNAMENT,
        IntentKind.IMPROVEMENT_LOOP,
        IntentKind.DRAFT_REPAIR_TASK,
        IntentKind.DISPATCH_CODE_AGENT,
        IntentKind.QUARANTINE,
    }
)

RISK_BY_KIND = {
    IntentKind.STATUS_QUERY: RiskLevel.INFORMATIONAL,
    IntentKind.BLOCKER_QUERY: RiskLevel.INFORMATIONAL,
    IntentKind.APPROVAL_QUEUE_QUERY: RiskLevel.INFORMATIONAL,
    IntentKind.EVIDENCE_QUERY: RiskLevel.INFORMATIONAL,
    IntentKind.EXPLAIN: RiskLevel.INFORMATIONAL,
    IntentKind.SHOW_DISAGREEMENTS: RiskLevel.INFORMATIONAL,
    IntentKind.COMPARE_RUNSHEET: RiskLevel.LOW,
    IntentKind.REQUEST_REVIEW: RiskLevel.LOW,
    IntentKind.SET_MODE: RiskLevel.LOW,
    IntentKind.PROHIBIT_TARGET: RiskLevel.LOW,
    IntentKind.STOP_ALL: RiskLevel.LOW,
    IntentKind.CORRECTION: RiskLevel.INFORMATIONAL,
    IntentKind.RUN_TOURNAMENT: RiskLevel.MEDIUM,
    IntentKind.IMPROVEMENT_LOOP: RiskLevel.MEDIUM,
    IntentKind.QUARANTINE: RiskLevel.MEDIUM,
    IntentKind.DRAFT_REPAIR_TASK: RiskLevel.MEDIUM,
    IntentKind.DISPATCH_CODE_AGENT: RiskLevel.HIGH,
    IntentKind.UNKNOWN: RiskLevel.MEDIUM,
}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Phrases that would be commands if the operator said them, and are therefore
# reported as injection attempts when they appear inside quoted document text.
INJECTION_MARKERS = (
    "ignore previous", "ignore the previous", "ignore all previous",
    "disregard", "you must now", "system prompt", "new instructions",
    "release the hold", "remove the hold", "approve", "grant", "bypass",
    "delete", "overwrite", "send to", "publish", "you are now",
)


@dataclass(frozen=True)
class Segment:
    text: str
    provenance: AuthoritySource

    @property
    def is_operator(self) -> bool:
        return self.provenance in (
            AuthoritySource.SPOKEN_UTTERANCE,
            AuthoritySource.TYPED_UTTERANCE,
        )


@dataclass(frozen=True)
class NormalizedIntent:
    kind: IntentKind
    confidence: float
    risk: RiskLevel
    slots: dict = field(default_factory=dict)
    requires_clarification: bool = False
    clarification_question: str = ""
    operator_text: str = ""
    quoted_segments: tuple = ()
    detected_injection: tuple = ()
    restatement: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "confidence": round(self.confidence, 3),
            "risk": self.risk.value,
            "slots": dict(self.slots),
            "requires_clarification": self.requires_clarification,
            "clarification_question": self.clarification_question,
            "operator_text": self.operator_text,
            "quoted_segments": list(self.quoted_segments),
            "detected_injection": list(self.detected_injection),
            "restatement": self.restatement,
        }


_QUOTE_PATTERNS = (
    re.compile(r"<document>(.*?)</document>", re.IGNORECASE | re.DOTALL),
    re.compile(r"[“”\"]([^“”\"]{8,})[“”\"]"),
)


def segment_transcript(text: str, channel: AuthoritySource) -> list[Segment]:
    """Split an utterance into operator speech and quoted document content."""
    segments: list[Segment] = []
    remaining = text or ""
    for pattern in _QUOTE_PATTERNS:
        pieces = []
        cursor = 0
        for match in pattern.finditer(remaining):
            pieces.append(remaining[cursor : match.start()])
            segments.append(Segment(match.group(1).strip(), AuthoritySource.QUOTED_DOCUMENT))
            cursor = match.end()
        pieces.append(remaining[cursor:])
        remaining = " ".join(piece for piece in pieces if piece)
    for line in remaining.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            segments.append(Segment(stripped.lstrip("> ").strip(), AuthoritySource.QUOTED_DOCUMENT))
        else:
            segments.append(Segment(stripped, channel))
    return segments


def detect_injection(segments) -> list[str]:
    findings = []
    for segment in segments:
        if segment.provenance is not AuthoritySource.QUOTED_DOCUMENT:
            continue
        lowered = segment.text.lower()
        for marker in INJECTION_MARKERS:
            if marker in lowered:
                findings.append(
                    f"Quoted document text contains an instruction-shaped phrase ({marker!r}); "
                    "treated as content with no authority."
                )
                break
    return findings


def _extract_count(text: str, default: int | None = None) -> int | None:
    match = re.search(r"\b(\d{1,2})\s+(?:independent\s+)?(?:agents?|readers?|candidates?|models?)\b", text)
    if match:
        return int(match.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\s+(?:independent\s+)?(?:agents?|readers?|candidates?|models?)\b", text):
            return value
    return default


def _extract_project(text: str) -> str | None:
    match = re.search(r"\bsection\s+(\d{1,3}[A-Za-z]?)\b", text, re.IGNORECASE)
    if match:
        return f"Section {match.group(1).upper()}"
    match = re.search(r"\bproject\s+([A-Za-z0-9_-]{2,32})\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


_TARGET_WORDS = {
    "workbook": "workbook",
    "spreadsheet": "workbook",
    "runsheet": "runsheet",
    "run sheet": "runsheet",
    "index": "index",
    "report": "report",
    "release": "release",
}


def _extract_targets(text: str) -> list[str]:
    found = []
    for phrase, target in _TARGET_WORDS.items():
        if phrase in text and target not in found:
            found.append(target)
    return found


def _mode_slots(text: str) -> dict | None:
    modes = {}
    if re.search(r"\bread[- ]only\b", text):
        modes["read_only"] = True
    if re.search(r"\bdraft[- ]only\b|\bdraft only\b|\bdo not execute\b", text):
        modes["draft_only"] = True
    if re.search(r"\bobserve only\b|\bjust watch\b", text):
        modes["observe_only"] = True
    if re.search(r"\blocal(?:[- ]only)? models?\b|\buse only local\b|\blocal[- ]only\b", text):
        modes["local_only"] = True
    if re.search(r"\bno cloud\b|\bcloud models? off\b|\bwithout cloud\b", text):
        modes["no_cloud"] = True
    if re.search(r"\bapprov\w* for everything\b|\brequire my approval\b", text):
        modes["approval_for_everything"] = True
    if re.search(r"\bdo not use client files?\b|\bno client files?\b", text):
        modes["no_client_files"] = True
    return modes or None


class IntentEngine:
    """Rule-based normalizer. Deterministic for the same input."""

    def normalize(
        self, transcript: str, channel: AuthoritySource = AuthoritySource.TYPED_UTTERANCE
    ) -> NormalizedIntent:
        segments = segment_transcript(transcript, channel)
        injections = detect_injection(segments)
        quoted = tuple(s.text for s in segments if s.provenance is AuthoritySource.QUOTED_DOCUMENT)
        operator_text = " ".join(s.text for s in segments if s.is_operator).strip()
        lowered = operator_text.lower()

        kind, confidence, slots = self._classify(lowered)
        risk = RISK_BY_KIND[kind]

        requires_clarification = False
        question = ""
        if kind is IntentKind.UNKNOWN:
            requires_clarification = True
            question = (
                "I could not map that to a known DataBossX action. "
                "Do you want status, a plan, a read-only comparison, or a task draft?"
            )
        elif kind in CONSEQUENTIAL and confidence < 0.6:
            requires_clarification = True
            question = (
                f"I read that as {kind.value.replace('_', ' ').lower()}, but I am not confident. "
                "Confirm the exact action before I draft anything."
            )
        elif kind is IntentKind.QUARANTINE and not slots.get("targets"):
            requires_clarification = True
            question = "Quarantine which candidate or artifact? Name it and I will draft the action."

        return NormalizedIntent(
            kind=kind,
            confidence=confidence,
            risk=risk,
            slots=slots,
            requires_clarification=requires_clarification,
            clarification_question=question,
            operator_text=operator_text,
            quoted_segments=quoted,
            detected_injection=tuple(injections),
            restatement=self.restate(kind, slots, operator_text),
        )

    # -- classification ---------------------------------------------------
    def _classify(self, text: str) -> tuple[IntentKind, float, dict]:
        slots: dict = {}
        project = _extract_project(text)
        if project:
            slots["project"] = project
        targets = _extract_targets(text)
        if targets:
            slots["targets"] = targets

        if not text:
            return IntentKind.UNKNOWN, 0.0, slots

        if re.search(r"\bthat is not what i (meant|said)\b|\bwrong transcript\b|\bi did not say\b", text):
            return IntentKind.CORRECTION, 0.95, slots

        if re.search(r"\bstop\b", text) and not re.search(r"\bstop condition\b", text):
            return IntentKind.STOP_ALL, 0.95, slots

        modes = _mode_slots(text)
        if modes:
            slots["modes"] = modes
            return IntentKind.SET_MODE, 0.9, slots

        if re.search(r"\b(do not|don't|never)\s+(touch|modify|change|open|write)\b", text):
            slots.setdefault("targets", targets or ["workbook"])
            return IntentKind.PROHIBIT_TARGET, 0.9, slots

        if re.search(r"\bquarantine\b", text):
            return IntentKind.QUARANTINE, 0.9, slots

        if re.search(r"\bwhat needs my approval\b|\bpending approvals?\b|\bawaiting (my )?approval\b", text):
            return IntentKind.APPROVAL_QUEUE_QUERY, 0.95, slots

        if re.search(r"\bwhat is blocking\b|\bwhat's blocking\b|\bwhy is it blocked\b|\bblocked\b", text):
            return IntentKind.BLOCKER_QUERY, 0.9, slots

        if re.search(r"\bshow me the evidence\b|\bwhat evidence\b|\bopen the evidence\b", text):
            return IntentKind.EVIDENCE_QUERY, 0.9, slots

        if re.search(r"\bwhere (they |the agents )?disagree\b|\bdisagreements?\b", text):
            return IntentKind.SHOW_DISAGREEMENTS, 0.9, slots

        if re.search(r"\bimprovement loop\b|\btry to improve\b|\biterate\b", text):
            slots["keep_baseline_on_regression"] = bool(
                re.search(r"\bkeep the old\b|\bif the new one is worse\b|\bkeep the baseline\b", text)
            )
            return IntentKind.IMPROVEMENT_LOOP, 0.9, slots

        # Tournament is checked before plain reconciliation: "have three agents
        # read this and compare it to the Runsheet" is one tournament, and every
        # tournament reconciles against the Runsheet anyway.
        agent_count = _extract_count(text)
        if re.search(r"\b(tournament|independently inspect|independent readings?|have \w+ agents?)\b", text) or (
            agent_count and re.search(r"\bagents?\b", text)
        ):
            slots["candidate_count"] = agent_count or 3
            return IntentKind.RUN_TOURNAMENT, 0.9, slots

        if re.search(r"\bcompare\b.*\brunsheet\b|\breconcile\b.*\brunsheet\b|\bagainst the runsheet\b", text):
            return IntentKind.COMPARE_RUNSHEET, 0.9, slots

        if re.search(r"\bsend\b.*\b(codex|claude code|coding task)\b|\bhand off\b.*\b(codex|claude)\b", text):
            slots["agent_target"] = "codex" if "codex" in text else "claude_code"
            return IntentKind.DISPATCH_CODE_AGENT, 0.9, slots

        if re.search(r"\bask claude\b|\breview the result\b|\bhave .* review\b|\bcode review\b", text):
            slots["reviewer"] = "claude" if "claude" in text else "unspecified"
            return IntentKind.REQUEST_REVIEW, 0.85, slots

        if re.search(r"\bdraft\b.*\b(task|repair|fix)\b|\bsafest repair\b", text):
            slots["safest"] = bool(re.search(r"\bsafest\b", text))
            return IntentKind.DRAFT_REPAIR_TASK, 0.9, slots

        if re.search(r"\bexplain\b|\bwalk me through\b|\bin plain (english|language)\b", text):
            slots["format"] = "phone" if re.search(r"\bphone\b|\bmobile\b", text) else "standard"
            slots["verbosity"] = "concise" if re.search(r"\bshort\b|\bbrief\b|\bconcise\b", text) else "standard"
            return IntentKind.EXPLAIN, 0.9, slots

        if re.search(r"\bwhat (is|'s) happening\b|\bstatus\b|\bwhat (is|'s) going on\b|\bwhere are we\b", text):
            return IntentKind.STATUS_QUERY, 0.9, slots

        # A bare project reference with a question mark is a status question.
        if project and text.strip().endswith("?"):
            return IntentKind.STATUS_QUERY, 0.6, slots

        return IntentKind.UNKNOWN, 0.2, slots

    # -- restatement ------------------------------------------------------
    def restate(self, kind: IntentKind, slots: dict, operator_text: str) -> str:
        """What the system believes was requested, shown back before any action."""
        project = slots.get("project", "the active project")
        if kind is IntentKind.STATUS_QUERY:
            return f"Report the current operational state of {project}."
        if kind is IntentKind.BLOCKER_QUERY:
            return f"Identify what is blocking {project} and cite the evidence."
        if kind is IntentKind.APPROVAL_QUEUE_QUERY:
            return "List everything currently waiting on your approval."
        if kind is IntentKind.EVIDENCE_QUERY:
            return "Open the supporting evidence for the current finding."
        if kind is IntentKind.EXPLAIN:
            return f"Explain the current result ({slots.get('format', 'standard')} format)."
        if kind is IntentKind.RUN_TOURNAMENT:
            count = slots.get("candidate_count", 3)
            return f"Run {count} independent read-only index readings and compare them."
        if kind is IntentKind.COMPARE_RUNSHEET:
            return "Reconcile the extracted index entries against the registered Runsheet."
        if kind is IntentKind.SHOW_DISAGREEMENTS:
            return "Show where the agents disagreed, with evidence for each disagreement."
        if kind is IntentKind.IMPROVEMENT_LOOP:
            return (
                "Run a bounded improvement loop, keeping the accepted baseline if the "
                "candidate does not measurably improve on it."
            )
        if kind is IntentKind.DRAFT_REPAIR_TASK:
            return "Draft the lowest-risk repair TaskEnvelope. Draft only — nothing executes."
        if kind is IntentKind.DISPATCH_CODE_AGENT:
            return f"Prepare a bounded coding handoff for {slots.get('agent_target', 'a coding agent')}."
        if kind is IntentKind.REQUEST_REVIEW:
            return f"Request an independent review from {slots.get('reviewer', 'a reviewer')}."
        if kind is IntentKind.SET_MODE:
            enabled = ", ".join(sorted(slots.get("modes", {}))) or "no change"
            return f"Change operating mode: {enabled}."
        if kind is IntentKind.PROHIBIT_TARGET:
            return f"Mark {', '.join(slots.get('targets', []))} as off limits until you say otherwise."
        if kind is IntentKind.STOP_ALL:
            return "Stop all stoppable queued work."
        if kind is IntentKind.QUARANTINE:
            return "Quarantine the named result so it cannot be accepted."
        if kind is IntentKind.CORRECTION:
            return "Discard the previous interpretation and wait for the corrected instruction."
        return f"Unrecognized request: {operator_text[:120]}"
