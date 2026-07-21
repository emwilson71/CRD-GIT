# ------------------------------------------------------------------------
"""X
crd_matrix.py
Decodes sw versions and passwords for connectivity
ewilson@us.medical.canon 05/24/25
"""
# ------------------------------------------------------------------------
# LIBRARIES
import json
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import time
import paramiko
import telnetlib
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget,
    QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QLabel, QLineEdit
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat
from cryptography.fernet import Fernet
import mod_stylesheets

# LOGGING SETUP -------------------------------------------------------
def setup_logging():
    log_path = Path('../logs/snapshottosp.log')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logging.basicConfig(
        handlers=[handler],
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

# PARSING PLAIN TEXT KEY-VALUE FILE ------------------------------------
def parse_key_value_file(file_path):
    file_path = Path(file_path)
    config = {}
    try:
        if not file_path.exists():
            logging.error(f"Configuration File Not Found: {file_path.resolve()}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Error", f"Configuration File Not Found: {file_path}")
            sys.exit(1)
        if not os.access(file_path, os.R_OK):
            logging.error(f"{file_path}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Error", f"{file_path}")
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    logging.warning(f"Ignoring invalid line: {line}")
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    except UnicodeDecodeError as e:
        logging.error(f"Failed to Decode '{file_path}' as UTF-8: {e}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Failed to Dcode '{file_path}' as UTF-8: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to Read '{file_path}': {e}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Failed to Read '{file_path}': {e}")
        sys.exit(1)
    return config

# READ CREDS FROM ENCRYPTED JSON ---------------------------------------
def read_credentials(credential_path):
    credential_path = Path(credential_path)
    key_path = Path('C:/CRD/config/user.key')
    if not key_path.exists():
        logging.error(f"Fernet Key Not Found: {key_path}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Fernet Key Not Found: {key_path}")
        sys.exit(1)
    if not credential_path.exists():
        logging.error(f"Credentials File Not Found: {credential_path}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Credentials File Not Found: {credential_path}")
        sys.exit(1)
    try:
        with open(key_path, 'rb') as f:
            key = f.read()
        try:
            fernet = Fernet(key)
        except ValueError as e:
            logging.error(f"Invalid Fernet key in '{key_path}': {e}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Error", f"Invalid Fernet key in '{key_path}': {e}")
            sys.exit(1)
        with open(credential_path, 'rb') as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        data = json.loads(decrypted_data.decode('utf-8'))
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in Decrypted '{credential_path}': {e}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Invalid JSON in Decrypted '{credential_path}': {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to decrypt or read '{credential_path}': {e}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Failed to decrypt or read '{credential_path}': {e}")
        sys.exit(1)
    config = {}
    try:
        sp_win10 = data.get('SP_WIN10', {})
        config['spuser'] = sp_win10.get('sp_user')
        config['sppass'] = sp_win10.get('sp_pass')
        mr_mp6 = data.get('MR_MP6+', {}).get('credentials', {})
        config['smuser'] = mr_mp6.get('host_user')
        config['smpass'] = mr_mp6.get('host_pass')
    except Exception as e:
        logging.error(f"Error parsing credentials: {e}")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(None, "Error", f"Error parsing credentials: {e}")
        sys.exit(1)
    expected_keys = ['spuser', 'sppass', 'smuser', 'smpass']
    for key in expected_keys:
        if not config.get(key):
            logging.error(f"Missing '{key}' in credentials file")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Error", f"Missing '{key}' in credentials file")
            sys.exit(1)
    return config

# CLASS CONFIGMGR ------------------------------------------------------
class ConfigManager:
    def __init__(self, config_path='C:/CRD/config/current.dat'):
        self.config = self.read_config(config_path)
        self.sm_ip = self.config.get('Host_IP')
        self.sp_ip = self.config.get('SP_IP')
        self.tunnel_type = self.config.get('TunnelType')
        self.sys_id = self.config.get('SID')
        self.sm_version = self.config.get('SW_Version')
        self.machine_type = self.config.get('Modality')
        self.system_name = self.config.get('SiteName')
        self.machine_name = self.config.get('Scanner')
        self.magnet_type = None
        self.modality_dir = None
        self.hosp_name = None
        # Determine connection type based on SW_Version
        self.connection_type = 'ssh'
        try:
            version = float(self.sm_version)
            if version < 6:
                self.connection_type = 'telnet'
                logging.info(f"Using Telnet for SW_Version {version} (< 6)")
        except (ValueError, TypeError):
            logging.warning(f"Invalid SW_Version '{self.sm_version}', defaulting to SSH")
        # VALIDATE SID FIRST
        if not self.sys_id:
            logging.error("'SID' Is Missing")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Configuration Error", "'SID' Is Missing")
            sys.exit(1)
        # ADD -000 TO sys_id
        self.monitor_directory = Path("c:/innervision.dir/M-Power") / f"{self.sys_id}-000" / "_tui.dir"
        self.validate_config()

    def read_config(self, config_path):
        return parse_key_value_file(config_path)

    def validate_config(self):
        try:
            import ipaddress
            ipaddress.ip_address(self.sm_ip)
            ipaddress.ip_address(self.sp_ip)
        except ValueError:
            logging.error(f"Invalid IP Address: smip={self.sm_ip}, spip={self.sp_ip}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Configuration Error",
                                 f"Invalid IP Addresses: smip={self.sm_ip}, spip={self.sp_ip}")
            sys.exit(1)
        if not self.sys_id or not all(c.isalnum() or c == '-' for c in self.sys_id):
            logging.error(f"Invalid System ID: {self.sys_id}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Configuration Error",
                                 f"Invalid System ID: {self.sys_id}")
            sys.exit(1)
        try:
            os.makedirs(self.monitor_directory, exist_ok=True)
            test_file = self.monitor_directory / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logging.error(f"Cannot Write '{self.monitor_directory}': {e}")
            QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
            QMessageBox.critical(None, "Configuration Error",
                                 f"Cannot Write '{self.monitor_directory}': {e}")
            sys.exit(1)

    def get_monitor_directory(self):
        return self.monitor_directory

    def get_sm_ip(self):
        return self.sm_ip

    def get_sp_ip(self):
        return self.sp_ip

    def get_sys_id(self):
        return self.sys_id

    def get_connection_type(self):
        return self.connection_type

# CLASS SSH WORKER -----------------------------------------------------
class SSHWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

    def __init__(self, hostname, username, password, command, port=22):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.command = command
        self.port = port

    def run(self):
        try:
            self.log.emit(f"Establishing SSH Connection To {self.hostname}:{self.port} As {self.username}...", "INFO")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=self.hostname, username=self.username, password=self.password, port=self.port)
            self.log.emit(f"Executing Command On {self.hostname}: {self.command}", "INFO")
            stdin, stdout, stderr = client.exec_command(self.command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                output = stdout.read().decode().strip()
                self.finished.emit(f"[{self.hostname}] {output or 'Command Executed Successfully'}")
            else:
                error = stderr.read().decode().strip() or "SSH error."
                self.error.emit(f"[{self.hostname}] Command Failed: {error}")
            client.close()
        except paramiko.AuthenticationException:
            self.error.emit(f"[{self.hostname}] Authentication Failed")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] {str(e)}")

# CLASS TELNET WORKER --------------------------------------------------
class TelnetWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

    def __init__(self, hostname, username, password, command, port=23):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.command = command
        self.port = port

    def run(self):
        try:
            self.log.emit(f"Establishing Telnet Connection To {self.hostname}:{self.port} As {self.username}...", "INFO")
            tn = telnetlib.Telnet(self.hostname, self.port, timeout=10)
            tn.read_until(b"login: ", timeout=5)
            tn.write(self.username.encode('ascii') + b"\n")
            tn.read_until(b"Password: ", timeout=5)
            tn.write(self.password.encode('ascii') + b"\n")
            tn.read_until(b"$ ", timeout=5)  # Assuming a shell prompt
            self.log.emit(f"Executing Command On {self.hostname}: {self.command}", "INFO")
            tn.write(self.command.encode('ascii') + b"\n")
            output = tn.read_until(b"$ ", timeout=10).decode('ascii').strip()
            tn.close()
            self.finished.emit(f"[{self.hostname}] {output or 'Command Executed Successfully'}")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] Telnet Failed: {str(e)}")

# CLASS SFTPWORKER -----------------------------------------------------
class SFTPWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

    def __init__(self, hostname, username, password, remote_path, local_path, port=22):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.local_path = local_path
        self.port = port

    def run(self):
        try:
            self.log.emit(f"Establishing SFTP Connection To {self.hostname}:{self.port} As {self.username}...", "INFO")
            transport = paramiko.Transport((self.hostname, self.port))
            transport.connect(username=self.username, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            self.log.emit(f"Listing Files in Remote Directory: {os.path.dirname(self.remote_path)}", "INFO")
            remote_dir = os.path.dirname(self.remote_path)
            log_files = sftp.listdir(remote_dir)
            snapshot_logs = [f for f in log_files if 'snapshot.log' in f.lower()]
            if not snapshot_logs:
                raise FileNotFoundError("No Snapshot.log File Found on SP")
            snapshot_logs_sorted = sorted(
                snapshot_logs,
                key=lambda x: sftp.stat(os.path.join(remote_dir, x)).st_mtime,
                reverse=True
            )
            latest_log = snapshot_logs_sorted[0]
            complete_remote_path = os.path.join(remote_dir, latest_log)
            self.log.emit(f"Transferring Latest File: {complete_remote_path} to {self.local_path}", "INFO")
            sftp.get(complete_remote_path, self.local_path)
            sftp.close()
            transport.close()
            self.finished.emit(f"Latest file '{latest_log}' transferred successfully to {self.local_path}")
        except paramiko.AuthenticationException:
            self.error.emit(f"[{self.hostname}] Authentication Failed")
        except FileNotFoundError:
            self.error.emit(f"[{self.hostname}] Snapshot Log File Not Found {os.path.dirname(self.remote_path)}")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] SFTP Transfer Failed: {str(e)}")

# CLASS FILE MONITOR ---------------------------------------------------
class FileMonitorWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

    def __init__(self, directory, search_wait=120):
        super().__init__()
        self.directory = directory
        self.search_wait = search_wait

    def run(self):
        try:
            self.log.emit(f"Starting to Monitor Directory: {self.directory}", "INFO")
            start_time = time.time()
            snapshot_found = False
            while time.time() - start_time < self.search_wait:
                if not os.path.exists(self.directory):
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
            if not snapshot_found:
                self.error.emit("Snapshot file Timeout")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

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

    def __init__(self, config_manager, credentials):
        super().__init__()
        self.config_manager = config_manager
        self.credentials = credentials
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.snapshot_processor = SnapshotProcessor(config_manager)
        self.connection_type = self.config_manager.get_connection_type()

    def run(self):
        sm_command = 'snapshot_tosp.bat'
        sm_thread = QThread()
        if self.connection_type == 'telnet':
            worker = TelnetWorker(
                hostname=self.sm_ip,
                username=self.credentials['smuser'],
                password=self.credentials['smpass'],
                command=sm_command
            )
        else:
            worker = SSHWorker(
                hostname=self.sm_ip,
                username=self.credentials['smuser'],
                password=self.credentials['smpass'],
                command=sm_command
            )
        worker.moveToThread(sm_thread)
        # CONNECT SIGNALS
        worker.log.connect(self.log.emit)
        worker.finished.connect(lambda msg: self.on_sm_finished(msg, sm_thread, worker))
        worker.error.connect(lambda err: self.on_error(err, sm_thread, worker))
        sm_thread.started.connect(worker.run)
        worker.finished.connect(sm_thread.quit)
        worker.finished.connect(worker.deleteLater)
        sm_thread.finished.connect(sm_thread.deleteLater)
        sm_thread.start()

    def on_sm_finished(self, message, sm_thread, sm_worker):
        QTimer.singleShot(5000, self.execute_sp_operations)

    def on_error(self, error_message, thread, worker):
        self.error.emit(error_message)

    def execute_sp_operations(self):
        sys_id = self.config_manager.get_sys_id()
        if not sys_id:
            self.error.emit("System ID (SID) Is Not Configured")
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
        sftp_worker.finished.connect(lambda msg: self.on_sftp_finished(msg, sftp_thread, sftp_worker, local_log_path))
        sftp_worker.error.connect(lambda err: self.on_error(err, sftp_thread, sftp_worker))
        sftp_thread.started.connect(sftp_worker.run)
        sftp_worker.finished.connect(sftp_thread.quit)
        sftp_worker.finished.connect(sftp_worker.deleteLater)
        sftp_thread.finished.connect(sftp_thread.deleteLater)
        sftp_thread.start()

    def on_sftp_finished(self, message, sftp_thread, sftp_worker, local_log_path):
        self.log.emit(message, "INFO")
        self.transfer_and_display_log(local_log_path)

    def transfer_and_display_log(self, local_log_path):
        try:
            if not local_log_path.exists():
                raise FileNotFoundError(f"Log File Not Found: {local_log_path}")
            with open(local_log_path, 'r') as file:
                log_content = file.read()
            processing_result = self.snapshot_processor.process_snapshot(local_log_path.name)
            self.log.emit(processing_result, "INFO")
            self.log.emit("<b>Latest Snapshot Log:</b>", "INFO")
            self.log.emit(f"<pre>{log_content}</pre>", "INFO")
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Failed to display log: {str(e)}")

# CLASS SNAPSHOT -------------------------------------------------------
class SnapshotToSP(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.setWindowTitle("SNAPSHOT TOOL")
        self.setFixedSize(1200, 800)
        self.setStyleSheet(mod_stylesheets.DIALOG_STYLE)

        # SETUP UI
        self.config_manager = config_manager
        self.credentials = read_credentials('C:/CRD/config/user.enc')
        self.keywords = self.load_keywords('C:/CRD/config/keywords.dat')
        self.current_highlight_index = -1
        self.highlight_positions = []
        self.last_keyword = None
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.snapshot_processor = SnapshotProcessor(config_manager)
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
        self.output_text.setStyleSheet(mod_stylesheets.TEXT_EDIT_STYLE)
        self.left_layout.addWidget(self.output_text)
        button_layout = QHBoxLayout()
        self.left_layout.addLayout(button_layout)
        self.execute_all_button = QPushButton("SNAPSHOT")
        self.execute_all_button.clicked.connect(self.execute_workflow)
        self.execute_all_button.setStyleSheet(mod_stylesheets.BUTTON_STYLE)
        button_layout.addWidget(self.execute_all_button)
        self.copy_button = QPushButton("COPY TO CLIPBOARD")
        self.copy_button.clicked.connect(self.copy_output_to_clipboard)
        self.copy_button.setStyleSheet(mod_stylesheets.BUTTON_STYLE)
        button_layout.addWidget(self.copy_button)
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.right_layout, stretch=1)
        self.highlight_label = QLabel()
        self.highlight_label.setWordWrap(True)
        self.highlight_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.highlight_label.setStyleSheet(mod_stylesheets.STD_LABEL_STYLE)
        self.right_layout.addWidget(self.highlight_label)
        self.right_layout.addSpacing(10)
        self.keywords_list = QListWidget()
        self.keywords_list.addItems(self.keywords)
        self.keywords_list.itemSelectionChanged.connect(self.delayed_highlight)
        self.keywords_list.setStyleSheet("""
            QListWidget {
                color: #E0E0E0;
                background-color: #2A2A2A;
                font-size: 11pt;
                border: 1px solid #5A5A5A;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #4A4A4A;
                color: #FFFFFF;
            }
        """)
        self.right_layout.addWidget(self.keywords_list)
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setStyleSheet(mod_stylesheets.LINE_EDIT_STYLE)
        self.search_edit.returnPressed.connect(self.perform_custom_search)
        search_layout.addWidget(self.search_edit, stretch=4)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_custom_search)
        self.search_button.setStyleSheet(mod_stylesheets.BUTTON_STYLE)
        search_layout.addWidget(self.search_button, stretch=1)
        self.right_layout.addLayout(search_layout)
        nav_layout = QHBoxLayout()
        self.up_button = QPushButton("▲")
        self.down_button = QPushButton("▼")
        self.up_button.clicked.connect(self.navigate_up)
        self.down_button.clicked.connect(self.navigate_down)
        self.up_button.setStyleSheet(mod_stylesheets.BUTTON_STYLE)
        self.down_button.setStyleSheet(mod_stylesheets.BUTTON_STYLE)
        nav_layout.addWidget(self.up_button)
        nav_layout.addWidget(self.down_button)
        self.right_layout.addLayout(nav_layout)

    def load_keywords(self, file_path):
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logging.error(f"Keywords Not Found: {file_path}")
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logging.error(f"Failed To Load Keywords: {e}")
            return []

    def delayed_highlight(self):
        self.highlight_timer.start(100)

    def perform_highlight(self):
        selected_items = self.keywords_list.selectedItems()
        if not selected_items:
            return
        keyword = selected_items[0].text()
        if self.last_keyword == keyword:
            return
        self.last_keyword = keyword
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
        text = self.output_text.toPlainText()
        start = 0
        while True:
            start = text.find(keyword, start)
            if start == -1:
                break
            self.highlight_positions.append(start)
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(keyword))
            cursor.mergeCharFormat(highlight_format)
            start += len(keyword)
        cursor.endEditBlock()
        scrollbar.setValue(current_scroll)
        self.current_highlight_index = -1 if not self.highlight_positions else 0
        if self.highlight_positions:
            self.scroll_to_highlight(self.current_highlight_index)

    def scroll_to_highlight(self, index):
        if not (0 <= index < len(self.highlight_positions)):
            return
        self.output_text.blockSignals(True)
        position = self.highlight_positions[index]
        cursor = self.output_text.textCursor()
        cursor.setPosition(position)
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        display_text = f"Match {index + 1}/{len(self.highlight_positions)}: {line_text}"
        self.highlight_label.setText(display_text)
        cursor.setPosition(position)
        if self.keywords_list.selectedItems():
            highlight_length = len(self.keywords_list.selectedItems()[0].text())
        else:
            highlight_length = len(self.last_keyword)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, highlight_length)
        self.output_text.setTextCursor(cursor)
        viewport_height = self.output_text.viewport().height()
        cursor_rect = self.output_text.cursorRect(cursor)
        scroll_value = self.output_text.verticalScrollBar().value()
        target_scroll = scroll_value + cursor_rect.top() - (viewport_height // 2)
        self.output_text.verticalScrollBar().setValue(int(target_scroll))
        self.output_text.horizontalScrollBar().setValue(0)
        self.output_text.blockSignals(False)

    def navigate_up(self):
        if self.highlight_positions and self.current_highlight_index > 0:
            self.current_highlight_index -= 1
            QTimer.singleShot(0, lambda: self.scroll_to_highlight(self.current_highlight_index))

    def navigate_down(self):
        if self.highlight_positions and self.current_highlight_index < len(self.highlight_positions) - 1:
            self.current_highlight_index += 1
            QTimer.singleShot(0, lambda: self.scroll_to_highlight(self.current_highlight_index))

    def perform_custom_search(self):
        self.keywords_list.clearSelection()
        search_text = self.search_edit.text().strip()
        if not search_text:
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
        text = self.output_text.toPlainText()
        start = 0
        while True:
            start = text.find(search_text, start)
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
            self.scroll_to_highlight(self.current_highlight_index)

    def append_log(self, message, level="INFO"):
        if level == "ERROR":
            colored_message = f'<span style="color:#FF0000;">{message}</span>'
        elif level == "WARNING":
            colored_message = f'<span style="color:#FFA500;">{message}</span>'
        else:
            colored_message = f'<span style="color:#E0E0E0;">{message}</span>'
        self.output_text.append(colored_message)
        self.output_text.moveCursor(QTextCursor.End)

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
        self.workflow_worker.error.connect(self.on_workflow_error)
        self.workflow_worker.finished.connect(self.on_workflow_finished)
        self.workflow_thread.started.connect(self.workflow_worker.run)
        self.workflow_worker.finished.connect(self.workflow_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.workflow_thread.finished.connect(self.workflow_thread.deleteLater)
        self.workflow_thread.start()

    def on_workflow_error(self, error_message):
        self.append_log(f"Error: {error_message}", "ERROR")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.critical(self, "Workflow Error", error_message)
        self.execute_all_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def on_workflow_finished(self):
        self.append_log("Workflow Executed OK", "INFO")
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.information(self, "Success", "Workflow Executed OK")
        self.execute_all_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def copy_output_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_text.toPlainText())
        QMessageBox.setStyleSheet(mod_stylesheets.MESSAGE_BOX_STYLE)
        QMessageBox.information(self, "COPIED", "Copied to Clipboard Successfully")

    def closeEvent(self, event):
        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait()
        event.accept()

    def __del__(self):
        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait()

#-----------------------------------------------------------------------
def main():
    setup_logging()
    app = QApplication(sys.argv)
    config_manager = ConfigManager('C:/CRD/config/current.dat')
    window = SnapshotToSP(config_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()