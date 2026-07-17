#---------------------------------------------------------------------
"""X
PowerShell Module
ewilson@us.medical.canon
Version 1.00 Updated 11/12/25  
"""
#---------------------------------------------------------------------
import sys
import paramiko
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QPushButton, QWidget,
    QLineEdit, QLabel, QComboBox, QHBoxLayout, QTabWidget
)
from PyQt5.QtCore import Qt
from cryptography.fernet import Fernet
import os
import logging
import json
from mod_stylesheets import (
    BUTTON_STYLE, LINE_EDIT_STYLE, STD_LABEL_STYLE,
    TAB_WIDGET_STYLE, TEXT_EDIT_STYLE, COMBOBOX_STYLE, DIALOG_STYLE
)
from mod_logging import CRDLogger
#---------------------------------------------------------------------
class SshSession(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = CRDLogger("CRD").get_logger()  
        self.logger.setLevel(logging.DEBUG)  
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.credentials = self.read_encrypted_credentials()
        self.data = self.read_current_data()
        self.logger.info(f"[MOD SSHPWRSHELL] Loaded Data From current.dat: {self.data}")
        self.username = self.credentials.get("host_user", "gpoperator")
        self.password = self.credentials.get("host_pass", "gpazumino&goodluck1048")
        self.sid = self.data.get("SID", "")
        self.site_name = self.data.get("SiteName", "")
        self.host = self.data.get("Host_IP", "")
        self.sw_version = self.data.get("SW_Version", "")
        #self.logger.debug(f"[MOD SSHPWRSHELL] UI values - SID: {self.sid}, SiteName: {self.site_name}, "
        #                 f"Host_IP: {self.host}, SW_Version: {self.sw_version}")
        self.init_ui()
#---------------------------------------------------------------------
# FIRST ROW
    def init_ui(self):
        layout = QVBoxLayout()
        sid_site_layout = QHBoxLayout()
        sid_container = QHBoxLayout()
        sid_label = QLabel("SID")
        sid_label.setStyleSheet(STD_LABEL_STYLE)
        sid_container.addWidget(sid_label)
        self.sid_input = QLineEdit(self)
        self.sid_input.setText(self.sid)
        self.sid_input.setPlaceholderText("SID")
        self.sid_input.setStyleSheet(LINE_EDIT_STYLE)
        sid_container.addWidget(self.sid_input)
        sid_site_layout.addLayout(sid_container)
        site_container = QHBoxLayout()
        site_label = QLabel("Site Name")
        site_label.setStyleSheet(STD_LABEL_STYLE)
        site_container.addWidget(site_label)
        self.site_name_input = QLineEdit(self)
        self.site_name_input.setText(self.site_name)
        self.site_name_input.setPlaceholderText("Site Name")
        self.site_name_input.setStyleSheet(LINE_EDIT_STYLE)
        site_container.addWidget(self.site_name_input)
        sid_site_layout.addLayout(site_container)
        layout.addLayout(sid_site_layout)
# SECOND ROW
        ip_sw_layout = QHBoxLayout()
        host_ip_container = QHBoxLayout()
        host_ip_label = QLabel("Host IP")
        host_ip_label.setStyleSheet(STD_LABEL_STYLE)
        host_ip_container.addWidget(host_ip_label)
        self.host_input = QLineEdit(self)
        self.host_input.setText(self.host)
        self.host_input.setPlaceholderText("Host IP")
        self.host_input.setStyleSheet(LINE_EDIT_STYLE)
        host_ip_container.addWidget(self.host_input)
        ip_sw_layout.addLayout(host_ip_container)
        sw_container = QHBoxLayout()
        sw_label = QLabel("SW Version")
        sw_label.setStyleSheet(STD_LABEL_STYLE)
        sw_container.addWidget(sw_label)
        self.sw_version_input = QLineEdit(self)
        self.sw_version_input.setText(self.sw_version)
        self.sw_version_input.setPlaceholderText("SW Version")
        self.sw_version_input.setStyleSheet(LINE_EDIT_STYLE)
        sw_container.addWidget(self.sw_version_input)
        ip_sw_layout.addLayout(sw_container)
        layout.addLayout(ip_sw_layout)
# USER / PASSWORD
        user_pass_layout = QHBoxLayout()
        user_container = QHBoxLayout()
        user_label = QLabel("USER")
        user_label.setStyleSheet(STD_LABEL_STYLE)
        user_container.addWidget(user_label)
        self.username_input = QLineEdit(self)
        self.username_input.setText(self.username)
        self.username_input.setPlaceholderText("Username")
        self.username_input.setStyleSheet(LINE_EDIT_STYLE)
        user_container.addWidget(self.username_input)
        user_pass_layout.addLayout(user_container)
        pass_container = QHBoxLayout()
        pass_label = QLabel("PASSWORD")
        pass_label.setStyleSheet(STD_LABEL_STYLE)
        pass_container.addWidget(pass_label)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText(self.password)
        self.password_input.setPlaceholderText("Password")
        self.password_input.setStyleSheet(LINE_EDIT_STYLE)
        pass_container.addWidget(self.password_input)
        user_pass_layout.addLayout(pass_container)
        layout.addLayout(user_pass_layout)
        self.output_text = QTextEdit(self)
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(TEXT_EDIT_STYLE)
        self.connect_button = QPushButton('Connect via SSH', self)
        self.connect_button.clicked.connect(self.connect_ssh)
        self.connect_button.setStyleSheet(BUTTON_STYLE)
        self.shell_selector = QComboBox(self)
        self.shell_selector.addItems(["Bash/WinCmd", "PowerShell"])
        self.shell_selector.setStyleSheet(COMBOBOX_STYLE)
        self.command_selector = QComboBox(self)
        self.command_selector.addItem(" ")
        self.command_selector.addItems(self.read_commands_from_file())
        self.command_selector.currentIndexChanged.connect(self.populate_command_input)
        self.command_selector.activated.connect(self.run_custom_command)
        self.command_selector.setStyleSheet(COMBOBOX_STYLE)
        self.command_input = QLineEdit(self)
        self.command_input.setPlaceholderText("Enter custom command here")
        self.command_input.setStyleSheet(LINE_EDIT_STYLE)
        self.command_input.returnPressed.connect(self.run_custom_command)
        self.run_custom_command_button = QPushButton('Run Command', self)
        self.run_custom_command_button.clicked.connect(self.run_custom_command)
        self.run_custom_command_button.setStyleSheet(BUTTON_STYLE)
        self.clear_output_button = QPushButton('Clear Output', self)
        self.clear_output_button.clicked.connect(self.clear_output)
        self.clear_output_button.setStyleSheet(BUTTON_STYLE)
        self.copy_to_clipboard_button = QPushButton('Copy to Clipboard', self)
        self.copy_to_clipboard_button.clicked.connect(self.copy_to_clipboard)
        self.copy_to_clipboard_button.setStyleSheet(BUTTON_STYLE)
        layout.addWidget(self.connect_button)
        layout.addWidget(QLabel("Select Shell").__setattr__('setStyleSheet', STD_LABEL_STYLE))
        layout.addWidget(self.shell_selector)
        layout.addWidget(QLabel("Select Command").__setattr__('setStyleSheet', STD_LABEL_STYLE))
        layout.addWidget(self.command_selector)
        layout.addWidget(self.command_input)
        layout.addWidget(self.run_custom_command_button)
        layout.addWidget(self.output_text)
        layout.addWidget(self.clear_output_button)
        layout.addWidget(self.copy_to_clipboard_button)
        self.setLayout(layout)
        self.setStyleSheet(DIALOG_STYLE)
#---------------------------------------------------------------------
    def read_encrypted_credentials(self):
        try:
            script_dir = os.path.dirname(__file__)
            key_file = os.path.normpath(os.path.join(script_dir, "..", "config", "user.key"))
            enc_file = os.path.normpath(os.path.join(script_dir, "..", "config", "user.enc"))
            with open(key_file, "rb") as file:
                fernet_key = file.read()
            fernet = Fernet(fernet_key)
            with open(enc_file, "rb") as file:
                encrypted_data = file.read()
            decrypted_data = fernet.decrypt(encrypted_data).decode('utf-8')
            credentials = json.loads(decrypted_data)
            return credentials.get("MR_MP6+", {}).get("credentials", {})
        except Exception as e:
            self.logger.error(f"[MOD SSHPWRSHELL] Error Reading/Decrypting Credentials: {str(e)}")
            return {}
#---------------------------------------------------------------------
    def read_current_data(self):
        try:
            #script_dir = os.path.dirname(__file__)
            #data_file = os.path.normpath(os.path.join(script_dir, "..", "config", "current.dat"))
            data_file = "C:\\CRD\\config\\current.dat"
            data = {}
            with open(data_file, "r") as file:
                for line in file:
                    line = line.strip()
                    if line and "=" in line:
                        key, value = line.split("=", 1)
                        data[key] = value
            if not data:
                self.logger.warning("[MOD SSHPWRSHELL] No Data Read From current.dat")
            return data
        except Exception as e:
            self.logger.error(f"[MOD SSHPWRSHELL] current.dat: {str(e)}")
            return {}
#---------------------------------------------------------------------
    def populate_command_input(self):
        selected_command = self.command_selector.currentText()
        self.command_input.setText(selected_command)
#---------------------------------------------------------------------
    def connect_ssh(self):
        host = self.host_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        try:
            self.ssh_client.connect(host, username=username, password=password)
            self.output_text.append(f"Connected To {host}")
            self.logger.info(f"[MOD SSHPWRSHELL] Connected To {host} via SSH")
        except Exception as e:
            self.output_text.append(f"Failed to connect: {str(e)}")
            self.logger.error(f"[MOD SSHPWRSHELL] Failed to connect: {e}")
#---------------------------------------------------------------------
    def run_custom_command(self):
        command = self.command_input.text()
        shell = self.shell_selector.currentText().lower()
        if not command:
            return
        if shell == 'powershell':
            command = f"powershell -Command \"{command}\""
        def execute_command():
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                while not stdout.channel.exit_status_ready():
                    while stdout.channel.recv_ready():
                        output = stdout.channel.recv(1024).decode('utf-8')
                        self.output_text.append(output)
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                if output:
                    self.output_text.append(output)
                if error:
                    self.output_text.append(error)
            except Exception as e:
                self.output_text.append(f"Failed to run command: {str(e)}")
                self.logger.error(f"[MOD SSHPWRSHELL] Failed to run command: {e}")
        threading.Thread(target=execute_command).start()
#---------------------------------------------------------------------
    def clear_output(self):
        self.output_text.clear()
#---------------------------------------------------------------------
    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_text.toPlainText())
#---------------------------------------------------------------------
    def read_commands_from_file(self):
        try:
            cmdfilepath = r"C:\crd\config\sshterm.dat"
            commands = []
            with open(cmdfilepath, "r") as file:
                for line in file:
                    command = line.strip()
                    if command:
                        commands.append(command)
            return commands
        except Exception as e:
            self.logger.error(f"[MOD SSHPWRSHELL] Error Reading ssh_term.dat: {str(e)}")
            return []
#---------------------------------------------------------------------
class SshTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        self.setWindowTitle('SSH Terminal Emulator MP6+')
        self.setGeometry(100, 100, 700, 800)
       
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(TAB_WIDGET_STYLE)
        self.setCentralWidget(self.tab_widget)
        self.add_new_tab()
        new_tab_button = QPushButton('New SSH Session')
        new_tab_button.clicked.connect(self.add_new_tab)
        new_tab_button.setStyleSheet(BUTTON_STYLE)
        layout = QVBoxLayout()
        layout.addWidget(new_tab_button)
        new_tab_container = QWidget()
        new_tab_container.setLayout(layout)
        self.tab_widget.setCornerWidget(new_tab_button)
       
        self.setStyleSheet(DIALOG_STYLE)
    def add_new_tab(self):
        new_tab = SshSession()
        self.tab_widget.addTab(new_tab, f" SSH Session {self.tab_widget.count() + 1} ")
#---------------------------------------------------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SshTerminal()
    window.show()
    sys.exit(app.exec())
#---------------------------------------------------------------------