# --------------------------------------------------------------
# v2.31 Log Purge Tool - CRD
# 1/30/26 (ew)
# CRD Only, Check for v2.3x and Ping
# Version 1.02 Updated 01/30/26   
# --------------------------------------------------------------
import sys, os, json, telnetlib
import ftplib, time
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTextEdit, QLabel, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPalette, QColor
# --------------------------------------------------------------
CONFIG_DIR = Path.cwd().parent / "config"
USER_KEY_PATH = CONFIG_DIR / "user.key"
USER_ENC_PATH = CONFIG_DIR / "user.enc"
CURRENT_DAT_PATH = CONFIG_DIR / "current.dat"
#COMMANDS_JSON_PATH = CONFIG_DIR / "231commands.json"
# --------------------------------------------------------------
class PurgeWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(int)
    sitename_signal = pyqtSignal(str)
    sid_signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.is_running = True
    def run(self):
        tn = None
        try:
            self.log_signal.emit("Reading Encryption Key and Credentials")
            if not USER_KEY_PATH.exists() or not USER_ENC_PATH.exists():
                raise FileNotFoundError("user.key or user.enc missing")
            with open(USER_KEY_PATH, "rb") as f:
                key = f.read()
            fernet = Fernet(key)
            with open(USER_ENC_PATH, "rb") as f:
                encrypted = f.read()
            decrypted = fernet.decrypt(encrypted).decode('utf-8')
            config = json.loads(decrypted)
            creds = config.get("MR_MP2", {}).get("credentials", {})
            host_user = creds.get("host_user", "").strip()
            host_pass = creds.get("host_pass", "").strip()
            port = 23
            self.log_signal.emit(f"User: '{host_user}'")
            self.log_signal.emit("Reading current.dat")
            if not CURRENT_DAT_PATH.exists():
                raise FileNotFoundError("current.dat not Found")
            current = {}
            with open(CURRENT_DAT_PATH, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        current[k.strip()] = v.strip()
            host_ip = current.get("Host_IP", "").strip()
            site_name = current.get("SiteName", "")
            sid = current.get("SID", "")
            sw_version = current.get("SW_Version", "").strip()
            self.sitename_signal.emit(site_name)
            self.sid_signal.emit(sid)
# IGNORE VERSION FOR NOW
            """
            if not sw_version.upper().startswith("V2.3"):
                error_msg = (
                    f"This Tool is Only Compatible with V2.3.x Versions.\n\n"
                    f"Found SW_Version: {sw_version}\n\n"
                    "Exiting the Program"
                )
                self.log_signal.emit("ERROR: Incompatible Software Version")
                self.log_signal.emit(f"Required V2.3x Found {sw_version}")
                self.finished_signal.emit(False, error_msg)
                return
            self.log_signal.emit(f"Software Version Check: OK ({sw_version})")
            """
            if not host_ip:
                raise ValueError("Host_IP Not Found in current.dat")
# PING CHECK
            self.log_signal.emit(f"Checking if Host is Reachable: {host_ip} ...")
            import subprocess
            import platform
            def ping_host(ip):
                param = '-n' if platform.system().lower() == 'windows' else '-c'
                try:
                    subprocess.check_output(
                        ["ping", param, "1", "-w", "3000", ip],
                        stderr=subprocess.STDOUT,
                        timeout=5
                    )
                    return True
                except Exception:
                    return False
            if not ping_host(host_ip):
                error_msg = (
                    f"Host is not Reachable ({host_ip})\n"
                    "Exiting the Program"
                )
                self.log_signal.emit(f"Host {host_ip} is NOT Reachable")
                self.finished_signal.emit(False, error_msg)
                return
            self.log_signal.emit(f"Host {host_ip} is Reachable")
            self.log_signal.emit(f"Target: {site_name} (SID: {sid})")
            self.log_signal.emit(f"Connecting to {host_ip}:{port}")
            self.log_signal.emit("Opening Telnet Socket")
            tn = telnetlib.Telnet(host_ip, port, timeout=20)
            self.progress_signal.emit(10)
            self.log_signal.emit("Socket Opened")
            self.log_signal.emit("Waiting for Response (12s)")
            try:
                banner = tn.read_until(b"\n", timeout=12).decode('ascii', errors='replace').strip()
                self.log_signal.emit(f"{repr(banner)}")
            except EOFError:
                self.log_signal.emit("(Connection Error)")
            self.log_signal.emit("Waiting for Login Prompt")
            login_data = tn.read_until(b"login: ", timeout=15).decode('ascii', errors='replace')
            if "login:" not in login_data.lower():
                raise ConnectionError("No Login Prompt Received")
            self.log_signal.emit("Sending User Name")
            tn.write(host_user.encode('ascii') + b"\r\n")
            self.progress_signal.emit(30)
            self.log_signal.emit("Waiting for Password Prompt")
            pw_data = tn.read_until(b"Password: ", timeout=12).decode('ascii', errors='replace')
            if "password:" not in pw_data.lower():
                raise ConnectionError("No Password Prompt Received")
            self.log_signal.emit("Sending Password")
            tn.write(host_pass.encode('ascii') + b"\r\n")
            self.progress_signal.emit(50)
            self.log_signal.emit("Waiting for Shell Prompt")
            prompt_data = tn.read_until(b">", timeout=20).decode('ascii', errors='replace')
            lines = [line.strip() for line in prompt_data.splitlines() if line.strip() and "Welcome to Microsoft Telnet Server" not in line]
            if all(p not in prompt_data for p in [">", "#", "$"]):
                raise ConnectionError("No Command Prompt After Login")
            self.log_signal.emit("Login Successful")
            self.progress_signal.emit(65)
# BATCH COMMANDS
            self.log_signal.emit("Loading Commands From commands.json")
            if not COMMANDS_JSON_PATH.exists():
                raise FileNotFoundError("commands.json Not Found")
            with open(COMMANDS_JSON_PATH, "r") as f:
                commands = json.load(f)
            self.log_signal.emit(f"Loaded {len(commands)} commands")
            output_lines = []
            logpurge_content = []
            for i, cmd in enumerate(commands, 1):
                if not self.is_running:
                    self.log_signal.emit("Purge Cancelled")
                    break
               
                self.log_signal.emit(f"[{i}/{len(commands)}] {cmd}")
                tn.write(cmd.encode('ascii') + b"\r\n")
               
                resp = tn.read_until(b">", timeout=15).decode('ascii', errors='replace').rstrip()
                clean_resp = resp.replace(cmd, '').strip()
                if clean_resp and ">" not in clean_resp:
                    self.log_signal.emit(" → " + clean_resp)
                progress = 65 + int(25 * i / len(commands))
                self.progress_signal.emit(min(90, progress))
            self.log_signal.emit("Waiting 3 Seconds")
            time.sleep(3)
            self.log_signal.emit("Closing Telnet session")
            try:
                tn.write(b"exit\r\n")
                tn.read_eager()
            except:
                pass
            tn.close()
            tn = None
            self.progress_signal.emit(95)
            final_content = self._download_log_via_ftp(host_ip, host_user, host_pass)
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, final_content)
           
        except Exception as e:
            err = f"ERROR: {type(e).__name__}: {str(e)}"
            self.log_signal.emit(err)
            if tn:
                try:
                    last = tn.read_eager().decode('ascii', errors='replace')
                    if last.strip():
                        self.log_signal.emit(f"Last output: {repr(last)}")
                except:
                    pass
            self.finished_signal.emit(False, err)
        finally:
            if tn:
                try:
                    tn.close()
                except:
                    pass
# --------------------------------------------------------------
    def _download_log_via_ftp(self, host: str, user: str, password: str) -> str:
        local_dir = Path("C:\\temp")
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / "LogPurge.txt"
       
        self.log_signal.emit("Opening FTP connection for log download...")
        self.progress_signal.emit(97)
       
        try:
            with ftplib.FTP(host, user, password, timeout=15) as ftp:
                ftp.set_pasv(True)
                self.log_signal.emit("FTP login successful")
               
                remote_path = "study/Utility/LogPurge.txt"
                with open(local_path, "wb") as f:
                    ftp.retrbinary(f"RETR {remote_path}", f.write)
               
                self.log_signal.emit(f"Downloaded {local_path}")
                self.progress_signal.emit(99)
                return local_path.read_text(encoding="utf-8", errors="replace").strip()
               
        except ftplib.all_errors as e:
            err = f"FTP download failed: {str(e)}"
            self.log_signal.emit(err)
            return f"[FTP ERROR] {err}\n\n(File May Exist on Remote System)"
        except Exception as e:
            err = f"Unexpected FTP error: {str(e)}"
            self.log_signal.emit(err)
            return f"[ERROR] {err}"
# --------------------------------------------------------------
class LogPurgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("v2.31 Log Purge Tool")
        self.resize(820, 580)
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e1e; color: #e0e0e0; }
            QTextEdit { background-color: #252526; border: 1px solid #444;
                        font-family: Consolas, monospace; font-size: 13px; }
            QLabel { color: #ffffff; }
            QProgressBar { background-color: #555; border: 1px solid #555;
                            text-align: center; color: #aaa; }
            QProgressBar::chunk { background-color: lightgray; }
        """)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.site_label = QLabel("")
        self.site_label.setStyleSheet("font-size: 16px; color: #ffffff;")
        layout.addWidget(self.site_label)
        self.sid_label = QLabel("")
        self.sid_label.setStyleSheet("font-size: 16px; color: #ffffff")
        layout.addWidget(self.sid_label)
        layout.addSpacing(10)
        self.status = QLabel("Initializing...")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)
        self.sid = ""
        QTimer.singleShot(400, self.ask_and_start)
# --------------------------------------------------------------
    def ask_and_start(self):
        reply = QMessageBox.question(
            self,
            "v2.31 Automatic Log Purge",
            "Start Remote Log Purge Now?\n\nThis Will Delete Old Log Files",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.start_purge()
        else:
            self.status.setText("Purge Cancelled – You May Close the Window")
            self.log_view.append("Operation cancelled by user")
# --------------------------------------------------------------
    def start_purge(self):
        self.log_view.clear()
        self.progress.setValue(0)
        self.status.setText("Connecting to Remote Host")
        self.worker = PurgeWorker()
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.sitename_signal.connect(lambda n: self.site_label.setText(f"Site: {n}"))
        self.worker.sid_signal.connect(self._set_sid)
        self.worker.start()
# --------------------------------------------------------------
    def _set_sid(self, s):
        self.sid = s
        self.sid_label.setText(f"SID: {s}")
# --------------------------------------------------------------
    def append_log(self, text):
        self.log_view.append(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
# --------------------------------------------------------------
    def on_finished(self, success, message):
        if success:
            self.status.setText("Purge Completed Successfully")
            self.log_view.append("\n" + "-" * 80)
            self.log_view.append("Captured Remote Output / LogPurge.txt")
            self.log_view.append("-" * 80)
            self.log_view.append(message or "(no output captured)")
            now = datetime.now()
            date_str = now.strftime("%m%d%Y")
            time_str = now.strftime("%H%M%S")
            filename = f"{self.sid}_231LogPurge_{date_str}{time_str}.txt"
            download_dir = Path("C:\\CRD\\downloads")
            download_dir.mkdir(parents=True, exist_ok=True)
            file_path = download_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
            self.log_view.append(f"\nSaved full log to {file_path}")
        else:
            self.status.setText("Operation Failed")
            QMessageBox.critical(self, "Error", message)
# --------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(37, 37, 38))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    window = LogPurgeWindow()
    window.show()
    sys.exit(app.exec_())
# --------------------------------------------------------------