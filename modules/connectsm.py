# -------------------------------------------------
"""X
ConnectSM Module
Handles SSH and Telnet connections to SM devices.
ewilson@us.medical.canon
Updated for unified logging
Version 1.00 Updated 11/12/25  
"""
# -------------------------------------------------
import paramiko
import telnetlib
import platform
import subprocess
import logging  
from mod_logging import CRDLogger
# -------------------------------------------------
class ConnectSM:
    def __init__(self, hostname, ssh_credentials, telnet_credentials):
        self.logger = CRDLogger("CRD").get_logger()
        self.logger.setLevel(logging.DEBUG)  
        self.hostname = hostname
        self.ssh_credentials = ssh_credentials
        self.telnet_credentials = telnet_credentials
        self.ssh_client = None
        self.telnet_client = None
# -------------------------------------------------
    def ping(self):
        command = ["ping", "-c", "1", self.hostname] if platform.system().lower() != "windows" else ["ping", "-n", "1", self.hostname]
        response = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return response.returncode == 0
# -------------------------------------------------
    def connect_ssh(self, user, password):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.hostname, username=user, password=password, timeout=7)
            self.logger.info(f"[MOD CONNECTSM] Connected to SM {self.hostname} SSH as {user}")
            return client
        except Exception as e:
            self.logger.error(f"[MOD CONNECTSM] SSH Connection Failed {user}: {e}")
            return None
# -------------------------------------------------
    def connect_telnet(self, user, password):
        try:
            tn = telnetlib.Telnet(self.hostname)
            tn.read_until(b"login: ")
            tn.write(user.encode('ascii') + b"\n")
            tn.read_until(b"Password: ")
            tn.write(password.encode('ascii') + b"\n")
            self.logger.info(f"[MOD CONNECTSM] Connected to SM at {self.hostname} Telnet as {user}")
            return tn
        except Exception as e:
            self.logger.error(f"[MOD CONNECTSM] Telnet Connection Failed {user}: {e}")
            return None
# -------------------------------------------------
    def connect(self):
        if not self.ping():
            self.logger.error(f"[MOD CONNECTSM] Host {self.hostname} is not reachable.")
            return None
# -------------------------------------------------
        for user, password in self.ssh_credentials:
            self.ssh_client = self.connect_ssh(user, password)
            if self.ssh_client:
                return self.ssh_client
# -------------------------------------------------
        for user, password in self.telnet_credentials:
            self.telnet_client = self.connect_telnet(user, password)
            if self.telnet_client:
                return self.telnet_client
        self.logger.error("[MOD CONNECTSM] All Connection Attempts Failed.")
        return None
# -------------------------------------------------
    def execute_command(self, command):
        if self.ssh_client:
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                if error:
                    self.logger.error(f"[MOD CONNECTSM] Command Error: {error}")
                    return None
                return output
            except Exception as e:
                self.logger.error(f"[MOD CONNECTSM] Failed to Execute SSH: {e}")
                return None
        elif self.telnet_client:
            try:
                self.telnet_client.write(command.encode('ascii') + b"\n")
                output = self.telnet_client.read_all().decode('ascii')
                return output
            except Exception as e:
                self.logger.error(f"[MOD CONNECTSM] Failed to Execute Telnet: {e}")
                return None
        else:
            self.logger.error("[MOD CONNECTSM] No Connections to Execute the Command.")
            return None
# -------------------------------------------------
    def close(self):
        if self.ssh_client:
            self.ssh_client.close()
            self.logger.info("[MOD CONNECTSM] SSH connection to SM closed.")
        if self.telnet_client:
            self.telnet_client.close()
            self.logger.info("[MOD CONNECTSM] Telnet connection to SM closed.")
# -------------------------------------------------
if __name__ == "__main__":
    hostname = "SM_DEVICE_IP"
    ssh_credentials = [
        ("SSH_USERNAME_1", "SSH_PASSWORD_1"),
        ("SSH_USERNAME_2", "SSH_PASSWORD_2")
    ]
    telnet_credentials = [
        ("TELNET_USERNAME_1", "TELNET_PASSWORD_1"),
        ("TELNET_USERNAME_2", "TELNET_PASSWORD_2")
    ]
    sm_connection = ConnectSM(hostname, ssh_credentials, telnet_credentials)
    sm_connection.connect()
# -------------------------------------------------
