# -------------------------------------------------
"""E
ConnectSP Module  
Handles SSH connections to SP devices.  
ewilson@us.medical.canon
Version 1.00 Updated 11/12/25  
"""  
# -------------------------------------------------
import paramiko  
import logging  
import platform  
import subprocess  
# -------------------------------------------------
class ConnectSP:  
    def __init__(self, hostname, credentials):   
        self.hostname = hostname  
        self.credentials = credentials  
        self.client = None  
# -------------------------------------------------
    def ping(self):  
        command = ["ping", "-c", "1", self.hostname] if platform.system().lower() != "windows" else ["ping", "-n", "1", self.hostname]  
        response = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  
        return response.returncode == 0  
# -------------------------------------------------
    def connect(self):  
        if not self.ping():  
            logging.error(f"Host {self.hostname} is not reachable.")  
            return None  
        for username, password in self.credentials:  
            try:  
                self.client = paramiko.SSHClient()  
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  
                self.client.connect(self.hostname, username=username, password=password, timeout=7)  
                logging.info(f"Connected to SP at {self.hostname} as {username}")  
                return self.client  
            except Exception as e:  
                logging.error(f"Failed to connect to SP with {username}: {e}")  
        logging.error("All connection attempts to SP failed.")  
        return None  
# -------------------------------------------------
    def execute_command(self, command):  
        if not self.client:  
            logging.error("SSH client is not connected.")  
            return None  
        stdin, stdout, stderr = self.client.exec_command(command)  
        output = stdout.read().decode('utf-8')  
        error = stderr.read().decode('utf-8')  
        if error:  
            logging.error(f"Command error: {error}")  
            return None  
        return output  
# -------------------------------------------------
    def close(self):  
        if self.client:  
            self.client.close()  
            logging.info("SP connection closed.")  
# -------------------------------------------------
if __name__ == "__main__":  
    hostname = "SP_DEVICE_IP"  
    credentials = [  
        ("USERNAME_1", "PASSWORD_1"),  
        ("USERNAME_2", "PASSWORD_2")  
    ]  
    sp_connection = ConnectSP(hostname, credentials)  
    sp_connection.connect()
# -------------------------------------------------