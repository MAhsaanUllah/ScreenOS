"""Measure file reading only; run from the project root."""
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extractor import extract_text


def main():
    root = Path(__file__).resolve().parents[1]
    lines = [
        "# Day 1 extraction measurements", "",
        f"Environment: Python {platform.python_version()}, {platform.system()}.",
        "Median of five reads per fictional CV, after imports; includes file opening.",
        "Short samples do not establish speed on full-length real CVs.", "",
        "| Sample | Characters | Median seconds |", "| --- | ---: | ---: |",
    ]
    for path in sorted((root / "samples/cvs").iterdir()):
        timings = []
        for _ in range(5):
            start = perf_counter()
            text = extract_text(path)
            timings.append(perf_counter() - start)
        lines.append(f"| {path.name} | {len(text)} | {median(timings):.6f} |")
    lines.extend(["", "Manual review time, screening accuracy and time savings are",
                  "not measured. This measures file reading only.", ""])
    report = "\n".join(lines)
    (root / "docs/day1_results.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
