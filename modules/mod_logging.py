# ----------------------------------------------------------------------
"""X
mod_logging.py
10/06/25 ewilson@us.medical.canon
Updated for unified logging to ../logs/CRD_MMDDYYYY.log
Version 1.01 Updated 10/06/25   
"""
# ----------------------------------------------------------------------
import os
import sys
import logging
import json
import subprocess
import platform
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QListView, QTextEdit, QMessageBox, QPushButton,
    QHBoxLayout, QLabel
)
from PyQt5.QtCore import QStringListModel, Qt, QTimer, pyqtSignal as Signal
# LOGGING --------------------------------------------------------------
class CRDLogger:
    _instance = None

    def __new__(cls, name):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.name = name
            cls._instance.datestamp = datetime.now().strftime('%m%d%Y') 
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cls._instance.logs_dir = os.path.join(base_dir, "..", "logs")
            try:
                os.makedirs(cls._instance.logs_dir, exist_ok=True)
            except (OSError, PermissionError) as e:
                cls._instance.logs_dir = os.path.expanduser("~/logs") 
                os.makedirs(cls._instance.logs_dir, exist_ok=True)
            cls._instance.log_file = os.path.join(cls._instance.logs_dir, f"CRD_{cls._instance.datestamp}.log")
            cls._instance.configure_logging()
        return cls._instance
# ----------------------------------------------------------------------
    def configure_logging(self):
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            try:
                file_handler = logging.FileHandler(self.log_file, mode='a')  
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except (OSError, PermissionError) as e:
                pass
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.propagate = False 
# ----------------------------------------------------------------------
    def get_logger(self):
        return logging.getLogger(self.name)
# ----------------------------------------------------------------------
class Paths:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    CONFIG_DIR = os.path.join(PARENT_DIR, 'config')
    LOG_DIR = os.path.join(PARENT_DIR, 'logs')
# CLASS FOR MESSAGE BOX ------------------------------------------------
class CustomMessageBox(QMessageBox):
    def __init__(self, title="", message="", msg_type=QMessageBox.Icon.Information, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(msg_type)
        self.setStyleSheet("""
            QMessageBox {
                background-color: #404040;
                color: lightgray;
            }
            QMessageBox QLabel {
                color: white;
            }
            QMessageBox QPushButton {
                background-color: gray;
                color: white;
                border: 1px solid gray;
                padding: 5px;
            }
            QMessageBox QPushButton:hover {
                background-color: red;
            }
        """)
        self.setStandardButtons(QMessageBox.StandardButton.Cancel)
        self.adjustSize()

    def center(self):
        if self.parent() is not None:
            parent_geometry = self.parent().geometry()
            self.move(
                parent_geometry.x() + (parent_geometry.width() - self.width()) // 2,
                parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            )

    def exec_custom(self):
        return self.exec()
# ----------------------------------------------------------------------