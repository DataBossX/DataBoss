"""DataBossX Command Center -- the unified land & title intelligence application.

This package ties the existing, unit-tested engines together behind one
project-based command so a non-programmer can run the full slice end to end:

    ingest -> extract/OCR -> structured records -> runsheet + ownership chain
    -> mineral / leasehold / working-interest / net-revenue math
    -> defect & missing-evidence report -> client-ready Excel + PDF
    -> project dashboard + evidence & audit trail

It does not replace the engines it orchestrates -- it reuses them:

* ``horizon``                  exact-fraction interest math, chaining, validation,
                               versioning (zero-destruction), examiner worklists
* ``grocery_report_pipeline``  deterministic inventory / text-extraction / dedup /
                               classification / structured-fact stages
* ``databossx.ownership``      unified mineral / leasehold / WI / NRI calculator
                               (new; built on ``horizon.interest`` -- exact math)

The Law of DataBossX (inherited from Horizon):

* **No fabrication.** A quantity that the files do not support is left blank and
  the row is flagged for examiner review -- never guessed to make totals tie.
* **Zero destruction.** Sources are only read; every output is written to a
  managed ``databossx_output`` folder and prior runs are backed up, never
  overwritten in place.
* **Human release gate.** Technical verification is not client release.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
