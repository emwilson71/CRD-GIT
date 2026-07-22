# ----------------------------------------------------------------------
"""
crd_update.py - Remote Update Module for Private Repo
Version 1.01 Updated 07/17/26
"""
import sys
import os
import requests
import json
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox

PROJECT_ROOT = os.path.join(
    os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__),
    "scripts"
)
GITHUB_TOKEN = "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"

def check_for_remote_updates(parent_window):
    try:
        base_url = f"https://{GITHUB_TOKEN}@raw.githubusercontent.com/emwilson71/CRD-GIT/main/"
        remote_versions_url = base_url + "config/versions.json"
        r = requests.get(remote_versions_url, timeout=10)
        if r.status_code != 200:
            QMessageBox.warning(parent_window, "Update Check", "Could Not Fetch Version")
            return
       
        remote_versions = r.json()
        local_versions_path = os.path.join(PROJECT_ROOT, "../config/versions.json")
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
            if remote_ver != local_ver:
                needs_update.append(rel_path)
       
        if needs_update:
            reply = QMessageBox.question(parent_window, "Update Available",
                f"Found Updates for {len(needs_update)} file(s).\n\nUpdate and Restart?",
                QMessageBox.Yes | QMessageBox.No)
           
            if reply == QMessageBox.Yes:
                download_and_restart(parent_window, base_url, needs_update)
        else:
            QMessageBox.information(parent_window, "Up to Date", "You Are Using the Latest Version.")
           
    except Exception as e:
        QMessageBox.warning(parent_window, "Update Check Failed", str(e))

def download_and_restart(parent_window, base_url, files_to_update):
    try:
        for rel_path in files_to_update:
            local_path = os.path.join(r"C:\CRD", rel_path)
            remote_url = base_url + rel_path.replace("\\", "/")
           
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
           
            r = requests.get(remote_url, timeout=15)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                print(f"Updated: {rel_path}")
       
        QMessageBox.information(parent_window, "Success", "Update complete.\nRestarting now...")
        restart_application()
       
    except Exception as e:
        QMessageBox.critical(parent_window, "Download Failed", str(e))

def restart_application():
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except:
        sys.exit(0)
# ----------------------------------------------------------------------