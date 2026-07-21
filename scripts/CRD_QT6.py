# ------------------------------------------------------------------------
"""
CanonRemoteDiagnostics.py
Main UI and Structure
Version 2.00 Updated 07/10/26    
JSmyser CHECK FOR JS_EDIT 25.12.24 TO SEE WHAT I CHANGED.
ALSO GOT RID OF SOME DUPLICATE METHODS. 2025.12.24'
"""
VERSION = "CRD - Canon Remote Diagnostics v2.00"
# ------------------------------------------------------------------------
# LIBRARIES
import sys, os, configparser, logging, platform, webbrowser, subprocess, warnings
import threading, json, importlib, socket, re, glob, traceback, html, zipfile
from pathlib import Path
from datetime import datetime
from cryptography.fernet import InvalidToken
try:
    from PyQT6.QTWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QProgressDialog,
                             QHBoxLayout, QLabel, QTreeWidget, QLayout, QTreeWidgetItem, QTextBrowser,
                             QStackedWidget, QPushButton, QMessageBox, QLineEdit,QListWidget,QShortcut, 
                             QScrollArea, QSizePolicy, QSpacerItem, QDialog, QTabWidget, QTextEdit,
                             QAction, QComboBox)
    
except ImportError:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QProgressDialog,
                             QHBoxLayout, QLabel, QTreeWidget, QLayout, QTreeWidgetItem, QTextBrowser,
                             QStackedWidget, QPushButton, QMessageBox, QLineEdit,QListWidget,QShortcut, 
                             QScrollArea, QSizePolicy, QSpacerItem, QDialog, QTabWidget, QTextEdit,
                             QAction, QComboBox)
try:
    from PyQt6.QtCore import QObject, pyqtSignal, Qt, QSize, QUrl, QTimer, QThread
except ImportError:
    from PyQt5.QtCore import QObject, pyqtSignal, Qt, QSize, QUrl, QTimer, QThread

try:
    from PyQt6.QtGui import QPixmap, QScreen, QColor, QPainter, QBrush, QFont, QKeySequence, QTextCursor, QIcon
except ImportError:
    from PyQt5.QtGui import QPixmap, QScreen, QColor, QPainter, QBrush, QFont, QKeySequence, QTextCursor, QIcon

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
except ImportError:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
# MODULES
import crd_matrix
import crd_update
import crd_putty
from crd_sidebar import AppTreeWidget
from crd_config import ConfigUI
from crd_sid_manager import SIDDatabase, EntryDialog, SIDDatabaseWindow
from crd_embedded import CustomMessageBox, Paths, CRDLogger, Styles, VersionManager
from crd_framework import ApplicationFramework, TabManager, ButtonState
from crd_led_monitor import (ConnectivityIndicator, ConnectionMonitorThread,
                              LedWidget, TunnelMonitorWorker)
from crd_encryptor import load_key, decrypt_json, update_config
warnings.filterwarnings("ignore", category=DeprecationWarning)
icon_path = lambda name: os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../html/icons/", name))
# ------------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
class CustomWebEnginePage(QWebEnginePage):
    def certificateError(self, certificateError):
        return True
# ------------------------------------------------------------------------
class CustomMessageBox(QMessageBox):
    def __init__(self, title, message, icon, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(icon)
        self.setStyleSheet(Styles.MESSAGE_BOX_STYLE) 
        self.setStandardButtons(QMessageBox.Ok)
    
    def center(self):
        if self.parent():
            parent_geo = self.parent().geometry()
            self_geo = self.geometry()
            self.move(parent_geo.center() - self_geo.center())
    
    def exec_custom(self):
        self.exec_()
# ------------------------------------------------------------------------
class EditorDialog(QDialog):
    CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("TEXT EDITOR")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(700, 500)
        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.setStyleSheet(Styles.COMBO_BOX)
        self.combo.currentTextChanged.connect(self.on_file_selected)

        refresh_btn = QPushButton("REFRESH")
        refresh_btn.clicked.connect(self.refresh_file_list)
        refresh_btn.setStyleSheet(Styles.BUTTON_STYLE)
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Config file:"))
        selector_layout.addWidget(self.combo, 1)
        selector_layout.addWidget(refresh_btn)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Select a File")
        
        save_btn = QPushButton(" SAVE ")
        save_btn.clicked.connect(self.save_file)
        save_btn.setStyleSheet(Styles.BUTTON_STYLE)
        close_btn = QPushButton(" CLOSE ")
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet(Styles.BUTTON_STYLE)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()

        main_layout = QVBoxLayout()
        main_layout.addLayout(selector_layout)
        main_layout.addWidget(self.text_edit, 1)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
        self.setStyleSheet(Styles.POPUP_DIALOG)
        self.refresh_file_list()
# ------------------------------------------------------------------------
    def get_config_files(self):
        if not os.path.isdir(self.CONFIG_DIR):
            return []                                  
        files = [
            f for f in os.listdir(self.CONFIG_DIR)
            if f.lower().endswith(('.txt', '.dat', '.json'))
        ]
        files.sort()
        return files
# ------------------------------------------------------------------------
    def refresh_file_list(self):
        self.combo.blockSignals(True)         
        self.combo.clear()
        files = self.get_config_files()
        if files:
            self.combo.addItems(files)
            self.combo.setCurrentIndex(0)
            self.load_file(self.combo.currentText())
        else:
            self.combo.addItem("<no .txt/.dat files>")
            self.text_edit.clear()
            self.text_edit.setPlaceholderText("No files in ../config")
        self.combo.blockSignals(False)
# ------------------------------------------------------------------------
    def on_file_selected(self, filename):
        if not filename or filename.startswith("<"):
            return
        self.load_file(filename)
# ------------------------------------------------------------------------
    def load_file(self, filename=None):
        if not filename:
            filename = self.combo.currentText()
            if not filename or filename.startswith("<"):
                self.text_edit.clear()
                return
        path = os.path.join(self.CONFIG_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text_edit.setPlainText(content)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could Not Read {filename}:\n{e}")
            self.text_edit.clear()
# ------------------------------------------------------------------------
    def save_file(self):
        filename = self.combo.currentText()
        if not filename or filename.startswith("<"):
            QMessageBox.warning(self, "Save", "Select a File First.")
            return
        path = os.path.join(self.CONFIG_DIR, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_edit.toPlainText())
            QMessageBox.information(self, "Saved", f"{filename} Saved Successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could Not Save {filename}:\n{e}")          
# ------------------------------------------------------------------------
class CustomWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        logger.warning(
            "JS console [%s] %s:%s — %s",
            level, source_id, line_number, message
        )

    def certificateError(self, error):
        logger.error(
            "Certificate error: %s | URL: %s",
            error.errorDescription(),
            error.url().toString()
        )
        #error.ignoreCertificateError()
        return False
# ------------------------------------------------------------------------
class DesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        profile = QWebEngineProfile.defaultProfile()
        self.app = QApplication(sys.argv)
        Styles.apply_theme(self.app, theme="dark")
        cache_path = os.path.join(os.path.expanduser("~"), ".vpntoolbox", "cache")
        os.makedirs(cache_path, exist_ok=True)
        profile.setCachePath(cache_path)
        profile.setPersistentStoragePath(cache_path)
        self.application_framework = ApplicationFramework(self)
        self.tab_widget = QTabWidget(self)
        self.tab_manager = TabManager(self.tab_widget)
        shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        shortcut.activated.connect(self.open_editor)
        self.button_states = ButtonState()
        self.vpn_connected = False
        self.buttons = {}
        self.vpn_username = ""
        self.vpn_password = ""
        self.vpn_key = ""
        self.auto_login_enabled = False
        self.config_ui_widget = None
        self.sp_ip = ""
        self.app_tree = None
        self.refresh_log_func = None
        self.tams_ip = ""
        self.sid_database_populated = False
        self.creds_dict = None
        self.edit_boxes = {
            "MachineName": None,
            "MachineType": None,
            "sw_version": None,
            "Modality": None,
            "machine": None
        }
        self.actions_matrix = {}
        self.vpn_connected = False
        self.sp_ip = ""
        self.sid_database_populated = False
        self.sid_data_manager = SIDDatabase()  
        self.setWindowTitle("CRD")
        self.resize(1400, 1000)
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #202020;")
        main_layout = QVBoxLayout(central_widget)

# ------------------------------------------------------------------------
# HEADER
        self.dynamic_header = QLabel("", self)
        self.dynamic_header.setAlignment(Qt.AlignCenter)
        self.dynamic_header.setStyleSheet(Styles.DYNAMIC_HEADER_STYLE)
        self.dynamic_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dynamic_header.setFixedHeight(40)
        self.dynamic_header.setMinimumWidth(200)
        main_layout.addWidget(self.dynamic_header)
        self.horizontal_layout = QHBoxLayout()
        main_layout.addLayout(self.horizontal_layout)
        self.dynamic_header.setStyleSheet(Styles.DYNAMIC_HEADER_STYLE)
        self.create_sidebar()

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setStyleSheet(Styles.TAB_WIDGET_STYLE)
        self.horizontal_layout.addWidget(self.tab_widget)
        self.init_tabs()
# ------------------------------------------------------------------------        
# FOOTER
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_widget.setFixedHeight(50)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        footer_image = QLabel()
        footer_image.setPixmap(QPixmap('canon.png'))
        footer_image.setAlignment(Qt.AlignLeft)
        footer_image.setMaximumHeight(60)
        footer_layout.addWidget(footer_image)
        footer_layout.addStretch()
    
        led_label = QLabel("VPN STATUS")
        led_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-right: 5px;")
        footer_layout.addWidget(led_label)
        self.connect_led = LedWidget(parent=self, diameter=20)
        footer_layout.addWidget(self.connect_led)
        footer_widget.setStyleSheet("background-color: #202020; color: white; padding: 1px;")
        main_layout.addWidget(footer_widget)
        self.load_config()
        self.sid_data_manager = SIDDatabaseWindow()
        self.tunnel_monitor = TunnelMonitorWorker(sp_ip="172.17.1.3")
        self.tunnel_monitor.status_signal.connect(self.update_vpn_status)
        QTimer.singleShot(30000, self.tunnel_monitor.start_monitoring)
        try:
            if self.sp_ip_edit_box:
                self.sp_ip_edit_box.textChanged.connect(self.update_tunnel_monitor_ip)
        except AttributeError:
            logger.error("[CRD UI] sp_ip_edit_box Not Initialized")
        self.load_actions_matrix()
# self.start_modality_polling() #JS_EDIT 25.12.24. THIS WAS CAUSING FLASHING. 
# DID THIS IN "CREATE_SIDEBAR" INSTEAD. self.modality_edit_box.textChanged.connect(self.check_modality)
        self.open_sid_database() #JS_EDIT 25.12.24. I like the DB to open right away. 
# ------------------------------------------------------------------------
# SIDEBAR
    def create_sidebar(self):
        sidebar = QWidget(self)
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(6)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar.setStyleSheet("background-color: #202020;")
        self.horizontal_layout.addWidget(sidebar)
# SID INPUT
        sid_layout = QHBoxLayout()
        sid_layout.setSpacing(2)
        self.edit_box_sid = QLineEdit()
        self.edit_box_sid.setStyleSheet(Styles.SID_EDIT_BOX_STYLE)
        self.edit_box_sid.setPlaceholderText("Enter SID Here...")
        self.edit_box_sid.setFixedHeight(26)
        self.edit_box_sid.setToolTip("Enter SID to Query Database")
        sid_layout.addWidget(self.edit_box_sid)
        sidebar_layout.addLayout(sid_layout)
# BUTTONS
        vpn_layout = QHBoxLayout()
        vpn_layout.setSpacing(2)
        self.vpn_sp_button = self.create_button("QUERY", self.handle_button_click)
        self.vpn_sp_button.setIcon(QIcon(icon_path("search.png")))
        self.vpn_sp_button.setIconSize(QSize(24, 24))
        self.vpn_sp_button.setFixedHeight(26)
        self.vpn_sp_button.setFixedWidth(100)
        self.vpn_sp_button.setToolTip("Query")
        self.button_states.set_state("vpn_sp", "QUERY VPN DB")
        vpn_layout.addWidget(self.vpn_sp_button)
        self.reset_btn = QPushButton("RESET")
        self.reset_btn.setIcon(QIcon(icon_path("refresh.png")))
        self.reset_btn.setIconSize(QSize(24, 24))
        self.reset_btn.setFixedWidth(100)
        self.reset_btn.setFixedHeight(26)
        self.reset_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.reset_btn.setToolTip("Reset and Clear Fields")
        self.reset_btn.clicked.connect(self.reset_state)
        vpn_layout.addWidget(self.reset_btn)
        self.sid_add_btn = QPushButton("ADD")
        self.sid_add_btn.setIcon(QIcon(icon_path("add.png")))
        self.sid_add_btn.setIconSize(QSize(24, 24))
        self.sid_add_btn.setFixedWidth(100)
        self.sid_add_btn.setFixedHeight(26)
        self.sid_add_btn.setStyleSheet(Styles.BUTTON_STYLE)
        self.sid_add_btn.setToolTip("Add Current SID to database")
        self.sid_add_btn.clicked.connect(self.add_to_sid_database)
        vpn_layout.addWidget(self.sid_add_btn)
        sidebar_layout.addLayout(vpn_layout)
# EDIT BOXES
        row_layout_tunnel = QHBoxLayout()
        row_layout_tunnel.setSpacing(2)
        tunnel_label = QLabel("TUNNEL TYPE:")
        tunnel_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        tunnel_label.setFixedHeight(26)
        row_layout_tunnel.addWidget(tunnel_label)
        self.tunnel_edit_box = QLineEdit()
        self.tunnel_edit_box.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.tunnel_edit_box.setFixedHeight(26)
        row_layout_tunnel.addWidget(self.tunnel_edit_box)
        sidebar_layout.addLayout(row_layout_tunnel)

        input_rows = [
            ("SP:", "sp_ip_edit_box", False),
            ("SM:", "sm_ip_edit_box", False),
            ("DISP:", "display_ip_edit_box", False),
            ("MODALITY:", "modality_edit_box", True),
            ("SW VERSION:", "sw_version_edit_box", True),
            ("SYSTEM:", "machine_edit_box", True),
        ]
        for label_text, attr_name, read_only in input_rows:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(2)
            label = QLabel(label_text)
            label.setStyleSheet(Styles.STD_LABEL_STYLE)
            label.setFixedHeight(26)
            row_layout.addWidget(label)
            edit_box = QLineEdit()
            edit_box.setStyleSheet(Styles.LINE_EDIT_STYLE)
            edit_box.setReadOnly(read_only)
            edit_box.setFixedHeight(26)
            row_layout.addWidget(edit_box)
            sidebar_layout.addLayout(row_layout)
            setattr(self, attr_name, edit_box)
            if attr_name == "display_ip_edit_box":
                label.hide()
                edit_box.hide() 
            if attr_name == "sw_version_edit_box":
                self.edit_boxes["sw_version"] = edit_box
            elif attr_name == "machine_edit_box":
                self.edit_boxes["machine"] = edit_box
            elif attr_name == "modality_edit_box":
                self.edit_boxes["Modality"] = edit_box
                edit_box.textChanged.connect(self.update_apptree)
            elif attr_name in self.edit_boxes:
                self.edit_boxes[attr_name] = edit_box
        
        label_row = QHBoxLayout()
        label_row.addStretch(1)
        icons_label = QLabel("💻⇄💻     💻⇄📁      💻⇄⌨  ")
        icons_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        icons_label.setAlignment(Qt.AlignRight)
        label_row.addWidget(icons_label) 
        sidebar_layout.addLayout(label_row)
# BUTTONS
        dynamic_rows = [
            ("SP:", ["RDP", "SFTP", "TERM"], [60,60,60]),
            ("SM:", ["SFTP", "TERM"], [60, 60]),
        ]
        for feature, buttons, widths in dynamic_rows:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(2)
            label = QLabel(feature)
            label.setStyleSheet(Styles.STD_LABEL_STYLE)
            label.setFixedHeight(22)
            row_layout.addWidget(label)
            for btn_text, width in zip(buttons, widths):
                button = QPushButton(btn_text)
                button.setFixedSize(width, 22)
                button.setStyleSheet(Styles.BUTTON_STYLE_ARRAY)
                button.setEnabled(False)
                self.buttons[(feature, btn_text)] = button
                button.clicked.connect(lambda checked, t=btn_text, f=feature: self.on_button_click(f, t))
                row_layout.addWidget(button)
            sidebar_layout.addLayout(row_layout)
# MISC
        analytics_layout = QHBoxLayout()
        analytics_layout.setSpacing(2)
        analytics_label = QLabel("MISC:")
        analytics_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        analytics_label.setFixedHeight(22)
        analytics_layout.addWidget(analytics_label)
        
        dashboard_button = QPushButton("DASHBOARD")
        dashboard_button.setFixedSize(110, 22)
        dashboard_button.setStyleSheet(Styles.BUTTON_STYLE_ARRAY)
        dashboard_button.setEnabled(True) 
        dashboard_button.setToolTip("External Dashboard")
        
        launch_button = QPushButton("🗂 DOWNLOAD")
        launch_button.setFixedSize(120, 22)
        launch_button.setStyleSheet(Styles.BUTTON_STYLE_ARRAY)
        launch_button.setEnabled(True) 
        launch_button.setToolTip("Download Folder")
        launch_button.clicked.connect(lambda checked: self.on_button_click("MISC:", "DOWNLOADS"))
        analytics_layout.addWidget(launch_button)

        sidebar_layout.addLayout(analytics_layout)
# APP TREE
        self.app_tree = AppTreeWidget()
        sidebar_layout.addWidget(self.app_tree, stretch=1)
        # JS_EDIT 25.12.24. MOVED THESE CONNECTS THAT WERN'T BEING USED HERE AND ENABLED ONE. 
        self.sw_version_edit_box.textChanged.connect(self.update_button_states) #JS_EDIT 25.12.24. ENABLED THIS TO MAKE THE BUTTONS ACTIVE RIGHT AWAY WHEN SELECTING FROM DATABASE. 
        self.modality_edit_box.textChanged.connect(self.check_modality) #JS_EDIT 25.12.24. ADDED THIS TO PREVENT APP FROM FLASHING. 
        self.update_apptree()
# ------------------------------------------------------------------------        
    def update_apptree(self):
        modality = self.edit_boxes.get("Modality", QLineEdit()).text().strip().upper()
        logger.debug(f"[CRD UI] Updating AppTree with modality: {modality}")
        self.app_tree.load_apptree_data(modality)
# ------------------------------------------------------------------------  
    def check_for_updates(self):
        try:
            crd_update.check_for_updates(self)  
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Update Error:\n{str(e)}")
# ------------------------------------------------------------------------
    def create_button(self, text, callback):
        button = QPushButton(text)
        button.setFixedHeight(26)
        button.setStyleSheet(Styles.BUTTON_STYLE)
        button.clicked.connect(callback)
        return button   
# ------------------------------------------------------------------------      
    def browser_go_home(self):
        try:
            crd_dir = os.path.dirname(os.path.abspath(__file__))
            mr_path = os.path.normpath(os.path.join(crd_dir, "../html/mr.html"))

            if os.path.exists(mr_path):
                url = QUrl.fromLocalFile(mr_path)
            else:
                url = QUrl("about:blank")
                logger.warning("mr.html not found")

            self.local_browser.setUrl(url)
            self.address_bar.setText(url.toString())

        except Exception as e:
            logger.error(f"Failed to load home: {e}")
            self.local_browser.setHtml("<h2>Error loading mr.html</h2>")
# ------------------------------------------------------------------------  
    def browser_navigate(self):
        if hasattr(self, 'local_browser') and hasattr(self, 'address_bar'):
            text = self.address_bar.text().strip()
            if not text:
                return
            if not text.startswith(('http://', 'https://', 'file://')):
                text = 'http://' + text
            self.local_browser.setUrl(QUrl(text))
# ------------------------------------------------------------------------  
    def on_browser_url_changed(self, qurl: QUrl):
        self.address_bar.setText(qurl.toString(QUrl.RemovePassword | QUrl.RemoveUserInfo))   
# ------------------------------------------------------------------------    
    def update_versions_json():
        try:
            crd_dir = os.path.dirname(os.path.abspath(__file__))
            versions_path = os.path.normpath(os.path.join(crd_dir, "../config/versions.json"))
            if not os.path.exists(versions_path):
                with open(versions_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=4)
            
            with open(versions_path, 'r', encoding='utf-8') as f:
                versions = json.load(f)

            scripts_dir = crd_dir
            modules_dir = os.path.join(crd_dir, 'modules')
            
            scripts_files = [
                f for f in os.listdir(scripts_dir)
                if (f.endswith('.py') or f.endswith('.pyw')) and not os.path.isdir(os.path.join(scripts_dir, f))
            ]
            
            modules_files = [
                os.path.join('modules', f) for f in os.listdir(modules_dir)
                if (f.endswith('.py') or f.endswith('.pyw')) and not os.path.isdir(os.path.join(modules_dir, f))
            ] if os.path.exists(modules_dir) else []
            
            all_current_files = set(scripts_files + modules_files)
            
            updated = False
            current_date_str = datetime.date.today().strftime("%m/%d/%y")
            current_date = datetime.date.today()

            for file_key in list(versions.keys()):
                if file_key not in all_current_files:
                    del versions[file_key]
                    updated = True

            for file_key in all_current_files:
                if file_key.startswith('modules/'):
                    file_name = file_key.split('/')[-1]
                    full_path = os.path.join(modules_dir, file_name)
                else:
                    full_path = os.path.join(scripts_dir, file_key)
                
                if not os.path.exists(full_path):
                    continue  
                
                file_mtime = os.path.getmtime(full_path)
                file_mod_date = datetime.date.fromtimestamp(file_mtime)
                
                if file_key not in versions:
                    versions[file_key] = f"1.00 ({current_date_str})"
                    updated = True
                else:
                    v = versions[file_key]
                    parts = v.split(' (')
                    version_str = parts[0].strip()
                    updated_str = parts[1].rstrip(')').strip() if len(parts) > 1 else 'N/A'
                    
                    if updated_str == 'N/A':
                        version_num = float(version_str)
                        new_version_num = version_num + 0.01
                        new_version = "{:.2f}".format(new_version_num)
                        versions[file_key] = f"{new_version} ({current_date_str})"
                        updated = True
                    else:
                        try:
                            json_date = datetime.datetime.strptime(updated_str, "%m/%d/%y").date()
                            if file_mod_date > json_date:
                                version_num = float(version_str)
                                new_version_num = version_num + 0.01
                                new_version = "{:.2f}".format(new_version_num)
                                versions[file_key] = f"{new_version} ({current_date_str})"
                                updated = True
                        except ValueError:
                            version_num = float(version_str)
                            new_version_num = version_num + 0.01
                            new_version = "{:.2f}".format(new_version_num)
                            versions[file_key] = f"{new_version} ({current_date_str})"
                            updated = True
            
            if updated:
                versions = dict(sorted(versions.items()))
                with open(versions_path, 'w', encoding='utf-8') as f:
                    json.dump(versions, f, indent=4)
        except Exception as e:
            pass
# ------------------------------------------------------------------------
    def is_valid_ip(self, value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, value):
            try:
                octets = value.split('.')
                return all(0 <= int(octet) <= 255 for octet in octets)
            except ValueError:
                return False
        hostname_pattern = re.compile(
            r'^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(hostname_pattern.match(value))
# ------------------------------------------------------------------------
    def on_button_click(self, feature, button_text):
        if feature == "MISC:" and button_text == "DOWNLOADS":
            path = r"C:\CRD\downloads"
            os.startfile(path)
        else:
            if feature == "SP:":
                ip = self.sp_ip_edit_box.text().strip()
                sw_version = None
            elif feature == "SM:":
                ip = self.sm_ip_edit_box.text().strip()
                sw_version = self.sw_version_edit_box.text().strip()
            try:
                success = crd_matrix.handle_feature_button_click(
                    feature=feature,
                    button_text=button_text,
                    host_ip=ip,
                    parent=self,
                    sw_version=sw_version
                )
                if not success:
                    logger.warning(f"[CRD UI] Action Failed {feature} {button_text}")
                    msg_box = CustomMessageBox(
                        title="Error",
                        message=f"Action Failed {feature} {button_text}",
                        icon=QMessageBox.Critical,
                        parent=self
                    )
                    msg_box.center()
                    msg_box.exec_custom()  
            except Exception as e:
                logger.error(f"[CRD UI] {feature} {button_text}: {str(e)}")
                msg_box = CustomMessageBox(
                    title="Error",
                    message=f"Executing {feature} {button_text}: {str(e)}",
                    icon=QMessageBox.Critical,
                    parent=self
                )
                msg_box.center()  
                msg_box.exec_custom()  
# ------------------------------------------------------------------------
# CHANGED 7/13/26 (EW)
    def update_button_states(self):
        sp_ip = self.sp_ip_edit_box.text().strip()
        sm_ip = self.sm_ip_edit_box.text().strip()
        sw_version = self.edit_boxes["sw_version"].text().strip()
        modality = self.edit_boxes.get("Modality", QLineEdit()).text().upper()
        tunnel_type = ""
        if hasattr(self, 'tunnel_edit_box') and self.tunnel_edit_box:
            tunnel_type = self.tunnel_edit_box.text().strip().upper()
        sp_valid = self.is_valid_ip(sp_ip)
# SM EDGE-TINA
        is_edge_tina = tunnel_type == "EDGE-TINA"
        sm_valid = (self.is_valid_ip(sm_ip) 
                    and bool(sw_version) 
                    and not is_edge_tina)

        logger.debug(f"[CRD UI] sp_valid={sp_valid}, sm_valid={sm_valid} "
                    f"(EDGE-TINA={is_edge_tina} → SM disabled)")
        for (feature, btn_text), button in self.buttons.items():
            if (feature, btn_text) != ("MISC:", "FILES (S)"):
                button.setEnabled(False)
# SP BUTTONS
        if sp_valid:
            for btn_text in ["RDP", "SFTP", "TERM"]:
                button = self.buttons.get(("SP:", btn_text))
                if button:
                    button.setEnabled(True)
                    logger.debug(f"[CRD UI] Enabling SP: {btn_text}")

        if sm_valid:
            for btn_text in ["SFTP", "TERM"]:
                button = self.buttons.get(("SM:", btn_text))
                if button:
                    button.setEnabled(True)
                    logger.debug(f"[CRD UI] Enabling SM: {btn_text}")

        for misc_btn in ["FILES (S)", "DASHBOARD"]:
            button = self.buttons.get(("MISC:", misc_btn))
            if button:
                button.setEnabled(True)
                
        mapped_buttons = {
            "SP": "SP:",
            "SM": "SM:"
        }
        if modality in self.actions_matrix:
            for feature, buttons in self.actions_matrix[modality].items():
                mapped_feature = mapped_buttons.get(feature, feature)
                for btn_text, enabled in buttons.items():
                    if enabled:
                        key = (mapped_feature, btn_text)
                        if key in self.buttons:
                            if mapped_feature == "SM:" and is_edge_tina:
                                continue
                            self.buttons[key].setEnabled(True)
                            logger.debug(f"[CRD UI] Enabling {mapped_feature} {btn_text}")
# ------------------------------------------------------------------------
# NEED TO UPDATE LOGIC WITH CREDENTIALS
    def handle_feature_button_click(self, button_text, feature):
        logger.info(f"[CRD UI] Button {button_text} clicked for {feature}")
        if feature == "SP:":
            ip = self.sp_ip_edit_box.text().strip()
            sw_version = None  
        elif feature == "SM:":
            ip = self.sm_ip_edit_box.text().strip()
            sw_version = self.sw_version_edit_box.text().strip()
        else:
            logger.error(f"[CRD UI] Invalid Feature: {feature}")
            msg_box = CustomMessageBox()
            msg_box.critical(self, "Error", f"Invalid Feature: {feature}")
            return
        try:
            success = crd_matrix.handle_feature_button_click(
                feature=feature,
                button_text=button_text,
                host_ip=ip,
                parent=self,
                sw_version=sw_version
            )
            if not success:
                logger.warning(f"[CRD UI] Action Failed {feature} {button_text}")
                msg_box = CustomMessageBox()
                msg_box.critical(self, "Error", f"Action Failed {feature} {button_text}")
        except Exception as e:
            logger.error(f"[CRD UI] Executing {feature} {button_text}: {str(e)}")
# ------------------------------------------------------------------------           
    def closeEvent(self, event):
        event.accept() 
        QApplication.quit()
        os._exit(0)   
# ------------------------------------------------------------------------                           
# USING HASATTR TO AVOID POTENTIAL ERRORS
    def populate_sid_database(self, data):
        logger.info(f"[CRD UI] Populating SID Database: {data}")
        if self.edit_boxes["MachineName"] and isinstance(self.edit_boxes["MachineName"], QLineEdit):
            self.edit_boxes["MachineName"].setText(data.get("MachineName", ""))
        if self.edit_boxes["Modality"] and isinstance(self.edit_boxes["Modality"], QLineEdit):
            self.edit_boxes["Modality"].setText(data.get("Modality", ""))    
        if self.edit_boxes["sw_version"] and isinstance(self.edit_boxes["sw_version"], QLineEdit):
            self.edit_boxes["sw_version"].setText(data.get("sw_version", ""))
        if self.edit_boxes["machine"] and isinstance(self.edit_boxes["machine"], QLineEdit):
            self.edit_boxes["machine"].setText(data.get("MachineName", ""))
        if hasattr(self, "sp_ip_edit_box") and isinstance(self.sp_ip_edit_box, QLineEdit):
            self.sp_ip_edit_box.setText(data.get("sp_ip", ""))
        if hasattr(self, "sm_ip_edit_box") and isinstance(self.sm_ip_edit_box, QLineEdit):
            self.sm_ip_edit_box.setText(data.get("host_ip", ""))
        if hasattr(self, "display_ip_edit_box") and isinstance(self.display_ip_edit_box, QLineEdit):
            self.display_ip_edit_box.setText(data.get("display_ip", ""))
            self.display_ip_edit_box.setEnabled(False)
        if hasattr(self, "tunnel_edit_box") and isinstance(self.tunnel_edit_box, QLineEdit):
            self.tunnel_edit_box.setText(data.get("TunnelType", ""))
        if hasattr(self, "dynamic_header") and isinstance(self.dynamic_header, QLabel):
            self.dynamic_header.setText(data.get("HospName", ""))
        self.sp_ip = data.get("sp_ip", "")
        self.tams_ip = data.get("host_ip", "")
        self.sid_database_populated = True
        self.update_button_states()
        logger.info("[CRD UI] SID Database Populated")
        return True
# ------------------------------------------------------------------------
    def load_actions_matrix(self):
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        actions_file = os.path.join(config_dir, "active.json")
        try:
            with open(actions_file, "r") as f:
                self.actions_matrix = json.load(f)
        except json.JSONDecodeError:
            self.actions_matrix = {}
            logger.error("[CRD UI] Failed To Parse Actions Matrix JSON")
# ------------------------------------------------------------------------
    def add_to_sid_database(self):
        data = {
            "sid": self.edit_box_sid.text().strip() if self.edit_box_sid else "",
            "site_name": self.dynamic_header.text().strip() if self.dynamic_header else "",
            "sp_ip": [self.sp_ip_edit_box.text().strip()] if self.sp_ip_edit_box and self.sp_ip_edit_box.text().strip() else [],
            "host_ip": [self.sm_ip_edit_box.text().strip()] if self.sm_ip_edit_box and self.sm_ip_edit_box.text().strip() else [],
            "display_ip": [self.display_ip_edit_box.text().strip()] if self.display_ip_edit_box and self.display_ip_edit_box.text().strip() else [],
            "tunnel": [self.tunnel_edit_box.text().strip()] if self.tunnel_edit_box and self.tunnel_edit_box.text().strip() else [],
            "modality": [self.edit_boxes["Modality"].text().strip()] if self.edit_boxes.get("Modality") and self.edit_boxes["Modality"].text().strip() else [],
            "machine": self.edit_boxes["machine"].text().strip() if self.edit_boxes.get("machine") and self.edit_boxes["machine"] else "",
            "sw_version": self.edit_boxes["sw_version"].text().strip() if self.edit_boxes.get("sw_version") and self.edit_boxes["sw_version"] else "",
            "note": []
        }
# VERIFY SID
        if not data["sid"]:
            msg_box = CustomMessageBox("Error", "SID is Required", QMessageBox.Icon.Critical, self)
            msg_box.setStyleSheet(Styles.MESSAGE_BOX)
            msg_box.center()
            msg_box.exec_custom()
            return
        try:
            siddb_path = os.path.join(os.getcwd(), '..', 'data', 'siddb.json')
            try:
                with open(siddb_path, 'r') as f:
                    siddb = json.load(f)
            except FileNotFoundError:
                siddb = {'index': []}

            if 'index' not in siddb or not isinstance(siddb['index'], list):
                siddb['index'] = []
            sid_exists = False
            for i, entry in enumerate(siddb['index']):
                if entry.get('sid') == data['sid']:
                    sid_exists = True
                    siddb['index'][i] = data
                    break
            if not sid_exists:
                siddb['index'].append(data)

            with open(siddb_path, 'w') as f:
                json.dump(siddb, f, indent=4)
# USER VALIDATION ON SID
            msg_box = CustomMessageBox(
                "Success",
                f"SID {'updated' if sid_exists else 'added'} successfully",
                QMessageBox.Icon.Information,
                self
            )
            msg_box.center()
            msg_box.exec_custom()
        except Exception as e:
            msg_box = CustomMessageBox(
                "Error",
                f"Failed To Process SID Database: {e}",
                QMessageBox.Icon.Critical,
                self
            )
            msg_box.center()
            msg_box.exec_custom()
# ------------------------------------------------------------------------
    def update_tunnel_monitor_ip(self, text):
        self.tunnel_monitor.sp_ip = text
        logger.info(f"[CRD UI] TunnelMonitorWorker IP updated to: {text}")    
# ------------------------------------------------------------------------
    def reset_state(self):
        self.sid_database_populated = False
        if self.sp_ip_edit_box:
            self.sp_ip_edit_box.setText("")
        if self.sm_ip_edit_box:
            self.sm_ip_edit_box.setText("")
        if self.display_ip_edit_box:
            self.display_ip_edit_box.setText("")
        if self.tunnel_edit_box:
            self.tunnel_edit_box.setText("")
        if self.edit_box_sid:
            self.edit_box_sid.setText("")
        if self.edit_boxes.get("Modality"):
            self.edit_boxes["Modality"].setText("")
        if self.edit_boxes.get("machine"):
            self.edit_boxes["machine"].setText("")
        if self.edit_boxes.get("sw_version"):
            self.edit_boxes["sw_version"].setText("")
        if self.dynamic_header:
            self.dynamic_header.setText("")
        logger.info("[CRD UI] Application state reset")
# ------------------------------------------------------------------------        
    def init_tabs(self):
        logger.info("[CRD UI] Initializing tabs")
        while self.tab_widget.count():
            self.tab_widget.removeTab(0)
# DATABASE
        dialog_tab = QWidget()
        self.local_tab_index = self.tab_widget.addTab(dialog_tab, " DATABASE ")
        dialog_tab.setEnabled(True)
        dialog_tab.setVisible(True)
        layout = QVBoxLayout(dialog_tab)
        dialog_tab.setLayout(layout)
        try:
            if not hasattr(self, 'sid_data_manager'):
                raise AttributeError("sid_data_manager not initialized")

            self.sid_manager_window = SIDDatabaseWindow(
                sid_manager=self.sid_data_manager,
                main_app=self,
                tab_widget=self.tab_widget
            )
            if self.sid_manager_window is None:
                raise Exception("Failed to Create SIDDatabaseWindow")

            self.sid_manager_window.close_requested.connect(lambda data=None: self.on_sid_selected(data))
            self.sid_manager_window.close_requested.connect(self.cleanup_sid_manager)
            layout.addWidget(self.sid_manager_window)
        except Exception as e:
            logger.error(f"[CRD UI] Failed To Initialize SID Database: {str(e)}")
            msg_box = CustomMessageBox(
                title="Error",
                message=f"Failed To Initialize SID Database: {str(e)}",
                icon=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
# CONFIG TAB
        config_tab = QWidget()
        config_tab_index = self.tab_widget.addTab(config_tab, " CONFIG ")
        config_tab.setEnabled(True)
        config_tab.setVisible(True)
        config_layout = QVBoxLayout(config_tab)
        config_layout.setContentsMargins(10, 10, 10, 10)
        config_layout.setSpacing(5)

        try:
            self.config_ui_widget = ConfigUI(parent=config_tab)
            if self.config_ui_widget is None:
                raise Exception("ConfigUI Instance is None")

            self.config_ui_widget.close_requested.connect(self.cleanup_config_ui)
            self.config_ui_widget.close_requested.connect(self.return_to_db_tab)
            self.config_ui_widget.config_updated.connect(self.on_config_updated)
            config_layout.addWidget(self.config_ui_widget)
            config_layout.addStretch()
            logger.info("[CRD UI] ConfigUI Successfully Initialized in CONFIG tab")
        except Exception as e:
            logger.error(f"[CRD UI] Failed to Initialize ConfigUI: {type(e).__name__}: {e}")
            error_label = QLabel(f"Error Loading CONFIG: {str(e)}")
            error_label.setStyleSheet("color: red; font-size: 12px; font-weight: bold;")
            config_layout.addWidget(error_label)
            config_layout.addStretch()

# VPN/URL
        browser_tab = QWidget()
        self.browser_tab_index = self.tab_widget.addTab(browser_tab, " VPN/URL ")
        browser_tab.setEnabled(True)
        browser_tab.setVisible(True)
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        self.browser_sub_tabs = QTabWidget()
        self.browser_sub_tabs.setStyleSheet("QTabWidget::pane { border: 0; }")

        for sub_name in [" VPN ", " LOCAL "]:
            sub_tab = QWidget()
            sub_tab.setStyleSheet("background-color: #202020;")
            sub_layout = QVBoxLayout(sub_tab)
            sub_layout.setContentsMargins(0, 0, 0, 0)
            sub_layout.setSpacing(0)

            if sub_name.strip() == "VPN":
                self.vpn_webview = QWebEngineView()
                self.vpn_webview.setStyleSheet(Styles.WEB_VIEW_WIDGET)
                sub_layout.addWidget(self.vpn_webview)
                sub_tab.browser_view = self.vpn_webview

                custom_page = CustomWebEnginePage(self.vpn_webview)
                self.vpn_webview.setPage(custom_page)
                self.vpn_webview.loadFinished.connect(self.on_vpn_page_loaded)
                self.vpn_webview.urlChanged.connect(self.on_vpn_url_changed)
                self.vpn_webview.loadStarted.connect(lambda: logger.info("[CRD UI] VPN Page load started"))
                self.vpn_webview.loadProgress.connect(lambda p: logger.debug(f"[CRD UI] VPN Page load progress: {p}%"))
            else:
                header_widget = QWidget()
                header_widget.setFixedHeight(50)
                header_widget.setStyleSheet("background-color: #202020; border-bottom: 1px solid #444444;")

                header_layout = QHBoxLayout(header_widget)
                header_layout.setContentsMargins(8, 6, 8, 6)
                header_layout.setSpacing(8)

                self.btn_back = QPushButton()
                self.btn_back.setFixedSize(36, 36)
                self.btn_back.setIcon(QIcon(icon_path("back.png")))
                self.btn_back.setIconSize(QSize(24, 24))
                self.btn_back.setToolTip("Back")
                self.btn_back.setStyleSheet(Styles.BUTTON_STYLE)
                self.btn_back.clicked.connect(lambda: self.local_browser.back() if hasattr(self, 'local_browser') else None)

                self.btn_forward = QPushButton()
                self.btn_forward.setFixedSize(36, 36)
                self.btn_forward.setIcon(QIcon(icon_path("forward.png")))
                self.btn_forward.setIconSize(QSize(24, 24))
                self.btn_forward.setToolTip("Forward")
                self.btn_forward.setStyleSheet(Styles.BUTTON_STYLE)
                self.btn_forward.clicked.connect(lambda: self.local_browser.forward() if hasattr(self, 'local_browser') else None)

                self.btn_home = QPushButton()
                self.btn_home.setFixedSize(36, 36)
                self.btn_home.setIcon(QIcon(icon_path("home.png")))
                self.btn_home.setIconSize(QSize(24, 24))
                self.btn_home.setToolTip("Home")
                self.btn_home.setStyleSheet(Styles.BUTTON_STYLE)
                self.btn_home.clicked.connect(self.browser_go_home)

                self.btn_refresh = QPushButton()
                self.btn_refresh.setFixedSize(36, 36)
                self.btn_refresh.setIcon(QIcon(icon_path("refresh.png")))
                self.btn_refresh.setIconSize(QSize(24, 24))
                self.btn_refresh.setToolTip("Refresh")
                self.btn_refresh.setStyleSheet(Styles.BUTTON_STYLE)
                self.btn_refresh.clicked.connect(lambda: self.local_browser.reload() if hasattr(self, 'local_browser') else None)

                header_layout.addWidget(self.btn_back)
                header_layout.addWidget(self.btn_forward)
                header_layout.addWidget(self.btn_home)
                header_layout.addWidget(self.btn_refresh)

                self.address_bar = QLineEdit()
                self.address_bar.setStyleSheet(Styles.LINE_EDIT_STYLE if hasattr(Styles, "LINE_EDIT_STYLE") else "")
                self.address_bar.returnPressed.connect(self.browser_navigate)
                header_layout.addWidget(self.address_bar, stretch=1)

                self.links_combo = QComboBox()
                self.links_combo.setFixedWidth(220)
                self.links_combo.setStyleSheet(Styles.COMBO_BOX)
                self.links_combo.currentIndexChanged.connect(self.on_links_combo_changed)
                header_layout.addWidget(self.links_combo)

                sub_layout.addWidget(header_widget)

                self.local_browser = QWebEngineView()
                self.local_browser.setStyleSheet(Styles.WEB_VIEW_WIDGET)
                sub_layout.addWidget(self.local_browser)
                sub_tab.browser_view = self.local_browser

                settings = self.local_browser.settings()
                settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
                settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
                settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

            self.browser_sub_tabs.addTab(sub_tab, sub_name)

        browser_layout.addWidget(self.browser_sub_tabs)
        self.browser_sub_tabs.setCurrentIndex(0)

        self.reload_vpn_credentials()
        if hasattr(self, 'vpn_webview'):
            def load_vpn():
                logger.info("[CRD UI] Loading VPN login page")
                self.vpn_webview.setUrl(QUrl("https://172.17.1.3/"))  
            QTimer.singleShot(800, load_vpn)

        if hasattr(self, 'local_browser'):
            self.local_browser.setUrl(QUrl.fromLocalFile(
                os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "html", "mr.html"))         ))
        self.load_html_links()
        self.browser_go_home()
# LOG
        log_tab = QWidget()
        log_tab_index = self.tab_widget.addTab(log_tab, " LOG ")
        log_tab.setEnabled(True)
        log_tab.setVisible(True)

        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(5)

        top_layout = QHBoxLayout()

        self.archive_button = QPushButton(" ARCHIVE")
        icon_file = icon_path("download.png")
        self.archive_button.setIcon(QIcon(icon_file))
        self.archive_button.setIconSize(QSize(24, 24))
        self.archive_button.setFixedSize(120, 30)
        self.archive_button.setStyleSheet(Styles.BUTTON_STYLE)
        self.archive_button.clicked.connect(self.on_archive_clicked)
        top_layout.addWidget(self.archive_button)
        top_layout.addStretch()
# REFRESH
        self.refresh_button = QPushButton(" REFRESH")
        icon_file = icon_path("refresh.png")
        self.refresh_button.setIcon(QIcon(icon_file))
        self.refresh_button.setIconSize(QSize(24, 24))
        self.refresh_button.setFixedSize(120, 30)
        self.refresh_button.setStyleSheet(Styles.BUTTON_STYLE)
        top_layout.addWidget(self.refresh_button)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet(Styles.TEXT_EDIT_STYLE)
        self.log_viewer.setFont(QFont("Consolas", 11))
        self.log_viewer.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        log_layout.addLayout(top_layout)
        log_layout.addWidget(self.log_viewer)

        def refresh_log():
            try:
                log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
                if not os.path.exists(log_dir):
                    self.log_viewer.setPlainText("Log Directory Not Found")
                    return

                log_files = glob.glob(os.path.join(log_dir, "CRD*.log"))
                if not log_files:
                    self.log_viewer.setPlainText("No log files found")
                    return

                latest_log = max(log_files, key=os.path.getmtime)
                with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
                    log_content = f.read()

                self.log_viewer.setPlainText(log_content)
                cursor = self.log_viewer.textCursor()
                cursor.movePosition(cursor.End)
                self.log_viewer.setTextCursor(cursor)
                self.log_viewer.ensureCursorVisible()
            except Exception as e:
                self.log_viewer.setPlainText(f"Error loading log: {e}")

        self.refresh_button.clicked.connect(refresh_log)
        self.refresh_log_func = refresh_log
        refresh_log()
# HELP/VER
        help_tab = QWidget()
        help_tab_index = self.tab_widget.addTab(help_tab, " VER ")
        help_tab.setEnabled(True)
        help_tab.setVisible(True)
        help_layout = QVBoxLayout(help_tab)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_layout.setSpacing(0)

        about_viewer = QTextEdit()
        about_viewer.setReadOnly(True)
        about_viewer.setStyleSheet(Styles.TEXT_EDIT_STYLE)
        about_viewer.setFont(QFont("Consolas", 12))
        about_viewer.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        VersionManager.load_versions(about_viewer)
        about_viewer.verticalScrollBar().setValue(0)
        cursor = about_viewer.textCursor()
        cursor.movePosition(QTextCursor.Start)
        about_viewer.setTextCursor(cursor)

        about_layout = QVBoxLayout()
        about_layout.setContentsMargins(8, 8, 8, 8)
        about_layout.setSpacing(10)
        about_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        about_layout.addWidget(about_viewer)

        self.update_btn = QPushButton("CHECK FOR UPDATES")
        icon_file = icon_path("check.png")
        self.update_btn.setIcon(QIcon(icon_file))
        self.update_btn.setIconSize(QSize(24, 24))
        self.update_btn.setFixedWidth(200)
        self.update_btn.setFixedHeight(30)
        self.update_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.update_btn.setStyleSheet(Styles.BUTTON_STYLE)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.update_btn)
        button_layout.addStretch()
        about_layout.addLayout(button_layout)
        about_layout.addSpacing(5)

        help_layout.addLayout(about_layout)
        self.update_btn.clicked.connect(lambda: crd_update.check_for_remote_updates(self))

        self.tab_widget.setTabEnabled(self.local_tab_index, True)
        self.tab_widget.setTabEnabled(config_tab_index, True)
        self.tab_widget.setTabEnabled(log_tab_index, True)
        self.tab_widget.setTabEnabled(help_tab_index, True)
        self.tab_widget.setTabEnabled(self.browser_tab_index, True)
        self.tab_widget.currentChanged.connect(self.on_main_tab_changed)
# ------------------------------------------------------------------------          
    def on_main_tab_changed(self, index):
        pass  
# ------------------------------------------------------------------------         
    def handle_sub_tab_changed(self, index):
        if index == 0 and (not hasattr(self, 'config_ui_widget') or self.config_ui_widget is None):
            sub_tab = self.remote_sub_tabs.widget(index)
            sub_tab_layout = sub_tab.layout()
            while sub_tab_layout.count():
                item = sub_tab_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            try:
                self.config_ui_widget = ConfigUI(parent=sub_tab)
                if self.config_ui_widget is None:
                    raise Exception("Failed To Create ConfigUI Instance")
                self.config_ui_widget.close_requested.connect(self.cleanup_config_ui)
                self.config_ui_widget.close_requested.connect(self.return_to_db_tab)
                self.config_ui_widget.config_updated.connect(self.on_config_updated)
                sub_tab_layout.addWidget(self.config_ui_widget)
                sub_tab_layout.addStretch()
            except Exception as e:
                msg_box = CustomMessageBox("Error", f"Failed To Reinitialize Config: {str(e)}", QMessageBox.Icon.Critical, self)
                msg_box.center()
                msg_box.exec_custom()
# ------------------------------------------------------------------------        
    def on_archive_clicked(self):
        self.archive_log()
# ------------------------------------------------------------------------        
    def archive_log(self):
        log_dir = r"C:\CRD\logs"
        archive_dir = os.path.join(log_dir, "archive")
        try:
            os.makedirs(archive_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            zip_path = os.path.join(archive_dir, f"log_archive_{timestamp}.zip")
            log_files = glob.glob(os.path.join(log_dir, "*.log"))
            if not log_files:
                return
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in log_files:
                    zf.write(f, arcname=os.path.basename(f))

            msg = f"\n[ARCHIVED] {len(log_files)} File(s) → {os.path.basename(zip_path)}"
            self.log_viewer.append(msg)
            self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())
            QMessageBox.information(
                self,
                "Archive Complete",
                f"Logs Archived to \n{zip_path}"
            )
        except Exception as e:
            logger.error(f"[CRD UI] Archive failed: {e}")
            QMessageBox.critical(self, "Archive Error", f"Failed to Archive Logs:\n{e}") 
# ------------------------------------------------------------------------
    def handle_help_link_click(self, url: QUrl):
        try:
            scheme = url.scheme().lower()
            if scheme == "mailto":
                webbrowser.open(url.toString())
                if self.help_text_browser:
                    QTimer.singleShot(50, self.restore_help_content)
                return  
            elif scheme in ("http", "https"):
                webbrowser.open(url.toString())
                if self.help_text_browser:
                    QTimer.singleShot(50, self.restore_help_content)
                return
            else:
                pass
        except Exception as e:
            traceback.print_exc()
# ------------------------------------------------------------------------
    def open_editor(self):
        dialog = EditorDialog(self)
        dialog.exec_()
# ------------------------------------------------------------------------
    def restore_help_content(self):
        try:
            if self.help_text_browser and self.help_html_content:
                self.help_text_browser.setHtml(self.help_html_content)
        except Exception as e:
            traceback.print_exc()
# ------------------------------------------------------------------------
# NOT CURRENTLY IMPLIMENTED USING ONLY SUB TAB
    def init_help_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet(Styles.LINE_EDIT_STYLE)
        layout.addWidget(help_text)
        help_button = QPushButton("VIEW HELP")
        help_button.setStyleSheet(Styles.BUTTON_STYLE)
        help_file_path = os.path.join(os.path.dirname(__file__), "..", "html", "toolbox_help.html")   
        help_button.clicked.connect(lambda: webbrowser.open(f"file://{os.path.abspath(help_file_path)}"))  
        layout.addWidget(help_button)
        layout.addStretch()
# ------------------------------------------------------------------------
# INIT VPN WITH FROM THIS URL USING WEBVIEW
    def init_vpn_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.vpn_webview = QWebEngineView()
        self.vpn_webview.setStyleSheet("background-color: #202020; border: none;")
        custom_page = CustomWebEnginePage(self.vpn_webview)
        self.vpn_webview.setPage(custom_page)
        url = QUrl("https://172.17.1.3/")
        self.vpn_webview.setUrl(url)
        layout.addWidget(self.vpn_webview)
        self.vpn_webview.loadFinished.connect(self.on_vpn_page_loaded)
        self.vpn_webview.urlChanged.connect(self.on_vpn_url_changed)
        self.vpn_webview.page().setDevToolsPage(self.vpn_webview.page())
        self.vpn_webview.loadStarted.connect(lambda: logger.info("[CRD UI] VPN Page load started"))
        self.vpn_webview.loadProgress.connect(lambda p: logger.debug(f"[CRD UI] VPN Page load progress: {p}%"))
# ------------------------------------------------------------------------
    def reload_vpn_credentials(self):
        try:
            cred_path = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "config", "vpn.creds"
            ))
            
            if not os.path.exists(cred_path):
                logger.warning("[CRD UI] vpn.creds file not found")
                self.auto_login_enabled = False
                return False

            with open(cred_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.vpn_username = data.get("username")
            self.vpn_password = data.get("password")
            self.vpn_key = data.get("key", "")
            self.auto_login_enabled = True
            
            logger.info(f"[CRD UI] VPN credentials loaded (username: {self.vpn_username})")
            return True
        except Exception as e:
            logger.error(f"[CRD UI] Failed to load VPN credentials: {e}")
            self.auto_login_enabled = False
            return False
# ------------------------------------------------------------------------
    def cleanup_config_ui(self):
        if hasattr(self, 'config_ui_widget') and self.config_ui_widget:
            self.config_ui_widget.deleteLater()
            self.config_ui_widget = None
# ------------------------------------------------------------------------
    def on_config_updated(self):
        self.load_config()
        if self.auto_login_enabled and self.vpn_username and self.vpn_password:
            self.reload_vpn_page()
# ------------------------------------------------------------------------
    def hide_local_tab(self):
        logger.info("[CRD UI] Hiding LOCAL tab")
# ------------------------------------------------------------------------
    def open_sid_database(self):
        logger.info("[CRD UI] Accessing SID Database")
        try:
            self.tab_widget.setCurrentIndex(self.local_tab_index)
            if hasattr(self, 'sid_manager_window'):
                try:
                    self.sid_manager_window.close_requested.disconnect()
                    self.sid_manager_window.deleteLater()
                except:
                    pass
            
            self.sid_manager_window = SIDDatabaseWindow(
                sid_manager=self.sid_data_manager,
                main_app=self,
                tab_widget=self.tab_widget
            )
            if self.sid_manager_window is None:
                raise Exception("Failed to create SIDDatabaseWindow")
            self.sid_manager_window.close_requested.connect(self.hide_local_tab)
            self.sid_manager_window.close_requested.connect(lambda data=None: self.on_sid_selected(data))
            self.sid_manager_window.close_requested.connect(self.return_to_db_tab)
            self.sid_manager_window.close_requested.connect(self.cleanup_sid_manager)
            dialog_tab = self.tab_widget.widget(self.local_tab_index)
            layout = dialog_tab.layout()
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            layout.addWidget(self.sid_manager_window)
        except Exception as e:
            logger.error(f"[CRD UI] Failed to Access SID Database: {str(e)}")
            msg_box = CustomMessageBox(
                title="Error",
                message=f"Failed to Access SID Database: {str(e)}",
                icon=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
# ------------------------------------------------------------------------
    def on_sid_selected(self, data):
        if data:
            self.populate_sid_database(data)
# ------------------------------------------------------------------------
    def cleanup_sid_manager(self):
        if hasattr(self, 'sid_manager_window'):
            try:
                self.sid_manager_window.close_requested.disconnect()
                self.sid_manager_window.deleteLater()
                del self.sid_manager_window
            except:
                pass
# ------------------------------------------------------------------------
    def return_to_db_tab(self):
        logger.info("[CRD UI] DATABASE SET")
# ------------------------------------------------------------------------
    def handle_button_click(self): 
        try:
            self.query_ip_addresses() 
        except Exception as e:
            pass
# ------------------------------------------------------------------------
    def test_is_tunnel_open(self, ip, port):
        try:
            port = self.edit_boxes.get("port", QLineEdit()).text().strip() or port
        except (AttributeError, KeyError):
            port = port
        logger.info(f"[CRD UI] Testing Tunnel: {ip}:{port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, int(port)))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"[CRD UI] Tunnel Test Failed: {e}")
            return False
# ------------------------------------------------------------------------
    def end_connection(self):
        logger.info("[CRD UI] Ending VPN Connection")
# ------------------------------------------------------------------------
# VPN DISCONNECT
# ------------------------------------------------------------------------
    def load_config(self):
        config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
        settings_path = os.path.join(config_dir, 'settings.json')
        key_path = os.path.join(config_dir, 'user.key')
        enc_path = os.path.join(config_dir, 'user.enc')
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                self.auto_login_enabled = settings.get('settings', {}).get('vpnauto', False)
        except Exception as e:
            logger.error(f"[CRD UI] Settings: {type(e).__name__}: {e}")
            self.auto_login_enabled = False

        self.vpn_username = ''
        self.vpn_password = ''
        self.vpn_key = None
        self.creds_dict = None
        if not os.path.exists(key_path) or not os.path.exists(enc_path):
            try:
                config = update_config({}, key_path, enc_path)
                self.vpn_key = load_key(key_path)
                self.creds_dict = config
                credentials = config.get('USER', {}).get('credentials', {})
                self.vpn_username = credentials.get('host_user', '')
                self.vpn_password = credentials.get('host_pass', '')
            except Exception as e:
                self.vpn_key = None
                self.creds_dict = {}
                logger.error(f"[CRD UI] Credentials: {type(e).__name__}: {e}")
        else:
            try:
                self.vpn_key = load_key(key_path)
                self.creds_dict = decrypt_json(enc_path, self.vpn_key)
                credentials = self.creds_dict.get('USER', {}).get('credentials', {})
                self.vpn_username = credentials.get('host_user', '')
                self.vpn_password = credentials.get('host_pass', '')
            except InvalidToken:
                logger.error("[CRD UI] Decryption Failed")
                self.vpn_key = None
                self.creds_dict = {}
            except Exception as e:
                logger.error(f"[CRD UI] Credentials: {type(e).__name__}: {e}")
                self.creds_dict = {}
# ------------------------------------------------------------------------        
    def refresh_vpn_page(self):
        if self.connect_led.color == QColor("gray"):
            logger.info("[CRD UI] Refreshing VPN Page Due to Disconnected Status")
            if hasattr(self, 'vpn_webview') and isinstance(self.vpn_webview, QWebEngineView):
                self.vpn_webview.reload() 
            else:
                logger.warning("[CRD UI] No VPN Webview Found to Refresh")
                self.tunnel_monitor.stop()  
                self.tunnel_monitor = TunnelMonitorWorker(sp_ip="172.17.1.3")  
                self.tunnel_monitor.status_signal.connect(self.update_vpn_status)
                self.tunnel_monitor.start_monitoring() 
        else:
            logger.info("[CRD UI] VPN is Connected")
# ------------------------------------------------------------------------
    def get_html_url(self, html_file):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'html', html_file)
        html_path = os.path.abspath(html_path)
        if os.path.exists(html_path):
            return QUrl.fromLocalFile(html_path)
        logger.error(f"[CRD UI] HTML File Not Found: {html_path}")
        return None
# ------------------------------------------------------------------------
    def load_html_links(self):
        if not hasattr(self, 'links_combo'):
            logger.warning("[CRD UI] links_combo not initialized")
            return

        self.links_combo.clear()

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(base_dir, ".."))
            json_path = os.path.join(project_root, "config", "html.json")

            logger.info(f"[CRD UI] Loading links from: {json_path}")

            if not os.path.exists(json_path):
                logger.warning(f"[CRD UI] html.json not found")
                self.links_combo.addItem("html.json not found", None)
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            links = data.get("links", []) if isinstance(data, dict) else data

            count = 0
            for item in links:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("text")
                    url_str = item.get("url")
                    if name and url_str:
                        if url_str.startswith(("..", "html/", "reports/")) or not url_str.startswith("http"):
                            abs_path = os.path.abspath(os.path.join(project_root, url_str.lstrip("./\\")))
                            url = QUrl.fromLocalFile(abs_path)
                        else:
                            url = QUrl(url_str)
                        self.links_combo.addItem(name, url)
                        count += 1
                        logger.info(f"[CRD UI] Added: {name}")
            logger.info(f"[CRD UI] Successfully loaded {count} links")

            if count > 0:
                self.links_combo.setCurrentIndex(0)

        except Exception as e:
            logger.error(f"[CRD UI] Failed to load html.json: {e}")
            self.links_combo.addItem("Error loading links", None)
# ------------------------------------------------------------------------
# APP EXE
    def check_modality(self):
        if not self.edit_boxes.get("Modality") or not isinstance(self.edit_boxes["Modality"], QLineEdit):
            return
        modality = self.edit_boxes["Modality"].text().strip().upper()
        self.update_web_view_modality(modality)
# ------------------------------------------------------------------------
    def update_web_view_modality(self, modality):
        if not hasattr(self, 'web_view') or not self.web_view:
            return
        if modality == "MR":
            html_file = "mr.html"
        html_url = self.get_html_url(html_file)
        if not html_url:
            html_url = self.get_html_url("index.html")
        if html_url and self.web_view.url().toString() != html_url.toString():
            self.web_view.setUrl(html_url)
# ------------------------------------------------------------------------
# JS_EDIT 25.12.24, NO LONGER USING THIS POLLING. DOING THIS INSTEAD self.modality_edit_box.textChanged.connect(self.check_modality)
    def start_modality_polling(self):
        self.modality_timer = QTimer(self)
        self.modality_timer.timeout.connect(self.check_modality)
        self.modality_timer.start(1000)
        logger.info("[CRD UI] Started Polling")
# ------------------------------------------------------------------------
    def handle_certificate_error(self, error):
        error.acceptCertificate()
        return True
# ------------------------------------------------------------------------    
    def on_links_combo_changed(self, index):
        if index < 0 or not hasattr(self, 'local_browser'):
            return

        url = self.links_combo.itemData(index)
        if isinstance(url, QUrl) and url.isValid():
            self.local_browser.setUrl(url)
            if hasattr(self, 'address_bar'):
                self.address_bar.setText(url.toString())
# ------------------------------------------------------------------------
    def write_connect_dat(self, creds_dict):
        try:
            config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
            connect_dat = os.path.join(config_dir, 'connect.dat')
            os.makedirs(config_dir, exist_ok=True)
            with open(connect_dat, 'w') as f:
                spuser = creds_dict.get("SP_WIN10", {}).get("credentials", {}).get("host_user", "IV_Service_User")
                sppass = creds_dict.get("SP_WIN10", {}).get("credentials", {}).get("host_pass", "SU_InnerVision2020")
                f.write(f"spuser={spuser}\n")
                f.write(f"sppass={sppass}\n")
        except Exception as e:
            logger.error(f"[CRD UI] Failed To Write connect.dat: {type(e).__name__}: {e}")
            raise
# ------------------------------------------------------------------------
    def query_ip_addresses(self):
        sid = self.edit_box_sid.text().strip() if self.edit_box_sid else ""
        if not sid:
            msg_box = CustomMessageBox("Warning", "Please Enter a Valid SID", QMessageBox.Icon.Warning, self)
            msg_box.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
            msg_box.center()
            msg_box.exec_custom()
            return False
        try:
            if self.creds_dict:
                self.write_connect_dat(self.creds_dict)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'crd_connectvpn.py')
            if not os.path.exists(script_path):
                raise OSError(f"Script File Does Not Exist: {script_path}")
            env = os.environ.copy()
            if self.creds_dict and "SP_WIN10" in self.creds_dict:
                env['SPUSER'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_user", "IV_Service_User")
                env['SPPASS'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_pass", "SU_InnerVision2020")
                env['PORT'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_port", "22") or "22"
            result = subprocess.run(
                [sys.executable, script_path, sid],
                capture_output=True,
                text=True,
                check=True,
                cwd=script_dir,
                timeout=180,
                env=env
            )
            json_data = result.stdout.strip()
            data = json.loads(json_data)
# UPDATE EDIT BOXES
            self.populate_sid_database(data)
            if not self.sp_ip_edit_box:
                raise AttributeError("sp_ip_edit_box is Not Initialized")
            self.sp_ip_edit_box.setText(data.get("sp_ip", ""))

            if not self.sm_ip_edit_box:
                raise AttributeError("sm_ip_edit_box is Not Initialized")
            self.sm_ip_edit_box.setText(data.get("host_ip", ""))

            if not self.display_ip_edit_box:
                raise AttributeError("display_ip_edit_box is Not Initialized")
            self.display_ip_edit_box.setText(data.get("display_ip", ""))
            
            if not self.tunnel_edit_box:
                raise AttributeError("tunnel_edit_box is Not Initialized")
            self.tunnel_edit_box.setText(data.get("TunnelType", ""))
            
            if not self.edit_boxes.get("Modality"): #JS_EDIT 25.12.24. ADDED THIS WARNING FOR MODALITY.
                logger.warning("[CRD UI] edit_boxes['Modality'] is Not initialized")
            else:
                modality = data.get("Modality", "")
                self.edit_boxes["Modality"].setText(modality)    
            if not self.edit_boxes.get("sw_version"):
                raise AttributeError("edit_boxes['sw_version'] is Not Initialized")
            sw_version = data.get("sw_version", "")
            self.edit_boxes["sw_version"].setText(sw_version)

            if not self.edit_boxes.get("machine"):
                logger.warning("[CRD UI] edit_boxes['machine'] is Not Initialized")
            else:
                machine_name = data.get("machine", "")
                self.edit_boxes["machine"].setText(machine_name)

            if not self.dynamic_header:
                raise AttributeError("dynamic_header is Not Initialized")
            hosp_name = data.get("HospName", "")
            if hosp_name.startswith("PreInstall:"):
                hosp_name = hosp_name[len("PreInstall:"):].strip()
            self.dynamic_header.setText(hosp_name if hosp_name else "")

# WRITE TO current.dat
# JS_EDIT 25.12.24. CHANGED Modality={data.get("modality", "")} to Modality={data.get("Modality", "")}
# because it wasn't pulling the modality. 
            config_content = f"""SID={sid}
SiteName={hosp_name}
SP_IP={data.get("sp_ip", "")}
Host_IP={data.get("host_ip", "")}
Display_IP={data.get("display_ip", "")}
TunnelType={data.get("TunnelType", "")}
Modality={data.get("Modality", "")}

SW_Version={data.get("sw_version", "")}
Scanner={data.get("machine", "")}
OnActive=1
"""
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'current.dat')
            try:
                with open(config_path, 'w') as f:
                    f.write(config_content)
            except Exception as e:
                logger.error(f"[CRD UI] Failed to write current.dat: {type(e).__name__}: {e}")

            self.sp_ip = data.get("sp_ip", "")
            self.tams_ip = data.get("host_ip", "")
            self.sid_database_populated = True
            self.update_button_states()
            return True
        except OSError as e:
            msg_box = CustomMessageBox("Error", f"Script: {type(e).__name__}: {e}", QMessageBox.Icon.Critical, self)
            msg_box.center()
            msg_box.exec_custom()
            self.reset_state()
            return False
# ------------------------------------------------------------------------
    def on_vpn_page_loaded(self, ok):
        if ok:
            logger.info("[CRD UI] VPN Page Loaded OK")
            status_check_script = """
            function checkVPNStatus() {
                const currentURL = window.location.href;
                const isConnected =
                    currentURL.includes('welcome') ||
                    currentURL.includes('success') ||
                    document.body.textContent.includes('Welcome') ||
                    document.body.textContent.includes('Connected');
                return isConnected;
            }
            checkVPNStatus();
            """
            self.vpn_webview.page().runJavaScript(status_check_script, self.update_vpn_status)
            if self.auto_login_enabled and self.vpn_username and self.vpn_password:
                logger.info(f"[CRD UI] Attempting auto-login with username: {self.vpn_username}")
                script = f"""
                if (window.credentialObserver) {{
                    window.credentialObserver.disconnect();
                }}
                function findLoginButton() {{
                    const buttons = Array.from(document.querySelectorAll('input[type="submit"], button[type="submit"], button, input[type="button"]'));
                    return buttons.find(button => {{
                        const buttonText = (button.value || button.textContent || '').toLowerCase();
                        return buttonText.includes('login') || buttonText.includes('log in') || buttonText.includes('sign in');
                    }});
                }}
                function fillCredentials() {{
                    let userField = document.querySelector('input[name="username"], input#username, input[name="user"], input[name="login"]');
                    let passField = document.querySelector('input[name="password"], input#password, input[type="password"], input[name="pass"]');
                    let keyField = document.querySelector('input[name="key"], input#key, input[name="token"], input[name="mfa"]');
                    console.log('User field:', userField ? 'Found' : 'Not found');
                    console.log('Pass field:', passField ? 'Found' : 'Not found');
                    console.log('Key field:', keyField ? 'Found' : 'Not found');
                    let loginButton = findLoginButton();
                    console.log('Login button:', loginButton ? 'Found' : 'Not found');
                    if (userField) {{
                        userField.value = "{self.vpn_username}";
                        userField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        userField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    if (passField) {{
                        passField.value = "{self.vpn_password}";
                        passField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        passField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    if (keyField && "{self.vpn_key}") {{
                        keyField.value = "{self.vpn_key}";
                        keyField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        keyField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    if (loginButton) {{
                        loginButton.click();
                    }} else {{
                        console.error('Login button not found');
                    }}
                }}
                fillCredentials();
                """
                self.vpn_webview.page().runJavaScript(script)
                QTimer.singleShot(2000, self.check_login_errors)
            else:
                logger.info(f"[CRD UI] Auto-login skipped: Enabled={self.auto_login_enabled}, "
                               f"Username={'Set' if self.vpn_username else 'Missing'}, "
                               f"Password={'Set' if self.vpn_password else 'Missing'}")
        else:
            self.vpn_connected = False
            self.connect_led.set_status(is_on=False)
# ------------------------------------------------------------------------
    def check_login_errors(self):
        error_script = """
        let errors = document.querySelectorAll('.error, .alert, .message');
        let errorText = '';
        for (let elem of errors) {
            if (elem.textContent.toLowerCase().includes('invalid') ||
                elem.textContent.toLowerCase().includes('failed')) {
                errorText = elem.textContent;
                break;
            }
        }
        errorText;
        """
        self.vpn_webview.page().runJavaScript(error_script, self.handle_login_error)
# ------------------------------------------------------------------------
    def handle_login_error(self, error_message):
        if error_message:
            self.vpn_connected = False
            self.connect_led.set_status(is_on=False)
            msg_box = CustomMessageBox("Login Error", f"VPN Login Failed: {error_message}", QMessageBox.Icon.Warning, self)
            msg_box.center()
            msg_box.exec_custom()
# ------------------------------------------------------------------------
    def update_vpn_status(self, is_connected):
        self.vpn_connected = bool(is_connected)
        
        if hasattr(self, 'connect_led'):
            self.connect_led.set_status(is_on=self.vpn_connected)
        
        if hasattr(self, 'update_button_states'):
            self.update_button_states()
# ------------------------------------------------------------------------
    def on_vpn_url_changed(self, url):
        current_url = url.toString()
        if 'welcome' in current_url.lower() or 'success' in current_url.lower() or 'connected' in current_url.lower():
            self.vpn_connected = True
        elif '172.17.1.3' in current_url:
            self.vpn_connected = False
        self.update_vpn_status(self.vpn_connected)
# ------------------------------------------------------------------------
    def is_vpn_connected(self):
        return self.vpn_connected
# ------------------------------------------------------------------------
    def reload_vpn_page(self):
        self.vpn_webview.setUrl(QUrl("https://172.17.1.3/"))
        logger.info("[CRD UI] VPN Page Reloaded")
# ------------------------------------------------------------------------
    def systemclose_button_click(self):
        logger.info("[CRD UI] System Close Button (placeholder)")
# ------------------------------------------------------------------------        
def main():
    VersionManager.update_json()
    app = QApplication(sys.argv)
    app.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
    desktop_app = DesktopApp()
    screen_geometry = app.primaryScreen().geometry()
    x = 10 
    y = 10 
    desktop_app.move(x, y)
    desktop_app.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
# ------------------------------------------------------------------------
#(screen_geometry.width() - desktop_app.width()) // 2
#(screen_geometry.height() - desktop_app.height()) // 2                                    