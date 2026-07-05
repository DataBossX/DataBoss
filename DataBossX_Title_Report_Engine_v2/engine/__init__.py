"""DataBossX Title Report Engine v2 -- evidence-based ownership/title reports.

Pipeline: ingest -> parser -> ogl_matcher -> chain -> verifier -> writer, with
audit recording every material action. Runsheet controls; template controls
formatting; the engine controls the math; the audit log controls trust.
"""

__all__ = ["ingest", "parser", "chain", "ogl_matcher", "verifier", "writer",
           "audit", "models"]
__version__ = "2.0.0"
