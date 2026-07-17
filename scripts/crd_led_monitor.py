# ----------------------------------------------------------------------
"""
crd_led_monitor (ew)
Manages Connectivity For the VPN DB /LED
Version 1.06 Updated 07/10/26
"""
# ----------------------------------------------------------------------
import sys, os, time  
import configparser, importlib, logging
import threading  
import subprocess, socket  
from typing import Optional  
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QTabWidget,  
                             QMessageBox, QStackedWidget, QMainWindow, QTreeWidget)  
from PyQt5.QtGui import QColor, QPainter, QBrush  
from PyQt5.QtCore import QSize, Qt, QUrl, QObject, pyqtSignal, QThread
from PyQt5.QtWebEngineWidgets import QWebEngineView
# VPN TUNNEL MONITOR FOR LED'S -----------------------------------------
class TunnelMonitorWorker(QThread):  
    status_signal = pyqtSignal(bool)  
    def __init__(self, sp_ip, parent=None):  
        super().__init__(parent)  
        self.sp_ip = sp_ip
        self.running = True

    def run(self):  
        while self.running:  
            cwan_status = self.is_tunnel_open(self.sp_ip, port=443)  
            barracuda_status = self.is_tunnel_open(self.sp_ip, port=80)  
            is_connected = cwan_status or barracuda_status   
            self.status_signal.emit(is_connected)  
            self.msleep(10000) 
# ----------------------------------------------------------------------
    def start_monitoring(self):  
        if not self.isRunning():  
            self.start()
# ----------------------------------------------------------------------
    def stop(self):  
        self.running = False
        self.wait()

    @staticmethod  
    def is_tunnel_open(ip, port, timeout=5):  
        try:  
            with socket.create_connection((ip, port), timeout=timeout):  
                return True  
        except (socket.timeout, ConnectionRefusedError, OSError):  
            return False
# CLASS LEDS -----------------------------------------------------------
class LedWidget(QLabel):  
    def __init__(self, parent=None, diameter=20):  
        super().__init__(parent)  
        self.diameter = diameter  
        self.setFixedSize(QSize(diameter, diameter))    
        self.color = QColor("gray")  
        self.set_status(is_on=False)  
# ----------------------------------------------------------------------
    def set_status(self, is_on: bool):  
        if is_on:  
            self.setStyleSheet("background-color: #202020;")  
            self.color = QColor("lime") 
        else:  
            self.setStyleSheet("background-color: #202020;")   
            self.color = QColor("gray") 
        self.update()  
# ----------------------------------------------------------------------
    def paintEvent(self, event):  
        painter = QPainter(self)  
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  
        painter.setBrush(QBrush(self.color))  
        rect = self.rect().adjusted(2, 2, -2, -2)  
        painter.drawEllipse(rect) 
# ----------------------------------------------------------------------
    def update_connection_status(self, is_connected: bool):  
        self.set_status(is_on=is_connected)

# CLASS CONNECTION MONITOR THREAD ---------------------------------------
class ConnectionMonitorThread(QThread):  
    connection_status_changed = pyqtSignal(bool)  
    def __init__(self, ip_address, tunnel_type='default'):  
        super().__init__()  
        self.ip_address = ip_address  
        self.tunnel_type = tunnel_type  
        self.monitoring = True  
# ----------------------------------------------------------------------
    def run(self):  
        while self.monitoring:  
            is_connected = self.check_connectivity()  
            self.connection_status_changed.emit(is_connected)  
            self.msleep(5000) 
# ----------------------------------------------------------------------
    def check_connectivity(self):  
        if self.tunnel_type == 'barracuda':  
            return self.check_barracuda_tunnel()  
        else:  
            return self.default_connectivity_check()  
# ----------------------------------------------------------------------
    def default_connectivity_check(self):  
        try:  
            socket.create_connection((self.ip_address, 22), timeout=5)  
            return True  
        except (socket.timeout, socket.error):  
            return False  
# ----------------------------------------------------------------------
    def check_barracuda_tunnel(self):  
        try:   
            result = subprocess.run(['ping', '-n', '1', self.ip_address],   
                                    capture_output=True, text=True)  
            return result.returncode == 0  
        except Exception:  
            return False  
# ----------------------------------------------------------------------
    def stop(self):  
        self.monitoring = False  
        self.wait()

# CLASS CONNECTIVITY INDICATOR -----------------------------------------
class ConnectivityIndicator(QLabel):  
    def __init__(self, parent=None):  
        super().__init__(parent)  
        self.setFixedSize(20, 20)  
        self.setStyleSheet("""  
            background-color: red;  
            border-radius: 10px;  
        """)
# ----------------------------------------------------------------------
    def set_status(self, is_connected):  
        color = "green" if is_connected else "red"  
        self.setStyleSheet(f"""  
            background-color: {color};  
            border-radius: 10px;  
        """)  
# ----------------------------------------------------------------------
    def show_reconnect_popup(self):  
        from PyQt5.QtWidgets import QMessageBox  
        msg_box = QMessageBox()  
        msg_box.setIcon(QMessageBox.Warning)  
        msg_box.setText("Network Connection Lost")  
        msg_box.setInformativeText("Please Re-Establish The VPN Connection")  
        msg_box.setWindowTitle("Connection Error")  
        msg_box.exec_()  
# ----------------------------------------------------------------------
    def cleanup_connectivity_monitoring(self):  
        if hasattr(self, 'connectivity_monitor') and self.connectivity_monitor:  
            self.connectivity_monitor.stop()
# ----------------------------------------------------------------------