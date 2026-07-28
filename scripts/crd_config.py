# ----------------------------------------------------------------------
"""
crd_config.py (ew)
PyQt6
Version 2.00 Updated 07/17/26
"""
# ----------------------------------------------------------------------
import sys
import json
import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QPushButton, QLayout,
    QComboBox, QLabel, QLineEdit, QSizePolicy, QSpacerItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon
from crd_encryptor import update_config
from crd_embedded import CustomMessageBox, Paths, CRDLogger, Styles
icon_path = lambda name: os.path.normpath(os.path.join(os.getcwd(), "images", "icons", name))
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
    def save_paths(self):
        putty_path = self.putty_edit.text()
        filezilla_path = self.filezilla_edit.text()
        for path, name in [
            (putty_path, "PuTTY"),
            (filezilla_path, "FileZilla")
        ]:
            if path and not os.path.exists(path):
                logging.error(f"[CONFIG] Invalid Path For {name}: {path}")
                return

        self.paths_config["paths"]["putty"] = putty_path
        self.paths_config["paths"]["filezilla"] = filezilla_path
        self.paths_config["settings"]["vpnauto"] = self.vpnauto_cb.isChecked()

        try:
            self.save_html_links()
        except Exception as e:
            logging.error(f"[CONFIG] Failed to Save Links {e}")
            QMessageBox.critical(self, "Error", f"Failed to Save Links {e}")
            return

        self.save_paths_config()
        self.config_updated.emit()
# ----------------------------------------------------------------------
    def init_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
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
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
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
        """
        autoupdate_layout = QHBoxLayout()
        autoupdate_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        self.autoupdate_cb = QCheckBox("WIP Check for Updates on Load")
        self.autoupdate_cb.setChecked(self.paths_config["settings"].get("autoupdate", False))
        self.autoupdate_cb.setEnabled(False)        
        self.autoupdate_cb.stateChanged.connect(self.update_settings)  

        autoupdate_layout.addWidget(self.autoupdate_cb)
        autoupdate_layout.addStretch()
        settings_layout.addLayout(autoupdate_layout)
        """
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
        self.username_label = QLabel("Username")
        self.username_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        username_sub_layout.addWidget(self.username_label)
        self.username_edit = QLineEdit()
        self.username_edit.setFixedWidth(150)
        self.username_edit.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        username_sub_layout.addWidget(self.username_edit)
        fields_layout.addLayout(username_sub_layout)

        password_sub_layout = QHBoxLayout()
        password_sub_layout.setSpacing(5)
        self.password_label = QLabel("Password")
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
# LINKS
        links_group = QGroupBox("LINKS")
        links_group.setStyleSheet(Styles.GROUP_BOX)
        links_group.setFixedHeight(180)
        links_layout = QVBoxLayout()
        links_layout.setContentsMargins(5, 15, 5, 5)
        links_layout.setSpacing(6)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(8)
        self.links_label = QLabel("Link:")
        self.links_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        combo_row.addWidget(self.links_label)

        self.links_combo = QComboBox()
        self.links_combo.setStyleSheet(Styles.COMBO_BOX)
        self.links_combo.setFixedWidth(200)
        self.links_combo.currentIndexChanged.connect(self.on_links_combo_changed)
        combo_row.addWidget(self.links_combo)
        combo_row.addStretch()
        links_layout.addLayout(combo_row)

        edit_row = QHBoxLayout()
        edit_row.setSpacing(8)

        self.link_name_label = QLabel("Name:")
        self.link_name_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        edit_row.addWidget(self.link_name_label)

        self.link_name_edit = QLineEdit()
        self.link_name_edit.setFixedWidth(160)
        edit_row.addWidget(self.link_name_edit)

        self.link_url_label = QLabel("URL:")
        self.link_url_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        edit_row.addWidget(self.link_url_label)

        self.link_url_edit = QLineEdit()
        self.link_url_edit.setFixedWidth(320)
        edit_row.addWidget(self.link_url_edit)
        edit_row.addStretch()
        links_layout.addLayout(edit_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_group = QGroupBox()
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setContentsMargins(8, 6, 8, 6)
        btn_layout.setSpacing(12)
        self.default_cb = QCheckBox("Default")
        self.default_cb.setStyleSheet(Styles.CHECKBOX_STYLE)
        btn_row.addWidget(self.default_cb)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)    

        self.add_btn = QPushButton("Add")
        self.add_btn.setIcon(QIcon(icon_path("add.png")))
        self.add_btn.setIconSize(QSize(18, 18))

        self.modify_btn = QPushButton("Modify")
        self.modify_btn.setIcon(QIcon(icon_path("edit.png")))
        self.modify_btn.setIconSize(QSize(18, 18))

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(QIcon(icon_path("delete.png")))
        self.delete_btn.setIconSize(QSize(18, 18))

        
        btn_row.addStretch()
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.modify_btn)
        btn_layout.addWidget(self.delete_btn)

        btn_group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        self.add_link_btn = QPushButton("ADD")
        self.add_link_btn.setIcon(QIcon(icon_path("add.png")))
        self.add_link_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.add_link_btn.setFixedWidth(100)
        self.add_link_btn.clicked.connect(self.add_link)
        btn_row.addWidget(self.add_link_btn)

        self.mod_link_btn = QPushButton("MODIFY")
        self.mod_link_btn.setIcon(QIcon(icon_path("edit.png")))
        self.mod_link_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.mod_link_btn.setFixedWidth(100)
        self.mod_link_btn.clicked.connect(self.modify_link)
        btn_row.addWidget(self.mod_link_btn)

        self.del_link_btn = QPushButton("DELETE")
        self.del_link_btn.setIcon(QIcon(icon_path("remove.png")))
        self.del_link_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.del_link_btn.setFixedWidth(100)
        self.del_link_btn.clicked.connect(self.delete_link)
        btn_row.addWidget(self.del_link_btn)
        btn_row.addStretch()
        
        links_layout.addLayout(btn_row)
        links_group.setLayout(links_layout)
        main_layout.addWidget(links_group)
        self.load_html_links()
        save_layout = QHBoxLayout()
        save_layout.addStretch()
# SAVE
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
        total_height = 160 + 100 + 150 + 200
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
            logging.info(f"[CONFIG] Saved Credentials for Section {norm_section}")
            QMessageBox.information(self, "Success", f"Saved Credentials for Section {norm_section}")
            self.config_updated.emit()
        except Exception as e:
            logging.error(f"[CONFIG] Saving Credentials {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to Save credentials {e}")
        try:
            self.save_paths()
        except Exception as e:
            logging.error(f"[CONFIG] Saving Paths: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to Save Paths {e}")
# ----------------------------------------------------------------------
    def update_settings(self):
        self.paths_config["settings"]["vpnauto"] = self.vpnauto_cb.isChecked()
        try:
            self.save_paths_config()
            self.config_updated.emit()
            QMessageBox.information(self, "Success", "Settings Saved")
        except Exception as e:
            logging.error(f"[CONFIG] Updating Settings: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to Save Settings {e}")
# ----------------------------------------------------------------------
    def update_credentials_fields(self):
        section = self.section_combo.currentText()
        norm_section = self.section_map.get(section.lower(), section)
        credentials = self.config.get(norm_section, {}).get("credentials", {}) if self.config else {}
        self.username_edit.setText(credentials.get("host_user", ""))
        self.password_edit.setText(credentials.get("host_pass", ""))
# ----------------------------------------------------------------------
    def get_html_json_path(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        return os.path.join(parent_dir, "config", "html.json")
# ----------------------------------------------------------------------
    def load_html_links(self):
        self.html_links = []
        self.links_combo.blockSignals(True)
        self.links_combo.clear()

        json_path = self.get_html_json_path()
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.html_links = data.get("links", [])
            except Exception as e:
                logging.error(f"[CONFIG] Failed to load html.json: {e}")
                self.html_links = []

        if not self.html_links:
            self.html_links = [
                {"name": "", "url": ""},
                {"name": "INTRANET", "url": "https://intranet.cmsu.com/default.aspx"},
                {"name": "HELP", "url": "html/help.html"},
                {"name": "nxVision LINK", "url": "https://nxv.cmsu.com"}
            ]

        for item in self.html_links:
            self.links_combo.addItem(item["name"])

        self.links_combo.blockSignals(False)
        default_name = self.paths_config.get("url", {}).get("urlname", "INTRANET")
        idx = self.links_combo.findText(default_name)
        if idx >= 0:
            self.links_combo.setCurrentIndex(idx)
        elif self.links_combo.count() > 0:
            self.links_combo.setCurrentIndex(0)
        self.on_links_combo_changed(self.links_combo.currentIndex())
# ----------------------------------------------------------------------
    def on_links_combo_changed(self, index):
        if index < 0 or index >= len(self.html_links):
            self.link_name_edit.clear()
            self.link_url_edit.clear()
            self.default_cb.setChecked(False)
            return
        item = self.html_links[index]
        self.link_name_edit.setText(item.get("name", ""))
        self.link_url_edit.setText(item.get("url", ""))
        default_name = self.paths_config.get("url", {}).get("urlname", "")
        self.default_cb.setChecked(item.get("name", "") == default_name)
# ----------------------------------------------------------------------
    def add_link(self):
        name = self.link_name_edit.text().strip()
        url = self.link_url_edit.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "Missing Data", "Both Name and URL are required.")
            return

        if any(item["name"].lower() == name.lower() for item in self.html_links):
            QMessageBox.warning(self, "Duplicate", f"A Link Named '{name}' Already Exists.")
            return

        self.html_links.append({"name": name, "url": url})
        self.links_combo.addItem(name)
        self.links_combo.setCurrentText(name)
        logging.info(f"[CONFIG] Added Link: {name}")
# ----------------------------------------------------------------------
    def modify_link(self):
        index = self.links_combo.currentIndex()
        if index < 0:
            return

        name = self.link_name_edit.text().strip()
        url = self.link_url_edit.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "Missing Data", "Both Name and URL are Required")
            return
        for i, item in enumerate(self.html_links):
            if i != index and item["name"].lower() == name.lower():
                QMessageBox.warning(self, "Duplicate", f"A Link Named '{name}' Already Exists")
                return

        self.html_links[index]["name"] = name
        self.html_links[index]["url"] = url
        self.links_combo.setItemText(index, name)
        logging.info(f"[CONFIG] Modified Link {name}")
# ----------------------------------------------------------------------
    def delete_link(self):
        index = self.links_combo.currentIndex()
        if index < 0:
            return

        name = self.html_links[index]["name"]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete Link '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        del self.html_links[index]
        self.links_combo.removeItem(index)
        logging.info(f"[CONFIG] Deleted Link {name}")

# ----------------------------------------------------------------------
    def save_html_links(self):
        json_path = self.get_html_json_path()
        try:
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({"links": self.html_links}, f, indent=4)
        except Exception as e:
            logging.error(f"[CONFIG] Failed to Save html.json: {e}")
            raise

        if self.default_cb.isChecked():
            current_name = self.link_name_edit.text().strip()
            current_url = self.link_url_edit.text().strip()
            if "url" not in self.paths_config:
                self.paths_config["url"] = {}
            self.paths_config["url"]["urlname"] = current_name
            self.paths_config["url"]["defaulturl"] = current_url
# ----------------------------------------------------------------------



