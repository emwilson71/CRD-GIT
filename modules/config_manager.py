# ------------------------------------------------
"""X
config_manager.py
ewilson@us.medical.canon
Version 1.01 Updated 11/12/25  
"""
# ------------------------------------------------
import os
import sys
import logging
from pathlib import Path
from custmsg import CustomMessageBox
from PyQt5.QtWidgets import QMessageBox
import ipaddress
from mod_logging import CRDLogger
# ------------------------------------------------
def parse_key_value_file(file_path):
    logger = CRDLogger("CRD").get_logger()  
    logger.setLevel(logging.DEBUG)  
    config = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    except Exception as e:
        error_message = f"[MOD CONFIGMGR] Failed To Read Config File '{file_path}': {e}"
        logger.error(error_message)
        msg_box = CustomMessageBox(
            title="Config Error",
            message=error_message,
            msg_type=QMessageBox.Critical
        )
        msg_box.exec_custom()
        sys.exit(1)
    return config
# ------------------------------------------------
class ConfigManager:
    def __init__(self, config_path='../config/current.dat'):
        self.logger = CRDLogger("ConfigManager").get_logger()  
        self.logger.setLevel(logging.DEBUG)  
        self.config = self.read_config(config_path)
        self.sm_ip = self.config.get('smip')
        self.sp_ip = self.config.get('spip')
        self.tunnel_type = self.config.get('tunneltype')
        self.sys_id = self.config.get('sys_id')
        self.sm_version = self.config.get('SmVersion')
        self.machine_type = self.config.get('MachineType')
        self.system_name = self.config.get('SystemName')
        self.machine_name = self.config.get('MachineName')
        self.magnet_type = self.config.get('MagnetType')
        self.modality_dir = self.config.get('ModalityDir')
        self.hosp_name = self.config.get('HospName')
        self.monitor_directory = Path(f"c:/Innervision.dir/M-Power/{self.sys_id}/_tui.dir")
        self.validate_config()
# ------------------------------------------------
    def read_config(self, config_path):
        if not os.path.exists(config_path):
            error_message = f"[MOD CONFIGMGR] Configuration file '{config_path}' does not exist."
            self.logger.error(error_message)
            msg_box = CustomMessageBox(
                title="Config Error",
                message=error_message,
                msg_type=QMessageBox.Critical
            )
            msg_box.exec_custom()
            sys.exit(1)
        return parse_key_value_file(config_path)
# ------------------------------------------------
    def validate_config(self):
        try:
            ipaddress.ip_address(self.sm_ip)
            ipaddress.ip_address(self.sp_ip)
        except ValueError:
            error_message = f"[MOD CONFIGMGR] Invalid IP Addresses In Config: smip={self.sm_ip}, spip={self.sp_ip}"
            self.logger.error(error_message)
            msg_box = CustomMessageBox(
                title="Config Error",
                message=error_message,
                msg_type=QMessageBox.Critical
            )
            msg_box.exec_custom()
            sys.exit(1)
        if not self.sys_id or not all(c.isalnum() or c == '-' for c in self.sys_id):
            error_message = f"[MOD CONFIGMGR] Invalid System ID: {self.sys_id}"
            self.logger.error(error_message)
            msg_box = CustomMessageBox(
                title="Config Error",
                message=error_message,
                msg_type=QMessageBox.Critical
            )
            msg_box.exec_custom()
            sys.exit(1)
        try:
            os.makedirs(self.monitor_directory, exist_ok=True)
            test_file = self.monitor_directory / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            error_message = f"[MOD CONFIGMGR] Cannot Write To Directory '{self.monitor_directory}': {e}"
            self.logger.error(error_message)
            msg_box = CustomMessageBox(
                title="Configuration Error",
                message=error_message,
                msg_type=QMessageBox.Critical
            )
            msg_box.exec_custom()
            sys.exit(1)
    def get_monitor_directory(self):
        return self.monitor_directory
    def get_sm_ip(self):
        return self.sm_ip
    def get_sp_ip(self):
        return self.sp_ip
    def get_sys_id(self):
        return self.sys_id
# ------------------------------------------------
