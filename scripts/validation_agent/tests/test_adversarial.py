"""Red-team suite: actively attempt to violate each core law and prove the
system rejects the attack. These tests exist specifically to break things.

Core laws under attack:
  * Never overwrite (baselines, versions, exports).
  * Append-only proof (no UPDATE/DELETE/DROP/injection, even obfuscated).
  * $100 cap mathematically enforced (dust, boundary, multi-guard, negatives).
  * No silent paid spend.
"""

import sqlite3
from decimal import Decimal

import pytest

from db.db_client import DatabaseManager, AppendOnlyViolation
from sources.spend_guard import SpendGuard
from core.run_manager import RunManager
from repair.xml_editor import XMLWorkbookEditor
from reports.output_generator import OutputGenerator
from tests.fixtures.make_fixtures import make_basic_workbook


# --------------------------------------------------------------------------- #
# Attack the append-only database
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db(tmp_path):
    d = DatabaseManager(tmp_path / "audit.db")
    yield d
    d.close()


@pytest.mark.parametrize("evil", [
    "UPDATE runs SET status='x'",
    "update runs set status='x'",
    "  UpDaTe   runs SET status='x'",
    "DELETE FROM runs",
    "DeLeTe FROM runs WHERE 1=1",
    "DROP TABLE runs",
    "ALTER TABLE runs ADD COLUMN hacked TEXT",
    "REPLACE INTO runs(run_id) VALUES('x')",
    "INSERT OR REPLACE INTO runs(run_id) VALUES('x')",
    "INSERT OR IGNORE INTO runs(run_id) VALUES('x')",
    "INSERT INTO runs(run_id) VALUES('a'); DROP TABLE runs",
    "INSERT INTO runs(run_id) VALUES('a'); DELETE FROM runs",
    "SELECT 1; DELETE FROM runs",
])
def test_every_mutating_statement_is_rejected(db, evil):
    with pytest.raises(AppendOnlyViolation):
        db.execute(evil)


@pytest.mark.parametrize("evil_query", [
    "WITH x AS (SELECT 1) DELETE FROM runs",
    "SELECT * FROM runs; DROP TABLE runs",
])
def test_query_path_cannot_mutate(db, evil_query):
    with pytest.raises(AppendOnlyViolation):
        db.query(evil_query)


def test_sql_injection_in_values_is_inert(db):
    # A malicious value must be stored literally (parameterized), never executed.
    evil = "'); DROP TABLE runs;--"
    db.record_launcher_event("evt", evil)
    # The table still exists and the value is stored verbatim.
    rows = db.query("SELECT description FROM launcher_events")
    assert rows[-1]["description"] == evil
    # runs table is intact.
    assert db.query("SELECT COUNT(*) AS c FROM runs")[0]["c"] == 0


def test_insert_into_unknown_table_blocked(db):
    with pytest.raises(AppendOnlyViolation):
        db.insert("sqlite_master", name="x")


def test_raw_connection_update_and_delete_blocked(tmp_path):
    d = DatabaseManager(tmp_path / "a.db")
    d.record_launcher_event("evt", "keep")
    d.close()
    raw = sqlite3.connect(tmp_path / "a.db")
    for stmt in ("UPDATE launcher_events SET description='x'",
                 "DELETE FROM launcher_events"):
        with pytest.raises(sqlite3.DatabaseError):
            raw.execute(stmt)
            raw.commit()
    assert raw.execute("SELECT description FROM launcher_events").fetchone()[0] \
        == "keep"
    raw.close()


# --------------------------------------------------------------------------- #
# Attack the spend cap
# --------------------------------------------------------------------------- #
def test_dust_accumulation_never_exceeds_cap(db):
    g = SpendGuard(db=db, run_id="r", cap_usd="100.00")
    approved = 0
    for _ in range(2000):  # 2000 x $0.10 = $200 attempted
        if g.authorize("0.10", "dust", examiner_approved=True).approved:
            approved += 1
    assert g.cumulative <= Decimal("100.00")
    assert g.cumulative == Decimal("100.00")
    assert approved == 1000  # exactly $100 worth cleared, no more


def test_subcent_rounding_cannot_breach_cap(db):
    g = SpendGuard(db=db, run_id="r", cap_usd="100.00")
    g.authorize("99.995", "round-up to 100.00", examiner_approved=True)
    # 99.995 rounds to 100.00 (half-up); one more cent must be blocked.
    assert g.cumulative == Decimal("100.00")
    assert g.authorize("0.01", "over", examiner_approved=True).approved is False


def test_negative_amount_rejected(db):
    g = SpendGuard(db=db, run_id="r", cap_usd="100.00")
    g.authorize("50.00", "real", examiner_approved=True)
    d = g.authorize("-40.00", "negative attack", examiner_approved=True)
    assert d.approved is False
    assert g.cumulative == Decimal("50.00")  # not decremented


def test_two_guards_cannot_jointly_exceed_cap(db):
    # Two independent guards on the same run share the durable ledger; neither
    # may approve spend that, combined, breaches the cap.
    g1 = SpendGuard(db=db, run_id="r", cap_usd="100.00")
    g2 = SpendGuard(db=db, run_id="r", cap_usd="100.00")
    assert g1.authorize("70.00", "g1", examiner_approved=True).approved
    # g2 was constructed before g1 spent, but must re-sync and block.
    assert g2.authorize("40.00", "g2", examiner_approved=True).approved is False
    assert db.cumulative_spend("r") <= 100.0


def test_no_approval_means_no_spend(db):
    g = SpendGuard(db=db, run_id="r", cap_usd="100.00", auto_approve=False)
    assert g.authorize("1.00", "unapproved").approved is False
    assert g.cumulative == Decimal("0.00")


# --------------------------------------------------------------------------- #
# Attack the no-overwrite guarantee
# --------------------------------------------------------------------------- #
def test_cannot_overwrite_baseline(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    rm = RunManager(tmp_path / "o", timestamp="20260101_000000")
    rm.ingest_baseline(src)
    with pytest.raises(FileExistsError):
        rm.ingest_baseline(src)


def test_cannot_overwrite_workbook_version(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx", with_hardcoded_total=True)
    dest = tmp_path / "v.xlsx"
    with XMLWorkbookEditor(src) as ed:
        ed.set_cell_formula("Tracts", "C13", "=SUM(C2:C11)")
        ed.save_as(dest)
    # A second editor cannot save onto the same version path.
    with XMLWorkbookEditor(src) as ed2:
        ed2.set_cell_formula("Tracts", "C13", "=SUM(C2:C11)")
        with pytest.raises(FileExistsError):
            ed2.save_as(dest)


def test_export_collision_is_numbered_not_overwritten(tmp_path):
    rm = RunManager(tmp_path / "o", timestamp="20260101_000001")
    gen = OutputGenerator(rm, db=None, run_id="r")
    a = gen.write_markdown("first", name="report.md")
    b = gen.write_markdown("second", name="report.md")
    assert a != b
    assert a.read_text() == "first"      # original preserved
    assert b.read_text() == "second"
