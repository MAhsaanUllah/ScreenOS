#!/usr/bin/env python3
"""Tiny backup: copy data/screenos.db + rubrics/archive to backups/<ts>. No deps."""
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DB = ROOT / "data" / "screenos.db"
SRC_ARCH = ROOT / "rubrics" / "archive"
DST = ROOT / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def main() -> int:
    if not SRC_DB.is_file() and not SRC_ARCH.is_dir():
        print("Nothing to backup (no DB nor archive).")
        return 0
    DST.mkdir(parents=True, exist_ok=True)
    if SRC_DB.is_file():
        shutil.copy2(SRC_DB, DST / "screenos.db")
        print(f"Saved {DST / 'screenos.db'}")
    if SRC_ARCH.is_dir():
        shutil.copytree(SRC_ARCH, DST / "archive", dirs_exist_ok=True)
        print(f"Saved {DST / 'archive'} ({len(list(SRC_ARCH.glob('*.md')))} rubrics)")
    print(f"Backup done: {DST}")
    print("Restore: copy back to data/ and rubrics/archive, or via docker volume.")
    print("Cron: 0 2 * * * cd /app && python scripts/backup.py  # daily 2am")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
