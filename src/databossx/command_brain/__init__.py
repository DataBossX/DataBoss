"""DataBossX Command Brain Alpha.

A voice-first, policy-gated command layer over DataBossX. It understands a
request, reads real operational state, proposes an inspectable plan, drafts a
scoped TaskEnvelope, dispatches bounded agents, judges their results against a
frozen baseline, and records an immutable receipt.

The governing rule, enforced in :mod:`.policy` and relied on everywhere else:
**an utterance is an instruction source, not proof of authority.** Only an
authenticated approval bound to an exact envelope hash authorizes consequential
work, and autonomy Level 4 (release or external action) is structurally disabled
in Alpha.
"""

from .autonomy import ALPHA_MAX_LEVEL, AutonomyLevel
from .envelope import EnvelopeDrafter, TaskEnvelope
from .errors import CommandBrainError
from .intent import IntentEngine, IntentKind
from .policy import AuthoritySource, DataSensitivity, PolicyEngine, PolicyProfile, RiskLevel
from .roles import ROLES, get_role, list_roles
from .runtime import CommandBrainRuntime
from .service import CommandBrain, CommandResponse
from .store import CommandBrainStore
from .voice import VoiceMode, VoiceSession

__all__ = [
    "ALPHA_MAX_LEVEL",
    "AutonomyLevel",
    "AuthoritySource",
    "CommandBrain",
    "CommandBrainError",
    "CommandBrainRuntime",
    "CommandBrainStore",
    "CommandResponse",
    "DataSensitivity",
    "EnvelopeDrafter",
    "IntentEngine",
    "IntentKind",
    "PolicyEngine",
    "PolicyProfile",
    "ROLES",
    "RiskLevel",
    "TaskEnvelope",
    "VoiceMode",
    "VoiceSession",
    "get_role",
    "list_roles",
]

__version__ = "0.1.0-alpha"
