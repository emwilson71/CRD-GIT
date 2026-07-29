#!/usr/bin/env python3
"""
Selective sync/update: CRD → CRD-GIT
Excludes folders and files listed in EXCLUDE_PATTERNS.
"""

import os
import shutil
import fnmatch
from pathlib import Path
from datetime import datetime

SOURCE_DIR = Path(r"C:\CRD")         
DEST_DIR   = Path(r"C:\CRD-GIT")      
EXCLUDE_PATTERNS = [
# FOLDERS
    ".git",
    ".backup",
    "__pycache__",
    "_nondist",
    "logs",
    "data",
    "CRD/scripts/__pycache__",
    "CRD/modules/__pycache__",
    "Sync*",
    "python",

# FILES
    "*.pyc",
    "*.pyo",
    "*.log",
    "gitsync.py",
    "crdbckup.py",
    "Thumbs.db",
    "desktop.ini",
    ".DS_Store",
    "config/secrets.ini",
    "CRD/__pycache__",
    "CRD.exe",
    "CRD.ico",
    "SyncToy*",          
    "Syncfolders_Database_db",
]

# DELETE IN DEST FOLDER
DELETE_EXTRA = True


def is_excluded(rel_path: Path) -> bool:
    rel_str = rel_path.as_posix()         
    name = rel_path.name

    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_str, pattern):
            return True
        if fnmatch.fnmatch(name, pattern):
            return True
        for part in rel_path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def should_copy(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime


def sync(src_root: Path, dst_root: Path):
    src_root = src_root.resolve()
    dst_root = dst_root.resolve()

    if not src_root.is_dir():
        raise FileNotFoundError(f"Source Directory Does Not Exist: {src_root}")

    dst_root.mkdir(parents=True, exist_ok=True)

    copied = skipped = 0
    print(f"[{datetime.now():%H:%M:%S}] Syncing {src_root} → {dst_root}")
    print("-" * 60)

    for root, dirs, files in os.walk(src_root):
        root_path = Path(root)
        rel_root = root_path.relative_to(src_root)
        dirs[:] = [
            d for d in dirs
            if not is_excluded(rel_root / d)
        ]
        dest_dir = dst_root / rel_root
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in files:
            src_file = root_path / filename
            rel_file = rel_root / filename

            if is_excluded(rel_file):
                skipped += 1
                print(f"  SKIP  {rel_file}")
                continue

            dest_file = dest_dir / filename

            if should_copy(src_file, dest_file):
                shutil.copy2(src_file, dest_file)
                copied += 1
                print(f"  COPY  {rel_file}")
            else:
                skipped += 1

    print("-" * 60)
    print(f"Done. Copied/updated: {copied}  |  Skipped {skipped}")

    if DELETE_EXTRA:
        print("\nCleaning Extra Files in Destination (DELETE_EXTRA=True)...")
        clean_extra(src_root, dst_root)


def clean_extra(src_root: Path, dst_root: Path):
    for root, dirs, files in os.walk(dst_root, topdown=False):
        root_path = Path(root)
        rel = root_path.relative_to(dst_root)

        for f in files:
            dest_file = root_path / f
            src_file = src_root / rel / f
            if not src_file.exists() and not is_excluded(rel / f):
                dest_file.unlink()
                print(f"  DELETE FILE {rel / f}")

        if not any(root_path.iterdir()) and not (src_root / rel).exists():
            root_path.rmdir()
            print(f"  DELETE FOLDER  {rel}")


if __name__ == "__main__":
    sync(SOURCE_DIR, DEST_DIR)