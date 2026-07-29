# --------------------------------------------------------------------
"""
Sync/Update: CRD - CRD-GIT
Then git add → commit → push to emwilson71/CRD-GIT
"""
# --------------------------------------------------------------------
import os
import shutil
import fnmatch
import subprocess
from pathlib import Path
from datetime import datetime
# --------------------------------------------------------------------
SOURCE_DIR = Path(r"C:\CRD")
DEST_DIR = Path(r"C:\CRD-GIT")
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

DELETE_EXTRA = True
# --------------------------------------------------------------------
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

# --------------------------------------------------------------------
def should_copy(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime

# --------------------------------------------------------------------
def run_git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    print(f"  → git {' '.join(cmd)}")
    result = subprocess.run(
        ["git"] + cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result

# --------------------------------------------------------------------
def git_sync_and_push(repo_dir: Path):
    print("\n" + "=" * 60)
    print(f"[{datetime.now():%H:%M:%S}] Git operations on {repo_dir}")
    print("=" * 60)

    if not (repo_dir / ".git").exists():
        print("ERROR: Destination is not a git repository (.git folder missing)")
        return

# 2 REFRESH
    print("\n[1/4] Scanning repository status...")
    status = run_git(["status", "--porcelain"], repo_dir)

    if not status.stdout.strip():
        print("No changes detected. Nothing to commit or push.")
        return

    print("\n[2/4] Staging all changes...")
    run_git(["add", "-A"], repo_dir)

# 3 COMMIT
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-sync from CRD — {timestamp}"
    print(f"\n[3/4] Committing: {commit_msg}")
    commit = run_git(["commit", "-m", commit_msg], repo_dir)

    if commit.returncode != 0:
        print("Commit Failed or Nothing New to Commit")
        return

# PUSH
    print("\n[4/4] Pushing to Origin (emwilson71/CRD-GIT)...")
    push = run_git(["push", "origin", "HEAD"], repo_dir)

    if push.returncode == 0:
        print("\nSuccessfully Pushed to emwilson71/CRD-GIT")
    else:
        print("\nPush Failed. Check Credentials / Remote Settings.")
# --------------------------------------------------------------------
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

        dirs[:] = [d for d in dirs if not is_excluded(rel_root / d)]

        dest_dir = dst_root / rel_root
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in files:
            src_file = root_path / filename
            rel_file = rel_root / filename

            if is_excluded(rel_file):
                skipped += 1
                print(f" SKIP {rel_file}")
                continue

            dest_file = dest_dir / filename
            if should_copy(src_file, dest_file):
                shutil.copy2(src_file, dest_file)
                copied += 1
                print(f" COPY {rel_file}")
            else:
                skipped += 1

    print("-" * 60)
    print(f"Done. Copied/updated: {copied} | Skipped {skipped}")

    if DELETE_EXTRA:
        print("\nCleaning Extra Files in Destination (DELETE_EXTRA=True)...")
        clean_extra(src_root, dst_root)
    git_sync_and_push(dst_root)
# --------------------------------------------------------------------
def clean_extra(src_root: Path, dst_root: Path):
    for root, dirs, files in os.walk(dst_root, topdown=False):
        root_path = Path(root)
        rel = root_path.relative_to(dst_root)

        for f in files:
            dest_file = root_path / f
            src_file = src_root / rel / f
            if not src_file.exists() and not is_excluded(rel / f):
                dest_file.unlink()
                print(f" DELETE FILE {rel / f}")

        if not any(root_path.iterdir()) and not (src_root / rel).exists():
            root_path.rmdir()
            print(f" DELETE FOLDER {rel}")

if __name__ == "__main__":
    sync(SOURCE_DIR, DEST_DIR)
# --------------------------------------------------------------------