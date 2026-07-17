# ---------------------------------------------------------------------
"""
savelog module
emwilson71@yahoo.com 06042025
Finalized for savelog V6: 
"""
#-----------------------------------------------------------------------
import json
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import time
import paramiko
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,QProgressBar,
    QTextEdit, QHBoxLayout, QPushButton, QMessageBox,
    QLabel, QProgressDialog
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QTextCursor
from cryptography.fernet import Fernet
import mod_stylesheets as styles
from mod_logging import CRDLogger
# ---------------------------------------------------------------------
def parse_key_value_file(file_path):
    file_path = Path(file_path)
    config = {}
    try:
        if not file_path.exists():
            logging.error(f"[MOD SAVELOG v6+] Configuration File Not Found: {file_path.resolve()}")
            sys.exit(1)
        if not os.access(file_path, os.R_OK):
            logging.error(f"[MOD SAVELOG v6+] No Read Permission {file_path}")
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    logging.warning(f"[MOD SAVELOG v6+] Ignoring Invalid Line: {line}")
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
                logging.debug(f"[MOD SAVELOG v6+] Read key-value pair: {key.strip()}={value.strip()}")
    except UnicodeDecodeError as e:
        logging.error(f"[MOD SAVELOG v6+] Failed to Decode '{file_path}' as UTF-8: {e}")
        msg_box = QMessageBox()
        sys.exit(1)
    except Exception as e:
        logging.error(f"[MOD SAVELOG v6+] Failed to Read '{file_path}': {e}")
        sys.exit(1)
    return config

# ---------------------------------------------------------------------
def read_credentials(credential_path=None):
    script_dir = os.path.dirname(__file__)
    key_path = os.path.normpath(os.path.join(script_dir, "..", "config", "user.key"))
    credential_path = os.path.normpath(os.path.join(script_dir, "..", "config", "user.enc"))

    if not os.path.exists(key_path):
        logging.error(f"[MOD SAVELOG v6+] Fernet Key Not Found: {key_path}")
        sys.exit(1)
    if not os.path.exists(credential_path):
        logging.error(f"[MOD SAVELOG v6+] Credentials File Not Found: {credential_path}")
        sys.exit(1)

    try:
        with open(key_path, 'rb') as f:
            key = f.read()
        try:
            fernet = Fernet(key)
        except ValueError as e:
            logging.error(f"[MOD SAVELOG v6+] Invalid Fernet key in '{key_path}': {e}")

            sys.exit(1)
        with open(credential_path, 'rb') as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        data = json.loads(decrypted_data.decode('utf-8'))
    except json.JSONDecodeError as e:
        logging.error(f"[MOD SAVELOG v6+] Invalid JSON in Decrypted '{credential_path}': {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"[MOD SAVELOG v6+] Failed to decrypt or read '{credential_path}': {e}")
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
        logging.error(f"[MOD SAVELOG v6+] Error Parsing Credentials: {e}")
        sys.exit(1)

    expected_keys = ['smuser', 'smpass', 'spuser', 'sppass']
    for key in expected_keys:
        if not config.get(key):
            logging.error(f"[MOD SAVELOG v6+] Missing '{key}' in credentials file")
            sys.exit(1)
    logging.debug(f"[MOD SAVELOG v6+] Loaded credentials: {config}")
    return config

# ---------------------------------------------------------------------
class ConfigManager:
    def __init__(self, config_path=None): 
        if config_path is None:
            script_dir = os.path.dirname(__file__)
            config_path = os.path.normpath(os.path.join(script_dir, "..", "config", "current.dat"))
        logging.debug(f"[MOD SAVELOG v6+] Loading Config From: {config_path}")
        self.config = self.read_config(config_path)
        self.sm_ip = self.config.get('Host_IP', '')
        self.sp_ip = self.config.get('SP_IP', '')
        self.sys_id = self.config.get('SID', '')
        self.sm_version = self.config.get('SW_Version', 'V6')
        self.monitor_directory = Path('C:/crd/downloads')
        self.remote_dir = 'C:/image/savelog'
        self.validate_config()
# ---------------------------------------------------------------------
    def read_config(self, config_path):
        return parse_key_value_file(config_path)
# ---------------------------------------------------------------------
    def validate_config(self):
        try:
            import ipaddress
            ipaddress.ip_address(self.sm_ip)
            if self.sp_ip:
                ipaddress.ip_address(self.sp_ip)
        except ValueError:
            logging.error(f"[MOD SAVELOG v6+] Invalid IP Address: sm_ip={self.sm_ip}, sp_ip={self.sp_ip}")
            sys.exit(1)

        if not self.sys_id or not all(c.isalnum() or c == '-' for c in self.sys_id):
            logging.error(f"[MOD SAVELOG v6+] Invalid System ID: {self.sys_id}")
            sys.exit(1)

        try:
            os.makedirs(self.monitor_directory, exist_ok=True)
            test_file = self.monitor_directory / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logging.error(f"[MOD SAVELOG v6+] Cannot Write '{self.monitor_directory}': {e}")
            sys.exit(1)
# ---------------------------------------------------------------------
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
# ---------------------------------------------------------------------
class SSHWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

    def __init__(self, hostname, username, password, command):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.command = command

    def run(self):
        try:
            self.log.emit(f"[MOD SAVELOG v6+] Establishing SSH Connection To {self.hostname} As {self.username}", "INFO")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=self.hostname, username=self.username, password=self.password)

            self.log.emit(f"[MOD SAVELOG v6+] Executing Command On {self.hostname} {self.command}", "INFO")
            stdin, stdout, stderr = client.exec_command(self.command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                output = stdout.read().decode('utf-8').strip()
                self.finished.emit(f"[MOD SAVELOG v6+] [{self.hostname}] {output or 'Command Executed Successfully'}")
            else:
                error = stderr.read().decode('utf-8').strip() or "SSH error."
                self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] Command Failed: {error}")

            client.close()
        except paramiko.AuthenticationException:
            self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] Authentication Failed")
        except Exception as e:
            self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] SSH Error: {str(e)}")
# ---------------------------------------------------------------------
class SFTPWorker(QObject):
    finished = pyqtSignal(str, float)  
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    cancel = pyqtSignal()

    def __init__(self, hostname, username, password, remote_dir, local_dir, sys_id, start_time, search_wait=900):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.remote_dir = remote_dir
        self.local_dir = local_dir
        self.sys_id = sys_id
        self.start_time = start_time
        self.search_wait = search_wait
        self._cancelled = False
# ---------------------------------------------------------------------
    def cancel_operation(self):
        self._cancelled = True
        self.log.emit("[MOD SAVELOG v6+] SFTP Cancelled", "INFO")
# ---------------------------------------------------------------------
    def run(self):
        try:
            self.log.emit(f"[MOD SAVELOG v6+] Monitoring Remote Directory: {self.remote_dir}", "INFO")
            start_time = self.start_time
            savelog_found = False
            transport = None
            sftp = None
            while time.time() - start_time < self.search_wait and not self._cancelled:
                if not transport:
                    self.log.emit(f"[MOD SAVELOG v6+] Establishing SFTP Connection To {self.hostname}", "INFO")
                    transport = paramiko.Transport((self.hostname, 22))
                    transport.connect(username=self.username, password=self.password)
                    sftp = paramiko.SFTPClient.from_transport(transport)

                self.log.emit(f"Listing Files in Remote Directory: {self.remote_dir}", "INFO")
                try:
                    log_files = sftp.listdir(self.remote_dir)
                    self.log.emit(f"[MOD SAVELOG v6+] Files found: {', '.join(log_files) if log_files else 'None'}", "INFO")
                except FileNotFoundError:
                    self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] Directory {self.remote_dir} does not exist")
                    break

                savelog_logs = [
                    f for f in log_files
                    if 'savelog.7z' in f.lower() and sftp.stat(os.path.join(self.remote_dir, f)).st_mtime > start_time
                ]
                if savelog_logs:
                    savelog_logs_sorted = sorted(
                        savelog_logs,
                        key=lambda x: sftp.stat(os.path.join(self.remote_dir, x)).st_mtime,
                        reverse=True
                    )
                    latest_log = savelog_logs_sorted[0]
                    complete_remote_path = os.path.join(self.remote_dir, latest_log)
                    file_stat = sftp.stat(complete_remote_path)
                    mtime = file_stat.st_mtime

                    prev_size = -1
                    curr_size = file_stat.st_size
                    self.log.emit(f"[MOD SAVELOG v6+] Found {latest_log}, size: {curr_size} bytes", "INFO")
                    time.sleep(10)  
                    if self._cancelled:
                        break
                    new_size = sftp.stat(complete_remote_path).st_size
                    if curr_size == new_size and curr_size != 0:  
                        savelog_found = True
                        timestamp = datetime.fromtimestamp(mtime).strftime('%d%m%Y_%H%M%S')
                        local_filename = f"{self.sys_id}_{timestamp}_savelog.7z"
                        local_path = Path(self.local_dir) / local_filename
                        self.log.emit(f"[MOD SAVELOG v6+] File {latest_log} is Complete, Transferring to {local_path}", "INFO")
                        sftp.get(complete_remote_path, str(local_path))
                        self.finished.emit(f"[MOD SAVELOG v6+] Latest file '{latest_log}' Transferred Successfully", mtime)
                        break
                    prev_size = curr_size
                    self.log.emit(f"[MOD SAVELOG v6+] File {latest_log} still being written, waiting...", "INFO")
                else:
                    self.log.emit("[MOD SAVELOG v6+] Waiting for savelog.7z file on SM", "INFO")
                time.sleep(5)
            
            if self._cancelled:
                self.error.emit("[MOD SAVELOG v6+] Operation cancelled by user")
            elif not savelog_found:
                self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] No stable savelog.7z file found on SM after timeout")
            
            if sftp:
                sftp.close()
            if transport:
                transport.close()
        except paramiko.AuthenticationException:
            self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] Authentication Failed")
        except FileNotFoundError as e:
            self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] Savelog File Not Found: {str(e)}")
        except Exception as e:
            self.error.emit(f"[MOD SAVELOG v6+] [{self.hostname}] SFTP Transfer Failed: {str(e)}")
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
# ---------------------------------------------------------------------
class SavelogWorkflowWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    cancel = pyqtSignal()

    def __init__(self, config_manager, credentials):
        super().__init__()
        self.config_manager = config_manager
        self.credentials = credentials
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.sys_id = self.config_manager.get_sys_id()
        self.sm_version = self.config_manager.get_sm_version()
        self.sftp_thread = None
        self.start_time = time.time()
        logging.debug(f"[MOD SAVELOG v6+] sm_ip: {self.sm_ip}, sp_ip: {self.sp_ip}, sys_id: {self.sys_id}, sm_version: {self.sm_version}")
# ---------------------------------------------------------------------
    def cancel_operation(self):
        if self.sftp_thread and self.sftp_thread.isRunning():
            self.cancel.emit()
            self.sftp_thread.quit()
            self.sftp_thread.wait()
        self.error.emit("Workflow Cancelled")
# ---------------------------------------------------------------------
    def run(self):
        sm_command = 'C:\\MRMPlus\\bin\\savelog-remote'
        sm_thread = QThread()
        
# For V6, use SSH
        sm_worker = SSHWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            command=sm_command
        )
        sm_worker.moveToThread(sm_thread)
        sm_worker.log.connect(self.log.emit)
        sm_worker.finished.connect(lambda msg: self.on_sm_finished(msg, sm_thread, sm_worker))
        sm_worker.error.connect(lambda err: self.on_error(err, sm_thread, sm_worker))
        sm_thread.started.connect(sm_worker.run)
        sm_worker.finished.connect(sm_thread.quit)
        sm_worker.finished.connect(sm_worker.deleteLater)
        sm_thread.finished.connect(sm_thread.deleteLater)
        sm_thread.start()
# ---------------------------------------------------------------------
    def on_sm_finished(self, message, sm_thread, sm_worker):
        self.log.emit(message, "INFO")
        QTimer.singleShot(5000, self.execute_sm_operations)
# ---------------------------------------------------------------------
    def on_error(self, error_message, thread, worker):
        self.error.emit(error_message)
# ---------------------------------------------------------------------
    def execute_sm_operations(self):
        if not self.sys_id:
            self.error.emit("System ID (SID) Is Not Configured")
            return

        remote_dir = self.config_manager.remote_dir
        local_dir = str(self.monitor_directory)

        self.sftp_thread = QThread()
        sftp_worker = SFTPWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            remote_dir=remote_dir,
            local_dir=local_dir,
            sys_id=self.sys_id,
            start_time=self.start_time
        )
        sftp_worker.moveToThread(self.sftp_thread)
        sftp_worker.log.connect(self.log.emit)
        sftp_worker.cancel.connect(sftp_worker.cancel_operation)
        self.cancel.connect(sftp_worker.cancel_operation)
        sftp_worker.finished.connect(lambda msg, mtime: self.on_sftp_finished(msg, self.sftp_thread, sftp_worker))
        sftp_worker.error.connect(lambda err: self.on_error(err, self.sftp_thread, sftp_worker))
        self.sftp_thread.started.connect(sftp_worker.run)
        sftp_worker.finished.connect(self.sftp_thread.quit)
        sftp_worker.finished.connect(sftp_worker.deleteLater)
        self.sftp_thread.finished.connect(self.sftp_thread.deleteLater)
        self.sftp_thread.start()
# ---------------------------------------------------------------------
    def on_sftp_finished(self, message, sftp_thread, sftp_worker):
        self.log.emit(message, "INFO")
        self.finished.emit()
# ---------------------------------------------------------------------
class SavelogTool(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.setWindowTitle("SAVELOG TOOL")
        self.setFixedSize(600, 400)
        self.setStyleSheet(styles.DIALOG_STYLE)

# SETUP UI
        self.config_manager = config_manager
        self.credentials = read_credentials()
        self.sm_ip = self.config_manager.get_sm_ip()
        self.sp_ip = self.config_manager.get_sp_ip()
        self.monitor_directory = self.config_manager.get_monitor_directory()

        logging.debug(f"SavelogTool - sm_ip: {self.sm_ip}, sp_ip: {self.sp_ip}, sys_id: {self.config_manager.get_sys_id()}")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(styles.TEXT_EDIT_STYLE)
        self.main_layout.addWidget(self.output_text)

        button_layout = QHBoxLayout()
        self.main_layout.addLayout(button_layout)
        self.execute_button = QPushButton("SAVELOG")
        self.execute_button.setStyleSheet(styles.BUTTON_STYLE)
        self.execute_button.clicked.connect(self.execute_workflow)
        button_layout.addWidget(self.execute_button)
        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.setStyleSheet(styles.BUTTON_STYLE)
        self.cancel_button.clicked.connect(self.cancel_workflow)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)
# ---------------------------------------------------------------------
    def append_log(self, message, level="INFO"):
        if level == "ERROR":
            colored_message = f'<span style="color:#FF0000;">{message}</span>'
        elif level == "WARNING":
            colored_message = f'<span style="color:#FFA500;">{message}</span>'
        else:
            colored_message = f'<span style="color:#E0E0E0;">{message}</span>'
        self.output_text.append(colored_message)
        self.output_text.moveCursor(QTextCursor.End)
# ---------------------------------------------------------------------
    def execute_workflow(self):
        self.execute_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.output_text.clear()
        self.progress = QProgressDialog("WORKING (Be Patient, May Take Several Minutes)", None, 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setRange(0,0)  
        self.progress.setValue(50)      
        self.progress.setStyleSheet("""
            QProgressDialog { background-color: #202020; }
            QProgressDialog QLabel { color: white; }
            QProgressDialog QProgressBar { 
                border: 2px solid #555; 
                border-radius: 5px; 
                background-color: #222; 
                text-align: center; 
                min-height: 20px; 
                max-height: 20px; 
            }
            QProgressDialog QProgressBar::chunk { 
                background-color: lightgray; 
                width: 20px; 
                margin: 1px; 
            }
        """)
        self.progress.show()

        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait()

        self.workflow_thread = QThread()
        self.workflow_worker = SavelogWorkflowWorker(self.config_manager, self.credentials)
        self.workflow_worker.moveToThread(self.workflow_thread)

        self.workflow_worker.log.connect(self.append_log)
        self.workflow_worker.error.connect(self.on_workflow_error)
        self.workflow_worker.finished.connect(self.on_workflow_finished)
        self.workflow_thread.started.connect(self.workflow_worker.run)
        self.cancel_button.clicked.connect(self.workflow_worker.cancel_operation)

        self.workflow_worker.finished.connect(self.workflow_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.workflow_thread.finished.connect(self.workflow_thread.deleteLater)

        self.workflow_thread.start()
# ---------------------------------------------------------------------
    def cancel_workflow(self):
        if hasattr(self, 'workflow_worker'):
            self.workflow_worker.cancel_operation()
        self.progress.close()
        self.append_log("[MOD SAVELOG v6+] Workflow Cancelled", "INFO")
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
# ---------------------------------------------------------------------
    def on_workflow_error(self, error_message):
        self.progress.close()
        self.append_log(f"[MOD SAVELOG v6+] Error: {error_message}", "ERROR")
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
# ---------------------------------------------------------------------
    def on_workflow_finished(self):
        self.progress.close()
        self.append_log("Savelog Downloaded OK", "INFO")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Success")
        msg_box.setText("Savelog Downloaded OK")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet(styles.MESSAGE_BOX_STYLE)
        msg_box.exec()
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

# ---------------------------------------------------------------------
def main():
    app_logger = CRDLogger("CRD").get_logger()
    app_logger.info("[MOD SAVELOG v6+] Starting Savelog Tool")
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  
    config_manager = ConfigManager()
    window = SavelogTool(config_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
# ---------------------------------------------------------------------
