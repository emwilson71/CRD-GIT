"""
Version 1.00 Updated 10/06/25  
"""
# ------------------------------------------------------------------------
# X
# cpingssh.py for CRD
# ewilson@us.medical.canon
# 10/06/25 Updated Logfile
# ------------------------------------------------------------------------

import re, os, sys, paramiko
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QMessageBox, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QCheckBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from mod_logging import CRDLogger, CustomMessageBox, Paths
from mod_stylesheets import (
    BUTTON_STYLE, STD_LABEL_STYLE, TEXT_EDIT_STYLE, DIALOG_STYLE,
    CHECKBOX_STYLE, SCROLL_AREA_STYLE, FRAME_STYLE, MESSAGE_BOX_STYLE
)
# ------------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
class PingWorker(QThread):
    output_signal = pyqtSignal(int, str)
    def __init__(self, tams_ip, target_ip, index, username, password):
        super().__init__()
        self.tams_ip = tams_ip
        self.target_ip = target_ip
        self.index = index
        self.username = username
        self.password = password
        self.ping_active = True
        self.client = None
        self.min_latency = None
        self.max_latency = None
# ------------------------------------------------------------------------
    def run(self):
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=self.tams_ip, username=self.username, password=self.password)
            self.client = ssh_client
            while self.ping_active:
                stdin, stdout, stderr = self.client.exec_command(f'ping -n 1 -l 65500 {self.target_ip}')
                output = stdout.read().decode()
                error = stderr.read().decode()
                if error:
                    self.output_signal.emit(self.index, f"Command error: {error}")
                    logger.error(f"[MOD CPINGSSH] Command error for {self.target_ip}: {error}")
                else:
                    latency = self.parse_latency(output)
                    if latency is not None:
                        if self.min_latency is None or latency < self.min_latency:
                            self.min_latency = latency
                        if self.max_latency is None or latency > self.max_latency:
                            self.max_latency = latency
                    self.output_signal.emit(self.index, output)              
        except Exception as e:
            self.output_signal.emit(self.index, f"Error: {str(e)}")
            logger.error(f"[MOD CPINGSSH] Error pinging {self.target_ip}: {str(e)}")
        finally:
            if self.client:
                self.client.close()
# ------------------------------------------------------------------------
    def parse_latency(self, output):
        match = re.search(r'\btime[=<]\s*([\d.]+)\s*(ms|milliseconds)?', output, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    def stop(self):
        self.ping_active = False
# ------------------------------------------------------------------------
class PingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.tams_ip = None
        self.sp_ip = None
        self.target_ips = ["172.16.2.1", "172.16.2.2", "172.16.2.12", "172.16.2.13", "172.16.2.14", "172.16.2.15"]
        self.display = ["SM-HOST", "RECON", "PCVAP00", "PCVAP01", "PCVAP02", "PCVAP03"]
        self.ping_flags = [True] * len(self.target_ips)
        self.read_config_ip()
        self.text_edits = []
        self.checkbox_flags = []
        self.stats_labels = []
        self.pings_sent = [0] * len(self.target_ips)
        self.pings_lost = [0] * len(self.target_ips)
        self.min_latency = [None] * len(self.target_ips)
        self.max_latency = [None] * len(self.target_ips)
        self.ping_threads = [None] * len(self.target_ips)
        self.init_ui()
# ------------------------------------------------------------------------
    def read_config_ip(self):
        try:
            config_path = os.path.join(Paths.CONFIG_DIR, "current.dat")
            
            data = {}
            with open(config_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if line and "=" in line:
                        key, value = line.split("=", 1)
                        data[key] = value
                        logger.debug(f"[MOD CPING] Read key-value pair: {key}={value}")
            if not data:
                raise ValueError("No data read from current.dat")
            self.tams_ip = data.get("Host_IP", "127.0.0.1")
            self.sp_ip = data.get("SP_IP", "172.16.2.1")
            logger.debug(f"[MOD CPING] Loaded config - Host_IP: {self.tams_ip}, SP_IP: {self.sp_ip}")
        except FileNotFoundError:
            logger.error(f"[MOD CPING] current.dat file not found at {config_path}")
            msg_box = CustomMessageBox(
                title="Error",
                message=f"current.dat file not found at {config_path}",
                msg_type=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
            self.tams_ip = "127.0.0.1"
            self.sp_ip = "172.16.2.1"
        except Exception as e:
            logger.error(f"[MOD CPING] Error reading current.dat: {str(e)}")
            msg_box = CustomMessageBox(
                title="Error",
                message=f"Error Reading IP Config: {e}",
                msg_type=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
            self.tams_ip = "127.0.0.1"
            self.sp_ip = "172.16.2.1"
# ------------------------------------------------------------------------
    def init_ui(self):
        self.setWindowTitle("Continuous Ping MP6+")
        self.setGeometry(100, 100, 700, 700)
        self.setStyleSheet(DIALOG_STYLE)
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        top_layout = QHBoxLayout()
        self.start_button = QPushButton("START PING")
        self.start_button.clicked.connect(self.start_ping)
        self.start_button.setStyleSheet(BUTTON_STYLE)
        top_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("STOP PING")
        self.stop_button.clicked.connect(self.stop_ping)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet(BUTTON_STYLE)
        top_layout.addWidget(self.stop_button)
        main_layout.addLayout(top_layout)
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(SCROLL_AREA_STYLE)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        for i in range(len(self.target_ips)):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            frame.setStyleSheet(FRAME_STYLE)
            frame_layout = QVBoxLayout()
            frame.setLayout(frame_layout)
            label = QLabel(f"{self.display[i]} ({self.target_ips[i]})")
            label.setStyleSheet(STD_LABEL_STYLE)
            frame_layout.addWidget(label)
            checkbox = QCheckBox("Enable Ping")
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda state, index=i: self.update_ping_flag(index, state))
            checkbox.setStyleSheet(CHECKBOX_STYLE)
            frame_layout.addWidget(checkbox)
            self.checkbox_flags.append(checkbox)
            stats_label = QLabel("Pings sent: 0, Lost: 0, Min Latency: N/A, Max Latency: N/A")
            stats_label.setStyleSheet(STD_LABEL_STYLE)
            frame_layout.addWidget(stats_label)
            self.stats_labels.append(stats_label)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setStyleSheet(TEXT_EDIT_STYLE)
            frame_layout.addWidget(text_edit)
            self.text_edits.append(text_edit)
            save_button = QPushButton("Save Log")
            save_button.clicked.connect(lambda _, index=i: self.save_log(index))
            save_button.setStyleSheet(BUTTON_STYLE)
            frame_layout.addWidget(save_button)
            scroll_layout.addWidget(frame)
# ------------------------------------------------------------------------
    def update_ping_flag(self, index, state):
        self.ping_flags[index] = state == Qt.CheckState.Checked
        if self.ping_flags[index] and self.ping_threads[index] is None:
            self.start_single_ping(index)
        elif not self.ping_flags[index] and self.ping_threads[index] is not None:
            self.stop_single_ping(index)
# ------------------------------------------------------------------------
    def parse_latency(self, output):
        match = re.search(r'\btime[=<]\s*([\d.]+)\s*(ms|milliseconds)?', output, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
# ------------------------------------------------------------------------
    def start_single_ping(self, index):
        username = 'gpoperator'
        password = 'gpazumino&goodluck1048'
        if self.ping_threads[index] is None:
            self.ping_threads[index] = PingWorker(
                self.tams_ip,
                self.target_ips[index],
                index,
                username,
                password
            )
            self.ping_threads[index].output_signal.connect(self.update_output)
            self.ping_threads[index].start()
# ------------------------------------------------------------------------
    def stop_single_ping(self, index):
        if self.ping_threads[index] is not None:
            self.ping_threads[index].stop()
            self.ping_threads[index].wait()
            self.ping_threads[index] = None
# ------------------------------------------------------------------------
    def start_ping(self):
        for i in range(len(self.target_ips)):
            if self.ping_flags[i] and self.ping_threads[i] is None:
                self.start_single_ping(i)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
# ------------------------------------------------------------------------
    def stop_ping(self):
        for i in range(len(self.target_ips)):
            self.stop_single_ping(i)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
# ------------------------------------------------------------------------
    def update_output(self, index, output):
        if index >= 0:
            self.text_edits[index].append(output.strip())
            self.pings_sent[index] += 1
            if "Destination" in output or "unreachable" in output.lower():
                self.pings_lost[index] += 1
            latency = self.parse_latency(output)
            if latency is not None:
                if self.min_latency[index] is None or latency < self.min_latency[index]:
                    self.min_latency[index] = latency
                if self.max_latency[index] is None or latency > self.max_latency[index]:
                    self.max_latency[index] = latency
            min_latency_str = f"{self.min_latency[index]} ms" if self.min_latency[index] is not None else "N/A"
            max_latency_str = f"{self.max_latency[index]} ms" if self.max_latency[index] is not None else "N/A"
            self.stats_labels[index].setText(
                f"Pings sent: {self.pings_sent[index]}, Lost: {self.pings_lost[index]}, "
                f"Min Latency: {min_latency_str}, Max Latency: {max_latency_str}"
            )
        else:
            msg_box = CustomMessageBox(
                title="Error",
                message=output,
                msg_type=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
            self.stop_ping()
# ------------------------------------------------------------------------
# CHANGED LOGDIR TO PATHS.LOG_DIR
    def save_log(self, index):
        log_directory = Paths.LOG_DIR  
        try:
            os.makedirs(log_directory, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"[MOD CPING] Failed to create log directory {log_directory}: {e}")
            log_directory = os.path.expanduser("~/logs")
            os.makedirs(log_directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"PingLog_{self.target_ips[index]}_{timestamp}.txt"
        file_path = os.path.join(log_directory, filename)
        pings_sent = self.pings_sent[index]
        pings_lost = self.pings_lost[index]
        min_latency = self.min_latency[index]
        max_latency = self.max_latency[index]
        min_latency_str = f"{min_latency} ms" if min_latency is not None else "N/A"
        max_latency_str = f"{max_latency} ms" if max_latency is not None else "N/A"
        header = (
            f"IP Address: {self.target_ips[index]}\n"
            f"Display Name: {self.display[index]}\n"
            f"Pings Sent: {pings_sent}\n"
            f"Pings Lost: {pings_lost}\n"
            f"Minimum Latency: {min_latency_str}\n"
            f"Maximum Latency: {max_latency_str}\n\n"
        )
        text_content = header + self.text_edits[index].toPlainText()
        try:
            with open(file_path, "w") as file:
                file.write(text_content)
            logger.info(f"[MOD CPING] Ping log saved as {file_path}")
            msg_box = CustomMessageBox(
                title="Saved Ping Log",
                message=f"Ping Log Saved as {filename}",
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
        except Exception as e:
            logger.error(f"[MOD CPING] Failed to save log {file_path}: {e}")
            msg_box = CustomMessageBox(
                title="Error",
                message=f"Failed to Save Log: {e}",
                msg_type=QMessageBox.Critical,
                parent=self
            )
            msg_box.center()
            msg_box.exec_custom()
# ------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    window = PingApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
# ------------------------------------------------------------------------