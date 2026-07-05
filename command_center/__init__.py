"""DataBossX Land Intelligence — Command Center.

A Streamlit command center plus a CrewAI agent swarm that autonomously chains
working interests for the target section (default ``31-12N-24W``, Roger Mills
County, Oklahoma) and perfects a cursory title report.

Design law (inherited from the Horizon engine this package wraps):

* **No fabrication.** Every interest is exact ``fractions.Fraction`` math — never
  a float. Where the files do not support a balance, the tract is tagged
  ``Needs Examiner Review`` or escalated; a number is never invented to make the
  chain tie out.
* **The Mathematician is deterministic.** The self-healing verification loop runs
  on the exact-fraction engine in :mod:`horizon`, not on an LLM. An LLM cannot be
  trusted to add 1/3 + 5/128; the engine can. The CrewAI agents *narrate and
  route* the deterministic result — they do not compute it.
* **Graceful degradation.** The full pipeline runs with only ``openpyxl`` +
  ``pydantic`` installed. CrewAI / an LLM API key are an optional narration layer;
  when they are absent the command center runs in deterministic mode and says so.
* **Modular for scale.** The engine is section-agnostic; ``31-12N-24W`` is only a
  default. Point it at another section's workbook and the same loop runs.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
