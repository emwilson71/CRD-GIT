# --------------------------------------------------------------------------
# X
# cPingTelnet for GP-MP5
# 10/04/2025 ewilson@us.medical.canon
# --------------------------------------------------------------------------
"""
Version 1.00 Updated 10/04/2025  
"""
import os
import sys
import time
import telnetlib
import re
import sm_matrix
from mod_logging import CRDLogger, Paths
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
# --------------------------------------------------------------------------
BUTTON_STYLE = """
    QPushButton {
        background-color: #4A4A4A;
        padding: 4px;
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
        border-radius: 4px;
        border: 1px solid #5A5A5A;
    }
    QPushButton:hover {
        background-color: #2A2A2A;
        border: 1px solid #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #3A3A3A;
    }
    QPushButton:disabled {
        background-color: #606060;
        color: #808080;
    }
"""

APP_DARK_QSS = """
QWidget {
    background-color: #1E1E1E;
    color: #E0E0E0;
    font-size: 12px;
}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {
    background-color: #2B2B2B;
    color: #E0E0E0;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    selection-background-color: #555555;
    selection-color: #FFFFFF;
}
QComboBox QAbstractItemView {
    background-color: #2B2B2B;
    color: #E0E0E0;
    border: 1px solid #3A3A3A;
    selection-background-color: #555555;
    selection-color: #FFFFFF;
}
QLabel {
    color: #CCCCCC;
}
QGroupBox {
    border: 1px solid #3A3A3A;
    border-radius: 6px;
    margin-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: #AFAFAF;
}
"""

# --------------------------------------------------------------------------
DEFAULT_PORT = 23  
DEFAULT_USERNAME = "operator"
DEFAULT_PASSWORD_FOR = {
    "operator": "goodluck",
    "gpoperator": "gpazumino&goodluck1048",
}
DEFAULT_COMMAND = "ping -t pcvap00"
DEFAULT_TARGETS = [
    "172.16.2.1",
    "172.16.2.2",
    "172.16.2.10",
    "pcvap00",
    "pcvap02",
    "pcvap04",
    "pcvap06",
]

LOGIN_TIMEOUT = 20
POST_LOGIN_DELAY = 1.5

LOGIN_PROMPTS = [b"login:", b"Login:", b"username:", b"Username:", b"user:", b"User:"]
PASSWORD_PROMPTS = [b"Password:", b"password:", b"PASSCODE:", b"Passcode:"]
SHELL_PROMPTS = [b"> ", b"# ", b"$ ", b"% ", b":~$ "]

WIN_SUCCESS_RE = re.compile(r"Reply\s+from\s+", re.IGNORECASE)
WIN_FAIL_RES = [
    re.compile(r"Request\s+timed\s+out\.?", re.IGNORECASE),
    re.compile(r"Destination\s+host\s+unreachable\.?", re.IGNORECASE),
    re.compile(r"General\s+failure\.?", re.IGNORECASE),
]
LIN_SUCCESS_RE = re.compile(r"bytes\s+from\s+", re.IGNORECASE)
LIN_FAIL_RES = [
    re.compile(r"Destination\s+Host\s+Unreachable", re.IGNORECASE),
    re.compile(r"100% packet loss", re.IGNORECASE),
    re.compile(r"Network\s+is\s+unreachable", re.IGNORECASE),
    re.compile(r"connect:\s+Network\s+is\s+unreachable", re.IGNORECASE),
    re.compile(r"ping:\s+sendmsg:", re.IGNORECASE),
]

PING_STYLE_AUTO = "auto"
PING_STYLE_WIN = "windows"
# --------------------------------------------------------------------------
def read_kv_from_current_dat():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dat_path = os.path.normpath(os.path.join(script_dir, "..", "config", "current.dat"))
        if not os.path.exists(dat_path):
            return {}
        kv = {}
        with open(dat_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                kv[key.strip().lower()] = value.strip()
        return kv
    except Exception:
        return {}
# --------------------------------------------------------------------------
def expect_any(tn, patterns, timeout):
    regex_list = []
    for p in patterns:
        if isinstance(p, (bytes, bytearray)):
            regex_list.append(re.compile(re.escape(p)))
        else:
            regex_list.append(p)
    return tn.expect(regex_list, timeout=timeout)
# --------------------------------------------------------------------------
class TelnetWorker(QtCore.QThread):
    output = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)
    stats = QtCore.pyqtSignal(int, int)  
    finished_ok = QtCore.pyqtSignal()
    finished_err = QtCore.pyqtSignal(str)

    def __init__(self, host, username, password, command, ping_style=PING_STYLE_AUTO):
        super().__init__()
        self.host = host
        self.port = DEFAULT_PORT
        self.username = username
        self.password = password
        self.command = command
        self._stop = False
        self.success_count = 0
        self.fail_count = 0
        self.ping_style = ping_style
        self._style_decided = False

    def stop(self):
        self._stop = True
# --------------------------------------------------------------------------
    def _detect_style(self, line):
        if self._style_decided:
            return
        if WIN_SUCCESS_RE.search(line) or any(r.search(line) for r in WIN_FAIL_RES):
            self.ping_style = PING_STYLE_WIN
            self._style_decided = True
# --------------------------------------------------------------------------
    def _update_counters(self, line):
        if self.ping_style == PING_STYLE_AUTO:
            self._detect_style(line)

        if self.ping_style in (PING_STYLE_WIN, PING_STYLE_AUTO):
            if WIN_SUCCESS_RE.search(line):
                self.success_count += 1
                self.stats.emit(self.success_count, self.fail_count)
                return
            for r in WIN_FAIL_RES:
                if r.search(line):
                    self.fail_count += 1
                    self.stats.emit(self.success_count, self.fail_count)
                    return

        if self.ping_style in (PING_STYLE_AUTO):
            if LIN_SUCCESS_RE.search(line):
                self.success_count += 1
                self.stats.emit(self.success_count, self.fail_count)
                return
            for r in LIN_FAIL_RES:
                if r.search(line):
                    self.fail_count += 1
                    self.stats.emit(self.success_count, self.fail_count)
                    return
# --------------------------------------------------------------------------
    def run(self):
        try:
            if not self.host:
                raise RuntimeError("Host_IP not found in ../config/current.dat")
            self.status.emit(f"Connecting to {self.host}:{self.port}...")
            tn = telnetlib.Telnet(self.host, self.port, timeout=LOGIN_TIMEOUT)

            time.sleep(0.5)
            banner = tn.read_very_eager()
            if banner:
                txt = banner.decode("utf-8", errors="replace")
                self.output.emit(txt)

            tn.write(b"\r\n")
            idx, _, _ = expect_any(tn, LOGIN_PROMPTS, timeout=LOGIN_TIMEOUT)
            if idx == -1:
                tn.write(b"\r\n")
                idx, _, _ = expect_any(tn, LOGIN_PROMPTS, timeout=LOGIN_TIMEOUT)
                if idx == -1:
                    diag = tn.read_until(b":", timeout=3)
                    self.output.emit(diag.decode("utf-8", errors="replace"))
                    raise RuntimeError("Login prompt not detected. Adjust prompts or timeout.")

            tn.write((self.username + "\r\n").encode("utf-8"))

            idx, _, _ = expect_any(tn, PASSWORD_PROMPTS, timeout=LOGIN_TIMEOUT)
            if idx == -1:
                tn.write(b"\r\n")
                idx, _, _ = expect_any(tn, PASSWORD_PROMPTS, timeout=LOGIN_TIMEOUT)
                if idx == -1:
                    diag = tn.read_until(b":", timeout=3)
                    self.output.emit(diag.decode("utf-8", errors="replace"))
                    raise RuntimeError("Password prompt not detected. Adjust prompts or timeout.")

            tn.write((self.password + "\r\n").encode("utf-8"))

            time.sleep(POST_LOGIN_DELAY)
            tn.write(b"\r\n")
            expect_any(tn, SHELL_PROMPTS, timeout=3)

            tn.write((self.command + "\r\n").encode("utf-8"))
            self.status.emit(f"Sent command: {self.command}")
            self.output.emit("\nStreaming output...\n")

            buffer = ""
            try:
                while not self._stop:
                    try:
                        data = tn.read_very_eager()
                        if data:
                            chunk = data.decode("utf-8", errors="replace")
                            self.output.emit(chunk)

                            buffer += chunk
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                self._update_counters(line)
                        else:
                            time.sleep(0.2)
                    except EOFError:
                        self.status.emit("Connection closed by remote host.")
                        break
            finally:
                try:
                    tn.write(b"\x03")  
                    time.sleep(0.3)
                    tn.write(b"exit\r\n")
                except Exception:
                    pass
                tn.close()
                self.status.emit("Telnet session closed.")
            self.finished_ok.emit()
        except Exception as e:
            self.finished_err.emit(str(e))
# --------------------------------------------------------------------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cPing Telnet")
        self.setMinimumSize(800, 500)

        sidebar = QtWidgets.QFrame()
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(340)
        side_layout = QtWidgets.QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(10)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        font = QtGui.QFont("Consolas")
        font.setStyleHint(QtGui.QFont.Monospace)
        self.output.setFont(font)
        self.status_label = QtWidgets.QLabel("Ready.")
        self.status_label.setObjectName("statusLabel")

        right = QtWidgets.QFrame()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)
        self.counter_label = QtWidgets.QLabel("0 pings, 0 failed")
        counter_font = self.counter_label.font()
        counter_font.setPointSize(counter_font.pointSize() + 1)
        counter_font.setBold(True)
        self.counter_label.setFont(counter_font)

        right_layout.addWidget(self.counter_label)
        right_layout.addWidget(self.output, 1)
        right_layout.addWidget(self.status_label)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        main_layout.addWidget(sidebar, 0)
        main_layout.addWidget(right, 1)
        self.setLayout(main_layout)
        kv = read_kv_from_current_dat()
        self.host = kv.get("host_ip", "")
        self.sid  = kv.get("sid", "")

        try:
            (
                _raw_version,
                self.version_key,          
                _creds,
                _file_proto,
                _term_proto,
                _host_port,
            ) = sm_matrix.load_credentials()
        except Exception as e:
            self.append_output(f"[ERROR] Version detection failed: {e}\n")
            self._disable_all_buttons()
            return

        ALLOWED_BUCKETS = {"MR_GP", "MR_MP2", "MR_MP3-5"}
        if self.version_key not in ALLOWED_BUCKETS:
            self.append_output(
                f"This Script Is Only For GP / MP2 / MP3-5\n"
                f"Detected Version {self.version_key}\n"
                f"Script Will Be Canceled\n"
            )
            try:
                from mod_logging import CRDLogger
                CRDLogger("CPING").get_logger().info(
                    f"Blocked Execution: Unsupported SW Version {self.version_key}"
                )
            except:
                pass
            return
#>
        self.sid_label  = QtWidgets.QLabel(self.sid if self.sid else "(not found)")
        self.host_label = QtWidgets.QLabel(self.host if self.host else "(not found)")

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.addItems(["operator", "gpoperator"])
        self.pass_edit = QtWidgets.QLineEdit(DEFAULT_PASSWORD_FOR[DEFAULT_USERNAME])
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.user_combo.currentTextChanged.connect(self.on_user_changed)

        conn_group = QtWidgets.QGroupBox("Connection")
        conn_form  = QtWidgets.QFormLayout(conn_group)
        conn_group.setFixedHeight(120)
        conn_form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        conn_form.addRow("SID:",      self.sid_label)
        conn_form.addRow("Host:",     self.host_label)
        conn_form.addRow("Username:", self.user_combo)
        conn_form.addRow("Password:", self.pass_edit)
        side_layout.addWidget(conn_group)

        cmd_group = QtWidgets.QGroupBox("Command")
        cmd_form  = QtWidgets.QFormLayout(cmd_group)
        cmd_group.setFixedHeight(80)
        cmd_form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.addItems(DEFAULT_TARGETS)
        self.cmd_edit = QtWidgets.QLineEdit(DEFAULT_COMMAND)
        self.cmd_edit.setPlaceholderText("Command To Run (e.g., ping -t pcvap00)")
        self.target_combo.currentTextChanged.connect(self.on_target_changed)
        cmd_form.addRow("Target:",  self.target_combo)
        cmd_form.addRow("Command:", self.cmd_edit)
        side_layout.addWidget(cmd_group)

        self.connect_btn = QtWidgets.QPushButton("START")
        self.stop_btn    = QtWidgets.QPushButton("STOP")
        self.save_btn    = QtWidgets.QPushButton("SAVE RESULTS")
        self.clear_btn   = QtWidgets.QPushButton("CLEAR")
        self.stop_btn.setEnabled(False)
        for b in (self.clear_btn, self.connect_btn, self.stop_btn, self.save_btn):
            b.setStyleSheet(BUTTON_STYLE)

        side_layout.addWidget(self.connect_btn)
        side_layout.addWidget(self.stop_btn)
        side_layout.addWidget(self.save_btn)
        side_layout.addStretch()
        side_layout.addWidget(self.clear_btn)
 #       
        self.worker = None
        self.connect_btn.clicked.connect(self.on_connect)
        self.stop_btn.clicked.connect(self.on_stop)
        self.save_btn.clicked.connect(self.on_save)
        self.clear_btn.clicked.connect(self.on_clear)
#
        if self.host:
            self.append_output(f"Using Host_IP From current.dat: {self.host}\n")
        else:
            self.append_output("Warning: Host_IP Not Found \n")
        if self.sid:
            self.append_output(f"SID: {self.sid}\n")
        else:
            self.append_output("Warning: SID Not Found \n")
        if self.target_combo.count() > 0:
            self.on_target_changed(self.target_combo.currentText())
# --------------------------------------------------------------------------
    def on_user_changed(self, username):
        self.pass_edit.setText(DEFAULT_PASSWORD_FOR.get(username, ""))

    def on_target_changed(self, target):
        target = target.strip()
        if target:
            self.cmd_edit.setText(f"ping -t {target}")
    
    def on_clear(self):
        self.output.clear()
    
    def set_running_state(self, running: bool):
        self.connect_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.save_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        
# --------------------------------------------------------------------------
    def on_connect(self):
        if self.worker is not None:
            return
        if not self.host:
            self.append_output("Error: Host_IP not available. Check ../config/current.dat.\n")
            return

        username = self.user_combo.currentText().strip()
        password = self.pass_edit.text()
        command = self.cmd_edit.text().strip() or DEFAULT_COMMAND


        self.success_count = 0
        self.fail_count = 0
        self.update_counters_label()

        self.worker = TelnetWorker(self.host, username, password, command, ping_style=PING_STYLE_AUTO)
        self.worker.output.connect(self.append_output)
        self.worker.status.connect(self.set_status)
        self.worker.stats.connect(self.on_stats)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.finished_err.connect(self.on_error)
        self.worker.start()

        self.set_running_state(True)
        self.set_status(f"Connecting To {self.host}:{DEFAULT_PORT}")

    def on_stop(self):
        if self.worker:
            self.worker.stop()

    def on_finished(self):
        self.append_output("\nDone.\n")
        self.cleanup_worker()
        self.set_status("Ready.")

    def on_error(self, msg):
        self.append_output(f"\nError: {msg}\n")
        self.cleanup_worker()
        self.set_status("Ready.")

    def cleanup_worker(self):
        if self.worker:
            self.worker.wait(1000)
            self.worker = None
        self.set_running_state(False)

    @QtCore.pyqtSlot(int, int)
    def on_stats(self, success, failed):
        self.success_count = success
        self.fail_count = failed
        self.update_counters_label()

    def update_counters_label(self):
        self.counter_label.setText(f"{self.success_count} pings, {self.fail_count} failed")

    @QtCore.pyqtSlot(str)
    def append_output(self, text):
        self.output.moveCursor(QtGui.QTextCursor.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(QtGui.QTextCursor.End)

    @QtCore.pyqtSlot(str)
    def set_status(self, text):
        self.status_label.setText(text)
# --------------------------------------------------------------------------
    def on_save(self):
        if self.worker is not None:
            self.append_output("Cannot Save While Pinging \n")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        downloads_dir = os.path.normpath(os.path.join(script_dir, "..", "downloads"))
        os.makedirs(downloads_dir, exist_ok=True)

        sid_sanitized = self.sid if self.sid else "000000"
        ts = datetime.now().strftime("%m%d%y_%H%M%S")
        filename = f"PingLog_{sid_sanitized}_{ts}.txt"
        path = os.path.join(downloads_dir, filename)

        username = self.user_combo.currentText().strip()
        command = self.cmd_edit.text().strip() or DEFAULT_COMMAND
        total = self.success_count + self.fail_count

        header_lines = [
            f"SID: {self.sid}",
            f"Host: {self.host}",
            f"Username: {username}",
            f"Command: {command}",
            f"Stats: {self.success_count} of {total} pings ({self.fail_count} failed)",
            "-" * 60,
        ]
        content = "\n".join(header_lines) + "\n" + self.output.toPlainText()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.append_output(f"\nSaved Results To: {path}\n")
        except Exception as e:
            self.append_output(f"\nFailed To Save File: {e}\n")

# --------------------------------------------------------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_DARK_QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
# --------------------------------------------------------------------------