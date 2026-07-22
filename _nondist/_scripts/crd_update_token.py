# ----------------------------------------------------------------------
"""
crd_update.py - Remote Update Module for Private Repo
Version 1.02 Updated 07/21/26
"""
# ----------------------------------------------------------------------
import sys
import os
import requests
import json
from PyQt5.QtWidgets import QMessageBox
# ----------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR
# ----------------------------------------------------------------------
def _load_github_token():
    token = os.environ.get("CRD_GITHUB_TOKEN")
    if token:
        return token

    token_path = [
        os.path.join(PROJECT_ROOT, "..", "config", "token.json"),         
    ]
    for path in token_path:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    token = data.get("github_token") or data.get("token")
                    if token:
                        return token.strip()
            except Exception:
                pass 
    return None
# ----------------------------------------------------------------------
GITHUB_TOKEN = _load_github_token()
REPO_OWNER = "emwilson71"
REPO_NAME = "CRD-GIT"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/"
# ----------------------------------------------------------------------
def _get_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "CRD-Updater/1.03"
    }
# ----------------------------------------------------------------------
def check_for_remote_updates(parent_window):
    try:
        remote_versions_url = RAW_BASE + "config/versions.json"

        r = requests.get(
            remote_versions_url,
            headers=_get_headers(),
            timeout=12
        )

        if r.status_code == 404:
            QMessageBox.warning(
                parent_window,
                "Update Check",
                "versions.json not found (404).\n\n"
                "Check:\n"
                "• File exists at config/versions.json on main\n"
                "• Token has repo / Contents:Read scope\n"
                "• Repo name / branch are correct"
            )
            return
        if r.status_code == 401 or r.status_code == 403:
            QMessageBox.warning(
                parent_window,
                "Update Check",
                f"Authentication failed ({r.status_code}).\n"
                "Token is invalid, expired, or lacks permission."
            )
            return
        if r.status_code != 200:
            QMessageBox.warning(
                parent_window,
                "Update Check",
                f"Could not fetch versions.json\nHTTP {r.status_code}\n{r.text[:200]}"
            )
            return

        remote_versions = r.json()

        local_versions_path = os.path.join(PROJECT_ROOT, "config", "versions.json")
        if os.path.exists(local_versions_path):
            with open(local_versions_path, "r", encoding="utf-8") as f:
                local_versions = json.load(f)
        else:
            local_versions = {}

        needs_update = []
        for rel_path, remote_ver in remote_versions.items():
            if not remote_ver:
                continue
            local_ver = local_versions.get(rel_path, "")
            if str(remote_ver) != str(local_ver):
                needs_update.append(rel_path)

        if needs_update:
            reply = QMessageBox.question(
                parent_window,
                "Update Available",
                f"Found updates for {len(needs_update)} file(s):\n\n"
                + "\n".join(needs_update[:8])
                + ("\n..." if len(needs_update) > 8 else "")
                + "\n\nDownload and restart?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                download_and_restart(parent_window, needs_update)
        else:
            QMessageBox.information(parent_window, "Up to Date", "You Have the Latest Version")
    except Exception as e:
        QMessageBox.warning(parent_window, "Update Check Failed", str(e))
# ----------------------------------------------------------------------
def download_and_restart(parent_window, files_to_update):
    try:
        INSTALL_ROOT = r"C:\CRD"         
        updated = []
        for rel_path in files_to_update:
            local_path = os.path.join(INSTALL_ROOT, rel_path.replace("/", os.sep))
            remote_url = RAW_BASE + rel_path.replace("\\", "/")

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            r = requests.get(remote_url, headers=_get_headers(), timeout=20)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                updated.append(rel_path)
                print(f"Updated: {rel_path}")
            else:
                raise RuntimeError(f"Failed to download {rel_path} → HTTP {r.status_code}")
        local_versions_path = os.path.join(INSTALL_ROOT, "config", "versions.json")
        os.makedirs(os.path.dirname(local_versions_path), exist_ok=True)
        r = requests.get(RAW_BASE + "config/versions.json", headers=_get_headers(), timeout=10)
        if r.status_code == 200:
            with open(local_versions_path, "wb") as f:
                f.write(r.content)

        QMessageBox.information(
            parent_window,
            "Success",
            f"Updated {len(updated)} File(s).\nRestarting Now..."
        )
        restart_application()

    except Exception as e:
        QMessageBox.critical(parent_window, "Download Failed", str(e))
# ----------------------------------------------------------------------
def restart_application():
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception:
        sys.exit(0)
# ----------------------------------------------------------------------