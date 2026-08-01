# Command Brain — Voice Setup

## Current state, stated plainly

**Live audio capture is not enabled in Command Brain Alpha.** The voice path is
fully implemented — session lifecycle, activation boundary, transcript display,
confirmation, correction, spoken response, emergency stop, retention policy — but
the speech-to-text and text-to-speech transports shipped here are
`SimulatedSpeechToText` and `SimulatedTextToSpeech`. They are labelled SIMULATED
in the session description, in the Command Center, and in every audit event.

`SimulatedSpeechToText.transcribe()` returns the text it is handed. It does not
process audio and does not pretend to.

This is a deliberate stopping point: the safety machinery is testable now, and
turning on a real microphone is a separate decision with its own review.

## Running the Command Center

```
python - <<'PY'
from databossx.command_brain.runtime import CommandBrainRuntime
from databossx.command_brain.service import CommandBrain
from databossx.command_brain.server import serve

runtime = CommandBrainRuntime("runtime/command_brain.db", project_id="sec32_synthetic")
serve(CommandBrain(runtime), host="127.0.0.1", port=8787)
PY
```

Open `http://127.0.0.1:8787`. The server refuses to bind a non-loopback address
without an explicit override, because Alpha is not authorized to expose the
application over a network.

The microphone button currently toggles a listening indicator and tells you to
type what you would say. That is the honest behaviour for a simulated transport.

## The voice interaction model

```
press_to_talk()      → mints a single-use activation token
submit_audio(a, tok) → transcribes; token must match; state → CONFIRMING
                       (shown to the operator, not yet an intent)
confirm()            → the transcript becomes the request
correct(text)        → supersedes the previous transcript; nothing is edited
speak(text)          → spoken response, concise or detailed
emergency_stop()     → available in every state, including mid-capture
```

Modes: `push_to_talk` (default), `hands_free` (requires an explicit recorded
operator confirmation), `text_fallback`.

## Why the activation token exists

It is what stops audio from the machine's own speakers — a video, a meeting, a
recording — from becoming an instruction. Audio submitted with no matching token
is discarded and the refusal is audited. Tokens are single-use, so a replayed
clip fails too.

This is a real control, not a comment: see
`tests/test_command_brain_intent.py::test_audio_without_activation_token_is_discarded`.

## What speech can and cannot do

Speech **can**: ask for status, ask what is blocked, ask for evidence, request
analysis, draft a plan, draft a TaskEnvelope, request agent work, produce an
approval card, change mode ("read-only", "draft only", "local models only"), mark
targets off limits, quarantine a result, and stop everything.

Speech **cannot**: lift a hold, release client work, alter an accepted workbook,
run a shell command, reach an unregistered path, reveal a secret, skip an
approval, skip a lease, skip a fencing token, overwrite accepted evidence, or
publish anything. Approving requires an authenticated act through the UI or API —
`ApprovalService.approve` refuses `SPOKEN_UTTERANCE` outright.

Voice biometrics are **not** treated as authorization for anything.

## Wiring a real transport

Subclass `SpeechToTextAdapter` / `TextToSpeechAdapter`, or inject a function into
`LocalCommandSpeechToText`:

```python
from databossx.command_brain.voice import LocalCommandSpeechToText, VoiceSession

def transcribe(audio_ref: str) -> str:
    # audio_ref is a server-resolved handle, never a browser-supplied path.
    return my_local_engine.transcribe(resolve(audio_ref))

session = VoiceSession(
    runtime.store,
    conversation_id,
    authenticated_session_id=authenticated_session,
    stt=LocalCommandSpeechToText(transcribe, adapter_id="local_whisper"),
)
```

`LocalCommandSpeechToText` with no function raises rather than silently degrading
to a simulator. Keep that property in anything you write: an adapter that cannot
do its job must say so.

Set `simulated = False` on your adapter **only** when it genuinely processes
audio. That flag drives the SIMULATED labelling throughout the UI and the ledger.

### Requirements for a real transport

1. **Local or explicitly authorized.** Under `local_only`, audio must not leave
   the machine. A cloud STT provider is remote egress and needs its own approval.
2. **Server-resolved audio handles.** The browser hands over an opaque ID; the
   server resolves it. Never accept a filesystem path — `scan_tool_input` would
   reject one anyway.
3. **Retention honoured.** `AudioRetention.NONE` means no audio reference is
   stored. The audit event records `audio_retained` so the choice is inspectable.
4. **Latency budget.** Transcription happens between `submit_audio` and the
   confirmation screen. Anything over a couple of seconds makes push-to-talk feel
   broken.

## Phone access

Alpha is loopback-only. There is no authorized private HTTPS transport yet, so
voice runs on the local desktop or an approved loopback environment.

The Command Center layout is already phone-shaped (responsive, large touch
targets, dark/light), and all phone-facing payloads are redacted — no absolute
paths, no secrets. When a private HTTPS path is authorized, the UI is ready; the
transport decision is what is outstanding.

## Recommended operator habits

- Stay in push-to-talk. Hands-free is implemented but wider open.
- Read the "What I heard" line before approving. It is there for exactly that.
- Use "That is not what I meant" freely — corrections append, they cost nothing.
- Say "Read-only mode" at the start of a session. Approval never raises the mode,
  so a low ceiling is a genuine floor under everything that follows.
