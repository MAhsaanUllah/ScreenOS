"""Read PDF, DOCX and UTF-8 TXT resumes without changing their wording."""

import argparse
from pathlib import Path
import re
import sys

import pdfplumber
from docx import Document
from docx.table import Table


def extract_text(file_path: str | Path) -> str:
    """Return readable text or raise ValueError with a useful explanation."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise ValueError("Choose a PDF, DOCX or TXT file.")
    if not path.is_file():
        raise ValueError("File not found. Check the file path.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("File is too large. Use a file under 10 MB.")

    try:
        if suffix == ".txt":
            raw = path.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            if any(not page.strip() for page in pages):
                raise ValueError(
                    "A PDF page has no readable text. It may be blank or scanned. "
                    "Provide a text-based PDF, DOCX or TXT version."
                )
            raw = "\n\n".join(pages)
        else:
            parts = []
            for block in Document(path).iter_inner_content():
                if isinstance(block, Table):
                    parts.extend(" | ".join(cell.text for cell in row.cells)
                                 for row in block.rows)
                else:
                    parts.append(block.text)
            raw = "\n".join(parts)
    except UnicodeError as exc:
        raise ValueError("Save the TXT file using UTF-8 encoding and try again.") from exc
    except Exception as exc:
        # File readers use different exceptions for damaged or locked documents.
        raise ValueError(f"Could not read {path.name}: {exc}") from exc

    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in raw.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        raise ValueError("No readable text found. Provide a non-empty resume.")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Read text from a resume.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        print(extract_text(args.file))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
