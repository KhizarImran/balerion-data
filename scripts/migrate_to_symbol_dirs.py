"""
migrate_to_symbol_dirs.py
-------------------------
One-off migration: moves all parquet files from the old flat layout
    data/<category>/<symbol>_<suffix>.parquet
to the new per-symbol layout
    data/<category>/<symbol>/<symbol>_<suffix>.parquet

Safe to re-run: files already in the correct location are skipped.
"""

from pathlib import Path
import shutil
import sys

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# All (category, file) pairs that need moving.
# Pattern: data/<category>/<stem>.parquet  ->  data/<category>/<symbol>/<stem>.parquet
# The symbol is extracted from the stem by taking the first underscore-delimited token.

CATEGORIES = ["fx", "indices", "crypto"]


def symbol_from_stem(stem: str) -> str:
    """eurusd_1m -> eurusd,  eurusd_dukascopy_1h -> eurusd,  usdjpy_1h -> usdjpy"""
    return stem.split("_")[0]


def migrate():
    moved = 0
    skipped = 0
    errors = 0

    for cat in CATEGORIES:
        cat_dir = DATA_DIR / cat
        if not cat_dir.exists():
            continue

        # Only files directly in the category dir (not already in subdirs)
        flat_files = [f for f in cat_dir.iterdir() if f.is_file() and f.suffix == ".parquet"]

        for src in flat_files:
            sym = symbol_from_stem(src.stem)
            dest_dir = cat_dir / sym
            dest = dest_dir / src.name

            if dest.exists():
                print(f"  [SKIP]  {src.relative_to(BASE_DIR)}  (already at destination)")
                skipped += 1
                continue

            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                print(f"  [MOVE]  {src.relative_to(BASE_DIR)}")
                print(f"       -> {dest.relative_to(BASE_DIR)}")
                moved += 1
            except Exception as exc:
                print(f"  [ERROR] {src.relative_to(BASE_DIR)}: {exc}", file=sys.stderr)
                errors += 1

    print()
    print(f"Done. Moved: {moved}  Skipped: {skipped}  Errors: {errors}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    migrate()
