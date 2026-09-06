"""Run with python -m app.screen FILE --name NAME [--send]."""

import argparse
from pathlib import Path
import sys

from app.extractor import extract_text
from app.guardrails import prepare_candidate
from app.providers import complete
from app.scorer import score_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview cleaned CV text or send it for human-reviewed scoring.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--address", default="")
    parser.add_argument("--graduation-year", type=int, action="append", default=[])
    parser.add_argument("--send", action="store_true", help="Send cleaned CV to the configured provider (may incur API usage).")
    args = parser.parse_args()
    options = dict(name=args.name, address=args.address, graduation_years=tuple(args.graduation_year))
    try:
        if not args.send:
            print(prepare_candidate(extract_text(args.file), **options)["cleaned_text"])
            print("\nReview this text. Add --send to send it for scoring.", file=sys.stderr)
        else:
            card = score_candidate(args.file, **options, complete=complete,
                rubric_path=Path(__file__).resolve().parents[1] / "rubrics/rubric.md")
            print(card.model_dump_json(indent=2))
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
