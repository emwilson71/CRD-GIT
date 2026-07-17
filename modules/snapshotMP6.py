# ------------------------------------------------------------------------
"""X
snapshotMP6.py
Executes command and reads back into ui
ewilson@us.medical.canon 07/24/25
"""
# ------------------------------------------------------------------------
import json
from pathlib import Path
import logging
import sys
import os
import time
import traceback
import paramiko
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget,
    QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QProgressBar,
    QLabel, QLineEdit
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat
from cryptography.fernet import Fernet
from mod_stylesheets import (
    BUTTON_STYLE, STD_LABEL_STYLE, TEXT_EDIT_STYLE, DIALOG_STYLE,
    CHECKBOX_STYLE, SCROLL_AREA_STYLE, FRAME_STYLE, MESSAGE_BOX_STYLE
)
from mod_logging import CRDLogger
# ------------------------------------------------------------------------
def parse_key_value_file(file_path):
    logger = CRDLogger("CRD").get_logger() 
    logger.setLevel(logging.DEBUG)
    
    file_path = Path(file_path)
    config = {}
    try:
        if not file_path.exists():
            logger.error(f"[MOD SNAPSHOT6+] Configuration File Not Found: {file_path.resolve()}")
            sys.exit(1)
        if not os.access(file_path, os.R_OK):
            logger.error(f"[MOD SNAPSHOT6+] No Read Permission for {file_path}")
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    logger.warning(f"[MOD SNAPSHOT6+] Ignoring Invalid Line: {line}")
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    except UnicodeDecodeError as e:
        logger.error(f"[MOD SNAPSHOT6+] Failed to Decode '{file_path}' as UTF-8: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[MOD SNAPSHOT6+] Failed to Read '{file_path}': {e}")
        sys.exit(1)
    return config
# READ CREDS FROM ENCRYPTED JSON ---------------------------------------
def read_credentials(credential_path=None):
    logger = CRDLogger("CRD").get_logger()  
    logger.setLevel(logging.DEBUG)  
    script_dir = os.path.dirname(__file__)
    key_path = os.path.normpath(os.path.join(script_dir, "..", "config", "user.key"))
    credential_path = os.path.normpath(os.path.join(script_dir, "..", "config", "user.enc"))
    if not os.path.exists(key_path):
        logger.error(f"[MOD SNAPSHOT6+] Fernet Key Not Found: {key_path}")
        sys.exit(1)
    if not os.path.exists(credential_path):
        logger.error(f"[MOD SNAPSHOT6+] Credentials File Not Found: {credential_path}")
        sys.exit(1)
    try:
        with open(key_path, 'rb') as f:
            key = f.read()
        try:
            fernet = Fernet(key)
        except ValueError as e:
            logger.error(f"[MOD SNAPSHOT6+] Invalid Fernet Key in '{key_path}': {e}")
            sys.exit(1)
        with open(credential_path, 'rb') as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        data = json.loads(decrypted_data.decode('utf-8'))
    except json.JSONDecodeError as e:
        logger.error(f"[MOD SNAPSHOT6+] Invalid JSON Decrypted '{credential_path}': {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[MOD SNAPSHOT6+] Failed to Decrypt '{credential_path}': {e}")
        sys.exit(1)
 
    config = {}
    try:
        mr_mp6 = data.get('MR_MP6+', {}).get('credentials', {})
        config['smuser'] = mr_mp6.get('host_user')
        config['smpass'] = mr_mp6.get('host_pass')
        config['smport'] = mr_mp6.get('host_port', '22')
        sp_win10 = data.get('SP_WIN10', {})
        config['spuser'] = sp_win10.get('sp_user')
        config['sppass'] = sp_win10.get('sp_pass')
    except Exception as e:
        logger.error(f"[MOD SNAPSHOT6+] Error Parsing Credentials: {e}")
        sys.exit(1)
    expected_keys = ['smuser', 'smpass', 'spuser', 'sppass']
    for key in expected_keys:
        if not config.get(key):
            logger.error(f"[MOD SNAPSHOT6+] Missing '{key}' in Credentials")
            sys.exit(1)
    #logger.info(f"[MOD SNAPSHOT6+] Loaded Credentials: {config}")
    return config
# CLASS CONFIGMGR ------------------------------------------------------
class ConfigManager:
    def __init__(self, config_path=None):
        self.logger = CRDLogger("CRD").get_logger()  
        self.logger.setLevel(logging.DEBUG)
        
        if config_path is None:
            script_dir = os.path.dirname(__file__)
            config_path = os.path.normpath(os.path.join(script_dir, "..", "config", "current.dat"))
        self.logger.info(f"[MOD SNAPSHOT6+] Loading config from: {config_path}")
        self.config = self.read_config(config_path)
        self.sm_ip = self.config.get('Host_IP', '')
        self.sp_ip = self.config.get('SP_IP', '')
        self.tunnel_type = self.config.get('TunnelType', '')
        self.sys_id = self.config.get('SID', '')
        self.sm_version = self.config.get('SW_Version', '')
        self.machine_type = self.config.get('Modality', '')
        self.system_name = self.config.get('SiteName', '')
        self.machine_name = self.config.get('Scanner', '')
        self.magnet_type = None
        self.modality_dir = None
        self.hosp_name = None
        self.logger.info(f"[MOD SNAPSHOT6+] ConfigManager initialized - SM {self.sm_ip}, SP {self.sp_ip}, SID {self.sys_id}")
# VALIDATE SID FIRST
        if not self.sys_id:
            self.logger.error("[MOD SNAPSHOT6+] 'SID' Is Missing")
            sys.exit(1)
# ADD -000 TO SYS_ID
        self.monitor_directory = Path("c:/innervision.dir/M-Power") / f"{self.sys_id}-000" / "_tui.dir"
        self.validate_config()
    def read_config(self, config_path):
        return parse_key_value_file(config_path)
    def validate_config(self):
        try:
            import ipaddress
            ipaddress.ip_address(self.sm_ip)
            if self.sp_ip:
                ipaddress.ip_address(self.sp_ip)
        except ValueError:
            self.logger.error(f"[MOD SNAPSHOT6+] Invalid IP Address: sm_ip={self.sm_ip}, sp_ip={self.sp_ip}")
            sys.exit(1)
        if not self.sys_id or not all(c.isalnum() or c == '-' for c in self.sys_id):
            self.logger.error(f"[MOD SNAPSHOT6+] Invalid System ID: {self.sys_id}")
            sys.exit(1)
        try:
            os.makedirs(self.monitor_directory, exist_ok=True)
            test_file = self.monitor_directory / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            self.logger.error(f"[MOD SNAPSHOT6+] Cannot Write '{self.monitor_directory}': {e}")
            sys.exit(1)
    def get_monitor_directory(self):
        return self.monitor_directory
    def get_sm_ip(self):
        return self.sm_ip
    def get_sp_ip(self):
        return self.sp_ip
    def get_sys_id(self):
        return self.sys_id
    def get_sm_version(self):
        return self.sm_version
# CLASS SSH WORKER -----------------------------------------------------
class SSHWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    ui_only = pyqtSignal(str)  
    def __init__(self, hostname, username, password, command, port=22):
        super().__init__()
        self.logger = CRDLogger("SnapshotToSP").get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.hostname = hostname
        self.username = username
        self.password = password
        self.command = command
        self.port = port

    def run(self):
        try:
            self.log.emit(f"Establishing SSH Connection To {self.hostname}:{self.port} As {self.username}...", "INFO")
            self.logger.info(f"[MOD SNAPSHOT6+] Establishing SSH Connection")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=self.hostname, username=self.username, password=self.password, port=self.port)
            self.log.emit(f"Executing Command On {self.hostname}: {self.command}", "INFO")
            stdin, stdout, stderr = client.exec_command(self.command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                output = stdout.read().decode().strip()
                self.ui_only.emit(f"[{self.hostname}] {output or 'Command Executed'}")  
                self.finished.emit(f"[{self.hostname}] Command Executed Successfully")  
            else:
                error = stderr.read().decode().strip() or "SSH error."
                self.error.emit(f"[{self.hostname}] Command Failed: {error}")
                self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] Command Failed: {error}")
            client.close()
        except paramiko.AuthenticationException:
            self.error.emit(f"[{self.hostname}] Authentication Failed")
            self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] Authentication Failed")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] {str(e)}")
            self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] {str(e)}")
# CLASS SFTPWORKER -----------------------------------------------------
class SFTPWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    ui_only = pyqtSignal(str)  
    def __init__(self, hostname, username, password, remote_path, local_path, search_wait=120):
        super().__init__()
        self.logger = CRDLogger("SnapshotToSP").get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.hostname = hostname
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.local_path = local_path
        self.search_wait = search_wait

    def run(self):
        try:
            self.log.emit(f"Monitoring Remote Directory: {os.path.dirname(self.remote_path)}", "INFO")
            self.logger.info(f"[MOD SNAPSHOT6+] Monitoring Remote Directory: {os.path.dirname(self.remote_path)}")
            start_time = time.time()
            snapshot_found = False
            transport = None
            sftp = None
            while time.time() - start_time < self.search_wait:
                if not transport:
                    self.log.emit(f"Establishing SFTP Connection To {self.hostname} As {self.username}...", "INFO")
                    self.logger.info(f"[MOD SNAPSHOT6+] Establishing SFTP Connection To {self.hostname} As {self.username}...")
                    transport = paramiko.Transport((self.hostname, 22))
                    transport.connect(username=self.username, password=self.password)
                    sftp = paramiko.SFTPClient.from_transport(transport)
                remote_dir = os.path.dirname(self.remote_path)
                log_files = sftp.listdir(remote_dir)
                snapshot_logs = [f for f in log_files if 'snapshot.log' in f.lower()]
                if snapshot_logs:
                    snapshot_found = True
                    snapshot_logs_sorted = sorted(
                        snapshot_logs,
                        key=lambda x: sftp.stat(os.path.join(remote_dir, x)).st_mtime,
                        reverse=True
                    )
                    latest_log = snapshot_logs_sorted[0]
                    complete_remote_path = os.path.join(remote_dir, latest_log)
                    self.ui_only.emit(f"Transferring Latest File: {complete_remote_path} to {self.local_path}")
                    sftp.get(complete_remote_path, self.local_path)
                    self.finished.emit(f"Latest file '{latest_log}' transferred successfully to {self.local_path}")
                    break
                self.log.emit("Waiting for snapshot file on SP", "INFO")
                self.logger.info("[MOD SNAPSHOT6+] Waiting for snapshot file on SP")
                time.sleep(5)
        
            if not snapshot_found:
                raise FileNotFoundError("No Snapshot.log File Found on SP after timeout")
        
            if sftp:
                sftp.close()
            if transport:
                transport.close()
        except paramiko.AuthenticationException:
            self.error.emit(f"[{self.hostname}] Authentication Failed")
            self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] Authentication Failed")
        except FileNotFoundError as e:
            self.error.emit(f"[{self.hostname}] Snapshot Log File Not Found: {str(e)}")
            self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] Snapshot Log File Not Found: {str(e)}")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] SFTP Transfer Failed: {str(e)}")
            self.logger.error(f"[MOD SNAPSHOT6+] [{self.hostname}] SFTP Transfer Failed: {str(e)}")
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
# CLASS FILE MONITOR ---------------------------------------------------
class FileMonitorWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    def __init__(self, directory, search_wait=120):
        super().__init__()
        self.logger = CRDLogger("SnapshotToSP").get_logger()  
        self.logger.setLevel(logging.DEBUG)  
        self.directory = directory
        self.search_wait = search_wait
    def run(self):
        try:
            self.log.emit(f"Starting to Monitor Directory: {self.directory}", "INFO")
            self.logger.info(f"[MOD SNAPSHOT6+] Starting to Monitor Directory: {self.directory}")
            start_time = time.time()
            snapshot_found = False
            while time.time() - start_time < self.search_wait:
                if not os.path.exists(self.directory):
                    self.error.emit(f"Directory Not Found: {self.directory}")
                    self.logger.error(f"[MOD SNAPSHOT6+] Directory Not Found: {self.directory}")
                    return
                files = os.listdir(self.directory)
                snapshot_files = [f for f in files if 'snapshot' in f.lower()]
                if snapshot_files:
                    snapshot_found = True
                    self.finished.emit(
                        f"Snapshot file(s) found: {', '.join(snapshot_files)}")
                    break
                time.sleep(5)
                self.log.emit("Waiting for snapshot file", "INFO")
                self.logger.info("[MOD SNAPSHOT6+] Waiting for snapshot file")
            if not snapshot_found:
                self.error.emit("Snapshot file Timeout")
                self.logger.error("[MOD SNAPSHOT6+] Snapshot file Timeout")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
            self.logger.error(f"[MOD SNAPSHOT6+] Error: {str(e)}")
# CLASS PROCESSOR ------------------------------------------------------
class SnapshotProcessor:
    def __init__(self, config_manager):
        self.monitor_directory = config_manager.get_monitor_directory()
    def process_snapshot(self, snapshot_filename):
        snapshot_path = Path(self.monitor_directory) / snapshot_filename
        try:
            if not snapshot_path.exists():
                raise FileNotFoundError(f"Snapshot_ToSP not Found: {snapshot_path}")
            with open(snapshot_path, 'r') as file:
                data = file.read()
            return f"Snapshot '{snapshot_filename}' Successful."
        except Exception as e:
            return f"Failed to Create Snapshot '{snapshot_filename}': {str(e)}"
# CLASS SNAPSHOT WORKER ------------------------------------------------
class SnapshotWorkflowWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    ui_only = pyqtSignal(str)  
    def __init__(self, config_manager, credentials):
        super().__init__()
        self.logger = CRDLogger("SnapshotToSP").get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.config_manager = config_manager
        self.credentials = credentials
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.sm_version = self.config_manager.get_sm_version()
        self.snapshot_processor = SnapshotProcessor(config_manager)
        self.logger.info(f"[MOD SNAPSHOT6+] SM {self.sm_ip}, SP {self.sp_ip}, VERSION {self.sm_version}")

    def run(self):
        sm_command = 'snapshot_tosp.bat'
        sm_thread = QThread()
        sm_worker = SSHWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            command=sm_command,
            port=self.credentials.get('smport', '22')
        )
        sm_worker.moveToThread(sm_thread)
        sm_worker.log.connect(self.log.emit)
        sm_worker.ui_only.connect(self.ui_only.emit) 
        sm_worker.finished.connect(lambda msg: self.on_sm_finished(msg, sm_thread, sm_worker))
        sm_worker.error.connect(lambda err: self.on_error(err, sm_thread, sm_worker))
        sm_thread.started.connect(sm_worker.run)
        sm_worker.finished.connect(sm_thread.quit)
        sm_worker.finished.connect(sm_worker.deleteLater)
        sm_thread.finished.connect(sm_thread.deleteLater)
        sm_thread.start()

    def on_sm_finished(self, message, sm_thread, sm_worker):
        self.log.emit(message, "INFO")
        self.logger.info(message)
        QTimer.singleShot(5000, self.execute_sp_operations)

    def on_error(self, error_message, thread, worker):
        self.error.emit(error_message)
        self.logger.error(error_message)

    def execute_sp_operations(self):
        sys_id = self.config_manager.get_sys_id()
        if not sys_id:
            self.error.emit("System ID (SID) Is Not Configured")
            self.logger.error("[MOD SNAPSHOT6+] System ID (SID) Is Not Configured")
            return
        remote_dir = f"c:/Innervision.dir/M-Power/{sys_id}-000/_tui.dir"
        remote_log_pattern = "_snapshot.log"
        remote_log_path = os.path.join(remote_dir, remote_log_pattern)
        local_dir = str(self.monitor_directory)
        local_log_path = Path(local_dir) / "latest_snapshot.log"
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        sftp_thread = QThread()
        sftp_worker = SFTPWorker(
            hostname=self.sp_ip,
            username=self.credentials['spuser'],
            password=self.credentials['sppass'],
            remote_path=remote_log_path,
            local_path=str(local_log_path)
        )
        sftp_worker.moveToThread(sftp_thread)
        sftp_worker.log.connect(self.log.emit)
        sftp_worker.ui_only.connect(self.ui_only.emit) 
        sftp_worker.finished.connect(lambda msg: self.on_sftp_finished(msg, sftp_thread, sftp_worker, local_log_path))
        sftp_worker.error.connect(lambda err: self.on_error(err, sftp_thread, sftp_worker))
        sftp_thread.started.connect(sftp_worker.run)
        sftp_worker.finished.connect(sftp_thread.quit)
        sftp_worker.finished.connect(sftp_worker.deleteLater)
        sftp_thread.finished.connect(sftp_thread.deleteLater)
        sftp_thread.start()

    def on_sftp_finished(self, message, sftp_thread, sftp_worker, local_log_path):
        self.log.emit(message, "INFO")
        self.logger.info(message)
        self.transfer_and_display_log(local_log_path)

    def transfer_and_display_log(self, local_log_path):
        try:
            local_log_path = Path(local_log_path)
            if not local_log_path.exists():
                raise FileNotFoundError(f"Log File Not Found: {local_log_path}")
            with open(local_log_path, 'r') as file:
                log_content = file.read()
            processing_result = self.snapshot_processor.process_snapshot(local_log_path.name)
            self.log.emit(processing_result, "INFO")
            self.logger.info(processing_result)
            self.ui_only.emit("<b>Latest Snapshot Log:</b>")
            self.ui_only.emit(f"<pre>{log_content}</pre>")
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Failed to display log: {str(e)}")
            self.logger.error(f"[MOD SNAPSHOT6+] Failed to display log: {str(e)}")
# CLASS SNAPSHOT -------------------------------------------------------
# PUSH STYLESHEETS TO MOD
class SnapshotToSP(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.logger = CRDLogger("SnapshotToSP").get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.setWindowTitle("SNAPSHOT TOOL")
        self.setFixedSize(1000, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #202020;
                color: white;
            }
            QPushButton {
                color: white;
                background-color: #606060;
                padding: 10px;
                font-size: 12pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #303030;
                border: 1px solid white;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QTextEdit {
                color: white;
                background-color: #202020;
                font-size: 11pt;
                border: 1px solid black;
                text-align: left;
                padding: 5px;
                margin: 0px;
            }
            QTextEdit QScrollBar:horizontal {
                height: 10px;
            }
            QTextEdit QScrollBar::handle:horizontal {
                background: #606060;
                min-width: 20px;
                border-radius: 5px;
            }
            QTextEdit QScrollBar::add-line:horizontal, QTextEdit QScrollBar::sub-line:horizontal {
                background: none;
                width: 0px;
            }
            QListWidget {
                color: white;
                background-color: #202020;
                font-size: 11pt;
            }
            QListWidget::item:selected {
                background-color: #505050;
                color: yellow;
            }
            QLabel {
                color: white;
                font-size: 12px;
                font-weight: bold;
                height: 26px;
            }
            QProgressBar {
                color: white;
                background-color: #202020;
                border: 1px solid #404040;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #606060;
            }
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
                width: 80px;
                min-width: 80px;
                max-width: 80px;
                text-align: center;
            }
            QMessageBox QPushButton:hover {
                background-color: #303030;
                border: 1px solid #ffffff;
            }
            QMessageBox QPushButton:pressed {
                background-color: #606060;
            }
            QLineEdit {
                color: white;
                background-color: #202020;
                padding: 5px;
                border: 1px solid #404040;
                border-radius: 3px;
                font-size: 10pt;
            }
        """)
        self.config_manager = config_manager
        self.credentials = read_credentials()
        self.keywords = self.load_keywords(os.path.join(os.path.dirname(__file__), "..", "config", "keywords.dat"))
        self.current_highlight_index = -1
        self.highlight_positions = []
        self.last_keyword = None
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.snapshot_processor = SnapshotProcessor(config_manager)
        self.logger.info(f"[MOD SNAPSHOT6+] SnapshotToSP - SM {self.sm_ip}, SP {self.sp_ip}, SID {self.config_manager.get_sys_id()}")
        self.highlight_timer = QTimer()
        self.highlight_timer.setSingleShot(True)
        self.highlight_timer.timeout.connect(self.perform_highlight)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.left_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_layout, stretch=2)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setAlignment(Qt.AlignLeft)
        self.output_text.horizontalScrollBar().setValue(0)
        self.left_layout.addWidget(self.output_text)
        button_layout = QHBoxLayout()
        self.left_layout.addLayout(button_layout)
        self.execute_all_button = QPushButton("SNAPSHOT")
        self.execute_all_button.clicked.connect(self.execute_workflow)
        button_layout.addWidget(self.execute_all_button)
        self.copy_button = QPushButton("COPY TO CLIPBOARD")
        self.copy_button.clicked.connect(self.copy_output_to_clipboard)
        button_layout.addWidget(self.copy_button)
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.right_layout, stretch=1)
        self.highlight_label = QLabel()
        self.highlight_label.setWordWrap(True)
        self.highlight_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.right_layout.addWidget(self.highlight_label)
        self.right_layout.addSpacing(10)
        self.keywords_list = QListWidget()
        self.keywords_list.addItems(self.keywords)
        self.keywords_list.itemSelectionChanged.connect(self.delayed_highlight)
        self.right_layout.addWidget(self.keywords_list)
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.returnPressed.connect(self.perform_custom_search)
        search_layout.addWidget(self.search_edit, stretch=4)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_custom_search)
        search_layout.addWidget(self.search_button, stretch=1)
        self.right_layout.addLayout(search_layout)
        nav_layout = QHBoxLayout()
        self.up_button = QPushButton("▲")
        self.down_button = QPushButton("▼")
        self.up_button.clicked.connect(self.navigate_up)
        self.down_button.clicked.connect(self.navigate_down)
        nav_layout.addWidget(self.up_button)
        nav_layout.addWidget(self.down_button)
        self.right_layout.addLayout(nav_layout)

    def load_keywords(self, file_path):
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                self.logger.error(f"[MOD SNAPSHOT6+] Keywords Not Found: {file_path}")
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.logger.error(f"[MOD SNAPSHOT6+] Failed To Load Keywords: {e}")
            return []

    def append_ui_only(self, message):
        """Append message to the UI QTextEdit without logging to file."""
        self.output_text.append(message)
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.horizontalScrollBar().setValue(0)

    def execute_workflow(self):
        self.execute_all_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.output_text.clear()
        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait()
        self.workflow_thread = QThread()
        self.workflow_worker = SnapshotWorkflowWorker(self.config_manager, self.credentials)
        self.workflow_worker.moveToThread(self.workflow_thread)
        self.workflow_worker.log.connect(self.append_log)
        self.workflow_worker.ui_only.connect(self.append_ui_only)
        self.workflow_worker.error.connect(self.on_workflow_error)
        self.workflow_worker.finished.connect(self.on_workflow_finished)
        self.workflow_thread.started.connect(self.workflow_worker.run)
        self.workflow_worker.finished.connect(self.workflow_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.workflow_thread.finished.connect(self.workflow_thread.deleteLater)
        self.workflow_thread.start()

    def append_log(self, message, level="INFO"):
        if level == "ERROR":
            colored_message = f'<span style="color:#FF0000;">{message}</span>'
        elif level == "WARNING":
            colored_message = f'<span style="color:#FFA500;">{message}</span>'
        else:
            colored_message = f'<span style="color:#FFFFFF;">{message}</span>'
        self.output_text.append(colored_message)
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.horizontalScrollBar().setValue(0)
        self.logger.log(
            logging.ERROR if level == "ERROR" else logging.WARNING if level == "WARNING" else logging.INFO,
            message
        )

    def on_workflow_error(self, error_message):
        self.append_log(f"[MOD SNAPSHOT6+] Error: {error_message}", "ERROR")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Workflow Error")
        msg_box.setText(error_message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setStyleSheet(MESSAGE_BOX_STYLE)
        msg_box.exec()
        self.execute_all_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def on_workflow_finished(self):
        self.append_log("Snapshot Aquired", "INFO")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Success")
        msg_box.setText("Snapshot Aquired OK")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet(MESSAGE_BOX_STYLE)
        msg_box.exec()
        self.execute_all_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def copy_output_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_text.toPlainText())
        msg_box = QMessageBox()
        msg_box.setWindowTitle("COPIED")
        msg_box.setText("Copied to Clipboard")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet(MESSAGE_BOX_STYLE)
        msg_box.exec()

    def perform_custom_search(self):
        search_text = self.search_edit.text().strip()
        if not search_text:
            self.keywords_list.clearSelection()
            self.highlight_positions = []
            self.current_highlight_index = -1
            self.output_text.setTextCursor(QTextCursor(self.output_text.document()))
            self.highlight_label.clear()
            return
        self.last_keyword = search_text
        cursor = self.output_text.textCursor()
        cursor.beginEditBlock()
        scrollbar = self.output_text.verticalScrollBar()
        current_scroll = scrollbar.value()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(Qt.yellow)
        highlight_format.setForeground(Qt.black)
        self.highlight_positions = []
        text = self.output_text.toPlainText().lower()
        search_text_lower = search_text.lower()
        start = 0
        while True:
            start = text.find(search_text_lower, start)
            if start == -1:
                break
            self.highlight_positions.append(start)
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(search_text))
            cursor.mergeCharFormat(highlight_format)
            start += len(search_text)
        cursor.endEditBlock()
        scrollbar.setValue(current_scroll)
        self.current_highlight_index = -1 if not self.highlight_positions else 0
        if self.highlight_positions:
            self.highlight_label.setText(f"{search_text} found {len(self.highlight_positions)} times")
            self.scroll_to_highlight(self.current_highlight_index)
        else:
            self.highlight_label.setText(f"'{search_text}' Not Found")

    def scroll_to_highlight(self, index):
        if not self.highlight_positions or index < 0:
            return
        pos = self.highlight_positions[index]
        cursor = self.output_text.textCursor()
        cursor.setPosition(pos)
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
        self.output_text.horizontalScrollBar().setValue(0)
        self.highlight_label.setText(
            f"Match {self.current_highlight_index + 1} of {len(self.highlight_positions)}"
        )

    def perform_highlight(self):
        if not self.highlight_positions or self.current_highlight_index < 0:
            return
        pos = self.highlight_positions[self.current_highlight_index]
        cursor = self.output_text.textCursor()
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(self.search_edit.text()))
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
        self.output_text.horizontalScrollBar().setValue(0)
        self.highlight_label.setText(
            f"Match {self.current_highlight_index + 1} of {len(self.highlight_positions)}"
        )

    def delayed_highlight(self):
        selected_items = self.keywords_list.selectedItems()
        if selected_items:
            keyword = selected_items[0].text()
            if keyword != self.last_keyword:
                self.last_keyword = keyword
                self.search_edit.setText(keyword)
                self.perform_custom_search()
        else:
            self.last_keyword = None
            self.search_edit.clear()
            self.highlight_positions = []
            self.current_highlight_index = -1
            self.output_text.setTextCursor(QTextCursor(self.output_text.document()))
            self.highlight_label.clear()

    def navigate_up(self):
        if self.current_highlight_index > 0:
            self.current_highlight_index -= 1
            self.perform_highlight()

    def navigate_down(self):
        if self.current_highlight_index < len(self.highlight_positions) - 1:
            self.current_highlight_index += 1
            self.perform_highlight()

    def closeEvent(self, event):
        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait(2000)
            if self.workflow_thread.isRunning():
                self.logger.warning("[MOD SNAPSHOT6+] Forcing termination of workflow_thread")
                self.workflow_thread.terminate()
                self.workflow_thread.wait()
        if hasattr(self, 'workflow_worker'):
            try:
                if hasattr(self.workflow_worker, 'sm_thread') and self.workflow_worker.sm_thread.isRunning():
                    self.workflow_worker.sm_thread.quit()
                    self.workflow_worker.sm_thread.wait(2000)
                    if self.workflow_worker.sm_thread.isRunning():
                        self.logger.warning("[MOD SNAPSHOT6+] Forcing termination of sm_thread")
                        self.workflow_worker.sm_thread.terminate()
                        self.workflow_worker.sm_thread.wait()
                if hasattr(self.workflow_worker, 'sftp_thread') and self.workflow_worker.sftp_thread.isRunning():
                    self.workflow_worker.sftp_thread.quit()
                    self.workflow_worker.sftp_thread.wait(2000)
                    if self.workflow_worker.sftp_thread.isRunning():
                        self.logger.warning("[MOD SNAPSHOT6+] Forcing termination of sftp_thread")
                        self.workflow_worker.sftp_thread.terminate()
                        self.workflow_worker.sftp_thread.wait()
            except Exception as e:
                self.logger.error(f"[MOD SNAPSHOT6+] Error Terminating Threads: {e}")
        event.accept()
# MAIN -----------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    window = SnapshotToSP(config_manager)
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()
# ---------------------------------------------------------------------
