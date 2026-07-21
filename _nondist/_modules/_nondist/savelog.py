import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import paramiko
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QMessageBox, QProgressDialog
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QTextCursor
from datetime import datetime
import sm_matrix

# Logging Setup
def setup_logging():
    script_dir = os.path.dirname(__file__)
    log_path = os.path.normpath(os.path.join(script_dir, "..", "logs", "savelog.log"))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logging.basicConfig(handlers=[handler], level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.debug(f"Script directory: {script_dir}, Working directory: {os.getcwd()}")

# Parse Key-Value File
def parse_key_value_file(file_path):
    file_path = Path(file_path)
    config = {}
    try:
        if not file_path.exists():
            logging.error(f"Configuration File Not Found: {file_path.resolve()}")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Configuration File Not Found: {file_path}")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f.read().splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    logging.warning(f"Ignoring invalid line: {line}")
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
                logging.debug(f"Read key-value pair: {key.strip()}={value.strip()}")
    except Exception as e:
        logging.error(f"Failed to Read '{file_path}': {e}")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Error")
        msg_box.setText(f"Failed to Read '{file_path}': {e}")
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.exec()
        sys.exit(1)
    return config

# ConfigManager
class ConfigManager:
    def __init__(self, config_path=None):
        if config_path is None:
            script_dir = os.path.dirname(__file__)
            config_path = os.path.normpath(os.path.join(script_dir, "..", "config", "current.dat"))
        self.config = parse_key_value_file(config_path)
        self.sm_ip = self.config.get('Host_IP', '')
        self.sp_ip = self.config.get('SP_IP', '')
        self.sys_id = self.config.get('SID', '')
        self.sm_version = self.config.get('SW_Version', '')
        self.monitor_directory = Path("C:/crd/downloads")
        try:
            import ipaddress
            ipaddress.ip_address(self.sm_ip)
            if self.sp_ip:
                ipaddress.ip_address(self.sp_ip)
            os.makedirs(self.monitor_directory, exist_ok=True)
            test_file = self.monitor_directory / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logging.error(f"Configuration Error: {e}")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Configuration Error: {e}")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            sys.exit(1)
    
    def get_monitor_directory(self): return self.monitor_directory
    def get_sm_ip(self): return self.sm_ip
    def get_sp_ip(self): return self.sp_ip
    def get_sys_id(self): return self.sys_id
    def get_sm_version(self): return self.sm_version

# SSHWorker
class SSHWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    
    def __init__(self, hostname, username, password, commands, check_dir="C:/image/savelog", check_file="savelog.7z", timeout=1200):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.commands = commands
        self.check_dir = check_dir
        self.check_file = check_file
        self.timeout = timeout

    def run(self):
        ssh = None
        try:
            self.log.emit(f"Establishing SSH Connection To {self.hostname}:22 As {self.username}...", "INFO")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.hostname, port=22, username=self.username, password=self.password, timeout=10)
            output = []
            
            # Execute initial commands
            for cmd in self.commands:
                self.log.emit(f"Executing Command On {self.hostname}: {cmd}", "INFO")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                response = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                output.append(f"[{cmd}] {response or error or 'Command executed'}")
            
            # Monitor check_dir for check_file
            start_time = time.time()
            file_found = False
            while time.time() - start_time < self.timeout:
                self.log.emit(f"Checking {self.check_dir} for {self.check_file}...", "INFO")
                stdin, stdout, stderr = ssh.exec_command(f"dir {self.check_dir}")
                response = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                output.append(f"[dir {self.check_dir}] {response or error or 'No output'}")
                if self.check_file.lower() in response.lower():
                    self.log.emit(f"Found {self.check_file} in {self.check_dir}", "INFO")
                    file_found = True
                    break
                time.sleep(45)
            
            if not file_found:
                self.error.emit(f"[{self.hostname}] {self.check_file} not found in {self.check_dir} after timeout")
                return
            
            self.finished.emit("\n".join(output))
        except Exception as e:
            self.error.emit(f"[{self.hostname}] SSH Failed: {str(e)}")
        finally:
            if ssh:
                ssh.close()

# SFTPWorker
class SFTPWorker(QObject):
    finished = pyqtSignal(str, float)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    cancel = pyqtSignal()
    
    def __init__(self, hostname, username, password, remote_dir, local_dir, sys_id, start_time, search_wait=1200):
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

    def cancel_operation(self):
        self._cancelled = True
        self.log.emit("SFTP Cancelled", "INFO")

    def run(self):
        transport = None
        sftp = None
        try:
            self.log.emit(f"Attempting SFTP Connection To {self.hostname}:22 As {self.username}...", "INFO")
            transport = paramiko.Transport((self.hostname, 22))
            transport.connect(username=self.username, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            self.log.emit(f"SFTP Connection Established", "INFO")
            
            savelog_found = False
            start_time = self.start_time
            self.log.emit(f"Monitoring Remote Directory via SFTP: {self.remote_dir}", "INFO")
            while time.time() - start_time < self.search_wait and not self._cancelled:
                try:
                    sftp.chdir(self.remote_dir)
                    log_files = sftp.listdir()
                    self.log.emit(f"Files found in {self.remote_dir}: {', '.join(log_files) if log_files else 'None'}", "INFO")
                    savelog_logs = [f for f in log_files if 'savelog.7z' in f.lower() and sftp.stat(f).st_mtime > start_time]
                    if savelog_logs:
                        savelog_logs_sorted = sorted(savelog_logs, key=lambda x: sftp.stat(x).st_mtime, reverse=True)
                        latest_log = savelog_logs_sorted[0]
                        complete_remote_path = os.path.join(self.remote_dir, latest_log)
                        curr_size = sftp.stat(complete_remote_path).st_size
                        self.log.emit(f"Found {latest_log} in {self.remote_dir}, size: {curr_size} bytes, checking stability...", "INFO")
                        time.sleep(10)
                        if self._cancelled:
                            break
                        new_size = sftp.stat(complete_remote_path).st_size
                        if curr_size == new_size and curr_size != 0:
                            savelog_found = True
                            timestamp = datetime.fromtimestamp(time.time()).strftime('%d%m%Y_%H%M%S')
                            local_filename = f"{self.sys_id}_{timestamp}_savelog.7z"
                            local_path = Path(self.local_dir) / local_filename
                            self.log.emit(f"File {latest_log} is stable, transferring to {local_path}", "INFO")
                            sftp.get(latest_log, str(local_path))
                            self.finished.emit(f"Latest file '{latest_log}' transferred successfully to {local_path}", time.time())
                            break
                        self.log.emit(f"File {latest_log} still being written, waiting...", "INFO")
                    else:
                        self.log.emit(f"Waiting for savelog.7z file in {self.remote_dir}", "INFO")
                except IOError as e:
                    self.log.emit(f"Directory {self.remote_dir} not accessible: {str(e)}", "WARNING")
                    break
                time.sleep(5)
            
            if self._cancelled:
                self.error.emit("Operation cancelled by user")
            elif not savelog_found:
                self.error.emit(f"[{self.hostname}] No stable savelog.7z file found in {self.remote_dir} after timeout")
        
        except Exception as e:
            self.error.emit(f"[{self.hostname}] SFTP Connection Failed: {str(e)}")
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

# SavelogWorkflowWorker
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
        self.monitor_directory = self.config_manager.get_monitor_directory()
        self.sys_id = self.config_manager.get_sys_id()
        self.sm_version = self.config_manager.get_sm_version()
        self.sftp_thread = None
        self.start_time = time.time()
        logging.debug(f"SavelogWorkflowWorker - sm_ip: {self.sm_ip}, sys_id: {self.sys_id}, sm_version: {self.sm_version}")

    def cancel_operation(self):
        if self.sftp_thread and self.sftp_thread.isRunning():
            self.cancel.emit()
            self.sftp_thread.quit()
            self.sftp_thread.wait()
        self.error.emit("Workflow Cancelled")

    def run(self):
        if self.credentials['term_protocol'] != 'ssh':
            self.error.emit("MR_MP6+ requires SSH protocol")
            return
        if self.credentials['file_protocol'] != 'sftp':
            self.error.emit("MR_MP6+ requires SFTP protocol")
            return
        
        commands = ["C:\\MRMPlus\\bin\\savelog-remote"]
        sm_thread = QThread()
        sm_worker = SSHWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            commands=commands,
            check_dir="C:/image/savelog",
            check_file="savelog.7z"
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

    def on_sm_finished(self, message, sm_thread, sm_worker):
        self.log.emit(message, "INFO")
        QTimer.singleShot(5000, self.execute_sftp_operations)

    def on_error(self, error_message, thread, worker):
        self.error.emit(error_message)

    def execute_sftp_operations(self):
        if not self.sys_id:
            self.error.emit("System ID (SID) Is Not Configured")
            return
        remote_dir = "C:/image/savelog"
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

    def on_sftp_finished(self, message, sftp_thread, sftp_worker):
        self.log.emit(message, "INFO")
        self.finished.emit()

# SavelogTool GUI
class SavelogTool(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.setWindowTitle("SAVELOG MP6+ TOOL")
        self.setFixedSize(600, 400)
        self.setStyleSheet("""
            QMainWindow { background-color: #202020; color: white; }
            QPushButton { color: white; background-color: #606060; padding: 10px; font-size: 12pt; border-radius: 4px; }
            QPushButton:hover { background-color: #303030; border: 1px solid white; }
            QPushButton:pressed { background-color: #606060; }
            QTextEdit { color: white; background-color: #202020; font-size: 11pt; border: 1px solid black; padding: 5px; }
            QProgressDialog { background-color: #202020; }
            QProgressDialog QLabel { color: white; }
            QProgressBar { border: 2px solid #555; border-radius: 5px; background-color: #222; text-align: center; }
            QProgressBar::chunk { background-color: #808080; width: 20px; margin: 1px; }
            QMessageBox { background-color: #202020; }
            QMessageBox QLabel { color: white; font-size: 12px; font-weight: bold; }
            QMessageBox QPushButton { background-color: #606060; color: white; font-size: 11px; font-weight: bold; border-radius: 4px; padding: 5px; width: 80px; }
        """)
        self.config_manager = config_manager
        self.sm_version = self.config_manager.get_sm_version()
        
        # Validate version
        import re
        major_version = int(re.match(r"(\d+)", re.sub(r"^(SM V)?", "", self.sm_version)).group(1))
        if "SP" not in self.sm_version or major_version < 6:
            logging.error(f"Invalid version for savelog: {self.sm_version}. Expected MR_MP6+.")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Invalid version: {self.sm_version}. This tool is for MR_MP6+ only.")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            sys.exit(1)
        
        # Load credentials
        try:
            credentials_tuple = sm_matrix.load_credentials()
            self.credentials = {
                'smuser': credentials_tuple[1].get('host_user'),
                'smpass': credentials_tuple[1].get('host_pass'),
                'file_protocol': credentials_tuple[2],
                'term_protocol': credentials_tuple[3]
            }
            if self.credentials['term_protocol'] != 'ssh' or self.credentials['file_protocol'] != 'sftp':
                logging.error(f"Invalid protocols for MR_MP6+: file_protocol={self.credentials['file_protocol']}, term_protocol={self.credentials['term_protocol']}")
                msg_box = QMessageBox()
                msg_box.setWindowTitle("Error")
                msg_box.setText("MR_MP6+ requires SSH and SFTP protocols")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.exec()
                sys.exit(1)
        except Exception as e:
            logging.error(f"Failed to load credentials: {str(e)}")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Failed to load credentials: {str(e)}")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            sys.exit(1)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.main_layout.addWidget(self.output_text)
        button_layout = QHBoxLayout()
        self.main_layout.addLayout(button_layout)
        self.execute_button = QPushButton("SAVELOG")
        self.execute_button.clicked.connect(self.execute_workflow)
        button_layout.addWidget(self.execute_button)
        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.clicked.connect(self.cancel_workflow)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

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
        self.execute_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.output_text.clear()
        self.progress = QProgressDialog("WORKING (Be Patient, May Take Several Minutes)", None, 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setRange(0, 0)
        self.progress.setStyleSheet("""
            QProgressBar { border: 2px solid #555; border-radius: 5px; background-color: #222; text-align: center; }
            QProgressBar::chunk { background-color: #808080; width: 20px; margin: 1px; }
            QProgressDialog QLabel { color: white; }
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

    def cancel_workflow(self):
        if hasattr(self, 'workflow_worker'):
            self.workflow_worker.cancel_operation()
        self.progress.close()
        self.append_log("Workflow Cancelled", "INFO")
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def on_workflow_error(self, error_message):
        self.progress.close()
        self.append_log(f"Error: {error_message}", "ERROR")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Workflow Error")
        msg_box.setText(error_message)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.exec()
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def on_workflow_finished(self):
        self.progress.close()
        self.append_log("Savelog Downloaded OK", "INFO")
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Success")
        msg_box.setText("Savelog Downloaded OK")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec()
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def closeEvent(self, event):
        if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
            self.workflow_thread.quit()
            self.workflow_thread.wait()
        event.accept()

# Main
def main():
    setup_logging()
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    window = SavelogTool(config_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()