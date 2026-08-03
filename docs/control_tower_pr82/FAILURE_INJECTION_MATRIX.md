# Failure Injection Matrix

FOR REVIEW - HOLD NO EXTERNAL RELEASE

| Window | Injection | Required result | Automated proof |
|---|---|---|---|
| Before claim | Retired command | Zero state, spool, Drive, lease, fence, ACK, and audit delta | `test_b1_retired_replay_has_byte_for_byte_zero_state_delta` |
| Before claim | Noncanonical Section 32 package | Observation preserved; zero authority delta | `test_b7_exact_noncanonical_fixture_has_zero_authority_state_delta` |
| Claim authority | Missing, expired, mismatched, or replayed ACK | Fail before mutation | B4 tests |
| START upload | Drive outage | Frozen START remains recoverable; no second START bytes | Existing durable recovery tests and B6 |
| Terminal preparation | Stale lease/fence | Claim remains OPEN; no terminal fields | B2 |
| Drive create/readback | Lease superseded | Created object is orphaned; claim cannot resolve | B3 |
| Startup | Duplicate or changed canonical pin | Fail before authority derivation | B5 |
| Process crash | Windows writer exits while holding lock | OS releases lock; next atomic transaction succeeds | Windows msvcrt process test |
| Concurrent lease | Two Windows processes race | Exactly one lease and fence 1 | Windows process race test |

No workbook, PDF, evidence source, or private Drive object is exercised by these synthetic tests.
