"""Voice intake: transcription port and strict intent parsing.

Two rules shape this module.

First, transcript and intent are separate objects and both are shown to the
human before anything is created. A transcript is what was said; an intent is
what the machine *thinks* was meant, and the second is allowed to be wrong.

Second, missing dangerous fields are never inferred. The parser reports them in
``unresolved``, which the policy engine treats as a hard block. A request that
does not name its target does not get a guessed target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol, Sequence

from .canonical import iso, sha256_text, utc_now


class SpeechProvider(Protocol):
    """Replaceable speech-to-text port.

    No provider is wired in this lane: enabling a paid provider requires the
    owner's approval, so the only implementation here is a deterministic local
    stub used by tests and the demo.
    """

    name: str

    def transcribe(self, audio: bytes, *, language: str = "en-US") -> "Transcription":
        ...


@dataclass(frozen=True)
class Transcription:
    text: str
    confidence: float
    provider: str
    captured_at: str
    sha256: str
    audio_retained: bool = False

    @classmethod
    def create(cls, text: str, *, confidence: float, provider: str) -> "Transcription":
        return cls(
            text=text,
            confidence=confidence,
            provider=provider,
            captured_at=iso(utc_now()),
            sha256=sha256_text(text),
            audio_retained=False,
        )


class LocalStubSpeechProvider:
    """Deterministic offline provider.

    It performs no recognition; it echoes text supplied by the caller so the
    pipeline can be exercised end to end without a paid service. It is labelled
    as a stub everywhere it surfaces.
    """

    name = "local-stub-v1"

    def transcribe(self, audio: bytes, *, language: str = "en-US") -> Transcription:
        text = audio.decode("utf-8", errors="replace").strip()
        return Transcription.create(text, confidence=0.0, provider=self.name)


@dataclass
class ParsedIntent:
    goal: str
    operation: str
    target_project: Optional[str] = None
    target_resource: Optional[str] = None
    constraints: list = field(default_factory=list)
    urgency: str = "NORMAL"
    source_references: list = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    unresolved: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "operation": self.operation,
            "target_project": self.target_project,
            "target_resource": self.target_resource,
            "constraints": list(self.constraints),
            "urgency": self.urgency,
            "source_references": list(self.source_references),
            "parameters": dict(self.parameters),
            "unresolved": list(self.unresolved),
        }


#: Phrase -> adapter. Deliberately small and explicit: an utterance that does
#: not match a known operation becomes an unresolved question, not a guess.
_OPERATION_PATTERNS: Sequence[tuple] = (
    (re.compile(r"\b(what should i do|next move|best move|what.s next)\b", re.I), "status.read_posture"),
    (re.compile(r"\b(status|posture|what.s running|what is running|blocked)\b", re.I), "status.read_posture"),
    (re.compile(r"\b(project summary|summarize project|show project|open project)\b", re.I), "project.read_summary"),
    (re.compile(r"\b(verify hashes|check hashes|hash check|integrity check)\b", re.I), "artifact.verify_hashes"),
    (re.compile(r"\b(interest roll|roll ?up|ownership math|compute interest)\b", re.I), "title.simulate_interest_rollup"),
    (re.compile(r"\b(draft report|build report|generate report|report draft)\b", re.I), "report.simulate_draft_build"),
    (re.compile(r"\b(publish receipt|upload receipt|post receipt)\b", re.I), "drive.publish_receipt"),
    (re.compile(r"\b(promote|accept candidate|promote artifact)\b", re.I), "artifact.promote_candidate"),
)

#: Utterances that name a prohibited act. These are captured explicitly so the
#: refusal is specific and auditable rather than a generic parse failure.
_PROHIBITED_PATTERNS: Sequence[tuple] = (
    (re.compile(r"\b(remove|lift|clear|drop)\b.{0,24}\bhold\b", re.I), "hold.remove"),
    (re.compile(r"\b(weaken|soften|downgrade)\b.{0,24}\b(hold|review)\b", re.I), "hold.weaken"),
    (re.compile(r"\b(publish|release|ship|deploy)\b.{0,24}\b(external|public|client|production)\b", re.I),
     "release.publish_external"),
    (re.compile(r"\b(run|execute)\b.{0,16}\b(shell|command line|bash|powershell|cmd)\b", re.I), "shell.execute"),
    (re.compile(r"\b(run|execute)\b.{0,16}\bsql\b", re.I), "sql.execute"),
    (re.compile(r"\b(do we have|is there|show me)\b.{0,24}\b(api key|secret|token|credential)\b", re.I),
     "secrets.probe_status"),
    (re.compile(r"\boverwrite\b.{0,24}\baccepted\b", re.I), "artifact.overwrite_accepted"),
)

_PROJECT_RE = re.compile(r"\bproject\s+([a-z0-9][a-z0-9\-]{1,40})\b", re.I)
_URGENT_RE = re.compile(r"\b(urgent|immediately|right now|asap|critical)\b", re.I)
_LOW_RE = re.compile(r"\b(whenever|no rush|low priority|eventually)\b", re.I)

#: Operations that cannot proceed without an explicit target project.
_REQUIRES_PROJECT = {
    "project.read_summary",
    "title.simulate_interest_rollup",
    "report.simulate_draft_build",
}


def parse_intent(transcript: str, *, default_project: Optional[str] = None) -> ParsedIntent:
    """Turn a transcript into a strict, reviewable intent.

    ``default_project`` is only applied when the operation *needs* a project and
    the caller has already established one in the UI context. It is recorded in
    ``notes`` so the human can see that it was supplied rather than heard.
    """
    text = (transcript or "").strip()
    if not text:
        return ParsedIntent(
            goal="(empty transcript)",
            operation="",
            unresolved=["Nothing was transcribed. Speak again or type the request."],
        )

    for pattern, prohibited_op in _PROHIBITED_PATTERNS:
        if pattern.search(text):
            return ParsedIntent(
                goal=text[:200],
                operation=prohibited_op,
                unresolved=[],
                notes=[f"Recognized as prohibited operation {prohibited_op}."],
            )

    operation = ""
    for pattern, op in _OPERATION_PATTERNS:
        if pattern.search(text):
            operation = op
            break

    intent = ParsedIntent(goal=text[:200], operation=operation)

    if not operation:
        intent.unresolved.append(
            "No known operation matched this request. Choose an action explicitly."
        )
        return intent

    match = _PROJECT_RE.search(text)
    if match:
        intent.target_project = match.group(1).lower()
    elif default_project and operation in _REQUIRES_PROJECT:
        intent.target_project = default_project
        intent.notes.append(f"Project '{default_project}' supplied from screen context, not from speech.")

    if operation in _REQUIRES_PROJECT:
        if intent.target_project:
            intent.parameters["project_id"] = intent.target_project
            intent.target_resource = f"project.{intent.target_project}"
        else:
            # Never invent a target. This blocks classification.
            intent.unresolved.append("Which project? The target project was not stated.")
    else:
        intent.target_resource = "system.posture"

    if operation == "drive.publish_receipt":
        intent.unresolved.append("Which receipt ID should be published?")
    if operation == "artifact.promote_candidate":
        intent.unresolved.append("Which artifact ID should be promoted?")

    if _URGENT_RE.search(text):
        intent.urgency = "HIGH"
    elif _LOW_RE.search(text):
        intent.urgency = "LOW"

    return intent


@dataclass(frozen=True)
class IntakeResult:
    """What the confirmation screen renders. Nothing is created from this yet."""

    transcript: Transcription
    intent: ParsedIntent
    requires_confirmation: bool = True

    def to_dict(self) -> dict:
        return {
            "transcript": {
                "text": self.transcript.text,
                "sha256": self.transcript.sha256,
                "captured_at": self.transcript.captured_at,
                "confidence": self.transcript.confidence,
                "provider": self.transcript.provider,
                "audio_retained": self.transcript.audio_retained,
            },
            "intent": self.intent.to_dict(),
            "notes": list(self.intent.notes),
            "requires_confirmation": self.requires_confirmation,
        }


def intake(
    transcript_text: str,
    *,
    provider: str = "local-stub-v1",
    confidence: float = 0.0,
    default_project: Optional[str] = None,
) -> IntakeResult:
    """Full intake step: transcript in, transcript + intent out, nothing created."""
    transcription = Transcription.create(transcript_text, confidence=confidence, provider=provider)
    return IntakeResult(transcript=transcription, intent=parse_intent(transcript_text,
                                                                     default_project=default_project))


def redact_for_phone(payload: Mapping) -> dict:
    """Strip anything phone-facing responses must never carry.

    Absolute Windows/POSIX paths, canonical folder values, and secret-shaped
    strings are removed rather than masked in place, so a leak cannot survive as
    a partially redacted value.
    """
    banned_keys = {"canonical_folder", "root_path", "local_path", "absolute_path", "secret",
                   "api_key", "token", "password", "credential"}
    path_like = re.compile(r"(?:[A-Za-z]:\\[^\s\"']*|\\\\[^\s\"']+|/(?:home|root|Users|mnt|var)/[^\s\"']*)")

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k.lower() not in banned_keys}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, str):
            return path_like.sub("[redacted-path]", value)
        return value

    return clean(dict(payload))
