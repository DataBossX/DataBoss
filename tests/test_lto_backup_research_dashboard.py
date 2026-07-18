"""Tests for backup verification, search packages, and the dashboard."""

import shutil
from pathlib import Path

from core.land_title_os.backup import create_manifest, verify_restore
from core.land_title_os.chain_graph import ChainGraph, InstrumentNode
from core.land_title_os.dashboard import generate_dashboard, write_dashboard
from core.land_title_os.research import (
    build_package, name_variants, packages_for_chain, render,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# -- backup ------------------------------------------------------------------

def test_backup_manifest_and_clean_restore(tmp_path):
    src = tmp_path / "src"
    (src / "docs").mkdir(parents=True)
    (src / "docs" / "deed.txt").write_text("deed")
    (src / "report.xlsx").write_text("workbook")

    manifest_path = tmp_path / "manifest.json"
    manifest = create_manifest(src, manifest_path)
    assert manifest["file_count"] == 2

    restored = tmp_path / "restored"
    shutil.copytree(src, restored)
    assert verify_restore(restored, manifest_path) == []


def test_restore_detects_missing_changed_extra(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    (src / "b.txt").write_text("beta")
    manifest_path = tmp_path / "manifest.json"
    create_manifest(src, manifest_path)

    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "a.txt").write_text("ALPHA CHANGED")
    (restored / "c.txt").write_text("intruder")

    kinds = {(p.kind, p.path) for p in verify_restore(restored, manifest_path)}
    assert kinds == {("changed", "a.txt"), ("missing", "b.txt"), ("extra", "c.txt")}


# -- research ----------------------------------------------------------------

def test_name_variants_individual():
    variants = name_variants("Ella Pearl Kirk")
    assert variants[0] == "Ella Pearl Kirk"
    assert "Ella Kirk" in variants               # dropped middle
    assert "Ella P. Kirk" in variants            # initial
    assert "Kirk, Ella Pearl" in variants        # index order
    assert "Ella Pearl Kirk Trust" in variants
    assert "Ella Pearl" in variants              # possible maiden reading


def test_name_variants_entity():
    variants = name_variants("Leede Exploration Company")
    assert "Leede Exploration" in variants
    pkg = build_package("Leede Exploration Company", "32-11N-25W", "Beckham", "OK")
    assert any("SoS records" in n for n in pkg.notes)
    assert "oil and gas lease" in pkg.instrument_types


def test_packages_for_chain_breaks():
    g = ChainGraph()
    g.add(InstrumentNode("P-1", "1907-01-01", ["United States"], ["A Root"], kind="patent"))
    g.add(InstrumentNode("D-1", "1950-01-01", ["Carol Stranger"], ["B Buyer"], kind="deed"))
    pkgs = packages_for_chain(g, "32-11N-25W", "Beckham", "Oklahoma")
    assert len(pkgs) == 1 and pkgs[0].party == "Carol Stranger"
    text = render(pkgs[0])
    assert "Carol Stranger" in text and "Beckham County" in text
    assert "Stranger, Carol" in text             # index-order variant rendered


# -- dashboard ---------------------------------------------------------------

def test_dashboard_renders_real_projects(tmp_path):
    html_text = generate_dashboard(REPO_ROOT / "projects", generated_at="2026-07-18")
    assert "OK-BECKHAM-32-11N-25W" in html_text
    assert "WY-CAMPBELL-05-47N-75W" in html_text
    assert "BLOCKED" in html_text                # Beckham critical items
    assert "What needs you" in html_text
    assert "no invented numbers" in html_text
    # self-contained: no external URLs
    assert "http://" not in html_text and "https://" not in html_text

    out = write_dashboard(REPO_ROOT / "projects", tmp_path / "dash.html",
                          generated_at="2026-07-18")
    assert out.exists() and out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_dashboard_escapes_html(tmp_path):
    from core.land_title_os.manifest import ProjectManifest
    proj = tmp_path / "OK-XSS-1"
    ProjectManifest(project_id="OK-XSS-1", client="<script>alert(1)</script>",
                    jurisdiction="OK", county="X", section="1", township="1N",
                    range="1W").save(proj / "manifest.json")
    html_text = generate_dashboard(tmp_path, generated_at="2026-07-18")
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;" in html_text
