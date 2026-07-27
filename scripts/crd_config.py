# ----------------------------------------------------------------------
"""
crd_config.py (ew)
PyQt6
Version 1.02 Updated 07/17/26
"""
# ----------------------------------------------------------------------
import sys
import json
import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QPushButton,
    QComboBox, QLabel, QLineEdit, QSizePolicy, QSpacerItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon
from crd_encryptor import update_config
from crd_embedded import CustomMessageBox, Paths, CRDLogger, Styles

icon_path = lambda name: os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../html/icons/", name))
# ----------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ----------------------------------------------------------------------
class ConfigUI(QWidget):
    close_requested = pyqtSignal()
    config_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.section_map = {
            "user": "USER",
            "sp_win10": "SP_WIN10",
            "sp_win7": "SP_WIN7",
            "mr_mp6+": "MR_MP6+",
            "mr_mp3-5": "MR_MP3-5",
            "mr_mp2": "MR_MP2",
            "mr_gp": "MR_GP",
            "ct_scan": "CT_SCAN",
            "ul": "UL",
            "vl": "VL",
            "xr": "XR",
            "ct_display": "CT_DISPLAY"
        }
        self.config = None
        self.paths_config = None
        try:
            self.config = self.load_config()
        except Exception as e:
            logging.error(f"[CONFIG] Loading Config Failed: {type(e).__name__}: {e}")
        try:
            self.paths_config = self.load_paths_config()
        except Exception as e:
            logging.error(f"[CONFIG] Loading Paths Failed: {type(e).__name__}: {e}")
            self.paths_config = self.get_default_paths_config()
        if not isinstance(self.paths_config, dict) or "paths" not in self.paths_config or "settings" not in self.paths_config:
            self.paths_config = self.get_default_paths_config()
        try:
            self.init_ui()
        except Exception as e:
            logging.error(f"[CONFIG] Initializing UI Failed: {type(e).__name__}: {e}")
            raise
# ----------------------------------------------------------------------
    def get_default_paths_config(self):
        return {
            "paths": {
                "putty": r"C:\Program Files\PuTTY\PuTTY.exe",
                "filezilla": r"C:\Program Files\FileZilla FTP Client\filezilla.exe"
            },
            "settings": {
                "vpnauto": True
            }
        }
# ----------------------------------------------------------------------
    def load_config(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        key_path = os.path.join(parent_dir, "config", "user.key")
        enc_path = os.path.join(parent_dir, "config", "user.enc")
        if not os.path.exists(key_path) or not os.path.exists(enc_path):
            logging.info("[CONFIG] user.key or user.enc Missing")
            raise FileNotFoundError("Missing user.key or user.enc")
        config = update_config({}, key_path, enc_path)
        return config
# ----------------------------------------------------------------------
    def load_paths_config(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        json_file = os.path.join(parent_dir, "config", "settings.json")
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if "paths" not in config or "settings" not in config:
                    logging.error("[CONFIG] settings.json Missing Keys")
                    return self.get_default_paths_config()
                if "debug" in config["settings"]:
                    config["settings"]["rdpres"] = config["settings"].pop("debug")
                if "setting_zilla" in config["settings"]:
                    config["settings"]["sidepop"] = config["settings"].pop("setting_zilla")
                if "setting_putty" in config["settings"]:
                    config["settings"]["misc2"] = config["settings"].pop("setting_putty")
                return config
            except json.JSONDecodeError as e:
                logging.error(f"[CONFIG] Failed to parse settings.json: {type(e).__name__}: {e}")
                return self.get_default_paths_config()
            except Exception as e:
                logging.error(f"[CONFIG] Reading settings.json failed: {type(e).__name__}: {e}")
                return self.get_default_paths_config()
        logging.warning(f"[CONFIG] settings.json not found at {json_file}; using default")
        return self.get_default_paths_config()
# ----------------------------------------------------------------------
    def save_paths_config(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        json_file = os.path.join(parent_dir, "config", "settings.json")
        try:
            os.makedirs(os.path.dirname(json_file), exist_ok=True)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.paths_config, f, indent=4)
        except Exception as e:
            logging.error(f"[CONFIG] Error Saving Settings: {type(e).__name__}: {e}")
            raise
# ----------------------------------------------------------------------
    def init_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        self.setStyleSheet(
            Styles.BUTTON_STYLE +
            Styles.LINE_EDIT_STYLE +
            Styles.STD_LABEL_STYLE +
            Styles.WIDGET_STYLE +
            Styles.GROUP_BOX +
            Styles.COMBO_BOX +
            Styles.CHECKBOX_STYLE
        )
        settings_group = QGroupBox("SETTINGS")
        settings_group.setStyleSheet(Styles.GROUP_BOX)
        settings_group.setFixedHeight(90)
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(5, 15, 5, 5)

        vpnauto_layout = QHBoxLayout()
        vpnauto_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        self.vpnauto_cb = QCheckBox("VPN Auto (Use For Auto Connecting to the VPN)")
        self.vpnauto_cb.setChecked(self.paths_config["settings"].get("vpnauto", False))
        self.vpnauto_cb.stateChanged.connect(self.update_settings)
        vpnauto_layout.addWidget(self.vpnauto_cb)
        vpnauto_layout.addStretch()
        settings_layout.addLayout(vpnauto_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        credentials_group = QGroupBox("CREDENTIALS")
        credentials_group.setStyleSheet(Styles.GROUP_BOX)
        credentials_group.setFixedHeight(90)
        credentials_layout = QVBoxLayout()
        credentials_layout.setContentsMargins(5, 5, 5, 5)
        credentials_layout.setSpacing(5)
        credentials_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(10)
        fields_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.section_combo = QComboBox()
        self.section_combo.setStyleSheet(Styles.COMBO_BOX)
        self.section_combo.addItems([
            "USER", "SP_WIN10", "SP_WIN7", "MR_MP6+", "MR_MP3-5", "MR_MP2", "MR_GP"
        ])
        self.section_combo.setFixedWidth(150)
        self.section_combo.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.section_combo.currentIndexChanged.connect(self.update_credentials_fields)
        fields_layout.addWidget(self.section_combo)

        username_sub_layout = QHBoxLayout()
        username_sub_layout.setSpacing(5)
        self.username_label = QLabel("Username:")
        self.username_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        username_sub_layout.addWidget(self.username_label)
        self.username_edit = QLineEdit()
        self.username_edit.setFixedWidth(150)
        self.username_edit.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        username_sub_layout.addWidget(self.username_edit)
        fields_layout.addLayout(username_sub_layout)

        password_sub_layout = QHBoxLayout()
        password_sub_layout.setSpacing(5)
        self.password_label = QLabel("Password:")
        self.password_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        password_sub_layout.addWidget(self.password_label)
        self.password_edit = QLineEdit()
        self.password_edit.setFixedWidth(150)
        self.password_edit.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        password_sub_layout.addWidget(self.password_edit)
        fields_layout.addLayout(password_sub_layout)

        fields_layout.addStretch()
        credentials_layout.addLayout(fields_layout)
        credentials_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        credentials_group.setLayout(credentials_layout)
        main_layout.addWidget(credentials_group)

        paths_group = QGroupBox("PATHS")
        paths_group.setStyleSheet(Styles.GROUP_BOX)
        paths_group.setFixedHeight(150)
        paths_layout = QVBoxLayout()
        paths_layout.setContentsMargins(5, 15, 5, 5)
        paths_layout.setSpacing(5)

        # PuTTY
        putty_field_layout = QHBoxLayout()
        putty_field_layout.setSpacing(10)
        self.putty_label = QLabel(" PuTTY:")
        self.putty_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        putty_field_layout.addWidget(self.putty_label)
        self.putty_edit = QLineEdit()
        self.putty_edit.setFixedWidth(350)
        self.putty_edit.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.putty_edit.setText(self.paths_config['paths'].get('putty', ''))
        putty_field_layout.addWidget(self.putty_edit)
        self.putty_browse_btn = QPushButton("+")
        self.putty_browse_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.putty_browse_btn.setFixedWidth(30)
        self.putty_browse_btn.setFixedHeight(30)
        self.putty_browse_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.putty_browse_btn.clicked.connect(self.browse_putty_path)
        putty_field_layout.addWidget(self.putty_browse_btn)
        putty_field_layout.addStretch()
        paths_layout.addLayout(putty_field_layout)

        # FileZilla
        filezilla_field_layout = QHBoxLayout()
        filezilla_field_layout.setSpacing(10)
        self.filezilla_label = QLabel("FileZilla:")
        self.filezilla_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        filezilla_field_layout.addWidget(self.filezilla_label)
        self.filezilla_edit = QLineEdit()
        self.filezilla_edit.setFixedWidth(350)
        self.filezilla_edit.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.filezilla_edit.setText(self.paths_config['paths'].get('filezilla', ''))
        filezilla_field_layout.addWidget(self.filezilla_edit)
        self.filezilla_browse_btn = QPushButton("+")
        self.filezilla_browse_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.filezilla_browse_btn.setFixedWidth(30)
        self.filezilla_browse_btn.setFixedHeight(30)
        self.filezilla_browse_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.filezilla_browse_btn.clicked.connect(self.browse_filezilla_path)
        filezilla_field_layout.addWidget(self.filezilla_browse_btn)
        filezilla_field_layout.addStretch()
        paths_layout.addLayout(filezilla_field_layout)

        paths_group.setLayout(paths_layout)
        main_layout.addWidget(paths_group)

        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton("SAVE")
        self.save_btn.setIcon(QIcon(icon_path("download.png")))
        self.save_btn.setIconSize(QSize(24, 24))
        self.save_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.save_btn.setFixedWidth(130)
        self.save_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.save_btn.clicked.connect(self.save_all)
        save_layout.addWidget(self.save_btn)
        save_layout.addStretch()
        main_layout.addLayout(save_layout)
        main_layout.addStretch()

        total_height = 150 + 90 + 150 + 30 + 100
        self.setFixedHeight(total_height)
        self.update_credentials_fields()
# ----------------------------------------------------------------------
    def browse_putty_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PuTTY Path", "", "Executable Files (*.exe)")
        if file_path:
            self.putty_edit.setText(file_path)
# ----------------------------------------------------------------------
    def browse_filezilla_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select FileZilla Path", "", "Executable Files (*.exe)")
        if file_path:
            self.filezilla_edit.setText(file_path)
# ----------------------------------------------------------------------
    def save_paths(self):
        putty_path = self.putty_edit.text()
        filezilla_path = self.filezilla_edit.text()
        for path, name in [
            (putty_path, "PuTTY"),
            (filezilla_path, "FileZilla")
        ]:
            if path and not os.path.exists(path):
                logging.error(f"[CONFIG] Invalid path for {name}: {path}")
                return
        self.paths_config["paths"]["putty"] = putty_path
        self.paths_config["paths"]["filezilla"] = filezilla_path
        self.paths_config["settings"]["vpnauto"] = self.vpnauto_cb.isChecked()
        # Note: rdpres / sidepop / misc2 checkboxes are currently commented out in the UI
        self.save_paths_config()
        self.config_updated.emit()
# ----------------------------------------------------------------------
    def save_all(self):
        section = self.section_combo.currentText()
        norm_section = self.section_map.get(section.lower(), section)
        try:
            updates = {
                norm_section: {
                    "credentials": {
                        "host_user": self.username_edit.text(),
                        "host_pass": self.password_edit.text()
                    }
                }
            }
            if norm_section in self.config and "credentials" in self.config[norm_section]:
                if "host_port" in self.config[norm_section]["credentials"]:
                    updates[norm_section]["credentials"]["host_port"] = self.config[norm_section]["credentials"]["host_port"]
                if "alt_port" in self.config[norm_section]["credentials"]:
                    updates[norm_section]["credentials"]["alt_port"] = self.config[norm_section]["credentials"]["alt_port"]
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)
            key_path = os.path.join(parent_dir, "config", "user.key")
            enc_path = os.path.join(parent_dir, "config", "user.enc")
            self.config = update_config(updates, key_path, enc_path)
            logging.info(f"[CONFIG] Saved credentials for section {norm_section}")
            QMessageBox.information(self, "Success", f"Saved credentials for section {norm_section}")
            self.config_updated.emit()
        except Exception as e:
            logging.error(f"[CONFIG] Saving Credentials: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save credentials: {e}")
        try:
            self.save_paths()
        except Exception as e:
            logging.error(f"[CONFIG] Saving Paths: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save paths: {e}")
# ----------------------------------------------------------------------
    def update_settings(self):
        self.paths_config["settings"]["vpnauto"] = self.vpnauto_cb.isChecked()
        try:
            self.save_paths_config()
            self.config_updated.emit()
            QMessageBox.information(self, "Success", "Settings saved successfully")
        except Exception as e:
            logging.error(f"[CONFIG] Updating Settings: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
# ----------------------------------------------------------------------
    def update_credentials_fields(self):
        section = self.section_combo.currentText()
        norm_section = self.section_map.get(section.lower(), section)
        credentials = self.config.get(norm_section, {}).get("credentials", {}) if self.config else {}
        self.username_edit.setText(credentials.get("host_user", ""))
        self.password_edit.setText(credentials.get("host_pass", ""))
# ----------------------------------------------------------------------