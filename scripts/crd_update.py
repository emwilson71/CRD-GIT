# crd_update.py - Remote Update Module for Public Repo
# Version 1.04 - Updated 07/22/26

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
INSTALL_ROOT = r"C:\CRD"          # ← Change only if needed
# ----------------------------------------------------------------------

REPO_OWNER = "emwilson71"
REPO_NAME = "CRD-GIT"
BRANCH = "main"

RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/"

def check_for_remote_updates(parent_window):
    try:
        remote_versions_url = RAW_BASE + "config/versions.json"
        r = requests.get(remote_versions_url, timeout=12)
        
        if r.status_code == 404:
            QMessageBox.warning(parent_window, "Update Check", 
                "versions.json not found on GitHub.\nMake sure it exists in config/versions.json")
            return
        if r.status_code != 200:
            QMessageBox.warning(parent_window, "Update Check", 
                f"Failed to fetch versions.json\nHTTP {r.status_code}")
            return

        remote_versions = r.json()

        local_versions_path = os.path.join(INSTALL_ROOT, "config", "versions.json")
        local_versions = {}
        if os.path.exists(local_versions_path):
            with open(local_versions_path, "r", encoding="utf-8") as f:
                local_versions = json.load(f)

        needs_update = [rel_path for rel_path, remote_ver in remote_versions.items() 
                       if remote_ver and str(remote_ver) != str(local_versions.get(rel_path, ""))]

        if needs_update:
            reply = QMessageBox.question(
                parent_window,
                "Update Available",
                f"Found updates for {len(needs_update)} file(s):\n\n" +
                "\n".join(needs_update[:10]) +
                ("\n..." if len(needs_update) > 10 else "") +
                "\n\nDownload and restart?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                download_and_restart(parent_window, needs_update)
        else:
            QMessageBox.information(parent_window, "Up to Date", "You have the latest version.")

    except Exception as e:
        QMessageBox.warning(parent_window, "Update Check Failed", str(e))


def download_and_restart(parent_window, files_to_update):
    try:
        updated = []
        for rel_path in files_to_update:
            local_path = os.path.join(INSTALL_ROOT, rel_path.replace("/", os.sep))
            remote_url = RAW_BASE + rel_path.replace("\\", "/")
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            r = requests.get(remote_url, timeout=20)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                updated.append(rel_path)
            else:
                raise RuntimeError(f"Failed to download {rel_path} (HTTP {r.status_code})")
            
        r = requests.get(RAW_BASE + "config/versions.json", timeout=10)
        if r.status_code == 200:
            local_versions_path = os.path.join(INSTALL_ROOT, "config", "versions.json")
            os.makedirs(os.path.dirname(local_versions_path), exist_ok=True)
            with open(local_versions_path, "wb") as f:
                f.write(r.content)

        QMessageBox.information(parent_window, "Success", 
            f"Successfully updated {len(updated)} file(s).\nRestarting...")
        restart_application()

    except Exception as e:
        QMessageBox.critical(parent_window, "Download Failed", str(e))


def restart_application():
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception:
        sys.exit(0)