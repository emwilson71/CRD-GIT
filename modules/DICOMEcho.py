# ---------------------------------------------------------
# DICOMEcho TEST (ew)
# Version 1.04 Updated 07/17/26
# ---------------------------------------------------------
import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QMessageBox
)
from PyQt5.QtGui import QFont
from pynetdicom import AE
from pynetdicom.sop_class import Verification

from mod_stylesheets import apply_dark_theme
# ---------------------------------------------------------
class DicomEchoGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DICOM Echo Test")
        self.setGeometry(100, 100, 760, 550)
        
        self.connections = {}
        self.json_file = "echo.json"
        
        self.load_connections()
        self.init_ui()
# ---------------------------------------------------------
    def load_connections(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, "r") as f:
                    self.connections = json.load(f)
            except Exception:
                self.connections = {}
# ---------------------------------------------------------
    def save_connections(self):
        try:
            with open(self.json_file, "w") as f:
                json.dump(self.connections, f, indent=4)
        except Exception as e:
            self.log(f"Failed to save echo.json: {e}", "ERROR")
# ---------------------------------------------------------
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        saved_group = QGroupBox("Saved Connections")
        saved_layout = QHBoxLayout()

        self.conn_combo = QComboBox()
        self.conn_combo.setEditable(True)
        self.conn_combo.setMinimumHeight(32)
        self.update_combo()

        self.save_btn = QPushButton("Save")
        self.save_btn.setMinimumHeight(32)
        self.save_btn.setMinimumWidth(140)
        self.save_btn.clicked.connect(self.save_current)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setMinimumHeight(32)
        self.delete_btn.setMinimumWidth(140)
        self.delete_btn.clicked.connect(self.delete_current)

        saved_layout.addWidget(QLabel("Connection Name:"), 0)
        saved_layout.addWidget(self.conn_combo, 1)
        saved_layout.addWidget(self.save_btn)
        saved_layout.addWidget(self.delete_btn)
        saved_group.setLayout(saved_layout)

        input_group = QGroupBox("DICOM Settings")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.ip_edit = QLineEdit("127.0.0.1")
        self.ae_edit = QLineEdit("TEST")
        self.port_edit = QLineEdit("104")

        form_layout.addRow("IP Address:", self.ip_edit)
        form_layout.addRow("AE Title:", self.ae_edit)
        form_layout.addRow("Port:", self.port_edit)
        input_group.setLayout(form_layout)

        btn_layout = QHBoxLayout()
        #btn_layout.stretch()
        
        self.echo_btn = QPushButton("Send C-ECHO")
        self.echo_btn.setMinimumHeight(35)
        self.echo_btn.setMinimumWidth(140)
        self.echo_btn.clicked.connect(self.perform_echo)

        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.setMinimumHeight(35)
        self.echo_btn.setMinimumWidth(140)
        self.clear_btn.clicked.connect(self.clear_log)

        #btn_layout.stretch()
        btn_layout.addWidget(self.echo_btn)
        btn_layout.addWidget(self.clear_btn)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 11))

        main_layout.addWidget(saved_group)
        main_layout.addWidget(input_group)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(QLabel("Status / Log"))
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

        apply_dark_theme(self)

        self.conn_combo.currentIndexChanged.connect(self.load_selected_connection)
        self.log("DICOM C-ECHO Ready", "INFO")
# ---------------------------------------------------------
    def update_combo(self):
        self.conn_combo.clear()
        for name in sorted(self.connections.keys()):
            self.conn_combo.addItem(name)
# ---------------------------------------------------------
    def save_current(self):
        name = self.conn_combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Please Enter a Connection Name")
            return
        data = {
            "ip": self.ip_edit.text().strip(),
            "ae": self.ae_edit.text().strip(),
            "port": self.port_edit.text().strip()
        }
        self.connections[name] = data
        self.save_connections()
        self.update_combo()
        self.conn_combo.setCurrentText(name)
        self.log(f"Saved Connection - {name}", "SUCCESS")
# ---------------------------------------------------------
    def delete_current(self):
        name = self.conn_combo.currentText().strip()
        if name in self.connections:
            reply = QMessageBox.question(self, "Delete", f"Delete '{name}'?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                del self.connections[name]
                self.save_connections()
                self.update_combo()
                self.log(f"Deleted - {name}", "WARN")

    def load_selected_connection(self):
        name = self.conn_combo.currentText().strip()
        if name in self.connections:
            data = self.connections[name]
            self.ip_edit.setText(data.get("ip", ""))
            self.ae_edit.setText(data.get("ae", ""))
            self.port_edit.setText(data.get("port", "104"))
# ---------------------------------------------------------
    def log(self, message: str, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#E0E0E0", "SUCCESS": "#00FF88", "ERROR": "#FF6666", "WARN": "#FFCC66"}
        color = colors.get(level, "#E0E0E0")
        self.log_area.append(
            f'<span style="color:#E0E0E0">[{timestamp}]</span> '
            f'<span style="color:{color}">{message}</span>'
        )
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
# ---------------------------------------------------------
    def perform_echo(self):
        ip = self.ip_edit.text().strip()
        ae_title = self.ae_edit.text().strip()
        port_text = self.port_edit.text().strip()

        if not ip or not ae_title:
            self.log("IP Address / AE Title Required", "ERROR")
            return
        try:
            port = int(port_text) if port_text else 104
        except ValueError:
            self.log("Invalid Port Number", "ERROR")
            return

        self.log(f"Connecting {ip}:{port} AE - {ae_title} ", "INFO")
        self.echo_btn.setEnabled(False)
        self.echo_btn.setText("Connecting...")

        try:
            ae = AE()
            ae.add_requested_context(Verification)
            assoc = ae.associate(ip, port, ae_title=ae_title)

            if assoc.is_established:
                status = assoc.send_c_echo()
                if status and status.Status == 0x0000:
                    self.log("C-ECHO Device is Responding Properly", "SUCCESS")
                else:
                    self.log("Association OK / C-ECHO Error", "WARN")
                assoc.release()
            else:
                self.log("Failed to Make Association", "ERROR")
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
        finally:
            self.echo_btn.setEnabled(True)
            self.echo_btn.setText("Send C-ECHO")
# ---------------------------------------------------------
    def clear_log(self):
        self.log_area.clear()
        self.log("Log Cleared")
# ---------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DicomEchoGUI()
    window.show()
    sys.exit(app.exec_())
# ---------------------------------------------------------
