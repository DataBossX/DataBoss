"""Deterministic priority scoring -- no AI call needed for ranking.

Scores favor: paid work closest to completion, deterministic/free actions,
projects with evidence already on hand, and short high-value moves.
"""


def score_project(project: dict) -> float:
    score = 0.0
    evidence_count = len(project.get("evidence_present", []))
    score += evidence_count * 10  # evidence already available
    file_count = project.get("file_count", 0)
    if 0 < file_count < 200:
        score += 5  # short/bounded action likely
    if file_count == 0:
        score -= 20  # nothing to act on yet
    last_mtime = project.get("last_mtime") or 0
    score += min(last_mtime / 1_000_000_000, 20)  # mild recency bias, bounded
    return score


def why_this_is_next(project: dict) -> str:
    evidence_count = len(project.get("evidence_present", []))
    if project.get("file_count", 0) == 0:
        return f"{project['project']} has no files yet -- lowest priority until source material lands."
    if evidence_count:
        return (
            f"{project['project']} already has {evidence_count} evidence type(s) on hand, "
            "so the next deterministic action can run without waiting on new sources."
        )
    return f"{project['project']} was touched most recently and is FREE to inspect right now."


def rank_projects(lane_projects: dict) -> list:
    """lane_projects: {lane: [project, ...]} -> flat ranked list with scores."""
    flat = []
    for lane, projects in lane_projects.items():
        for p in projects:
            entry = dict(p)
            entry["score"] = score_project(p)
            entry["why"] = why_this_is_next(p)
            flat.append(entry)
    flat.sort(key=lambda p: p["score"], reverse=True)
    return flat


def next_best_move(lane_projects: dict) -> dict:
    ranked = rank_projects(lane_projects)
    if not ranked:
        return {
            "project": None,
            "action": "scan_project",
            "label": "No projects discovered yet",
            "why": (
                "No project roots were found or they are empty. Configure "
                "DATABOSSX_PENTERRA_ROOT / DATABOSSX_HORIZON_ROOT, or drop "
                "project folders under the configured roots."
            ),
        }
    top = ranked[0]
    action = "build_worklist" if top.get("evidence_present") else "scan_project"
    return {
        "project": top["project"],
        "path": top["path"],
        "lane": top["lane"],
        "action": action,
        "label": "DO NEXT BEST MOVE",
        "why": top["why"],
    }
