"""Rubric registry: every `rubrics/<job_id>.md` is a selectable job rubric.

The file name is the job id; the file's `# Job:` line is the display title.
"""

from pathlib import Path

from app.scorer import rubric_info

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_DIR = ROOT / "rubrics"
DEFAULT = "ai-engineer"


def path_for(job_id: str) -> Path:
    """Resolve a job id to its file. Matches against the directory listing, never a built path."""
    for path in sorted(RUBRIC_DIR.glob("*.md")):
        if path.stem == job_id:
            return path
    raise KeyError(job_id)


def list_rubrics() -> list[dict]:
    """Selectable rubrics for the workspace dropdown."""
    rubrics = []
    for path in sorted(RUBRIC_DIR.glob("*.md")):
        info = rubric_info(path)
        rubrics.append({"job_id": path.stem, "job": info["job"],
                        "points": sum(row["points"] for row in info["rows"])})
    return rubrics


def update_rubric(job_id: str, rows: list[dict]) -> dict:
    """HR-editable rubric: overwrite points/evidence for DEFAULT job only. Keeps header."""
    if job_id != DEFAULT:
        raise ValueError("Only the default rubric can be edited from HR Controls.")
    if not rows:
        raise ValueError("Rubric needs at least one requirement.")
    seen = set()
    total = 0
    for r in rows:
        req = (r.get("requirement") or "").strip()
        ev = (r.get("evidence") or "").strip()
        pts = r.get("points")
        if not req or not ev:
            raise ValueError("Each row needs requirement and evidence.")
        if req in seen:
            raise ValueError("Requirement names must be unique.")
        seen.add(req)
        try:
            pts = float(pts)
        except Exception:
            raise ValueError("Points must be numbers.") from None
        if not 0 < pts <= 100:
            raise ValueError("Points must be between 0 and 100.")
        total += pts
    if total != 100:
        raise ValueError("Points must total exactly 100.")
    path = path_for(job_id)
    # versioning: archive current file before overwrite — ponytail: flat files, git is the real history
    try:
        old = path.read_text(encoding="utf-8")
        arch = RUBRIC_DIR / "archive"
        arch.mkdir(exist_ok=True)
        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%S")
        (arch / f"{job_id}_{ts}.md").write_text(old, encoding="utf-8")
    except Exception:
        pass
    header = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("|"):
            break
        header.append(line)
    table = ["| Requirement | Points | Evidence to look for |", "| --- | ---: | --- |"]
    for r in rows:
        req = r["requirement"].strip().replace("|", "/")
        ev = r["evidence"].strip().replace("|", "/")
        pts = int(r["points"]) if float(r["points"]).is_integer() else r["points"]
        table.append(f"| {req} | {pts} | {ev} |")
    footer_start = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("## How to award"):
            footer_start = i
            break
    footer = lines[footer_start:] if footer_start is not None else []
    new_content = "\n".join(header + table + ([""] + footer if footer else [])) + "\n"
    path.write_text(new_content, encoding="utf-8")
    return rubric_info(path)
