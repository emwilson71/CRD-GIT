# ----------------------------------------------------------------------
"""
crd_embedded.py 04/02/25 (ew)
PyQt6
2025.10.14 Edited SIDEBAR_STYLE, JS
2026.07.17 Cleaned Up Code, EW
Version 1.10 Updated 03/04/26
"""
# ----------------------------------------------------------------------
import os, sys, logging, json, subprocess, platform
import mysql.connector
import datetime as dt
import paramiko, re
import glob
import telnetlib
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QListView, QTextEdit, QMessageBox, QPushButton,
    QHBoxLayout, QLabel
)
from PyQt6.QtCore import QStringListModel, Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
# LOGGING --------------------------------------------------------------
class CRDLogger:
    def __init__(self, name):
        self.name = name
        self.datestamp = datetime.now().strftime('%m%d%Y')
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        self.logs_dir = os.path.join(parent_dir, "logs")  
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file = os.path.join(self.logs_dir, f"CRD_{self.datestamp}.log")
        self.clear_previous_logs()
        self.configure_logging()
# ----------------------------------------------------------------------
    def clear_previous_logs(self):
        log_pattern = os.path.join(self.logs_dir, "*.log")
        current_log = self.log_file
        for log_file in glob.glob(log_pattern):
            if log_file != current_log:
                try:
                    os.remove(log_file)
                except OSError as e:
                    pass
# ----------------------------------------------------------------------
    def configure_logging(self):
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
# ----------------------------------------------------------------------
    def get_logger(self):
        return logging.getLogger(self.name)
# CLASS MAPPING DIR ----------------------------------------------------
class Paths:
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    CONFIG_DIR = os.path.join(PARENT_DIR, 'config')
    LOG_DIR    = os.path.join(PARENT_DIR, 'logs')
    HTML_DIR   = os.path.join(PARENT_DIR, 'html')
# CLASS FOR MESSAGE BOX ------------------------------------------------
class CustomMessageBox(QMessageBox):
    def __init__(self, title="", message="", msg_type=QMessageBox.Icon.Information, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(msg_type)
        self.setStyleSheet(Styles.MESSAGE_BOX_STYLE)        
        self.setStandardButtons(QMessageBox.StandardButton.Ok) 
        self.adjustSize()
# CENTER BOX ON UI
    def center(self):
        if self.parent() is not None:
            parent_geometry = self.parent().geometry()
            self.move(
                parent_geometry.x() + (parent_geometry.width() - self.width()) // 2,
                parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            )
    def exec_custom(self):
        return self.exec()
# ----------------------------------------------------------------------
class Styles:
    MENU_STYLE = """
        QMenu {
            background-color: #202020;
            color: white;
            border: 1px solid #404040;
            padding: 2px;
            font-size: 12px;
            font-weight: bold;
        }
        QMenu::item {
            background-color: transparent;
            color: white;
            padding: 5px 25px 5px 20px;
            border: 1px solid transparent;
        }
        QMenu::item:selected {
            background-color: #404040;
            color: white;
        }
        QMenu::item:disabled {
            background-color: transparent;
            color: #808080;
        }
        QMenu::separator {
            height: 1px;
            background: #404040;
            margin-left: 10px;
            margin-right: 10px;
        }
    """
    BUTTON_STYLE = """
        QPushButton {
            background-color: #606060;
            padding: 4px;
            color: white;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
        QPushButton:pressed {
            background-color: #606060;
        }
        QPushButton:disabled {
            background-color: #808080;
            color: #A0A0A0;
        }
    """
    BUTTON_STYLE_ARRAY = """
        QPushButton {
            background-color: #606060;
            padding: 4px;
            color: white;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
        QPushButton:pressed {
            background-color: #606060;
        }
        QPushButton:disabled {
            background-color: #808080;
            color: #A0A0A0;
        }
    """
    CONFIG_BUTTON_STYLE_ARRAY = """
        QPushButton {
            background-color: #606060;
            padding: 4px;
            color: white;
            font-size: 12px;
            font-weight: bold;
            border-radius: 4px;
            width: 80px;
            min-width: 80px;
            max-width: 80px;
            text-align: center;
        }
        QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
        QPushButton:pressed {
            background-color: #606060;
        }
        QPushButton:disabled {
            background-color: #808080;
            color: #A0A0A0;
        }
    """
    LINE_EDIT_STYLE = """
        QLineEdit {
            background-color: #404040;
            font-size: 14px;
            font-weight: bold;
            color: white;
            border: none;
            height: 22px;
        }
    """
    SID_EDIT_BOX_STYLE = """
        QLineEdit {
            background-color: lightgray;
            color: black;
            font-size: 14px;
            font-weight: bold;
            border: none;
            height: 26px;
        }
    """
    STD_LABEL_STYLE = """
        QLabel {
            color: white;
            font-size: 12px;
            font-weight: bold;
            height: 26px;
        }
    """
    ERROR_LABEL = """
        QLabel {
            color: red;
            font-size: 12px;
            font-weight: bold;
        }
    """
    GROUP_BOX = """
        QGroupBox {
            color: white;
            font-size: 12px;
            font-weight: bold;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
        }
    """
    COMBO_BOX = """
        QComboBox {
            background-color: #404040;
            color: white;
            font-size: 12px;
            font-weight: bold;
            border: none;
            padding: 5px;
        }
        QComboBox QAbstractItemView {
            background-color: #404040;
            color: white;
            selection-background-color: #606060;
        }
    """
    DYNAMIC_HEADER_STYLE = """
        QLabel {
            background-color: #202020;
            color: white;
            font-size: 20px;
            font-weight: bold;
            padding: 10px;
            border-radius: 4px;
        }
    """
    WEB_VIEW_WIDGET = """
        QTextBrowser {
            background-color: #404040;
            color: white;
            border: none;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
        }
        QTextBrowser a {
            color: #ffffff;
            text-decoration: none;
            font-weight: bold;
        }
        QTextBrowser a:hover {
            color: #ffff00;
            text-decoration: underline;
        }
    """
    MESSAGE_BOX_STYLE = """
        QMessageBox {
            background-color: #202020;
        }
        QMessageBox QLabel {
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        QMessageBox QPushButton {
            background-color: #606060;
            color: white;
            font-size: 11px;
            font-weight: bold;
            border-radius: 4px;
            padding: 5px;
            width: 60px;
        }
        QMessageBox QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
    """
    DIALOG = """
        QDialog {
            background-color: #202020;
        }
        QLabel {
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        QLineEdit {
            background-color: #404040;
            color: white;
            border: none;
            padding: 5px;
            font-size: 12px;
        }
        QCheckBox {
            color: white;
            font-size: 12px;
        }
    """
    LOADING_DIALOG_STYLE = """
        QDialog {
            background-color: #202020;
        }
        QLabel, QProgressBar {
            color: white;
            font-size: 14px;
        }
        QProgressBar {
            border: 2px solid #555;
            border-radius: 5px;
            background-color: #222;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: red;
            width: 20px;
            margin: 1px;
        }
    """
    TEXT_EDIT_STYLE = """
        QTextEdit {
            background-color: #202020;
            color: white;
            border: 1px solid #505050;
            padding: 4px;
        }
    """
    POPUP_DIALOG = """
        QDialog {
            background-color: #202020;
            color: #ffffff;
        }
        QTextEdit {
            background-color: #404040;
            color: white;
            font-size: 14px;
            border: 1px solid #808080;
            padding: 4px;
        }
        QPushButton {
            background-color: #606060;
            padding: 4px;
            color: white;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
        QPushButton:pressed {
            background-color: #606060;
        }
    """
    WEB_VIEW_STYLE = """
        QVBoxLayout {
            background-color: #202020;
            border: none;
        }
    """
    TAB_WIDGET_STYLE = """
        QTabWidget::pane {
            border: 1px solid #5A5A5A;
            background-color: #1A1A1A;
        }
        QTabBar::tab {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #5A5A5A;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 5px 10px;
            margin-right: 2px;
            font-family: Consolas, Monaco, monospace;
            font-size: 12px;
        }
        QTabBar::tab:selected {
            background-color: #4A4A4A;
            border: 1px solid #5A5A5A;
            border-bottom: none;
        }
        QTabBar::tab:hover {
            border: 1px solid #FFFFFF;
            border-bottom: none;
        }
    """
    CHECKBOX_STYLE = """
        QCheckBox {
            color: white;
            font-size: 12px;
        }
    """
    WIDGET_STYLE = """
        QWidget {
            background-color: #202020;
        }
        QGroupBox {
            color: white;
            font-size: 12px;
            font-weight: bold;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
        }
        QLabel {
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        QLineEdit {
            background-color: #404040;
            color: white;
            border: none;
            padding: 5px;
            font-size: 12px;
        }
        QCheckBox {
            color: white;
            font-size: 12px;
        }
        QComboBox {
            background-color: #404040;
            color: white;
            font-size: 12px;
            font-weight: bold;
            border: none;
            padding: 5px;
        }
        QComboBox QAbstractItemView {
            background-color: #404040;
            color: white;
            selection-background-color: #606060;
        }
    """
    SIDEBAR_STYLE = """
        QWidget {
            background-color: #202020;
            color: white;
        }
        QTreeWidget {
            background-color: #202020;
            color: white;
            border: 1px solid #404040;
            outline: none;
        }
        QTreeWidget::item:selected {
            background-color: #404040;
            color: white;
        }
        QPushButton {
            background-color: #606060;
            padding: 3px;
            color: white;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
            min-height: 10px;
            margin-bottom: 3px;
        }
        QPushButton:hover {
            background-color: #303030;
            border: 1px solid #ffffff;
        }
    """
# ----------------------------------------------------------------------
    @classmethod
    def apply_theme(cls, app, theme="dark"):
        if theme == "dark":
            full_stylesheet = (
                cls.MESSAGE_BOX_STYLE +
                cls.DIALOG +
                cls.LOADING_DIALOG_STYLE +
                cls.MENU_STYLE
            )
            app.setStyleSheet(full_stylesheet)
# ----------------------------------------------------------------------
class VersionManager:
    @staticmethod
    def update_json():
        try:
            crd_dir = os.path.dirname(os.path.abspath(__file__))
            versions_path = os.path.normpath(
                os.path.join(crd_dir, "../config/versions.json")
            )
            modules_dir = os.path.normpath(
                os.path.join(crd_dir, "../modules")
            )
            if not os.path.exists(versions_path):
                with open(versions_path, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=4)
            try:
                with open(versions_path, "r", encoding="utf-8") as f:
                    versions = json.load(f)
            except (json.JSONDecodeError, OSError):
                versions = {}
            ignored_files = {"__init__.py", "__init__.pyw"}
            scripts_files = [
                filename
                for filename in os.listdir(crd_dir)
                if (
                    filename.endswith((".py", ".pyw"))
                    and filename not in ignored_files
                    and os.path.isfile(os.path.join(crd_dir, filename))
                )
            ]
            modules_files = []
            if os.path.isdir(modules_dir):
                modules_files = [
                    os.path.join("modules", filename)
                    for filename in os.listdir(modules_dir)
                    if (
                        filename.endswith((".py", ".pyw"))
                        and filename not in ignored_files
                        and os.path.isfile(os.path.join(modules_dir, filename))
                    )
                ]
            all_current_files = set(scripts_files + modules_files)
            updated = False
            for file_key in list(versions):
                if file_key.replace("\\", "/") not in all_current_files:
                    del versions[file_key]
                    updated = True
            for file_key in all_current_files:
                normalized_key = file_key.replace("\\", "/")
                if normalized_key.startswith("modules/"):
                    full_path = os.path.join(
                        modules_dir,
                        os.path.basename(normalized_key)
                    )
                else:
                    full_path = os.path.join(crd_dir, file_key)
                try:
                    with open(
                        full_path,
                        "r",
                        encoding="utf-8",
                        errors="ignore"
                    ) as f:
                        content = f.read()
                except OSError:
                    continue
                version_match = re.search(r"Version\s+(\d+\.\d+)", content)
                date_match = re.search(r"Updated\s+(\d{2}/\d{2}/\d{2})", content)
                version = (
                    f"{float(version_match.group(1)):.2f}"
                    if version_match
                    else ""
                )
                updated_date = date_match.group(1) if date_match else ""
                if version and updated_date:
                    new_value = f"{version} ({updated_date})"
                elif version:
                    new_value = version
                elif updated_date:
                    new_value = f" ({updated_date})"
                else:
                    new_value = ""
                if versions.get(file_key) != new_value:
                    versions[file_key] = new_value
                    updated = True
            if updated:
                with open(versions_path, "w", encoding="utf-8") as f:
                    json.dump(dict(sorted(versions.items())), f, indent=4)
        except Exception:
            pass
# ----------------------------------------------------------------------
    @staticmethod
    def load_versions(about_viewer):
        try:
            crd_dir = os.path.dirname(os.path.abspath(__file__))
            versions_path = os.path.normpath(os.path.join(crd_dir, "../config/versions.json"))
            if not os.path.exists(versions_path):
                about_viewer.setPlainText("Versions File Not Found")
                return

            with open(versions_path, 'r', encoding='utf-8') as f:
                try:
                    versions = json.load(f)
                except json.JSONDecodeError:
                    versions = {}

            scripts = {}
            modules = {}
            for k, v in versions.items():
                k_norm = k.replace('\\', '/')
                if not k_norm.startswith('modules/'):
                    scripts[k] = v
                else:
                    module_name = k_norm.split('/')[-1]
                    modules[module_name] = v

            script_list = []
            for filename in sorted(scripts.keys()):
                v = scripts[filename]
                if ' (' in v:
                    parts = v.split(' (')
                    version_str = parts[0].strip()
                    updated = parts[1].rstrip(')').strip() if len(parts) > 1 else ''
                elif v.startswith(' ('):
                    version_str = ""
                    updated = v[2:-1].strip() if v.endswith(')') else v[1:].strip()
                else:
                    version_str = v.strip()
                    updated = ''

                version = version_str if version_str else ''
                if updated != '':
                    try:
                        date_obj = dt.datetime.strptime(updated, "%Y-%m-%d")
                    except ValueError:
                        try:
                            date_obj = dt.datetime.strptime(updated, "%m/%d/%y")
                        except ValueError:
                            date_obj = None
                    if date_obj:
                        updated = date_obj.strftime("%Y%m%d")

                base_name = os.path.splitext(filename)[0]
                script_list.append((base_name, version, updated))

            about_text = ""
            if script_list:
                max_name = max(len(name) for name, ver, upd in script_list)
                max_ver = max(len(ver) for name, ver, upd in script_list)
                max_upd = max(len(upd) for name, ver, upd in script_list)

                about_text += "SCRIPTS\n"
                about_text += f"{'Name'.ljust(max_name)}  {'ver'.rjust(max_ver)}    {'Package'.rjust(max_upd)}\n"
                about_text += "-" * (max_name + max_ver + max_upd + 8) + "\n"
                for name, ver, upd in script_list:
                    about_text += f"{name.ljust(max_name)}   {ver.rjust(max_ver)}    {upd.rjust(max_upd)}\n"

            if modules:
                if about_text:
                    about_text += "\n"
                about_text += "MODULES\n"

            module_list = []
            for filename in sorted(modules.keys()):
                v = modules[filename]
                if ' (' in v:
                    parts = v.split(' (')
                    version_str = parts[0].strip()
                    updated = parts[1].rstrip(')').strip() if len(parts) > 1 else ''
                elif v.startswith(' ('):
                    version_str = ""
                    updated = v[2:-1].strip() if v.endswith(')') else v[1:].strip()
                else:
                    version_str = v.strip()
                    updated = ''

                version = version_str if version_str else ''
                if updated != '':
                    try:
                        date_obj = dt.datetime.strptime(updated, "%Y-%m-%d")
                    except ValueError:
                        try:
                            date_obj = dt.datetime.strptime(updated, "%m/%d/%y")
                        except ValueError:
                            date_obj = None
                    if date_obj:
                        updated = date_obj.strftime("%Y%m%d")

                base_name = os.path.splitext(filename)[0]
                module_list.append((base_name, version, updated))

            if module_list:
                max_name = max(len(name) for name, ver, upd in module_list)
                max_ver = max(len(ver) for name, ver, upd in module_list)
                max_upd = max(len(upd) for name, ver, upd in module_list)

                about_text += f"{'Name'.ljust(max_name)}  {'ver'.rjust(max_ver)}   {'Package'.rjust(max_upd)}\n"
                about_text += "-" * (max_name + max_ver + max_upd + 8) + "\n"
                for name, ver, upd in module_list:
                    about_text += f"{name.ljust(max_name)}   {ver.rjust(max_ver)}   {upd.rjust(max_upd)}\n"

            about_viewer.setPlainText(about_text)
            cursor = about_viewer.textCursor()
            cursor.movePosition(cursor.MoveOperation.End) 
            about_viewer.setTextCursor(cursor)
            scrollbar = about_viewer.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            about_viewer.ensureCursorVisible()
        except Exception as e:
            about_viewer.setPlainText(f"Error Loading Versions: {str(e)}")
# ----------------------------------------------------------------------