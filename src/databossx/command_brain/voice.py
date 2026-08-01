"""Voice interface and provider-neutral speech adapters.

The voice layer is a *capture* device, not an authority. It produces a transcript
that the operator confirms, and the confirmed transcript feeds the same intent
engine the text channel uses. Nothing about a request being spoken raises its
privilege.

Specific defences implemented here:

* **Activation boundary.** A transcript can only be submitted against the token
  minted by an explicit press-to-talk. Audio that arrives with no activation —
  including audio played through the machine's own speakers — has no token and is
  refused.
* **Confirmation before consequence.** A consequential utterance must be
  confirmed as displayed text before it can become a plan.
* **Correction appends.** "That is not what I meant" supersedes the previous
  transcript with a new record; it never edits the old one.
* **Emergency stop.** Available in every state, including mid-capture.
* **Retention.** Audio retention is configuration, and ``none`` means no audio
  reference is ever stored.

Adapters are pluggable so cloud STT/TTS, local STT/TTS, and the labelled
simulator are interchangeable. No provider SDK is imported at module scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import CommandBrainError
from .policy import AuthoritySource
from .util import Clock


class VoiceError(CommandBrainError):
    code = "VOICE_ERROR"


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    CONFIRMING = "confirming"
    STOPPED = "stopped"


class VoiceMode(str, Enum):
    PUSH_TO_TALK = "push_to_talk"
    HANDS_FREE = "hands_free"
    TEXT_FALLBACK = "text_fallback"


class AudioRetention(str, Enum):
    NONE = "none"
    TRANSCRIPT_ONLY = "transcript_only"
    AUDIO_RETAINED = "audio_retained"


class SpeechToTextAdapter:
    """Interface for any STT provider."""

    adapter_id = "abstract_stt"
    simulated = False
    is_local = True

    def transcribe(self, audio_ref: str) -> str:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"adapter_id": self.adapter_id, "simulated": self.simulated, "is_local": self.is_local}


class TextToSpeechAdapter:
    adapter_id = "abstract_tts"
    simulated = False
    is_local = True

    def speak(self, text: str) -> dict:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"adapter_id": self.adapter_id, "simulated": self.simulated, "is_local": self.is_local}


class SimulatedSpeechToText(SpeechToTextAdapter):
    """SIMULATED transport. Takes the text it is given and returns it verbatim.

    Live audio capture is not enabled in Alpha, so this adapter exists to keep the
    whole voice path exercisable — session lifecycle, confirmation, correction,
    stop — without pretending an audio pipeline exists.
    """

    adapter_id = "simulated_stt"
    simulated = True

    def transcribe(self, audio_ref: str) -> str:
        return audio_ref


class SimulatedTextToSpeech(TextToSpeechAdapter):
    """SIMULATED transport. Returns the text that *would* be spoken."""

    adapter_id = "simulated_tts"
    simulated = True

    def speak(self, text: str) -> dict:
        return {"adapter_id": self.adapter_id, "simulated": True, "spoken_text": text}


class LocalCommandSpeechToText(SpeechToTextAdapter):
    """Adapter for a locally installed STT binary or server.

    ``transcribe_fn`` is injected by the host environment after it verifies the
    engine is actually installed. With no function the adapter refuses rather
    than degrading silently to a simulator.
    """

    adapter_id = "local_stt"
    simulated = False

    def __init__(self, transcribe_fn=None, adapter_id: str = "local_stt"):
        self.adapter_id = adapter_id
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_ref: str) -> str:
        if self._transcribe_fn is None:
            raise VoiceError(
                f"{self.adapter_id} has no verified local engine configured.",
                detail={"adapter_id": self.adapter_id},
            )
        return self._transcribe_fn(audio_ref)


@dataclass
class TranscriptRecord:
    transcript_id: str
    raw_text: str
    confirmed: bool
    created_at: str
    corrected_from: str | None = None
    superseded_by: str | None = None

    def to_dict(self) -> dict:
        return {
            "transcript_id": self.transcript_id,
            "raw_text": self.raw_text,
            "confirmed": self.confirmed,
            "created_at": self.created_at,
            "corrected_from": self.corrected_from,
            "superseded_by": self.superseded_by,
        }


class VoiceSession:
    """One authenticated voice session bound to one conversation."""

    def __init__(
        self,
        store,
        conversation_id: str,
        *,
        authenticated_session_id: str,
        stt: SpeechToTextAdapter | None = None,
        tts: TextToSpeechAdapter | None = None,
        mode: VoiceMode = VoiceMode.PUSH_TO_TALK,
        retention: AudioRetention = AudioRetention.NONE,
        clock: Clock | None = None,
    ):
        if not authenticated_session_id:
            raise VoiceError(
                "A voice session requires an authenticated session. Voice biometrics alone are "
                "not authorization."
            )
        self.store = store
        self.clock = clock or store.clock
        self.conversation_id = conversation_id
        self.authenticated_session_id = authenticated_session_id
        self.stt = stt or SimulatedSpeechToText()
        self.tts = tts or SimulatedTextToSpeech()
        self.mode = VoiceMode(mode)
        self.retention = AudioRetention(retention)
        self.state = VoiceState.IDLE
        self.session_id = store.new_id("voice")
        self._activation_token: str | None = None
        self.pending: TranscriptRecord | None = None

        store.execute(
            """
            INSERT INTO cb_voice_sessions (
                id, conversation_id, stt_adapter, tts_adapter, simulated, mode, state,
                audio_retention, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.session_id,
                conversation_id,
                self.stt.adapter_id,
                self.tts.adapter_id,
                int(self.stt.simulated or self.tts.simulated),
                self.mode.value,
                self.state.value,
                self.retention.value,
                self.clock.now_iso(),
            ),
        )
        store.audit(
            "voice.session_started",
            "voice_session",
            self.session_id,
            {
                "mode": self.mode.value,
                "stt": self.stt.describe(),
                "tts": self.tts.describe(),
                "audio_retention": self.retention.value,
            },
            actor_type="operator",
            actor_id=authenticated_session_id,
        )

    @property
    def simulated(self) -> bool:
        return bool(self.stt.simulated or self.tts.simulated)

    def _set_state(self, state: VoiceState) -> None:
        self.state = state
        self.store.execute(
            "UPDATE cb_voice_sessions SET state = ? WHERE id = ?", (state.value, self.session_id)
        )

    # -- capture ----------------------------------------------------------
    def press_to_talk(self) -> str:
        """Begin capture. Returns the activation token a transcript must carry."""
        if self.state is VoiceState.STOPPED:
            raise VoiceError("Session is stopped. Start a new session to continue.")
        self._activation_token = self.store.new_id("act")
        self._set_state(VoiceState.LISTENING)
        self.store.audit(
            "voice.activation", "voice_session", self.session_id, {"mode": self.mode.value}
        )
        return self._activation_token

    def enable_hands_free(self, *, confirmed_by_operator: bool) -> None:
        """Hands-free still needs an explicit, recorded operator decision."""
        if not confirmed_by_operator:
            raise VoiceError("Hands-free mode requires an explicit operator confirmation.")
        self.mode = VoiceMode.HANDS_FREE
        self.store.execute(
            "UPDATE cb_voice_sessions SET mode = ? WHERE id = ?", (self.mode.value, self.session_id)
        )
        self.store.audit("voice.hands_free_enabled", "voice_session", self.session_id, {})

    def submit_audio(self, audio_ref: str, activation_token: str | None = None) -> TranscriptRecord:
        """Transcribe captured audio into a pending, unconfirmed transcript."""
        if self.state is VoiceState.STOPPED:
            raise VoiceError("Session is stopped; audio was discarded.")
        if self._activation_token is None or activation_token != self._activation_token:
            # This is the path that blocks audio playing through the machine's
            # own speakers, or a replayed clip, from ever becoming an instruction.
            raise VoiceError(
                "Audio arrived without a matching activation token and was discarded. "
                "Capture requires an explicit press-to-talk.",
                detail={"session_id": self.session_id},
            )
        raw_text = self.stt.transcribe(audio_ref)
        record = TranscriptRecord(
            transcript_id=self.store.new_id("tr"),
            raw_text=raw_text,
            confirmed=False,
            created_at=self.clock.now_iso(),
        )
        self._persist(record)
        self.pending = record
        self._activation_token = None
        self._set_state(VoiceState.CONFIRMING)
        return record

    def submit_text(self, text: str) -> TranscriptRecord:
        """Text fallback. Typed input needs no activation token but is still unconfirmed."""
        record = TranscriptRecord(
            transcript_id=self.store.new_id("tr"),
            raw_text=text,
            confirmed=False,
            created_at=self.clock.now_iso(),
        )
        self._persist(record)
        self.pending = record
        self._set_state(VoiceState.CONFIRMING)
        return record

    def _persist(self, record: TranscriptRecord) -> None:
        self.store.execute(
            """
            INSERT INTO cb_transcripts (
                id, conversation_id, voice_session_id, raw_text, confirmed, corrected_from, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.transcript_id,
                self.conversation_id,
                self.session_id,
                record.raw_text,
                int(record.confirmed),
                record.corrected_from,
                record.created_at,
            ),
        )
        self.store.audit(
            "voice.transcript_captured",
            "transcript",
            record.transcript_id,
            {
                "confirmed": record.confirmed,
                "corrected_from": record.corrected_from,
                "audio_retained": self.retention is AudioRetention.AUDIO_RETAINED,
                "text": record.raw_text,
            },
            actor_type="operator",
            actor_id=self.authenticated_session_id,
        )

    # -- confirmation and correction --------------------------------------
    def confirm(self, transcript_id: str | None = None) -> TranscriptRecord:
        record = self.pending
        if record is None or (transcript_id and record.transcript_id != transcript_id):
            raise VoiceError("No matching pending transcript to confirm.")
        record.confirmed = True
        self.store.execute(
            "UPDATE cb_transcripts SET confirmed = 1 WHERE id = ?", (record.transcript_id,)
        )
        self.store.audit(
            "voice.transcript_confirmed", "transcript", record.transcript_id, {"text": record.raw_text}
        )
        self._set_state(VoiceState.IDLE)
        return record

    def correct(self, corrected_text: str) -> TranscriptRecord:
        """"That is not what I meant." Supersedes rather than edits."""
        previous = self.pending
        record = TranscriptRecord(
            transcript_id=self.store.new_id("tr"),
            raw_text=corrected_text,
            confirmed=False,
            created_at=self.clock.now_iso(),
            corrected_from=previous.transcript_id if previous else None,
        )
        self._persist(record)
        if previous is not None:
            self.store.execute(
                "UPDATE cb_transcripts SET superseded_by = ? WHERE id = ?",
                (record.transcript_id, previous.transcript_id),
            )
            previous.superseded_by = record.transcript_id
            self.store.audit(
                "voice.transcript_superseded",
                "transcript",
                previous.transcript_id,
                {"superseded_by": record.transcript_id},
            )
        self.pending = record
        self._set_state(VoiceState.CONFIRMING)
        return record

    # -- output and control -----------------------------------------------
    def speak(self, text: str, verbosity: str = "standard") -> dict:
        if verbosity == "concise":
            text = text.split(". ")[0].rstrip(".") + "."
        response = self.tts.speak(text)
        self.store.audit(
            "voice.response_spoken",
            "voice_session",
            self.session_id,
            {"verbosity": verbosity, "simulated": response.get("simulated", False)},
        )
        return response

    def emergency_stop(self, reason: str = "operator stop") -> dict:
        """Always available, including mid-capture."""
        self._activation_token = None
        self.pending = None
        self._set_state(VoiceState.STOPPED)
        self.store.execute(
            "UPDATE cb_voice_sessions SET ended_at = ? WHERE id = ?",
            (self.clock.now_iso(), self.session_id),
        )
        self.store.audit(
            "voice.emergency_stop",
            "voice_session",
            self.session_id,
            {"reason": reason},
            actor_type="operator",
            actor_id=self.authenticated_session_id,
        )
        return {"session_id": self.session_id, "state": self.state.value, "reason": reason}

    def describe(self) -> dict:
        return {
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "mode": self.mode.value,
            "state": self.state.value,
            "simulated": self.simulated,
            "audio_retention": self.retention.value,
            "stt": self.stt.describe(),
            "tts": self.tts.describe(),
            "authority_source": AuthoritySource.SPOKEN_UTTERANCE.value,
            "note": (
                "SIMULATED voice transport. Live audio capture is not enabled in Command Brain Alpha."
                if self.simulated
                else "Live voice transport."
            ),
        }
