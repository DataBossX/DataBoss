from __future__ import annotations

import json
import time
from pathlib import Path

from databossx.discover import discover, scan_project, write_registry


def make_project(root: Path, name: str, files=(), dirs=(), status=None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    for sub in dirs:
        (d / sub).mkdir(parents=True)
    for rel, content in files:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
    if status is not None:
        (d / "STATUS.json").write_text(json.dumps({"status": status}))
    return d


def test_flags_missing_artifacts(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    p = make_project(root, "raw_scans", files=[("inbox/deed.pdf", "%PDF")])
    scan = scan_project(p, root, now=time.time())
    assert scan.missing == ["no_ocr", "no_report", "no_qa"]
    assert scan.score >= 30


def test_ocr_report_qa_detection(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    p = make_project(
        root, "worked",
        files=[
            ("inbox/deed.pdf", "%PDF"),
            ("work/deed_ocr.txt", "text layer"),
            ("outputs/title_report_v001.xlsx", b"PK"),
            ("proofs/qa_checklist.md", "- [x] reviewed"),
        ],
    )
    scan = scan_project(p, root, now=time.time())
    assert scan.missing == []
    assert not scan.complete


def test_txt_sidecar_counts_as_ocr(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    p = make_project(root, "sidecar", files=[
        ("docs/deed.pdf", "%PDF"), ("docs/deed.txt", "ocr text"),
    ])
    scan = scan_project(p, root, now=time.time())
    assert "no_ocr" not in scan.missing


def test_completed_projects_skipped(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    make_project(root, "done_by_status", status="complete")
    done2 = make_project(root, "done_by_marker")
    (done2 / "COMPLETE.txt").write_text("shipped")
    make_project(root, "open_one", files=[("a.pdf", "%PDF")])

    registry = discover_config_registry(tmp_path)
    names = [p["name"] for p in registry["projects"]]
    skipped = [p["name"] for p in registry["skipped_complete"]]
    assert names == ["open_one"]
    assert sorted(skipped) == ["done_by_marker", "done_by_status"]


def discover_config_registry(tmp_path: Path):
    from databossx.config import FoundryConfig

    config = FoundryConfig(root=tmp_path, discover_roots=(tmp_path / "Horizon",))
    return discover(config)


def test_ranking_more_missing_first(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    make_project(root, "worst", files=[("x.pdf", "%PDF")])  # 3 missing
    make_project(root, "better", files=[
        ("x.pdf", "%PDF"), ("x_ocr.txt", "t"), ("final_report.xlsx", b"PK"),
    ])  # only no_qa
    registry = discover_config_registry(tmp_path)
    assert [p["name"] for p in registry["projects"]] == ["worst", "better"]


def test_missing_root_recorded_not_fatal(tmp_path: Path):
    from databossx.config import FoundryConfig

    config = FoundryConfig(
        root=tmp_path,
        discover_roots=(tmp_path / "Horizon", tmp_path / "Penterra"),
    )
    (tmp_path / "Horizon").mkdir()
    registry = discover(config)
    states = {r["path"]: r["exists"] for r in registry["roots"]}
    assert states[str(tmp_path / "Horizon")] is True
    assert states[str(tmp_path / "Penterra")] is False


def test_write_registry_stable_plus_versioned_snapshot(tmp_path: Path):
    from databossx.config import FoundryConfig

    config = FoundryConfig(root=tmp_path, discover_roots=())
    registry = {"generated_at": "now", "roots": [], "projects": [], "skipped_complete": []}
    out1, snap1 = write_registry(config, registry)
    out2, snap2 = write_registry(config, registry)
    assert out1 == out2 == tmp_path / "registry.json"
    assert snap1.name == "registry_v001.json"
    assert snap2.name == "registry_v002.json"
    assert json.loads(out1.read_text())["generated_at"] == "now"


def test_unreadable_status_json_is_not_complete(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    p = make_project(root, "weird")
    (p / "STATUS.json").write_text("{broken")
    scan = scan_project(p, root, now=time.time())
    assert not scan.complete
