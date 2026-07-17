# -------------------------------------------------------------
"""X
Connect Wrapper
SSH and Telnet connections to SP/SM devices.
Version 1.00 Updated 11/12/25  
"""
# -------------------------------------------------------------
import os
import paramiko
from mod_logging import CRDLogger
from connectsm import ConnectSM
from connectsp import ConnectSP
# -------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# -------------------------------------------------------------
credentials = [
    ("gpoperator", "gpazumino&goodluck1048"),
    ("gpoperator", "goodluck"),
]
# -------------------------------------------------------------
class ConnectDevice:
    def __init__(self, hostname, credentials, device_type='SM'):
        self.hostname = hostname
        self.credentials = credentials
        self.device_type = device_type
        self.client = None
# -------------------------------------------------------------
    def connect(self):
        if self.device_type == 'SM':
            from connectsm import ConnectSM
            connector = ConnectSM(self.hostname, self.credentials)
            logger.info(f"[MOD CONNECT] Initiating SM Connection to {self.hostname}")
        elif self.device_type == 'SP':
            from connectsp import ConnectSP
            connector = ConnectSP(self.hostname, self.credentials)
            logger.info(f"[MOD CONNECT] Initiating SP connection to {self.hostname}")
        else:
            logger.error(f"[MOD CONNECT] Unknown Device Type: {self.device_type}")
            raise ValueError(f"Unknown Type: {self.device_type}")
        self.client = connector.connect()
        if self.client:
            logger.info(f"[MOD CONNECT] Connected to {self.hostname} as {self.device_type}")
        else:
            logger.error(f"[MOD CONNECT] Failed to Connect to {self.hostname} as {self.device_type}")
        return self.client
# -------------------------------------------------------------
    def connect(self):
        for username, password in self.credentials:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(self.hostname, username=username, password=password, timeout=7)
                logger.info(f"[MOD CONNECT] Connected to {self.hostname} as {username}")
                return self.client
            except Exception as e:
                logger.error(f"[MOD CONNECT] Failed to Connect to {self.hostname} with {username}: {str(e)}")
        return None
# -------------------------------------------------------------
    def execute_command(self, command):
        if not self.client:
            logger.error("[MOD CONNECT] SSH Client is Not Connected")
            return None
        stdin, stdout, stderr = self.client.exec_command(command)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        if error:
            logger.error(f"[MOD CONNECT] Command Execution Failed On {self.hostname}: {error}")
            return None
        logger.info(f"[MOD CONNECT] Executed Command On {self.hostname}: {command}")
        return output
# -------------------------------------------------------------
    def close(self):
        if self.client:
            self.client.close()
            logger.info(f"[MOD CONNECT] Connection Closed For {self.hostname}")
# -------------------------------------------------------------