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
