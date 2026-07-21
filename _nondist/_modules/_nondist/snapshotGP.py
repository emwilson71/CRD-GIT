import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import telnetlib
import ftplib
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
    log_path = os.path.normpath(os.path.join(script_dir, "..", "logs", "snapshotMP35.log"))
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

# TelnetWorker
class TelnetWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)
    
    def __init__(self, hostname, username, password, commands):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.commands = commands

    def run(self):
        try:
            self.log.emit(f"Establishing Telnet Connection To {self.hostname}:23 As {self.username}...", "INFO")
            tn = telnetlib.Telnet(self.hostname, 23, timeout=10)
            tn.read_until(b"login: ", timeout=10)
            tn.write(f"{self.username}\n".encode())
            tn.read_until(b"Password: ", timeout=10)
            tn.write(f"{self.password}\n".encode())
            output = []
            for cmd in self.commands:
                self.log.emit(f"Executing Command On {self.hostname}: {cmd}", "INFO")
                tn.write(f"{cmd}\n".encode())
                response = tn.read_until(b"\n", timeout=15).decode().strip()
                output.append(f"[{cmd}] {response or 'Command executed'}")
            tn.close()
            self.finished.emit("\n".join(output))
        except Exception as e:
            self.error.emit(f"[{self.hostname}] Telnet Failed: {str(e)}")
        finally:
            if 'tn' in locals():
                tn.close()

# FTPWorker
class FTPWorker(QObject):
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

    def cancel_operation(self):
        self._cancelled = True
        self.log.emit("FTP Cancelled", "INFO")

    def run(self):
        try:
            self.log.emit(f"Monitoring Remote Directory via FTP: {self.remote_dir}", "INFO")
            start_time = self.start_time
            savelog_found = False
            ftp = None
            while time.time() - start_time < self.search_wait and not self._cancelled:
                if not ftp:
                    self.log.emit(f"Establishing FTP Connection To {self.hostname}:21 As {self.username}...", "INFO")
                    ftp = ftplib.FTP()
                    ftp.connect(self.hostname, 21)
                    ftp.login(self.username, self.password)
                
                try:
                    ftp.cwd(self.remote_dir)
                    log_files = ftp.nlst()
                    self.log.emit(f"Files found: {', '.join(log_files) if log_files else 'None'}", "INFO")
                    savelog_logs = [f for f in log_files if 'savelog.zip' in f.lower() and ftp.voidcmd(f"MDTM {f}")[4:].strip() > datetime.fromtimestamp(start_time).strftime('%Y%m%d%H%M%S')]
                    if savelog_logs:
                        savelog_logs_sorted = sorted(savelog_logs, key=lambda x: ftp.voidcmd(f"MDTM {x}")[4:].strip(), reverse=True)
                        latest_log = savelog_logs_sorted[0]
                        complete_remote_path = os.path.join(self.remote_dir, latest_log)
                        curr_size = ftp.size(complete_remote_path)
                        self.log.emit(f"Found {latest_log}, size: {curr_size} bytes, checking stability...", "INFO")
                        time.sleep(10)
                        if self._cancelled:
                            break
                        new_size = ftp.size(complete_remote_path)
                        if curr_size == new_size and curr_size != 0:
                            savelog_found = True
                            timestamp = datetime.fromtimestamp(time.time()).strftime('%d%m%Y_%H%M%S')
                            local_filename = f"{self.sys_id}_{timestamp}_savelog.zip"
                            local_path = Path(self.local_dir) / local_filename
                            self.log.emit(f"File {latest_log} is stable, transferring to {local_path}", "INFO")
                            with open(local_path, 'wb') as local_file:
                                ftp.retrbinary(f"RETR {latest_log}", local_file.write)
                            self.finished.emit(f"Latest file '{latest_log}' transferred successfully to {local_path}", time.time())
                            break
                        self.log.emit(f"File {latest_log} still being written, waiting...", "INFO")
                    else:
                        self.log.emit("Waiting for savelog.zip file on SM", "INFO")
                except ftplib.error_perm:
                    self.log.emit(f"Directory {self.remote_dir} not accessible, retrying...", "WARNING")
                time.sleep(5)
            
            if self._cancelled:
                self.error.emit("Operation cancelled by user")
            elif not savelog_found:
                self.error.emit(f"[{self.hostname}] No stable savelog.zip file found on SM after timeout")
            
            if ftp:
                ftp.quit()
        except ftplib.error_perm:
            self.error.emit(f"[{self.hostname}] FTP Authentication Failed")
        except FileNotFoundError as e:
            self.error.emit(f"[{self.hostname}] File Not Found: {str(e)}")
        except Exception as e:
            self.error.emit(f"[{self.hostname}] FTP Transfer Failed: {str(e)}")
        finally:
            if ftp:
                ftp.quit()

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
        self.ftp_thread = None
        self.start_time = time.time()
        logging.debug(f"SavelogWorkflowWorker - sm_ip: {self.sm_ip}, sys_id: {self.sys_id}, sm_version: {self.sm_version}")

    def cancel_operation(self):
        if self.ftp_thread and self.ftp_thread.isRunning():
            self.cancel.emit()
            self.ftp_thread.quit()
            self.ftp_thread.wait()
        self.error.emit("Workflow Cancelled")

    def run(self):
        if self.credentials['term_protocol'] != 'telnet':
            self.error.emit("MR_MP3-5 requires Telnet protocol")
            return
        if self.credentials['file_protocol'] != 'ftp':
            self.error.emit("MR_MP3-5 requires FTP protocol")
            return
        
        commands = ["unknown_savelog_command"]
        remote_dir = "C:\\tmp"
        
        sm_thread = QThread()
        sm_worker = TelnetWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            commands=commands
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
        QTimer.singleShot(5000, self.execute_ftp_operations)

    def on_error(self, error_message, thread, worker):
        self.error.emit(error_message)

    def execute_ftp_operations(self):
        if not self.sys_id:
            self.error.emit("System ID (SID) Is Not Configured")
            return
        remote_dir = "C:/tmp"
        local_dir = str(self.monitor_directory)
        self.ftp_thread = QThread()
        ftp_worker = FTPWorker(
            hostname=self.sm_ip,
            username=self.credentials['smuser'],
            password=self.credentials['smpass'],
            remote_dir=remote_dir,
            local_dir=local_dir,
            sys_id=self.sys_id,
            start_time=self.start_time
        )
        ftp_worker.moveToThread(self.ftp_thread)
        ftp_worker.log.connect(self.log.emit)
        ftp_worker.cancel.connect(ftp_worker.cancel_operation)
        self.cancel.connect(ftp_worker.cancel_operation)
        ftp_worker.finished.connect(lambda msg, mtime: self.on_ftp_finished(msg, self.ftp_thread, ftp_worker))
        ftp_worker.error.connect(lambda err: self.on_error(err, self.ftp_thread, ftp_worker))
        self.ftp_thread.started.connect(ftp_worker.run)
        ftp_worker.finished.connect(self.ftp_thread.quit)
        ftp_worker.finished.connect(ftp_worker.deleteLater)
        self.ftp_thread.finished.connect(self.ftp_thread.deleteLater)
        self.ftp_thread.start()

    def on_ftp_finished(self, message, ftp_thread, ftp_worker):
        self.log.emit(message, "INFO")
        self.finished.emit()

# SnapshotMP35 GUI
class SnapshotMP35(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.setWindowTitle("SNAPSHOT MP3-5 TOOL")
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
            QProgressBar::chunk { background-color: lightgray; width: 20px; margin: 1px; }
            QMessageBox { background-color: #202020; }
            QMessageBox QLabel { color: white; font-size: 12px; font-weight: bold; }
            QMessageBox QPushButton { background-color: #606060; color: white; font-size: 11px; font-weight: bold; border-radius: 4px; padding: 5px; width: 80px; }
        """)
        self.config_manager = config_manager
        self.sm_version = self.config_manager.get_sm_version()
        
        # Validate version
        if "SP" not in self.sm_version or not int(re.match(r"(\d+)", re.sub(r"^(SM V)?", "", self.sm_version)).group(1)) in [3, 4, 5]:
            logging.error(f"Invalid version for snapshotMP35: {self.sm_version}. Expected MR_MP3-5.")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Invalid version: {self.sm_version}. This tool is for MR_MP3-5 only.")
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
            if self.credentials['term_protocol'] != 'telnet' or self.credentials['file_protocol'] != 'ftp':
                logging.error(f"Invalid protocols for MR_MP3-5: file_protocol={self.credentials['file_protocol']}, term_protocol={self.credentials['term_protocol']}")
                msg_box = QMessageBox()
                msg_box.setWindowTitle("Error")
                msg_box.setText("MR_MP3-5 requires Telnet and FTP protocols")
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
        self.execute_button = QPushButton("SNAPSHOT MP3-5")
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
            QProgressBar::chunk { background-color: lightgray; width: 20px; margin: 1px; }
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
    window = SnapshotMP35(config_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()