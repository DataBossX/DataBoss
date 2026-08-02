# Independent verification — DataBossX Control Tower build

**Release state: FOR REVIEW - HOLD NO EXTERNAL RELEASE**

Read-only independent reproduction of the four verification gates self-reported by
`DBX_RECEIPT__CONTROL_TOWER_BUILD_PRESENT__20260802T1625Z.json` (Drive ID
`1XCMJBy5XrHRdWOuEugBFdF4yV4-yUpdU`).

Those results were reported by the same lane that authored the code. Nothing had
independently reproduced them. The owner authorization names Claude Code as the
independent read-only reviewer; this is that review.

## Subject

- Build commit `fb4186e77612e6c81bdab819a78b9b79457edde9` (branch
  `claude/databossx-section32-recovery-ouyziy`, draft PR #74)
- Extracted with `git archive` into an isolated scratch directory. The repository
  working tree was not modified and the build was never executed from inside it.

## Results

| Gate | Self-reported | Independently observed | Verdict |
|---|---|---|---|
| pytest suite | 88 passed, exit 0 | 88 passed, 0 failed, 0 errors | reproduced exactly |
| `cli selftest` | 18/18, exit 0, 0 Drive writes | 18/18, 0 failed, exit 0 | reproduced exactly |
| `cli canary` | 7/7, exit 0, 0 network calls | 7/7, 0 failed, exit 0 | reproduced exactly |
| `cli audit` | exit 2, `PARTIAL_HOST_MISMATCH`, V12 `NOT_VERIFIED_UNREACHABLE` | identical | reproduced exactly |

The audit result is the important one. Given a V12 path that does not exist, the
tower refused to certify V12 and exited non-zero rather than reporting a clean
result it had not earned. The fail-closed posture is executable, not just documented.

## Method caveat on the pytest number

pytest is not installed here and there is no PyPI access. The suite ran under a
purpose-written stdlib shim covering only the API the suite uses (`raises`,
`mark.parametrize`, `fixture`, `tmp_path`, `monkeypatch`). The shim is strict:
`raises()` asserts *DID NOT RAISE* when nothing is raised and propagates any
non-matching exception, so a shim bug shows up as a failure or error, never as a
false pass. 88 = 63 test functions expanded by 8 parametrize decorators.

This is a faithful reproduction, **not** a run of upstream pytest. Read it that way.

## Checks the test suite structurally cannot make

The suite imports the same `constants` module it asserts against, so a substituted
folder ID would pass all 88 tests. Constants were therefore compared against the
owner-authorized values taken from the owner supplement and the Gate 0 command:

- `QUEUE_FOLDER_ID`, `RECEIPTS_FOLDER_ID`, `WATCHER_OUTPUT_FOLDER_ID`,
  `V12_EXPECTED_SHA256`, `HOLD` — **all match**
- `ALLOWED_WRITE_FOLDER_IDS` — five entries (02_RECEIPTS, 09_WATCHER_OUTPUT,
  03_STATUS, 04_BLOCKED, 07_HUMAN_APPROVAL). 04_BLOCKED and 07_HUMAN_APPROVAL are
  expressly named as write destinations by Gate 0 REQUIRED ACTION 9. No
  unauthorized folder is writable; 01_QUEUED is read-only.

**Verdict: all pinned constants authentic.**

The offline claim was also confirmed statically: the only `socket` reference in the
entire package is `socket.gethostname()` for host identity. There is no HTTP client
and no outbound call path. Third-party dependencies: zero — so it runs on the
Windows workstation with nothing installed but Python.

## What this does NOT establish

- **V12 is not verified here.** That path is on the Windows host.
- **The live Drive leg is unproven for this build.** selftest and canary use
  in-process offline doubles.
- Gate 0 was not claimed, terminalized, or altered.
- Finding R-01 (whether the 1110CDT BLOCKED terminal consumed the command's single
  terminal slot) is unresolved and needs an owner ruling.
- Finding R-04 (missing `.sha256` sidecar for the Gate 0 terminal receipt) is not
  fixed here; those bytes must be hashed by the Windows host that wrote them.

## Reproducing this

```
mkdir /tmp/verify && cd /tmp/verify
git archive fb4186e | tar -x
cp .../reproduction/pytest_shim_DO_NOT_IMPORT_AS_PYTEST.py ./pytest.py
cp .../reproduction/run_suite_with_shim.py ./
python3 run_suite_with_shim.py
python3 -m control_tower.cli selftest
python3 -m control_tower.cli canary
python3 -m control_tower.cli audit --v12-path /nonexistent/V12.xlsx
```

The shim is deliberately **not** named `pytest.py` in this repository so it can
never shadow real pytest for other tooling. Copy it under that name only inside a
throwaway directory.

## Next permitted action

On the Windows workstation that owns `C:\DataBoss`: copy the repository at
`fb4186e`, run `run_control_tower.bat selftest` and confirm 18/18, then
`run_control_tower.bat audit` with `DBX_V12_PATH` set to the pinned V12 path. Only
if that audit returns exit 0 with `v12_ruling VERIFIED_EXACT` may a Gate 0 claim be
considered — and per R-01 no claim should be attempted until Ryan rules on whether
the command's terminal slot is already spent.

**FOR REVIEW - HOLD NO EXTERNAL RELEASE**
