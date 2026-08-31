# ROLLBACK INSTRUCTIONS — CONTROL TOWER BUILD PROOF PACKAGE

Release state: FOR REVIEW - HOLD NO EXTERNAL RELEASE
Run ID: DBX-S32-CT-BUILDPROOF-20260802T1539Z

## What this package changed

Nothing outside itself. This lane performed **no** mutation of any pre-existing
tracked file, no merge, no deploy, no workbook access, and no Drive deletion or
overwrite.

**Superseded note:** this package was initially left uncommitted. It was
subsequently committed and pushed to the designated branch at the owner's
explicit direction, delivered through the session stop-hook policy check. See
`CORRECTION_01__REPOSITORY_COMMIT_AUTHORIZED.json`. Gate 0 was never claimed or
entered, so no Gate 0 execution constraint was in force.

The only filesystem change is the creation of this directory:

    /home/user/DataBoss/_CONTROL_TOWER_PROOF_20260802/

It is untracked by git. `git status` was clean before creation and shows only
this untracked directory afterward.

## Rollback

Full rollback is a single directory removal:

    rm -rf /home/user/DataBoss/_CONTROL_TOWER_PROOF_20260802

To roll back the committed form, revert the single commit on the designated
branch. The commit adds only this evidence directory; reverting it restores the
tree to 582d951 exactly. No other tracked file was touched.

## Drive rollback

If the append-only evidence record was uploaded to 02_RECEIPTS, it is
append-only by policy and MUST NOT be deleted. To supersede it, append a new
correcting record that names the superseded Drive ID. Never edit or overwrite
an existing receipt.

## Host caveat

This container is ephemeral. Anything not recorded to Drive is lost when the
session ends. This package is therefore mirrored to the Drive control package
as an append-only evidence record.
