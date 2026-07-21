"""
---------------------------------------------------------------------------------------------
JSmyser
Version 1.30 Updated 06/02/26
---------------------------------------------------------------------------------------------
"""
VERSION = "HPM2_Monitor_V1_30"

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from dateutil.relativedelta import relativedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QLineEdit, QDialog, QCheckBox,
                             QFrame, QSizePolicy, QDateEdit, QSpacerItem, QFileDialog, 
                             QTextEdit, QMessageBox)
from PyQt5.QtCore import QTimer, Qt, QRectF, QPointF, QPoint, QDate
from PyQt5.QtGui import (QPainter, QPen, QColor, QFont, QLinearGradient, QCursor, QPixmap, 
                         QTextCursor, QPainterPath)
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import glob
import re
import time
from tzlocal import get_localzone
import zoneinfo
import json
import serial
import subprocess
import shutil
# Optional dependencies for firmware update (METROBOOT detection)
try:
    import win32api
    import psutil
    HAS_FIRMWARE_SUPPORT = True
except ImportError:
    win32api = None
    psutil = None
    HAS_FIRMWARE_SUPPORT = False

def get_base_path():
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe), use the directory of the executable
        return os.path.dirname(sys.executable)
    else:
        # Otherwise, use the directory of the Python script
        return os.path.dirname(os.path.abspath(__file__))

LOG_FOLDERS = [
#    {"path": os.path.join(get_base_path(), "logs"), "recursive": True},
#    {"path": os.path.join(get_base_path()), "recursive": False},
#    {"path": os.path.join(get_base_path(), "..", "downloads"), "recursive": True},
#    {"path": r"c:\crd\downloads", "recursive": True},
    {"path": r"c:\programdata\helium_pressure_monitor", "recursive": False},
            ]

CONFIG_FILE = os.path.join(get_base_path(), "hpm2_data.json")
FIRMWARE_DIR = os.path.join(get_base_path(), "HPM2_Firmware")
DEFAULT_CURRENTDB_PATH = "C:/CRD/config/current.dat"

DARK_BG = QColor(30, 30, 30)
TEXT_COLOR = QColor(200, 200, 200)
FRAME_BG = QColor(40, 40, 40)
BORDER = QColor(80, 80, 80)

# New colors for better visibility
LIGHT_GREEN = QColor(120, 255, 140)   # Nice bright but not neon green
WARNING_YELLOW = QColor(255, 240, 100)
CRITICAL_RED = QColor(255, 90, 90)
SOFT_GRAY = QColor(200, 200, 210) 

class CustomTooltip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()}; border: 1px solid {TEXT_COLOR.name()}; padding: 5px;")
        self.setFont(QFont("Arial", 10))
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setTextFormat(Qt.RichText)
        self.hide()

    def show_at(self, pos, text):
        self.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()

    def hide(self):
        super().hide()

class CustomQLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window().toggle_gauge_section()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

class CustomQFrame(QFrame):
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window().toggle_gauge_section()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

class DialGauge(QWidget):
    def __init__(self, min_value=-2, max_value=3, red_ranges=None, yellow_ranges=None, green_ranges=None, parent=None):
        # Initialize the gauge with specified value ranges and color-coded regions
        super().__init__(parent)
        self.min_value = min_value  # Minimum gauge value
        self.max_value = max_value  # Maximum gauge value
        self.red_ranges = red_ranges or []  # Red zones indicating critical ranges
        self.yellow_ranges = yellow_ranges or []  # Yellow zones indicating warning ranges
        self.green_ranges = green_ranges or []  # Green zones indicating safe ranges
        self.value = 0  # Current gauge value
        self.mag_value = 0
        self.setMinimumSize(400, 200)  # Minimum dimensions for the gauge
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background-color: {DARK_BG.name()};")

    def setValue(self, value):
        # Set the gauge value, clamping it between min_value and max_value
        self.mag_value = value
        self.value = max(self.min_value, min(self.max_value, value))
        self.update()

    def paintEvent(self, event):
        # Render the gauge with colored arcs, ticks, labels, needle, and center dot
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        size_y = rect.height()
        size = size_y * 2.2
        gauge_rect = QRectF(rect.center().x() - size/2, rect.center().y() - size/3, size, size/1)
        arc_rect = QRectF(rect.center().x() - size/2, rect.center().y() - size/2.515, size * 0.34, size*0.34)
        
        # Draw background gradient
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, DARK_BG)
        gradient.setColorAt(1, QColor(50, 50, 50))
        painter.fillRect(rect, gradient)
        
        # Transform to center for drawing arcs and needle
        painter.translate(gauge_rect.center().x(), gauge_rect.center().y())
        painter.scale(2.0, 1.8)
        
        span = self.max_value - self.min_value
        # Draw red arcs for critical ranges
        for r_min, r_max in self.red_ranges:
            start_value = r_min
            end_value = r_max
            start_angle = 180 - ((start_value - self.min_value) / span * 180)
            span_angle = -((end_value - start_value) / span * 180)
            painter.setPen(QPen(QColor('red'), 12, Qt.SolidLine, Qt.FlatCap))
            painter.drawArc(QRectF(-arc_rect.width()/2, arc_rect.y(), arc_rect.width(), arc_rect.height()), 
                           int(start_angle * 16), int(span_angle * 16))
        
        # Draw yellow arcs for warning ranges
        for y_min, y_max in self.yellow_ranges:
            start_value = y_min
            end_value = y_max
            start_angle = 180 - ((start_value - self.min_value) / span * 180)
            span_angle = -((end_value - start_value) / span * 180)
            painter.setPen(QPen(QColor('yellow'), 12, Qt.SolidLine, Qt.FlatCap))
            painter.drawArc(QRectF(-arc_rect.width()/2, arc_rect.y(), arc_rect.width(), arc_rect.height()), 
                           int(start_angle * 16), int(span_angle * 16))
        
        # Draw green arcs for safe ranges
        for g_min, g_max in self.green_ranges:
            start_value = g_min
            end_value = g_max
            start_angle = 180 - ((start_value - self.min_value) / span * 180)
            span_angle = -((end_value - start_value) / span * 180)
            painter.setPen(QPen(QColor('green'), 12, Qt.SolidLine, Qt.FlatCap))
            painter.drawArc(QRectF(-arc_rect.width()/2, arc_rect.y(), arc_rect.width(), arc_rect.height()), 
                           int(start_angle * 16), int(span_angle * 16))
        
        # Draw tick marks and labels
        painter.setPen(QPen(TEXT_COLOR, 2))
        for value in range(int(self.min_value * 2), int(self.max_value * 2) + 1):
            tick_value = value / 2.0
            angle = 270 + ((tick_value - self.min_value) / span * 180)
            painter.save()
            painter.rotate(angle)
            pen_width = 4 if abs(tick_value - 0.5) < 0.01 else 2
            painter.setPen(QPen(TEXT_COLOR, pen_width))
            painter.drawLine(QPointF(0, -size/5.5), QPointF(0, -size/6.5))  # Larger ticks
            if value % 2 == 0 or abs(tick_value - 0.5) < 0.01:
                painter.setFont(QFont("Helvetica", int(size * 0.0135)))
                painter.drawText(QPointF(-size/50, -size/5.2), f"{tick_value:.1f}")
            # Add small ticks at 0.1 intervals within range and correct angle
            if -1.9 <= tick_value <= 2.9:  # Adjusted to prevent boundary overflow
                for offset in [-0.4, -0.3, -0.2, -0.1, 0.1, 0.2, 0.3, 0.4]:
                    sub_tick_value = tick_value + offset
                    if -2.0 <= sub_tick_value <= 3.0:  # Double-check range
                        sub_angle = 270 + ((sub_tick_value - self.min_value) / span * 180)
                        # Adjust angle to 270–450 range (180-degree arc wrapping)
                        adjusted_angle = sub_angle if sub_angle <= 450 else sub_angle - 360
                        if 270 <= adjusted_angle <= 450:  # Constrain to full 180-degree span
                            painter.save()
                            painter.rotate(adjusted_angle - angle)  # Relative rotation
                            painter.setPen(QPen(TEXT_COLOR, 1))  # Thinner pen for small ticks
                            painter.drawLine(QPointF(0, -size/6.0), QPointF(0, -size/5.8))  # Shorter ticks
                            painter.restore()
            painter.restore()
        
        # Draw needle pointing to current value (red)
        angle = 270 + ((self.value - self.min_value) / span * 180)
        painter.setPen(QPen(QColor(255, 69, 0), 2, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(QColor(255, 83, 0))
        painter.rotate(angle)
        needle_path = QPainterPath()
        needle_path.moveTo(0, -size/6)
        needle_path.lineTo(-3, 0)
        needle_path.lineTo(3, 0)
        needle_path.closeSubpath()
        painter.drawPath(needle_path)
        
        # Draw center dot and digital readout (slightly more than half, shifted down)
        painter.resetTransform()
        center_size = size / 2.5
        center_rect = QRectF(rect.center().x() - center_size/2, rect.center().y() - center_size/2 + size/6 + 10, center_size, center_size)  # Shifted down by 10 units
        painter.setPen(Qt.NoPen)  # Reset pen to remove outline
        painter.setBrush(QColor(20, 20, 20))  # Dark grey background
        painter.drawPie(center_rect, 0 * 16, 180 * 16)  # Start at 0 degrees, span 180 degrees
        painter.setPen(QPen(QColor(100, 100, 100), 1))  # Grey line
        painter.drawPie(QRectF(rect.center().x() - (center_size/2 - 5), rect.center().y() - (center_size/2 - 5) + size/6 + 9, center_size - 10, center_size - 14), 0 * 16, 180 * 16)  # Top half grey line
        
        # Shift text up from center with dynamic size
        text_y_offset = center_rect.top() + (center_rect.height() * -0.1)  # Using your working offset
        font = QFont("Helvetica", int(center_size * 0.1), QFont.Bold)  # 10% of center_size as base font size
        painter.setPen(QPen(TEXT_COLOR, 2))
        painter.setFont(font)
        painter.drawText(QRectF(center_rect.left(), text_y_offset, center_rect.width(), center_rect.height() * 0.85), Qt.AlignCenter, f"{self.mag_value:.2f} psi")  # Digital value and unit

    def mouseDoubleClickEvent(self, event):
        # Handle double-click to toggle gauge section visibility
        if event.button() == Qt.LeftButton:
            self.window().toggle_gauge_section()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)




class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tools")
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")
        
        self.layout = QVBoxLayout()
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(15, 15, 15, 15)

    # GUI version (hardcoded or from your own VERSION variable)
        gui_ver_layout = QHBoxLayout()
        gui_ver_layout.setSpacing(10)
        gui_ver_layout.setContentsMargins(0, 0, 0, 0)        
        gui_ver_text = (QLabel("HPM2 Monitor Ver.:"))
        gui_ver_text.setFixedWidth(120)  # ← set to longest label width
        gui_ver_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)        
        gui_ver_layout.addWidget(gui_ver_text)
        self.gui_ver_label = QLabel(VERSION)
        self.gui_ver_label.setStyleSheet("color: #00cc00; font-weight: bold;")
        gui_ver_layout.addWidget(self.gui_ver_label, stretch=1)
        self.layout.addLayout(gui_ver_layout)

        # Check if config file exists (standalone mode?)
        is_standalone = not os.path.exists(CONFIG_FILE)

        if is_standalone:
            # Standalone mode: only show GUI version + a note
            standalone_note = QLabel("Standalone Mode (No service config found)")
            standalone_note.setStyleSheet("color: #888888; font-style: italic;")
            standalone_note.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(standalone_note)
            self.layout.addStretch()
            self.setLayout(self.layout)
            return  # ← exit early - nothing else added

    # Service version from JSON
        service_ver_layout = QHBoxLayout()
        service_ver_layout.setSpacing(10)
        service_ver_layout.setContentsMargins(0, 0, 0, 0)         
        service_ver_text = QLabel("HPM2 Service Ver.:")
        service_ver_text.setFixedWidth(120)  # ← set to longest label width
        service_ver_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)          
        service_ver_layout.addWidget(service_ver_text)
        self.service_ver_label = QLabel("Checking...")
        self.service_ver_label.setStyleSheet("color: #00cc00; font-weight: bold;")
        service_ver_layout.addWidget(self.service_ver_label, stretch=1)
        self.layout.addLayout(service_ver_layout)

        self.add_separator()

    # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        sample_btn = QPushButton("Take Sample")
        sample_btn.clicked.connect(self.take_sample)
        actions_layout.addWidget(sample_btn)

        reboot_btn = QPushButton("Reboot Controller")
        reboot_btn.clicked.connect(self.reboot_controller)
        actions_layout.addWidget(reboot_btn)        

        # Terminal button
        terminal_btn = QPushButton("Open Terminal")
        terminal_btn.clicked.connect(self.open_terminal)
        actions_layout.addWidget(terminal_btn)

        open_manual_btn = QPushButton("Open Manual")
        open_manual_btn.clicked.connect(self.open_manual)
        actions_layout.addWidget(open_manual_btn)

        log_btn = QPushButton("View Error Log")
        log_btn.clicked.connect(self.open_error_log)
        actions_layout.addWidget(log_btn)

        self.layout.addLayout(actions_layout)
        self.layout.addStretch()

        self.setLayout(self.layout)

        self.add_separator()

    # Current offset row - same label width for perfect alignment
        offset_layout = QHBoxLayout()
        offset_layout.setSpacing(10)
        offset_layout.setContentsMargins(0, 0, 0, 0)

        offset_label_text = QLabel("Current Offset:")
        offset_label_text.setFixedWidth(120)  # same as above
        offset_label_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        offset_layout.addWidget(offset_label_text)

        self.offset_label = QLabel("0.00")
        self.offset_label.setStyleSheet("color: #00cc00; font-weight: bold;")
        offset_layout.addWidget(self.offset_label)  # value expands right

        self.offset_warning = QLabel("")
        self.offset_warning.setStyleSheet("color: #ff4444; font-weight: bold;")
        offset_layout.addWidget(self.offset_warning, stretch=1)

        self.layout.addLayout(offset_layout)
        self._offset_raw_valid = False

        # Gauge pressure input
        gauge_layout = QHBoxLayout()
        gauge_layout.addWidget(QLabel("Gauge Pressure:"))
        self.gauge_input = QLineEdit()
        self.gauge_input.setPlaceholderText("e.g. 0.5")
        self.gauge_input.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
    #    self.gauge_input.returnPressed.connect(self.send_gauge_offset)
        gauge_layout.addWidget(self.gauge_input)
        self.set_gauge_btn = QPushButton("Set Offset (Gauge)")
        self.set_gauge_btn.clicked.connect(self.send_gauge_offset)
        gauge_layout.addWidget(self.set_gauge_btn)
        self.layout.addLayout(gauge_layout)

        # Manual offset input
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Manual Offset:"))
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("e.g. 0.50 or -1.23")
        self.manual_input.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.manual_input.returnPressed.connect(self.send_manual_offset)
        manual_layout.addWidget(self.manual_input)
        set_manual_btn = QPushButton("Set Manual Offset")
        set_manual_btn.clicked.connect(self.send_manual_offset)
        manual_layout.addWidget(set_manual_btn)
        self.layout.addLayout(manual_layout)

        # Reset button
        reset_btn = QPushButton("Reset Offset to 0.00")
        reset_btn.clicked.connect(self.send_reset_offset)
        self.layout.addWidget(reset_btn)

        self.add_separator()

    # Firmware version row
        fw_layout = QHBoxLayout()
        fw_layout.setSpacing(10)
        fw_layout.setContentsMargins(0, 0, 0, 0)

        # Label pushed left, fixed width for alignment
        fw_label_text = QLabel("Controller Firmware:")
        fw_label_text.setFixedWidth(120)  
        fw_label_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        fw_layout.addWidget(fw_label_text)

        self.fw_label = QLabel("Checking...")
        self.fw_label.setStyleSheet("color: #00cc00; font-weight: bold;")
        fw_layout.addWidget(self.fw_label)  # value expands right

        self.fw_warning = QLabel("")
        self.fw_warning.setStyleSheet("color: #ff4444; font-weight: bold;")
        fw_layout.addWidget(self.fw_warning, stretch=1)

        self.layout.addLayout(fw_layout)

        self.fw_update_btn = QPushButton("Update Firmware")
        self.fw_update_btn.clicked.connect(self.update_firmware)
        self.layout.addWidget(self.fw_update_btn)

        self.add_separator()

    # Service name display (read-only for now) 
        service_name_layout = QHBoxLayout()
        service_name_layout.setSpacing(10)
        service_name_layout.setContentsMargins(0, 0, 0, 0)        
        service_name_text = QLabel("Service Name:")
        service_name_text.setFixedWidth(90)  
        service_name_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)         
        service_name_layout.addWidget(service_name_text)
        self.service_name_label = QLabel("HPM2_Service") # <<================ NEEDS TO PULL SERVICE NAME ================================================ 
        self.service_name_label.setFixedWidth(120)   
        self.service_name_label.setStyleSheet("color: #00cccc;")
        service_name_layout.addWidget(self.service_name_label)
        status_label_text = QLabel("Status:")
        service_name_layout.addWidget(status_label_text)

        self.service_status = QLabel("Checking...")
        self.service_status.setStyleSheet("color: #00cc00; font-weight: bold;")
        service_name_layout.addWidget(self.service_status, stretch=1)
        self.layout.addLayout(service_name_layout)

        # Service layout control buttons
        service_layout = QHBoxLayout()
        service_layout.setSpacing(10)
        start_btn = QPushButton("Start Service")
        start_btn.clicked.connect(self.start_service)
        service_layout.addWidget(start_btn)
        stop_btn = QPushButton("Stop Service")
        stop_btn.clicked.connect(self.stop_service)
        service_layout.addWidget(stop_btn)
        restart_btn = QPushButton("Restart Service")
        restart_btn.clicked.connect(self.restart_service)
        service_layout.addWidget(restart_btn)
        self.layout.addLayout(service_layout)

        self.add_separator()
        
        com_msg_layout = QHBoxLayout()
        com_msg_layout.setSpacing(10)
        com_msg_layout.setContentsMargins(80, 0, 0, 0)        
        com_msg_text = QLabel("Changing COM Port might require system reboot.")
    #    com_msg_text.setFixedWidth(120)  
    #    com_msg_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    #    com_msg_text.setAlignment(Qt.AlignCenter)              
        com_msg_layout.addWidget(com_msg_text)
        self.layout.addLayout(com_msg_layout)

    # COM port editor (loads from JSON)
        com_layout = QHBoxLayout()
        com_layout.setSpacing(10)
        com_layout.setContentsMargins(0, 0, 0, 0) 
        com_layout.addWidget(QLabel("COM Port:"))
        self.com_input = QLineEdit("9")  # default
        self.com_input.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.com_input.returnPressed.connect(self.apply_com_port)
        self.com_input.setFixedWidth(100)
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            loaded_port = config.get("config", {}).get("com_port", "COM9")
            
            # Strip "COM" if present, so we only show the number
            if isinstance(loaded_port, str) and loaded_port.upper().startswith("COM"):
                loaded_port = loaded_port[3:].strip()
            
            self.com_input.setText(loaded_port)
        except:
            self.com_input.setText("9")   # default
        com_layout.addWidget(self.com_input)
        apply_com_btn = QPushButton("Apply and Restart Service")
        apply_com_btn.clicked.connect(self.apply_com_port)
        com_layout.addWidget(apply_com_btn, stretch=1)
        self.layout.addLayout(com_layout)
        self.add_separator()
        
    # Polling timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_labels)
        self.status_timer.start(5000)  # 5 seconds

    # Initial update
        self.update_status_labels()



#### HELPER FUNCTIONS =============================================================================

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            event.accept()
            return
        super().keyPressEvent(event)

    def add_separator(self):
        """Add a clean horizontal separator line"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {BORDER.name()}; max-height: 2px;")
        self.layout.addWidget(line)

    def send_command(self, payload):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            config["pending_command"] = payload
            with open(CONFIG_FILE + ".tmp", 'w') as f:
                json.dump(config, f, indent=2)
            os.replace(CONFIG_FILE + ".tmp", CONFIG_FILE)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send command:\n{e}")

    def show_temp_message(self, title, text, timeout_ms=5000):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.NoButton)
        msg.setAttribute(Qt.WA_DeleteOnClose, True)
        msg.setModal(False)

        def auto_close():
            if msg.isVisible():
                msg.reject()  # or msg.close() — reject is more reliable here
        QTimer.singleShot(timeout_ms, auto_close)

        msg.show()



#### VERSION UPDATES ========================================================================================

    def update_status_labels(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            status = config.get("status", {})

            service_ver = status.get("service_version", "Unknown")
            offset_raw = status.get("real_offset", "Unknown")
            offset_warning = status.get("offset_warning", "")
            fw = status.get("firmware_version", "Unknown")

            # Service Version
            self.service_ver_label.setText(service_ver)
            if service_ver == "Unknown" or service_ver == "Error":
                self.service_ver_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            else:
                self.service_ver_label.setStyleSheet("color: #00cc00; font-weight: bold;")

            # Offset + Offset Warning
            if offset_raw == "Unknown" or offset_raw is None or offset_raw == "" or offset_warning != "":
                self.offset_label.setText(str(offset_raw))
                self.offset_label.setStyleSheet("color: #ff4444; font-weight: bold;")
                self.set_gauge_btn.setEnabled(False)
                self.set_gauge_btn.setStyleSheet("color: #666666;")
                if self._offset_raw_valid:
                    try:
                        self.gauge_input.returnPressed.disconnect()
                    except TypeError:
                        pass
                    self._offset_raw_valid = False
                
                if offset_warning:
                    self.offset_warning.setText(str(offset_warning))
                    self.offset_warning.setStyleSheet("color: #ff4444; font-weight: bold;")
                else:
                    self.offset_warning.setText("")
            else:
                try:
                    offset_float = float(offset_raw)
                    self.offset_label.setText(f"{offset_float:.2f}")
                    self.offset_label.setStyleSheet("color: #00cc00; font-weight: bold;")
                    self.offset_warning.setText("")   # clear warning when offset is good
                    self.set_gauge_btn.setEnabled(True)
                    self.set_gauge_btn.setStyleSheet("")
                    if not self._offset_raw_valid:
                        self.gauge_input.returnPressed.connect(self.send_gauge_offset)
                        self._offset_raw_valid = True
                except (ValueError, TypeError):
                    self.offset_label.setText("Error")
                    self.offset_label.setStyleSheet("color: #ff4444; font-weight: bold;")
                    self.offset_warning.setText("")
                    self.set_gauge_btn.setEnabled(False)
                    self.set_gauge_btn.setStyleSheet("color: #666666;")
                    if self._offset_raw_valid:
                        try:
                            self.gauge_input.returnPressed.disconnect()
                        except TypeError:
                            pass
                        self._offset_raw_valid = False

            # Firmware Version
            self.fw_label.setText(fw)
            if fw == "Unknown" or fw == "Error":
                self.fw_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            else:
                self.fw_label.setStyleSheet("color: #00cc00; font-weight: bold;")

            self.update_firmware_warning(fw)
            self.update_service_status()

        except Exception as e:
            self.service_ver_label.setText("Error")
            self.service_ver_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.offset_label.setText("Error")
            self.offset_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.offset_warning.setText("")
            self.fw_label.setText("Error")
            self.fw_label.setStyleSheet("color: #ff4444; font-weight: bold;")            
            self.fw_warning.setText("")
            print(f"Error updating status labels: {e}")

    def update_firmware_warning(self, device_fw):
        try:
            if device_fw == "Unknown":
                self.fw_warning.setText("See Error Log")
                self.fw_label.setStyleSheet("color: #ff4444; font-weight: bold;")
                self.fw_update_btn.setEnabled(True)
                self.fw_update_btn.setStyleSheet("")
                return

            uf2_files = [f for f in os.listdir(FIRMWARE_DIR) if f.endswith('.uf2')]
            if not uf2_files:
                self.show_temp_message("Firmware Error", "No .uf2 files found in HPM2_Firmware folder.")
                self.fw_warning.setText("")
                return

            latest_file = max(uf2_files)
            file_version = latest_file.replace('.uf2', '')

            if file_version > device_fw:
                self.fw_update_btn.setEnabled(True)
                self.fw_update_btn.setStyleSheet("")
                self.fw_warning.setText("New firmware is available.")
                self.fw_label.setStyleSheet("color: #cccc00; font-weight: bold;")
            elif file_version < device_fw:
                self.fw_update_btn.setEnabled(True)
                self.fw_update_btn.setStyleSheet("")
                self.fw_warning.setText("Controller has newer firmware than HPM2_Firmware folder.")
                self.fw_label.setStyleSheet("color: #cccc00; font-weight: bold;")
            else:
                self.fw_warning.setText("")
                self.fw_label.setStyleSheet("color: #00cc00; font-weight: bold;")
                self.fw_update_btn.setEnabled(False)
                self.fw_update_btn.setStyleSheet("color: #666666;")
        except:
            self.fw_warning.setText("")



#### ACTION BUTTONS ==========================================================================

    def take_sample(self):
        self.show_temp_message("Action", "Taking Sample. Wait 20 seconds...")
        self.send_command({"type": "sample"})

    def reboot_controller(self):
        self.show_temp_message("Action", "Rebooting Controller. Wait 60 seconds...")
        self.send_command({"type": "reboot"})

    def open_terminal(self):
        # Load COM port from JSON
        com_port = "9"
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            com_port = config_data.get("config", {}).get("com_port", "9")
        except:
            pass

        # Check service status
        result = subprocess.run(['sc', 'query', 'HPM2_Service'], capture_output=True, text=True)
        if "RUNNING" in result.stdout:
            reply = QMessageBox.question(
                self, "Service Running",
                f"Terminal needs direct access to {com_port}.\nStop service now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            
            try:
                self.stop_service()
                # Wait a bit longer for stop_service to complete before opening terminal
                QTimer.singleShot(2000, lambda: self._open_terminal_dialog(com_port))
                return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to stop service:\n{e}")
                return

        # Service is already stopped
        self.show_temp_message("Service", f"Opening direct terminal on {com_port}...", timeout_ms=2500)
        self._open_terminal_dialog(com_port)

    def _open_terminal_dialog(self, com_port):
        """Helper to open terminal after service has stopped"""
        terminal = TerminalDialog(com_port=com_port, baud_rate=9600, parent=self)
        terminal.exec_()

    def open_manual(self):
        """Open a PDF file with the system's default viewer"""
        pdf_path = os.path.join(get_base_path(), "HPM2_Software_Manual_2.pdf")
        try:
            if os.path.exists(pdf_path):
                os.startfile(pdf_path)          # Windows only - opens with default app
                # self.show_temp_message("PDF", f"Opened: {os.path.basename(pdf_path)}")
            else:
                QMessageBox.warning(self, "File Not Found", 
                                  f"PDF file not found:\n{pdf_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"Failed to open PDF:\n{str(e)}")

    def open_error_log(self):
        today = datetime.now().strftime('%Y%m%d')
        log_path = os.path.join(get_base_path(), f"hpm2_app_error_{today}.log")
        if os.path.exists(log_path):
            os.startfile(log_path)
        else:
            QMessageBox.information(self, "No Log", "No error log for today yet.")



#### SETTING CONTROLLER OFFSET ==========================================================================

    def send_gauge_offset(self):
        text = self.gauge_input.text().strip()
        if not text:
            return

        # === Safety Check: Verify recent HPM2_Test_data.log file ===
        try:
            log_dir = os.path.join(get_base_path(), "..")
            test_files = [f for f in os.listdir(log_dir) if f.endswith("HPM2_Test_data.log")]

            if not test_files:
                self.show_temp_message("Offset Check", "No _HPM2_Test_data.log file found.\nPlease run a new test sample first.")
                return

            # Use the most recently modified test file
            latest_test_file = max(test_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
            file_path = os.path.join(log_dir, latest_test_file)

            # Check age (must be within last 5 minutes)
            age_seconds = time.time() - os.path.getmtime(file_path)

            if age_seconds > 300:   # 5 minutes
                self.show_temp_message("Offset Check", 
                    "HPM2_Test_data.log is older than 5 minutes.\n"
                    "Please take a sample first.")
                return

        except Exception as e:
            self.show_temp_message("Offset Check", f"Error checking test data file:\n{e}")
            return
        # === End of safety check ===

        try:
            value = float(text)
            self.show_temp_message("Setting Offset", "Calculating and Sending Offset. Wait 20 seconds...")
            self.send_command({"type": "set_offset", "gauge_pressure": value})
            self.gauge_input.clear()
            self.manual_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Gauge pressure must be a number.")

    def send_manual_offset(self):
        text = self.manual_input.text().strip()
        if not text:
            return
        try:
            value = float(text)
            self.show_temp_message("Setting Offset", "Sending Manual Offset. Wait 20 seconds...")
            self.send_command({"type": "set_offset", "new_offset": value})
            self.manual_input.clear()
            self.gauge_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Manual offset must be a number.")

    def send_reset_offset(self):
        self.show_temp_message("Setting Offset", "Resetting Offset. Wait 20 seconds...")
        self.send_command({"type": "set_offset", "new_offset": 0.00})
        self.gauge_input.clear()
        self.manual_input.clear()
        self.check_and_show_offset_errors()



#### FIRMWARE SECTION ===============================================================================

    def update_firmware(self):
        """Main firmware update handler"""
        if not HAS_FIRMWARE_SUPPORT:
            self.show_temp_message("Firmware Update", "Firmware Update not Supported")            
            return
        self.show_temp_message("Firmware Update", 
                                "Starting Firmware Update...")

        self.restart_service()
        QTimer.singleShot(1500, self._continue_firmware_update)

    def _continue_firmware_update(self):
        current_version = self.fw_label.text().strip()
        try:
            self.previous_offset = float(self.offset_label.text().strip())
        except:
            self.previous_offset = 0.0

        newest_uf2 = self.get_newest_uf2_file()
        if not newest_uf2:
            QMessageBox.warning(self, "Firmware Update", "No .uf2 files found in HPM2_Firmware folder.")
            return

        new_filename = os.path.basename(newest_uf2)

        if new_filename.replace('.uf2', '').strip() == current_version.replace('.uf2', '').strip():
            QMessageBox.information(self, "Firmware Update", 
                                    f"Firmware is already up-to-date.\nCurrent: {current_version}")
            return
        elif new_filename.replace('.uf2', '').strip() <= current_version.replace('.uf2', '').strip():
            reply = QMessageBox.question(
                self, "Firmware Update",
                f"Firmware in HPM2_Firmware folder is older than what's on controller. \ncurrent version: {current_version}\nnew verison: {new_filename}\nUpdate anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return       

        self.show_firmware_instructions(newest_uf2)

    def get_newest_uf2_file(self):
        try:
            uf2_files = [f for f in os.listdir(FIRMWARE_DIR) if f.lower().endswith('.uf2')]
            if not uf2_files:
                return None
            newest = max(uf2_files, key=lambda f: os.path.getmtime(os.path.join(FIRMWARE_DIR, f)))
            return os.path.join(FIRMWARE_DIR, newest)
        except:
            return None

    def show_firmware_instructions(self, uf2_path):
        self.new_uf2_path = uf2_path
        self.firmware_update_in_progress = True

        # Start polling immediately
        self.drive_poll_timer = QTimer(self)
        self.drive_poll_timer.timeout.connect(self.check_for_metroboot)
        self.drive_poll_timer.start(800)

        instructions = (
            "Firmware Update Instructions:\n\n"
            "1. Connect the controller to this computer using a USB-C cable.\n"
            "2. Locate the reset button on the controller (see picture).\n"
            "    (Note: Old controller's have reset1 pins instead of a reset button.)\n"
            "3. Quickly double-click the reset button. \n"
            "    (for reset1 pins, short the pins twice in quick succession to simiulate a double click.)\n"
        )

    #    base_dir = get_base_path()
        # Robust image path for both normal run and PyInstaller .exe
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            base_dir = sys._MEIPASS
        else:
            # Running as Python script
            base_dir = os.path.dirname(os.path.abspath(__file__))

        image_path = os.path.join(base_dir, "images", "reset_button.jpg")

        self.instructions_dialog = FirmwareUpdateDialog(self, instructions, image_path)
        
        # Connect finished signal to clean up timer if dialog is closed (Cancel or X)
        self.instructions_dialog.finished.connect(self._on_instructions_closed)
        
        self.instructions_dialog.exec_()

    def _on_instructions_closed(self):
        """Stop polling if user closes or cancels the dialog"""
        if hasattr(self, 'drive_poll_timer'):
            self.drive_poll_timer.stop()
        self.firmware_update_in_progress = False

    def check_for_metroboot(self):
        if not getattr(self, 'firmware_update_in_progress', False):
            return

        metroboot_path = self.find_metroboot_drive()
        if metroboot_path:
            self.drive_poll_timer.stop()
            
            # Automatically close the instructions dialog
            if hasattr(self, 'instructions_dialog') and self.instructions_dialog.isVisible():
                self.instructions_dialog.accept()
            self.perform_firmware_copy(metroboot_path)

    def find_metroboot_drive(self):

        for part in psutil.disk_partitions():
            if 'removable' in part.opts.lower() and part.mountpoint:
                try:
                    label = win32api.GetVolumeInformation(part.mountpoint)[0]
                    if label and 'METROBOOT' in label.upper():
                        return part.mountpoint
                except:
                    pass
        return None

    def perform_firmware_copy(self, drive_path):
        try:
            dest = os.path.join(drive_path, os.path.basename(self.new_uf2_path))
            shutil.copy2(self.new_uf2_path, dest)

            self.show_temp_message("Copy Complete", 
                                    "Firmware copied.\nWaiting for flash to complete (~10 seconds)...", timeout_ms=10000)

            QTimer.singleShot(10000, self.finish_firmware_update)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy firmware:\n{str(e)}")
            self.firmware_update_in_progress = False

    def finish_firmware_update(self):
        newest_uf2 = self.get_newest_uf2_file()
        new_version = os.path.basename(newest_uf2)
        value = self.previous_offset
        if abs(self.previous_offset) > 0:
            self.send_command({"type": "set_offset", "new_offset": value})
            self.check_and_show_offset_errors()
            QTimer.singleShot(7000, self.restart_service)
            QMessageBox.information(self, "Success", 
                f"Firmware successfully updated to {new_version}.\nAn Offset of {value} was re-applied.\nWait 2 minutes before trying anything else.")
        else:
            QTimer.singleShot(3000, self.restart_service)
            QMessageBox.information(self, "Success", 
                f"Firmware successfully updated to {new_version}.\nWait 2 minutes before trying anything else.")
        
        self.firmware_update_in_progress = False



#### SERVICE CONTROLS =============================================================================================

    def update_service_status(self):
        # Do not overwrite temporary status messages
        current_text = self.service_status.text().strip()
        if current_text in ("Starting...", "Stopping...", "Restarting..."):
            return

        try:
            result = subprocess.run(['sc', 'query', 'HPM2_Service'], 
                                  capture_output=True, 
                                  text=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)

            if "RUNNING" in result.stdout.upper():
                self.service_status.setText("RUNNING")
                self.service_status.setStyleSheet("color: #00cc00; font-weight: bold;")
            elif "STOPPED" in result.stdout.upper():
                self.service_status.setText("STOPPED")
                self.service_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            else:
                self.service_status.setText("UNKNOWN")
                self.service_status.setStyleSheet("color: #ffff00;")

        except Exception as e:
            self.service_status.setText("ERROR")
            self.service_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            print(f"Service check failed: {e}")

    def force_update_service_status(self):
        """Force update status - used after start/stop/restart operations"""
        try:
            result = subprocess.run(['sc', 'query', 'HPM2_Service'], 
                                  capture_output=True, 
                                  text=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)

            if "RUNNING" in result.stdout.upper():
                self.service_status.setText("RUNNING")
                self.service_status.setStyleSheet("color: #00cc00; font-weight: bold;")
            elif "STOPPED" in result.stdout.upper():
                self.service_status.setText("STOPPED")
                self.service_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            else:
                self.service_status.setText("UNKNOWN")
                self.service_status.setStyleSheet("color: #ffff00;")

        except Exception as e:
            self.service_status.setText("ERROR")
            self.service_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            print(f"Service check failed: {e}")            

    def start_service(self):
        """Start the HPM2_Service with proper UI feedback"""
        self.service_status.setText("Starting...")
        self.service_status.setStyleSheet("color: #ffff00; font-weight: bold;")

        # Use QTimer to let the UI update before running blocking subprocess calls
        QTimer.singleShot(1000, self._perform_start) 

    def _perform_start(self):
        result = subprocess.run(['sc', 'query', 'HPM2_Service'], capture_output=True, text=True)
        if "RUNNING" in result.stdout:
            self.show_temp_message("Service", "Service is already running.", timeout_ms=2500)
            self.service_status.setText("RUNNING")
            self.service_status.setStyleSheet("color: #00cc00; font-weight: bold;")            
            return
        try:
            subprocess.run(['net', 'start', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.force_update_service_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start service:\n{e}")

    def stop_service(self):
        """Stop the HPM2_Service with proper UI feedback"""
        self.service_status.setText("Stopping...")
        self.service_status.setStyleSheet("color: #ffff00; font-weight: bold;")

        # Use QTimer to let the UI update before running blocking subprocess calls
        QTimer.singleShot(1000, self._perform_stop)

    def _perform_stop(self):
        result = subprocess.run(['sc', 'query', 'HPM2_Service'], capture_output=True, text=True)
        if "STOPPED" in result.stdout or "not running" in result.stdout.lower():
            self.show_temp_message("Service", "Service is already stopped.", timeout_ms=2500)
            self.service_status.setText("STOPPED")
            self.service_status.setStyleSheet("color: #ff4444; font-weight: bold;")            
            return
        try:
            subprocess.run(['net', 'stop', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.force_update_service_status() 
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop service:\n{e}")

    def restart_service(self):
        """Restart the HPM2_Service with proper UI feedback"""
        # Immediately show "Restarting..." status
        self.service_status.setText("Restarting...")
        self.service_status.setStyleSheet("color: #ffff00; font-weight: bold;")

        # Use QTimer to let the UI update before running blocking subprocess calls
        QTimer.singleShot(1000, self._perform_restart)

    def _perform_restart(self):
        result = subprocess.run(['sc', 'query', 'HPM2_Service'], capture_output=True, text=True)
        if "RUNNING" not in result.stdout:
            try:
                subprocess.run(['net', 'start', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.update_service_status() 
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed:\n{e}")
            return

        try:
            subprocess.run(['net', 'stop', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            time.sleep(2)
            subprocess.run(['net', 'start', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            QTimer.singleShot(2000, self.force_update_service_status)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restart service:\n{e}")
        


#### COM PORT SETTING =====================================================================================

    def apply_com_port(self):
        new_port = self.com_input.text().strip()
        if not new_port:
            QMessageBox.warning(self, "Invalid", "Enter a COM port (e.g. 9)")
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            if "config" not in config:
                config["config"] = {}
            config["config"]["com_port"] = f"COM{new_port}"
            with open(CONFIG_FILE + ".tmp", 'w') as f:
                json.dump(config, f, indent=2)
            os.replace(CONFIG_FILE + ".tmp", CONFIG_FILE)

    #        QMessageBox.information(
    #            self, "Updated",
    #            f"COM port set to {new_port}.\n\n"
    #            "Note: Changes may require rebooting the computer to take effect."
    #        )
            self.restart_service()  # optional: auto-restart
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update COM port:\n{e}")





class FirmwareUpdateDialog(QDialog):
    def __init__(self, parent, instructions_text, image_path):
        super().__init__(parent)
        self.setWindowTitle("Firmware Update Instructions")
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")
        self.setMinimumWidth(580)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        instr_label = QLabel(instructions_text)
        instr_label.setWordWrap(True)
        instr_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(instr_label)

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(520, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_label = QLabel()
                img_label.setPixmap(pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(img_label)

        # Button layout with Cancel
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.setLayout(layout)
        layout.addLayout(btn_layout)





class TerminalDialog(QDialog):
    def __init__(self, com_port="COM9", baud_rate=9600, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Direct Terminal (Service Stopped)")
        self.setGeometry(200, 200, 900, 700)
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")

        self.com_port = com_port
        self.baud_rate = baud_rate
        self.ser = None

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Help label at the top (same text, grey color like before)
        help_label = QLabel("Hit ? then Enter for controller help menu")
        help_label.setStyleSheet("color: #cccc00; font-family: Consolas; font-size: 10pt;")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)

        # RX display
        self.rx_display = QTextEdit()
        self.rx_display.setReadOnly(True)
        self.rx_display.setStyleSheet(f"""
            background-color: #1e1e1e;
            color: #c8c8c8;
            font-family: Consolas;
            font-size: 12pt;
            border: 1px solid #505050;
        """)
        layout.addWidget(self.rx_display)

        # Input area
        input_layout = QHBoxLayout()
        self.tx_input = QLineEdit()
        self.tx_input.setPlaceholderText("Type command and press Enter...")
        self.tx_input.setStyleSheet(f"""
            background-color: #282828;
            color: #c8c8c8;
            font-family: Consolas;
            font-size: 12pt;
            padding: 6px;
            border: 1px solid #505050;
        """)
        self.tx_input.returnPressed.connect(self.send_command)
        input_layout.addWidget(self.tx_input)

        send_btn = QPushButton("Send")
        send_btn.setStyleSheet(f"background-color: #282828; color: #c8c8c8; padding: 6px;")
        send_btn.clicked.connect(self.send_command)
        input_layout.addWidget(send_btn)

        layout.addLayout(input_layout)
        self.setLayout(layout)

        # Read timer
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.read_serial)
        self.read_timer.start(100)

        self.open_serial()
        self.tx_input.setFocus()

    def open_serial(self):
        try:
            self.ser = serial.Serial(self.com_port, self.baud_rate, timeout=1)
            self.rx_display.append(f"Connected to {self.com_port} at {self.baud_rate} baud")
        except Exception as e:
            QMessageBox.critical(self, "Serial Error", f"Failed to open {self.com_port}:\n{e}")
            self.reject()

    def send_command(self):
        cmd = self.tx_input.text().strip()
        if not cmd or not self.ser or not self.ser.is_open:
            return

        try:
            self.ser.write((cmd + '\r\n').encode())
            self.ser.flush()
            self.rx_display.append(f"TX> {cmd}")
            self.rx_display.moveCursor(QTextCursor.End)
        except Exception as e:
            self.rx_display.append(f"Send error: {e}")

        self.tx_input.clear()

    def read_serial(self):
        if not self.ser or not self.ser.is_open:
            return

        try:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('ascii', errors='ignore').rstrip()
                self.rx_display.append(f"RX: {line}")
                self.rx_display.moveCursor(QTextCursor.End)
        except Exception as e:
            self.rx_display.append(f"Read error: {e}")

    def show_temp_message(self, title, text, timeout_ms=2500):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.NoButton)
        msg.setAttribute(Qt.WA_DeleteOnClose, True)
        msg.setModal(False)

        def auto_close():
            if msg.isVisible():
                msg.reject()  # or msg.close() — reject is more reliable here
        QTimer.singleShot(timeout_ms, auto_close)

        msg.show()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Restart Service",
            "Restart the service now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )

        if self.ser and self.ser.is_open:
            self.ser.close()

        if reply == QMessageBox.Yes:
#            try:
#                subprocess.run(['net', 'start', 'HPM2_Service'], check=True, timeout=15)
#                QMessageBox.information(self, "Restarted", "Service restarted.")
#            except Exception as e:
#                QMessageBox.warning(self, "Restart Failed", f"Could not restart:\n{e}")
            result = subprocess.run(['sc', 'query', 'HPM2_Service'], capture_output=True, text=True)
            if "RUNNING" in result.stdout:
                self.show_temp_message("Service", "Service is already running.")
                return
            try:
                subprocess.run(['net', 'start', 'HPM2_Service'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.show_temp_message("Service", "Service is starting...")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start service:\n{e}")                

        event.accept()



class MainWindow(QMainWindow):
    def __init__(self):
        # Initialize the main window
        super().__init__()

        # Set up window properties
        self.setWindowTitle(VERSION)
        self.setGeometry(0, 0, 1200, 800)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")
        self.errors = "n/a"
        self.start_date = None
        self.end_date = None     
        self.selected_sid = None
        self.sid_list = []
        self.cached_df = None
        self.all_log_folders = None
        self.section_states = {'gauge': True, 'pressure': True, 'water': True}
        self.is_fullscreen = False
        self.active_graph = None
        self.is_updating = False
        self.current_point_idx = None  # Track current point for arrow navigation
        self.active_plot = None  # Track which plot is active (pressure or water)
        self.pressure_y_default = [-1.05, 2.1]  # Default y-range for pressure plot
        self.water_y_default = [57, 83]  # Default y-range for water plot
        self.prev_update_key = None  # Track previous SID and date range
        self.is_keyboard_nav = False  # Track if keyboard navigation is active        
        self.selected_series = None # Track closest series for arrow key point selection
        self.known_files = {} # Persistent file info: {full_path: {'mtime': float, 'size': int}}
        self.is_processing = False
        self.selected_sid_dates = []
        # NOT USED FOR NOW.
        self.processed_files = set() # Track which files were already processed into cached_df


        # Initialize tooltips for plots
        self.pressure_tooltip = CustomTooltip(self)
        self.water_tooltip = CustomTooltip(self)
        self.pressure_pixel_cache = []   # list of (px_x, px_y, df_idx, series_key)
        self.water_pixel_cache = []      

        # Define semi-transparent cursor (global or in __init__)
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor(0, 0, 0, 50))  # 20% opacity black
        painter.drawEllipse(0, 0, 10, 10)  # Small circle
        painter.end()
        self.transparent_cursor = QCursor(pixmap)
        # Bold Font for graph ticks
        bold_font = QFont()
        bold_font.setBold(True)
        # Set up main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_widget.setLayout(main_layout)

        # Create top control layout
        top_control_layout = QHBoxLayout()
        top_control_layout.setContentsMargins(30, 10, 0, 0)
        settings_btn = QPushButton("Tools")
        settings_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        settings_btn.clicked.connect(self.open_settings)
        top_control_layout.addWidget(settings_btn)
        self.gauge_check = QCheckBox("Gauge Section")
        self.gauge_check.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.gauge_check.setChecked(True)
        self.gauge_check.stateChanged.connect(self.update_sections)
        top_control_layout.addWidget(self.gauge_check)
        self.pressure_check = QCheckBox("Magnet Press. Data")
        self.pressure_check.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.pressure_check.setChecked(True)
        self.pressure_check.stateChanged.connect(self.update_sections)
        top_control_layout.addWidget(self.pressure_check)
        self.water_check = QCheckBox("Water Temp. Data")
        self.water_check.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.water_check.setChecked(True)
        self.water_check.stateChanged.connect(self.update_sections)
        top_control_layout.addWidget(self.water_check)
        show_all_btn = QPushButton("Show All")
        show_all_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        show_all_btn.clicked.connect(self.show_all_sections)
        top_control_layout.addWidget(show_all_btn)
        top_control_layout.addSpacerItem(QSpacerItem(10, 0))
        sid_label = QLabel("Select SID:")
        sid_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        top_control_layout.addWidget(sid_label)
        self.sid_combo = QComboBox()
        self.sid_combo.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.sid_combo.currentTextChanged.connect(self.on_sid_changed)
        top_control_layout.addWidget(self.sid_combo)
        self.browse_log_folder_btn = QPushButton("Open Folder")
        self.browse_log_folder_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.browse_log_folder_btn.clicked.connect(self.open_log_folder)
        top_control_layout.addWidget(self.browse_log_folder_btn)
        self.search_folder = QLineEdit("Searching Default Folders")
        self.search_folder.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.search_folder.setMinimumWidth(175)
        top_control_layout.addWidget(self.search_folder)
        self.subfolder_search_cb = QCheckBox("Incl. Subfolders")
        self.subfolder_search_cb.setStyleSheet(f"""
            /* Label text color */
            QCheckBox {{
                color: {TEXT_COLOR.name()};
            }}

            '''
            /* Indicator box (unchecked) */
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {BORDER.name()};  /* -> '#646464' */
                background: {FRAME_BG.name()};
                border-radius: 3px; /* optional, rounded square */
                THIS ABOVE DOESN'T WORK, IT DELETES THE CHECK '''
            }}""")

        top_control_layout.addWidget(self.subfolder_search_cb)
        top_control_layout.addStretch()
        main_layout.addLayout(top_control_layout)

        # Set up fullscreen frame
        self.fullscreen_frame = CustomQFrame()
        self.fullscreen_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.fullscreen_frame.setStyleSheet(f"background-color: {FRAME_BG.name()};")
        self.fullscreen_layout = QVBoxLayout()
        self.fullscreen_layout.setContentsMargins(0, 10, 0, 0)
        self.fullscreen_layout.setSpacing(30)
        self.columns_widget = QWidget()
        self.columns_widget.setFixedHeight(140)
        self.columns_layout = QHBoxLayout()
        self.columns_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_layout.setSpacing(30)
        self.columns_layout.addStretch(2)
        self.left_display = CustomQLabel()
        self.left_display.setFont(QFont("Arial", 12))
        self.left_display.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.columns_layout.addWidget(self.left_display)
        self.right_display = CustomQLabel()
        self.right_display.setFont(QFont("Arial", 12))
        self.right_display.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.columns_layout.addWidget(self.right_display)
        self.columns_layout.addStretch(2)
        self.columns_layout.setStretch(0, 2)
        self.columns_layout.setStretch(1, 1)
        self.columns_layout.setStretch(2, 1)
        self.columns_layout.setStretch(3, 2)
        self.columns_widget.setLayout(self.columns_layout)
        self.fullscreen_layout.addWidget(self.columns_widget)
        self.fullscreen_gauge = DialGauge(min_value=-2, max_value=3,
                                         red_ranges=[(-2.0, 0.0), (1.75, 3.0)],
                                         yellow_ranges=[(0.0, 0.3), (0.6, 1.75)],
                                         green_ranges=[(0.3, 0.6)])
        self.fullscreen_layout.addWidget(self.fullscreen_gauge)
        self.fullscreen_layout.setStretch(0, 0)
        self.fullscreen_layout.setStretch(1, 3)
        self.fullscreen_layout.setStretch(2, 0)
        self.fullscreen_frame.setLayout(self.fullscreen_layout)
        self.fullscreen_frame.setVisible(False)
        main_layout.addWidget(self.fullscreen_frame)

        # Set up gauge section
        self.gauge_section = CustomQFrame()
        self.gauge_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.gauge_section.setStyleSheet(f"background-color: {FRAME_BG.name()};")
        self.gauge_section.setFixedHeight(250)
        self.gauge_layout = QHBoxLayout()
        self.gauge_layout.setContentsMargins(20, 20, 20, 20)
        self.gauge_layout.setSpacing(30)
        self.gauge_layout.addStretch(2)
        self.gauge = DialGauge(min_value=-2, max_value=3,
                              red_ranges=[(-2.0, 0.0), (1.75, 3.0)],
                              yellow_ranges=[(0.0, 0.3), (0.6, 1.75)],
                              green_ranges=[(0.3, 0.6)])
        self.gauge_layout.addWidget(self.gauge)
        self.gauge_layout.addWidget(self.left_display)
        self.gauge_layout.addWidget(self.right_display)
        self.gauge_layout.addStretch(2)
        self.gauge_layout.setStretch(0, 2)
        self.gauge_layout.setStretch(1, 1)
        self.gauge_layout.setStretch(2, 1)
        self.gauge_layout.setStretch(3, 1)
        self.gauge_layout.setStretch(4, 2)
        self.gauge_section.setLayout(self.gauge_layout)
        main_layout.addWidget(self.gauge_section)

        # Define custom widget for line-point icon
        class LinePointIcon(QWidget):
            def __init__(self, color, parent=None):
                super().__init__(parent)
                self.color = QColor(color)
                self.setFixedSize(20, 10)

            def paintEvent(self, event):
                # Draw line segment with point in the middle for series ICON
                painter = QPainter(self)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(QPen(self.color, 2, Qt.SolidLine))
                painter.drawLine(2, 5, 8, 5)
                painter.setBrush(self.color)
                painter.drawEllipse(QPointF(8, 5), 1.5, 1.5)
                painter.drawLine(8, 5, 14, 5)

        # Set up PRESSURE PLOT section
        self.pressure_section = QFrame()
        self.pressure_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.pressure_section.setStyleSheet(f"background-color: {FRAME_BG.name()};")
        pressure_layout = QVBoxLayout()
        self.pressure_plot = pg.PlotWidget(axisItems={'bottom': DateAxisItem(orientation='bottom')})
        self.pressure_plot.getViewBox().setMouseEnabled(x=True, y=True)
        self.pressure_plot.setAntialiasing(True)
        self.pressure_plot.getViewBox().mouseDoubleClickEvent = lambda ev: self.handle_plot_double_click('pressure', ev)
        title_label = QLabel("Magnet Press. Data")
        title_label.setStyleSheet(f"color: {TEXT_COLOR.name()}; font: 14pt Arial;")
        title_layout = QHBoxLayout()
        title_layout.addWidget(title_label)
        self.pressure_checks = {}
        # Define color mapping for pressure lines
        pressure_colors = {
            'mag_psi': '#FF0000',  # Red
            'avg_mag_psi': '#0000FF',  # Blue
            'wika_psi': '#00FF00',  # Green
            'atm_psi': '#FFFF00'  # Yellow
        }
        for key, name in [('mag_psi', 'Magnet Pressure'), ('avg_mag_psi', 'Avg Magnet Pressure'),
                          ('wika_psi', 'Wika Pressure'), ('atm_psi', 'Atmospheric Pressure')]:
            cb = QCheckBox(name)
            cb.setStyleSheet(f"color: {TEXT_COLOR.name()};")
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plots)
            self.pressure_checks[key] = cb
            # Add line-point icon next to checkbox
            icon = LinePointIcon(pressure_colors[key])
            title_layout.addWidget(icon)
            title_layout.addWidget(cb)
        title_layout.addStretch()
        self.p_notes_label = QLabel("")
        self.p_notes_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")# font: 14pt Arial;")
        title_layout.addWidget(self.p_notes_label)
        pressure_layout.addLayout(title_layout)
        self.pressure_plot.setBackground(FRAME_BG)
        self.pressure_plot.getAxis('bottom').setTextPen(TEXT_COLOR)
        self.pressure_plot.getAxis('left').setTextPen(TEXT_COLOR)
        self.pressure_plot.getAxis('bottom').setTickSpacing(major=86400, minor=3600)
        self.pressure_plot.getAxis('bottom').setTickFont(bold_font)
        pressure_layout.addWidget(self.pressure_plot)
        self.pressure_section.setLayout(pressure_layout)
        main_layout.addWidget(self.pressure_section)

        # Set up WATER PLOT section
        self.water_section = QFrame()
        self.water_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.water_section.setStyleSheet(f"background-color: {FRAME_BG.name()};")
        water_layout = QVBoxLayout()
        self.water_plot = pg.PlotWidget(axisItems={'bottom': DateAxisItem(orientation='bottom')})
        self.water_plot.getViewBox().setMouseEnabled(x=True, y=True)
        self.water_plot.setAntialiasing(True)
        self.water_plot.getViewBox().mouseDoubleClickEvent = lambda ev: self.handle_plot_double_click('water', ev)
        water_title_label = QLabel("Water Temp. Data")
        water_title_label.setStyleSheet(f"color: {TEXT_COLOR.name()}; font: 14pt Arial;")
        water_title_layout = QHBoxLayout()
        water_title_layout.addWidget(water_title_label)
        self.water_checks = {}
        # Define color mapping for water lines
        water_colors = {
            'water_in_f': '#0000FF',  # Blue
            'water_out_f': '#FF0000',  # Red
            'water_diff': '#00FF00'  # Green
        }
        for key, name in [('water_in_f', 'Water In Temp'), ('water_out_f', 'Water Out Temp'),
                          ('water_diff', 'Water Temp Diff')]:
            cb = QCheckBox(name)
            cb.setStyleSheet(f"color: {TEXT_COLOR.name()};")
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plots)
            self.water_checks[key] = cb
            # Add line-point icon next to checkbox
            icon = LinePointIcon(water_colors[key])
            water_title_layout.addWidget(icon)
            water_title_layout.addWidget(cb)
        water_title_layout.addStretch()
        self.w_notes_label = QLabel("")
        self.w_notes_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")# font: 14pt Arial;")
        water_title_layout.addWidget(self.w_notes_label)        
        water_layout.addLayout(water_title_layout)
        self.water_plot.setBackground(FRAME_BG)
        self.water_plot.getAxis('bottom').setTextPen(TEXT_COLOR)
        self.water_plot.getAxis('left').setTextPen(TEXT_COLOR)
        self.water_plot.getAxis('bottom').setTickSpacing(major=86400, minor=3600)
        self.water_plot.getAxis('bottom').setTickFont(bold_font)
        water_layout.addWidget(self.water_plot)
        self.water_section.setLayout(water_layout)
        main_layout.addWidget(self.water_section)


        # CONNECT PLOTS TO UPDATE_x_PIXEL_CACHE
        self.pressure_plot.getViewBox().sigRangeChanged.connect(self.update_pressure_pixel_cache)
        self.water_plot.getViewBox().sigRangeChanged.connect(self.update_water_pixel_cache)

        # Set up control bar
        controls_outer_layout = QHBoxLayout()
        controls_outer_layout.addStretch(1)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.range_combo = QComboBox()
        self.range_combo.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.range_combo.addItems(["1 Day", "3 Days", "1 Week", "1 Month", "Custom"])
        self.range_combo.setCurrentText("1 Day")
        self.range_combo.currentTextChanged.connect(self.update_date_range)
        controls_layout.addWidget(self.range_combo)
        self.left_arrow = QPushButton("<")
        self.left_arrow.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.left_arrow.clicked.connect(self.shift_range_left)
        controls_layout.addWidget(self.left_arrow)
        self.right_arrow = QPushButton(">")
        self.right_arrow.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.right_arrow.clicked.connect(self.shift_range_right)
        controls_layout.addWidget(self.right_arrow)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.start_date_edit.dateChanged.connect(self.on_date_changed)
        controls_layout.addWidget(self.start_date_edit)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.end_date_edit.dateChanged.connect(self.on_date_changed)
        controls_layout.addWidget(self.end_date_edit)
        self.today_btn = QPushButton("Set End to Today")
        self.today_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        self.today_btn.clicked.connect(self.set_end_to_today)
        controls_layout.addWidget(self.today_btn)
        reset_btn = QPushButton("Reset Zoom")
        reset_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        reset_btn.clicked.connect(self.reset_zoom)
        controls_layout.addWidget(reset_btn)
        controls_outer_layout.addLayout(controls_layout)
        controls_outer_layout.addStretch(1)
        main_layout.addLayout(controls_outer_layout)

        # Initialize plot lines
        self.pressure_lines = {
            'mag_psi': self.pressure_plot.plot(pen='r', name='Magnet Pressure', symbol='o', symbolSize=2.5, symbolPen='r', symbolBrush='r'),
            'avg_mag_psi': self.pressure_plot.plot(pen='b', name='Avg Magnet Pressure', symbol='o', symbolSize=2.5, symbolPen='b', symbolBrush='b'),
            'wika_psi': self.pressure_plot.plot(pen='g', name='Wika Pressure', symbol='o', symbolSize=2.5, symbolPen='g', symbolBrush='g'),
            'atm_psi': self.pressure_plot.plot(pen='y', name='Atmospheric Pressure', symbol='o', symbolSize=2.5, symbolPen='y', symbolBrush='y')
        }
        self.water_lines = {
            'water_in_f': self.water_plot.plot(pen='b', name='Water In Temp', symbol='o', symbolSize=2.5, symbolPen='b', symbolBrush='b'),
            'water_out_f': self.water_plot.plot(pen='r', name='Water Out Temp', symbol='o', symbolSize=2.5, symbolPen='r', symbolBrush='r'),
            'water_diff': self.water_plot.plot(pen='g', name='Water Temp Diff', symbol='o', symbolSize=2.5, symbolPen='g', symbolBrush='g')
        }

        # Add legends to plots
        self.pressure_plot.addLegend()
        self.water_plot.addLegend()

        # Enable mouse interaction for plots
        self.pressure_plot.setMouseEnabled(x=True, y=True)
        self.water_plot.setMouseEnabled(x=True, y=True)

        # Connect mouse movement events
        self.pressure_plot.scene().sigMouseMoved.connect(self.mouse_moved_pressure)
        self.water_plot.scene().sigMouseMoved.connect(self.mouse_moved_water)
        self.pressure_plot.leaveEvent = self.pressure_leave_event
        self.water_plot.leaveEvent = self.water_leave_event


        if len(sys.argv) > 1:
            for i in range(1, len(sys.argv)):
                arg = sys.argv[i]
                if arg.startswith("path="):
                    path_value = arg[5:].strip('"').strip("'").lower()
                    if os.path.isdir(path_value):
                        self.search_folder.setText(path_value)
                    else:
                        print(f"Warning: Provided path not found or invalid: {path_value}")
                elif arg.startswith("recursive="):
                    rec_value = arg[10:].strip().lower()
                    if rec_value in ("true", "1", "yes", "on"):
                        self.subfolder_search_cb.setChecked(True)
                    elif rec_value in ("false", "0", "no", "off"):
                        self.subfolder_search_cb.setChecked(False)
                   


        # Load initial methods  
# <==== LOADING NEW SIDS CALLS ON_SID_CHANGED WHICH CALLS UPDATE_DATE_RANGE WHICH THEN CALLS UPDATE_DATA
#        print("STARTING: load_sids in init which will eventually call update_data.")
        self.load_sids()

        # Set up timer for periodic updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5000)  # 5-second interval
        
        # Check and clear log file if older than today
        self.clear_log_if_needed()  
        self.set_end_to_today()
        QTimer.singleShot(200, self.reset_zoom) # <=== Needed to delay it a little to allow for graph to render

        if len(sys.argv) > 1:
            for i in range(1, len(sys.argv)):
                arg = sys.argv[i]
                if arg == "use_current_dat":
                    sid = self.get_current_dat_sid()
                    index = self.sid_combo.findText(sid)
                    if index != -1:
                        self.sid_combo.setCurrentIndex(index)
                    else:
                        # Optional: Handle if SID not in list (e.g., add it or log a warning)
                        print(f"Current_dat SID {sid} not found in combo box options.")
                elif arg.startswith("SID="):
                    sid = arg[4:].strip('"').strip("'")
                    index = self.sid_combo.findText(sid)
                    if index != -1:
                        self.sid_combo.setCurrentIndex(index)
                    else:
                        print(f"arg SID=,  SID {sid} not found in combo box options.")
      
        """
        if len(sys.argv) > 1 and sys.argv[1] == "use_current_dat":
            sid = self.get_current_dat_sid()
            index = self.sid_combo.findText(sid)
            if index != -1:
                self.sid_combo.setCurrentIndex(index)
            else:
                # Optional: Handle if SID not in list (e.g., add it or log a warning)
                print(f"SID {sid} not found in combo box options.")
        """


####  ================ INITIAL LOAD HELPERS ==================================================


    def _update_caches(self):
        self.update_pressure_pixel_cache()
        self.update_water_pixel_cache()


    def get_current_dat_sid(self):
        """Get the sid from current.dat."""
        try:
            with open(DEFAULT_CURRENTDB_PATH, 'r') as f:
                for line in f:
                    if line.startswith("SID="):
                        return line.strip().split('=', 1)[1]
            return "000"
        except Exception as e:
            self.log_error(f"Error reading sid from current.dat: {str(e)}")
            return "000"


    def show_popup(self, message):
        # Display a temporary popup message without sound
        popup = QLabel(message, self)
        popup.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()}; border: 1px solid {TEXT_COLOR.name()}; padding: 5px;")
        popup.setFont(QFont("Arial", 10))
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.adjustSize()
        popup.move(self.rect().center() - popup.rect().center())
        popup.show()
        QTimer.singleShot(2000, popup.hide) # Set time message will be displayed. 

    def log_error(self, message):
        print(f"LOG_ERROR: {message}")
        self.show_popup(f"{message}")
        return
        try:
            with open(os.path.join(get_base_path(), "hpm2_monitor_error.log"), 'a') as f:
                timestamp = datetime.now().strftime('%Y%m%d %H:%M:%S')
                f.write(f"{timestamp} - {message}\n")
                print(f"Log_Error = {message}")
        except Exception as e:
            pass


    def clear_log_if_needed(self):
        # Clear log file if it was last modified before today
        error_log_file = os.path.join(get_base_path(), "hpm2_monitor_error.log")
        try:
            if os.path.exists(error_log_file):
                last_modified = datetime.fromtimestamp(os.path.getmtime(error_log_file))
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if last_modified.date() < today.date():
                    with open(error_log_file, 'w') as f:
                        f.write("")  # Clear the file
        except Exception as e:
            self.log_error(f"Error clearing log file: {e}")


    def load_sids(self):
    # LOAD_SIDS ENDS UP CALLING UPDATE_DATE_RANGE WHEN THE SID CHANGES. THIS HAPPENS ON EVERY BOOT. 
        start_time = time.time()
        self.compile_log_folders()
        log_files = []
        pattern_new = "*_*_HPM2_Test_data.log"          # existing
        pattern_old = "*_*_HPM2_BTrdr2_test_data.txt"   # new
        for entry in self.all_log_folders:
            folder = entry["path"]
            recursive = entry.get("recursive", False)
            if not os.path.exists(folder):
                continue
            matches_new = glob.glob(os.path.join(folder, "**", pattern_new), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_new))
            matches_old = glob.glob(os.path.join(folder, "**", pattern_old), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_old))
            log_files.extend(matches_new + matches_old)

        sids = set()
        for log_file in log_files:
            match = re.match(r"^(\d+)_\d{8}", os.path.basename(log_file))
            if match:
                sids.add(match.group(1))
        self.sid_list = sorted(sids, key=int)
        self.sid_combo.clear()
        self.sid_combo.addItems(self.sid_list)
        if self.sid_list:
            self.selected_sid = self.sid_list[0]
            self.sid_combo.setCurrentText(self.selected_sid)

        end_time = time.time()
#        print(f"FINISHED: load_sids - took {end_time - start_time:.2f} seconds")


    def on_sid_changed(self, sid):
#        print("STARTING: on_sid_changed")
        # Handle SID selection change called from sid_combo.connect, reset cache and update data
        if sid:
            self.selected_sid = sid
            local_tz = get_localzone()  # Get local timezone
            self.end_date = datetime.now(local_tz).replace(tzinfo=local_tz)
#            print("    on_sid_changed - DON'T forget to uncomment self.end_date = datetime.now(local_tz).replace(tzinfo=local_tz) <=========================================")
            self.update_date_range()
#            print("FINISHED: on_sid_changed - CALLING: set_end_to_today")   


    def compile_log_folders(self):
        log_folders = LOG_FOLDERS.copy()   # preserve original list/format

        current_path = self.search_folder.text().strip()
        if current_path and os.path.isdir(current_path):
            recursive = self.subfolder_search_cb.isChecked()
            new_entry = {"path": current_path, "recursive": recursive}
            log_folders.append(new_entry)

        self.all_log_folders = log_folders
#        print(f"log_folders {self.all_log_folders}")
        return self.all_log_folders


    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()



    def open_log_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Log Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.search_folder.setText(folder)




#### ======== APP LAYOUT HELPER FUNCTIONS ========================================================
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_fullscreen:
            window_size = self.centralWidget().size()
            gauge_width = max(400, min(int(window_size.width() * 0.95), window_size.width() - 40))
            gauge_height = max(200, min(int((window_size.height() - 240) * 0.8), window_size.height() - 240))
            self.fullscreen_gauge.setMinimumSize(gauge_width, gauge_height)
        
        # Debounce cache update - safe version
        if hasattr(self, '_resize_timer') and self._resize_timer is not None:
            self._resize_timer.stop()

        # Schedule cache update shortly after user stops resizing
        self._resize_timer = QTimer.singleShot(80, self._update_caches)           
        

    def handle_plot_double_click(self, section, event):
        if event.button() == Qt.LeftButton:
            if self.is_fullscreen:
                self.toggle_gauge_section()
            else:
                self.toggle_sections(section)
            event.accept()


    def toggle_sections(self, section):
        self.gauge_check.blockSignals(True)
        self.pressure_check.blockSignals(True)
        self.water_check.blockSignals(True)
        
        if self.active_graph == section:
            self.active_graph = None
            self.gauge_check.setChecked(self.section_states['gauge'])
            self.pressure_check.setChecked(self.section_states['pressure'])
            self.water_check.setChecked(self.section_states['water'])
        else:
            self.section_states = {
                'gauge': self.gauge_section.isVisible(),
                'pressure': self.pressure_section.isVisible(),
                'water': self.water_section.isVisible()
            }
            self.active_graph = section
            if section == 'pressure':
                self.gauge_check.setChecked(False)
                self.pressure_check.setChecked(True)
                self.water_check.setChecked(False)
            elif section == 'water':
                self.gauge_check.setChecked(False)
                self.pressure_check.setChecked(False)
                self.water_check.setChecked(True)
        
        self.gauge_check.blockSignals(False)
        self.pressure_check.blockSignals(False)
        self.water_check.blockSignals(False)
        self.update_sections()


    def toggle_gauge_section(self):
        self.gauge_check.blockSignals(True)
        self.pressure_check.blockSignals(True)
        self.water_check.blockSignals(True)
        
        if not self.is_fullscreen:
            self.section_states = {
                'gauge': self.gauge_section.isVisible(),
                'pressure': self.pressure_section.isVisible(),
                'water': self.water_section.isVisible()
            }
        
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.active_graph = None
            self.gauge_check.setChecked(True)
            self.pressure_check.setChecked(False)
            self.water_check.setChecked(False)
        else:
            self.active_graph = None
            self.gauge_check.setChecked(self.section_states['gauge'])
            self.pressure_check.setChecked(self.section_states['pressure'])
            self.water_check.setChecked(self.section_states['water'])
        
        self.gauge_check.blockSignals(False)
        self.pressure_check.blockSignals(False)
        self.water_check.blockSignals(False)
        self.update_sections()


    def update_sections(self):
        if self.is_updating:
            return
        self.is_updating = True
        
        if self.is_fullscreen and (self.pressure_check.isChecked() or self.water_check.isChecked()):
            self.is_fullscreen = False
            self.section_states = {
                'gauge': self.gauge_check.isChecked(),
                'pressure': self.pressure_check.isChecked(),
                'water': self.water_check.isChecked()
            }
        
        elif self.gauge_check.isChecked() and not (self.pressure_check.isChecked() or self.water_check.isChecked()) and not self.is_fullscreen:
            self.section_states = {
                'gauge': self.gauge_section.isVisible(),
                'pressure': self.pressure_section.isVisible(),
                'water': self.water_section.isVisible()
            }
            self.is_fullscreen = True
            self.active_graph = None
            self.gauge_check.setChecked(True)
            self.pressure_check.setChecked(False)
            self.water_check.setChecked(False)
        
        if not self.is_fullscreen:
            self.active_graph = None
            graph_count = sum([self.pressure_check.isChecked(), self.water_check.isChecked()])
            if graph_count == 1 and not self.gauge_check.isChecked():
                if self.pressure_check.isChecked():
                    self.active_graph = 'pressure'
                elif self.water_check.isChecked():
                    self.active_graph = 'water'
        
        if not (self.gauge_check.isChecked() or self.pressure_check.isChecked() or self.water_check.isChecked()) and not self.is_fullscreen:
            self.active_graph = None
            self.gauge_check.setChecked(self.section_states.get('gauge', True))
            self.pressure_check.setChecked(self.section_states.get('pressure', True))
            self.water_check.setChecked(self.section_states.get('water', True))
        
        self.fullscreen_frame.setVisible(self.is_fullscreen)
        self.gauge_section.setVisible(self.gauge_check.isChecked() and not self.is_fullscreen)
        self.pressure_section.setVisible(self.pressure_check.isChecked() and not self.is_fullscreen)
        self.water_section.setVisible(self.water_check.isChecked() and not self.is_fullscreen)
        
        if self.is_fullscreen:
            self.move_displays_to_fullscreen()
        else:
            self.move_displays_to_gauge()
        
        self.update_checkboxes()
        self.adjust_layout()
        self.is_updating = False
        self.update_plots()


    def show_all_sections(self):
        self.gauge_check.blockSignals(True)
        self.pressure_check.blockSignals(True)
        self.water_check.blockSignals(True)
        
        self.is_fullscreen = False
        self.active_graph = None
        self.section_states = {'gauge': True, 'pressure': True, 'water': True}
        self.gauge_check.setChecked(True)
        self.pressure_check.setChecked(True)
        self.water_check.setChecked(True)
        
        self.gauge_check.blockSignals(False)
        self.pressure_check.blockSignals(False)
        self.water_check.blockSignals(False)
        self.update_sections()


    def move_displays_to_fullscreen(self):
        self.gauge_layout.removeWidget(self.left_display)
        self.gauge_layout.removeWidget(self.right_display)
        self.columns_layout.insertWidget(1, self.left_display)
        self.columns_layout.insertWidget(2, self.right_display)


    def move_displays_to_gauge(self):
        self.columns_layout.removeWidget(self.left_display)
        self.columns_layout.removeWidget(self.right_display)
        self.gauge_layout.insertWidget(2, self.left_display)
        self.gauge_layout.insertWidget(3, self.right_display)


    def update_checkboxes(self):
        self.gauge_check.blockSignals(True)
        self.pressure_check.blockSignals(True)
        self.water_check.blockSignals(True)
        
        self.gauge_check.setChecked(self.is_fullscreen or self.gauge_section.isVisible())
        self.pressure_check.setChecked(self.pressure_section.isVisible())
        self.water_check.setChecked(self.water_section.isVisible())
        
        self.gauge_check.blockSignals(False)
        self.pressure_check.blockSignals(False)
        self.water_check.blockSignals(False)


    def adjust_layout(self):
        visible_sections = sum([self.gauge_section.isVisible(), self.pressure_section.isVisible(), self.water_section.isVisible()])
        stretch = 1 if visible_sections > 0 or self.is_fullscreen else 0
        self.centralWidget().layout().setStretch(1, 1 if self.is_fullscreen else 0)
        self.centralWidget().layout().setStretch(2, 1 if self.gauge_section.isVisible() else 0)
        self.centralWidget().layout().setStretch(3, 10 if self.active_graph == 'pressure' else 1 if self.pressure_section.isVisible() else 0)
        self.centralWidget().layout().setStretch(4, 10 if self.active_graph == 'water' else 1 if self.water_section.isVisible() else 0)
        self.centralWidget().layout().setStretch(5, 0)




#### ================= GRAPH DATA SECTION ====================================================

## Mouse Moved section ---------------------------------------------------
    def mouse_moved_pressure(self, pos):
        QApplication.restoreOverrideCursor()  # Restore cursor
        self.active_plot = 'pressure'
        self.pressure_plot.setFocus()  # Set focus on hover
        self.is_keyboard_nav = False
        self.selected_series = None
        if not self.pressure_plot.sceneBoundingRect().contains(pos):
            self.pressure_tooltip.hide()
            for key, line in self.pressure_lines.items():
                x_data, y_data = line.getData()
                if x_data is not None:
                    line.setData(x=x_data, y=y_data, symbolSize=2.5)
            self.current_point_idx = None
            return
        
        try:
            vb = self.pressure_plot.getViewBox()
            mouse_point = vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            
            any_valid_series = False
            for key, line in self.pressure_lines.items():
                if line.isVisible() and self.pressure_checks[key].isChecked() and line.getData()[0] is not None:
                    any_valid_series = True
                    break
            if not any_valid_series:
                self.pressure_tooltip.hide()
                return
            
            global_pos = self.pressure_plot.mapToGlobal(QPoint(int(pos.x()), int(pos.y())))
            offset_x = 200 if global_pos.x() <= self.geometry().center().x() else -400
            tooltip_pos = QPoint(int(global_pos.x() + offset_x), int(global_pos.y() - 30))
            
            if self.cached_df is not None and not self.cached_df.empty:
                df = self.cached_df[(self.cached_df['DATE TIME'] >= self.start_date) & (self.cached_df['DATE TIME'] <= self.end_date)]
                if df.empty:
                    self.pressure_tooltip.hide()
                    return
                
                # ── Use precomputed pixel cache for fast distance search ───────
                min_distance = float('inf')
                new_idx = None
                closest_series = None
                mouse_pixel = pos
                
                for px_x, px_y, df_idx, key in self.pressure_pixel_cache:
                    distance = np.sqrt((px_x - mouse_pixel.x())**2 + (px_y - mouse_pixel.y())**2)
                    if distance < min_distance:
                        min_distance = distance
                        new_idx = df_idx
                        closest_series = key
                # ───────────────────────────────────────────────────────────────
                
                # Only update symbols and tooltip if the closest point changed
                if new_idx == self.current_point_idx and closest_series == self.selected_series:
                    return  # No change → skip redraw and tooltip update
                
                self.current_point_idx = new_idx
                self.selected_series = closest_series
                
                if new_idx is not None and new_idx < len(df):
                    for key, line in self.pressure_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)
                    tooltip = [f"<span style='color:{SOFT_GRAY.name()};'>Time: {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}</span>"]

                    
                #    tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}"]
                    row = df.iloc[new_idx].to_dict()
                    colors = self.get_alert_colors_for_row(row)

                    for key, line in self.pressure_lines.items():
                        if line.isVisible() and self.pressure_checks[key].isChecked():
                            value = df[key].iloc[new_idx]
                            if pd.isna(value):
                                continue
                            unit = 'psi'
                            color = colors.get(key, TEXT_COLOR.name())
                            tooltip.append(
                                f"<br><span style='color:{color};'>{line.name()+':':<21} {value:>6.2f} {unit}</span>"
                            )
                            x_data, y_data = line.getData()
                            if x_data is not None and new_idx < len(df):
                                sizes = [2.5] * len(x_data)
                                local_idx = np.where((df[key].notna()) & (df.index <= new_idx))[0][-1]
                                if local_idx < len(x_data):
                                    sizes[local_idx] = 10 # Size of highlighted mouse move point.
                                    line.setData(x=x_data, y=y_data, symbolSize=sizes)
                    
#                    # This displays one error or the total number of errors.  
#                    if colors['pressure_error_text'] != 'No pressure errors':
#                        tooltip.append(
#                            f"<br><span style='color:{colors['pressure_errors']};'>Errors: {colors['pressure_error_text']}</span>"
#                        )
                    # DISPLAYS FULL LIST OF ERRORS
                    # Pressure warnings (yellow)
                    for msg in colors.get('pressure_warning_list', []):
                        tooltip.append(f"<br><span style='color:yellow;'>• {msg}</span>")

                    # Pressure errors/critical (red)
                    for msg in colors.get('pressure_error_list', []):
                        tooltip.append(f"<br><span style='color:red;'>• {msg}</span>")

                    tooltip_text = "".join(tooltip)

                    self.pressure_tooltip.show_at(tooltip_pos, tooltip_text)
                else:
                    self.pressure_tooltip.hide()
            else:
                self.pressure_tooltip.hide()
        except Exception as e:
            self.log_error(f"Error in pressure tooltip: {e}")
            self.pressure_tooltip.hide()


    def mouse_moved_water(self, pos):
        QApplication.restoreOverrideCursor()  # Restore cursor
        self.active_plot = 'water'
        self.water_plot.setFocus()  # Set focus on hover
        self.is_keyboard_nav = False
        self.selected_series = None
        if not self.water_plot.sceneBoundingRect().contains(pos):
            self.water_tooltip.hide()
            for key, line in self.water_lines.items():
                x_data, y_data = line.getData()
                if x_data is not None:
                    line.setData(x=x_data, y=y_data, symbolSize=2.5)
            self.current_point_idx = None
            return
        
        try:
            vb = self.water_plot.getViewBox()
            mouse_point = vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            
            any_valid_series = False
            for key, line in self.water_lines.items():
                if line.isVisible() and self.water_checks[key].isChecked() and line.getData()[0] is not None:
                    any_valid_series = True
                    break
            if not any_valid_series:
                self.water_tooltip.hide()
                return
            
            global_pos = self.water_plot.mapToGlobal(QPoint(int(pos.x()), int(pos.y())))
            offset_x = 200 if global_pos.x() <= self.geometry().center().x() else -400
            tooltip_pos = QPoint(int(global_pos.x() + offset_x), int(global_pos.y() - 30))

    ### TESTING TOOLTIP POSITION BELOW. 
#            tooltip_pos = QPoint(int(self.geometry().center().x() -400), int(self.geometry().center().y()))

            if self.cached_df is not None and not self.cached_df.empty:
                df = self.cached_df[(self.cached_df['DATE TIME'] >= self.start_date) & (self.cached_df['DATE TIME'] <= self.end_date)]
                if df.empty:
                    self.water_tooltip.hide()
                    return
                
                # ── Use precomputed pixel cache for fast distance search ───────
                min_distance = float('inf')
                new_idx = None
                closest_series = None
                mouse_pixel = pos
                
                for px_x, px_y, df_idx, key in self.water_pixel_cache:
                    distance = np.sqrt((px_x - mouse_pixel.x())**2 + (px_y - mouse_pixel.y())**2)
                    if distance < min_distance:
                        min_distance = distance
                        new_idx = df_idx
                        closest_series = key
                # ───────────────────────────────────────────────────────────────
                
                # Only update symbols and tooltip if the closest point changed
                if new_idx == self.current_point_idx and closest_series == self.selected_series:
                    return  # No change → skip redraw and tooltip update
                
                self.current_point_idx = new_idx
                self.selected_series = closest_series
                
                if new_idx is not None and new_idx < len(df):
                    for key, line in self.water_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)

                    tooltip = [f"<span style='color:{SOFT_GRAY.name()};'>Time: {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}</span>"]

                    
                #    tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}"]
                    row = df.iloc[new_idx].to_dict()
                    colors = self.get_alert_colors_for_row(row)

                    for key, line in self.water_lines.items():
                        if line.isVisible() and self.water_checks[key].isChecked():
                            value = df[key].iloc[new_idx]
                            if pd.isna(value):
                                continue
                            unit = '°F'
                            color = colors.get(key, TEXT_COLOR.name())
                            tooltip.append(
                                f"<br><span style='color:{color};'>{line.name()+':':<21} {value:>6.2f} {unit}</span>"
                            )
                            x_data, y_data = line.getData()
                            if x_data is not None and new_idx < len(df):
                                sizes = [2.5] * len(x_data)
                                local_idx = np.where((df[key].notna()) & (df.index <= new_idx))[0][-1]
                                if local_idx < len(x_data):
                                    sizes[local_idx] = 10  # Size of highlighted mouse move point.
                                    line.setData(x=x_data, y=y_data, symbolSize=sizes)

#                    # This displays one error or the total number of errors.    
#                    if colors['water_error_text'] != 'No water errors':
#                        tooltip.append(
#                            f"<br><span style='color:{colors['water_errors']};'>Errors: {colors['water_error_text']}</span>"
#                        )
                    # DISPLAYS FULL LIST OF ERRORS
                    # Water warnings (yellow)
                    for msg in colors.get('water_warning_list', []):
                        tooltip.append(f"<br><span style='color:yellow;'>• {msg}</span>")

                    # Water errors/critical (red)
                    for msg in colors.get('water_error_list', []):
                        tooltip.append(f"<br><span style='color:red;'>• {msg}</span>")

                    tooltip_text = "".join(tooltip)

                    self.water_tooltip.show_at(tooltip_pos, tooltip_text)
                else:
                    self.water_tooltip.hide()
            else:
                self.water_tooltip.hide()
        except Exception as e:
            self.log_error(f"Error in water tooltip: {e}")
            self.water_tooltip.hide()


## PIXEL CACHE SECTION ----------------------------------------------------------
# Using precomputed pixel cache for hover - should be very fast even with months of data
    def update_pressure_pixel_cache(self, vb=None, range=None):

        if self.cached_df is None or self.cached_df.empty:
            self.pressure_pixel_cache = []
            return
        start_time = time.time()
        vb = self.pressure_plot.getViewBox()
        view_range = vb.viewRange()
        x_min, x_max = view_range[0]

        # Get currently visible df slice
        visible_df = self.cached_df[
            (self.cached_df['DATE TIME'] >= self.start_date) &
            (self.cached_df['DATE TIME'] <= self.end_date) &
            (self.cached_df['DATE TIME'].apply(lambda t: t.timestamp()) >= x_min) &
            (self.cached_df['DATE TIME'].apply(lambda t: t.timestamp()) <= x_max)
        ]

        if visible_df.empty:
            self.pressure_pixel_cache = []
            return

        cache = []
        for key, line in self.pressure_lines.items():
            if not (line.isVisible() and self.pressure_checks[key].isChecked()):
                continue

            y_data = visible_df[key].values
            valid_mask = ~np.isnan(y_data)
            valid_df = visible_df[valid_mask]
            if valid_df.empty:
                continue

            timestamps = valid_df['DATE TIME'].apply(lambda t: t.timestamp()).values
            ys = y_data[valid_mask]

            for i, (t, y_val) in enumerate(zip(timestamps, ys)):
                point_scene = vb.mapViewToScene(QPointF(t, y_val))
                px_x = point_scene.x()
                px_y = point_scene.y()
                df_idx = valid_df.index[i]
                cache.append((px_x, px_y, df_idx, key))

        self.pressure_pixel_cache = cache
        end_time = time.time()
#        print(len(cache), "points cached for pressure.", f"it took {end_time - start_time} seconds")


    def update_water_pixel_cache(self, vb=None, range=None):
        if self.cached_df is None or self.cached_df.empty:
            self.water_pixel_cache = []
            return
        start_time = time.time()
        vb = self.water_plot.getViewBox()
        view_range = vb.viewRange()
        x_min, x_max = view_range[0]

        visible_df = self.cached_df[
            (self.cached_df['DATE TIME'] >= self.start_date) &
            (self.cached_df['DATE TIME'] <= self.end_date) &
            (self.cached_df['DATE TIME'].apply(lambda t: t.timestamp()) >= x_min) &
            (self.cached_df['DATE TIME'].apply(lambda t: t.timestamp()) <= x_max)
        ]

        if visible_df.empty:
            self.water_pixel_cache = []
            return

        cache = []
        for key, line in self.water_lines.items():
            if not (line.isVisible() and self.water_checks[key].isChecked()):
                continue

            y_data = visible_df[key].values
            valid_mask = ~np.isnan(y_data)
            valid_df = visible_df[valid_mask]
            if valid_df.empty:
                continue

            timestamps = valid_df['DATE TIME'].apply(lambda t: t.timestamp()).values
            ys = y_data[valid_mask]

            for i, (t, y_val) in enumerate(zip(timestamps, ys)):
                point_scene = vb.mapViewToScene(QPointF(t, y_val))
                px_x = point_scene.x()
                px_y = point_scene.y()
                df_idx = valid_df.index[i]
                cache.append((px_x, px_y, df_idx, key))

        self.water_pixel_cache = cache
        end_time = time.time()
#        print(len(cache), "points cached for water.", f"it took {end_time - start_time} seconds") 
# Cache update methods - call these after data load or manually trigger if needed        #   


## PRESSURE LEAVE EVENTS SECTIONS--------------------------------------
    def pressure_leave_event(self, event):
#        print("STARTING: pressure_leave_event")
        if self.is_keyboard_nav:
            return
        QApplication.restoreOverrideCursor()  # Restore cursor
        self.pressure_tooltip.hide()
        for key, line in self.pressure_lines.items():
            x_data, y_data = line.getData()
            if x_data is not None:
                line.setData(x=x_data, y=y_data, symbolSize=2.5)
        self.active_plot = None
        self.current_point_idx = None
        self.selected_series = None

    def water_leave_event(self, event):
#        print("STARTING: water_leave_event")
        if self.is_keyboard_nav:
            return
        QApplication.restoreOverrideCursor()  # Restore cursor        
        self.water_tooltip.hide()
        for key, line in self.water_lines.items():
            x_data, y_data = line.getData()
            if x_data is not None:
                line.setData(x=x_data, y=y_data, symbolSize=2.5)
        self.active_plot = None
        self.current_point_idx = None
        self.selected_series = None


## KEYPRESS EVENT SECTION  -----------------------------------------------------
    def keyPressEvent(self, event):
    #        print("STARTING: keyPressEvent")
        if not self.active_plot or self.cached_df is None or self.cached_df.empty:
            self.current_point_idx = None
            self.selected_series = None
            self.is_keyboard_nav = False
            self.pressure_tooltip.hide()
            self.water_tooltip.hide()
            QApplication.restoreOverrideCursor()
            return

        df = self.cached_df[(self.cached_df['DATE TIME'] >= self.start_date) & (self.cached_df['DATE TIME'] <= self.end_date)]
        if df.empty:
            self.current_point_idx = None
            self.selected_series = None
            self.is_keyboard_nav = False
            self.pressure_tooltip.hide()
            self.water_tooltip.hide()
            QApplication.restoreOverrideCursor()
            return

        timestamps = df['DATE TIME'].apply(lambda x: x.timestamp()).values
        if len(timestamps) == 0:
            self.current_point_idx = None
            self.selected_series = None
            self.is_keyboard_nav = False
            self.pressure_tooltip.hide()
            self.water_tooltip.hide()
            QApplication.restoreOverrideCursor()
            return

        # Cache data ranges for efficiency
        data_x_range = [self.start_date.timestamp(), self.end_date.timestamp()]
        is_pressure = self.active_plot == 'pressure'
        lines = self.pressure_lines if is_pressure else self.water_lines
        checks = self.pressure_checks if is_pressure else self.water_checks
        tooltip_hide_other = self.water_tooltip.hide if is_pressure else self.pressure_tooltip.hide
        reset_lines_other = self.water_lines if is_pressure else self.pressure_lines
        reset_lines_this = self.pressure_lines if is_pressure else self.water_lines
        update_tooltip = self.update_pressure_tooltip if is_pressure else self.update_water_tooltip
        plot = self.pressure_plot if is_pressure else self.water_plot
        data_y_range = [min(df[key].min() for key in lines if checks[key].isChecked() and not df[key].isna().all()),
                        max(df[key].max() for key in lines if checks[key].isChecked() and not df[key].isna().all())]

        # Only handle Left/Right arrow keys for navigation
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            self.is_keyboard_nav = True

            # Initialize index based on mouse position if None
            if self.current_point_idx is None or self.current_point_idx >= len(timestamps):
                vb = plot.getViewBox()
                cursor_pos = QCursor.pos()
                cursor_widget = plot.mapFromGlobal(cursor_pos)
                cursor_scene = vb.mapToScene(cursor_widget)
                cursor_view = vb.mapSceneToView(cursor_scene)
                cursor_x = cursor_view.x()
                self.current_point_idx = np.argmin(np.abs(timestamps - cursor_x)) if len(timestamps) > 0 else 0
            else:
                if event.key() == Qt.Key_Left and self.current_point_idx > 0:
                    self.current_point_idx -= 1
                elif event.key() == Qt.Key_Right and self.current_point_idx < len(timestamps) - 1:
                    self.current_point_idx += 1
                else:
                    return

            # Select closest series based on y-position on first key press
            if self.selected_series is None:
                vb = plot.getViewBox()
                cursor_pos = QCursor.pos()
                cursor_widget = plot.mapFromGlobal(cursor_pos)
                cursor_scene = vb.mapToScene(cursor_widget)
                cursor_view = vb.mapSceneToView(cursor_scene)
                cursor_y = cursor_view.y()
                min_distance = float('inf')
                selected_key = None
                for key, line in lines.items():
                    if key in checks and key in df.columns and line.isVisible() and checks[key].isChecked():
                        value = df[key].iloc[self.current_point_idx]
                        if not pd.isna(value):
                            distance = abs(value - cursor_y)
                            if distance < min_distance:
                                min_distance = distance
                                selected_key = key
                self.selected_series = selected_key

            if self.selected_series is None:
                self.current_point_idx = None
                self.is_keyboard_nav = False
                self.pressure_tooltip.hide()
                self.water_tooltip.hide()
                return

            # Update tooltip and highlights
            tooltip_hide_other()
            for key, line in reset_lines_other.items():
                x_data, y_data = line.getData()
                if x_data is not None:
                    line.setData(x=x_data, y=y_data, symbolSize=2.5)

            for key, line in reset_lines_this.items():
                x_data, y_data = line.getData()
                if x_data is not None:
                    line.setData(x=x_data, y=y_data, symbolSize=2.5)

            update_tooltip(self.current_point_idx, df, self.selected_series)

            # Track point in x and y directions if zoomed
            vb = plot.getViewBox()
            current_x_range = vb.viewRange()[0]
            current_y_range = vb.viewRange()[1]
            current_point_x = timestamps[self.current_point_idx]

            point_y = None
            if self.selected_series and self.selected_series in df.columns:
                value = df[self.selected_series].iloc[self.current_point_idx]
                if not pd.isna(value):
                    point_y = value

            # X-direction tracking
            if current_x_range[1] - current_x_range[0] < data_x_range[1] - data_x_range[0]:
                point_scene = vb.mapViewToScene(QPointF(current_point_x, 0))
                point_view_x = vb.mapSceneToView(point_scene).x()
                view_width = current_x_range[1] - current_x_range[0]
                margin = view_width * 0.1
                relative_pos = (point_view_x - current_x_range[0]) / view_width

                if relative_pos < 0.1:
                    shift = (0.1 - relative_pos) * view_width
                    new_x_min = max(data_x_range[0], current_x_range[0] - shift)
                    new_x_max = new_x_min + view_width
                    vb.setXRange(new_x_min, new_x_max, padding=0)
                elif relative_pos > 0.9:
                    shift = (relative_pos - 0.9) * view_width
                    new_x_max = min(data_x_range[1], current_x_range[1] + shift)
                    new_x_min = new_x_max - view_width
                    vb.setXRange(new_x_min, new_x_max, padding=0)

            # Y-direction tracking
            if point_y is not None and data_y_range[1] > data_y_range[0]:
                view_height = current_y_range[1] - current_y_range[0]
                margin = view_height * 0.1
                relative_pos_y = (point_y - current_y_range[0]) / view_height
#                print(f"relative_pos_y = {relative_pos_y}, view_height = {view_height} \n current_y_range = {current_y_range}")

                if relative_pos_y < 0.1:
                    shift = (0.1 - relative_pos_y) * view_height
                    new_y_min = min(data_y_range[0], current_y_range[0] - shift)
                    new_y_max = new_y_min + view_height
                    vb.setYRange(new_y_min, new_y_max, padding=0)
#                    print(f"if relative <.01 new_y_min = {new_y_min}, new_y_max = {new_y_max}")
                elif relative_pos_y > 0.9:
                    shift = (relative_pos_y - 0.9) * view_height
                    new_y_max = max(data_y_range[1], current_y_range[1] + shift)
                    new_y_min = new_y_max - view_height
#                    print(f"if relative >0.9 new_y_min = {new_y_min}, new_y_max = {new_y_max}")
                    vb.setYRange(new_y_min, new_y_max, padding=0)

            # Force plot refresh
            plot.repaint()

            event.accept()
        else:
            self.current_point_idx = None
            self.selected_series = None
            self.is_keyboard_nav = False
            self.pressure_tooltip.hide()
            self.water_tooltip.hide()
            QApplication.restoreOverrideCursor()
            super().keyPressEvent(event)


## Update tooltip section --------------------------------------------------------------
# These are only used with KeyPressEvent. 

    def update_pressure_tooltip(self, idx, df, selected_series=None):
        # THIS IS USED IN KEYPRESSEVENT. 
        if idx is None or idx >= len(df):
            self.pressure_tooltip.hide()
            return
        
        # Build tooltip text for all checked series, highlight selected series if keyboard nav
        tooltip = [f"<span style=''color:{SOFT_GRAY.name()};'>Time: {df['DATE TIME'].iloc[idx].strftime('%Y-%m-%d %H:%M:%S')}</span>"]
        row = df.iloc[idx].to_dict()
        colors = self.get_alert_colors_for_row(row)

        point_y = None
        if selected_series and selected_series in df.columns:
            value = df[selected_series].iloc[idx]
            if not pd.isna(value):
                point_y = value

        for key, line in self.pressure_lines.items():
            x_data, y_data = line.getData()
            if x_data is not None:
                line.setData(x=x_data, y=y_data, symbolSize=2.5)  # Reset sizes
            if line.isVisible() and self.pressure_checks[key].isChecked():
                value = df[key].iloc[idx]
                if not pd.isna(value):
                    unit = 'psi'
                    color = colors.get(key, TEXT_COLOR.name())
                    tooltip.append(
                        f"<br><span style='color:{color};'>{line.name()+':':<21} {value:>6.2f} {unit}</span>"
                    )
                    if x_data is not None and idx < len(x_data):
                        if not self.is_keyboard_nav or key == selected_series:
                            sizes = [2.5] * len(x_data)
                            sizes[idx] = 10
                            line.setData(x=x_data, y=y_data, symbolSize=sizes)

#        # This displays one error or the total number of errors.  
#        if colors['pressure_error_text'] != 'No pressure errors':
#            tooltip.append(
#                f"<br><span style='color:{colors['pressure_errors']};'>Errors: {colors['pressure_error_text']}</span>"
#            )
        # DISPLAYS FULL LIST OF ERRORS
        # Pressure warnings (yellow)
        for msg in colors.get('pressure_warning_list', []):
            tooltip.append(f"<br><span style='color:yellow;'>• {msg}</span>")

        # Pressure errors/critical (red)
        for msg in colors.get('pressure_error_list', []):
            tooltip.append(f"<br><span style='color:red;'>• {msg}</span>")

        tooltip_text = "".join(tooltip)
        
        # Determine tooltip position based on point's screen position
        vb = self.pressure_plot.getViewBox()
        current_x_range = vb.viewRange()[0]
        current_point_x = df['DATE TIME'].iloc[idx].timestamp()
        
        # Map point to widget coordinates for x-position
        point_scene = vb.mapViewToScene(QPointF(current_point_x, point_y if point_y is not None else vb.viewRange()[1][0]))
        point_widget = vb.mapToDevice(point_scene)
        global_pos = self.pressure_plot.mapToGlobal(point_widget.toPoint())
        
        # Position tooltip: center at pressure plot's global center
        plot_rect = self.pressure_plot.rect()
        tooltip_x = global_pos.x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)
        tooltip_y = self.pressure_plot.mapToGlobal(plot_rect.center()).y() - self.pressure_tooltip.height() // 2
        
        # Check if point is near edge (x-axis only)
        view_width = current_x_range[1] - current_x_range[0]
        relative_pos_x = (current_point_x - current_x_range[0]) / view_width
        
        if relative_pos_x < 0.1:
            tooltip_x = self.pressure_plot.mapToGlobal(QPoint(0, 0)).x() + (355 if global_pos.x() <= self.geometry().center().x() else -495)  # Left edge
        elif relative_pos_x > 0.9:
            tooltip_x = self.pressure_plot.mapToGlobal(QPoint(plot_rect.width(), 0)).x() + (355 if global_pos.x() <= self.geometry().center().x() else -495)  # Right edge
        
        tooltip_pos = QPoint(tooltip_x, tooltip_y)
        self.pressure_tooltip.show_at(tooltip_pos, tooltip_text)


    def update_water_tooltip(self, idx, df, selected_series=None):
        # THIS IS USED IN KEYPRESSEVENT. 
        if idx is None or idx >= len(df):
            self.water_tooltip.hide()
            return
        
        # Build tooltip text for all checked series, highlight selected series if keyboard nav
        tooltip = [f"<span style='color:{SOFT_GRAY.name()};'>Time: {df['DATE TIME'].iloc[idx].strftime('%Y-%m-%d %H:%M:%S')}</span>"]
        row = df.iloc[idx].to_dict()
        colors = self.get_alert_colors_for_row(row)

        point_y = None
        if selected_series and selected_series in df.columns:
            value = df[selected_series].iloc[idx]
            if not pd.isna(value):
                point_y = value

        for key, line in self.water_lines.items():
            x_data, y_data = line.getData()
            if x_data is not None:
                line.setData(x=x_data, y=y_data, symbolSize=2.5)  # Reset sizes
            if line.isVisible() and self.water_checks[key].isChecked():
                value = df[key].iloc[idx]
                if not pd.isna(value):
                    unit = '°F'
                    color = colors.get(key, TEXT_COLOR.name())
                    tooltip.append(
                        f"<br><span style='color:{color};'>{line.name()+':':<21} {value:>6.2f} {unit}</span>"
                    )
                    if x_data is not None and idx < len(x_data):
                        if not self.is_keyboard_nav or key == selected_series:
                            sizes = [2.5] * len(x_data)
                            sizes[idx] = 10
                            line.setData(x=x_data, y=y_data, symbolSize=sizes)

#        # This displays one error or the total number of errors.    
#        if colors['water_error_text'] != 'No water errors':
#            tooltip.append(
#                f"<br><span style='color:{colors['water_errors']};'>Errors: {colors['water_error_text']}</span>"
#            )
        # DISPLAYS FULL LIST OF ERRORS
        # Water warnings (yellow)
        for msg in colors.get('water_warning_list', []):
            tooltip.append(f"<br><span style='color:yellow;'>• {msg}</span>")

        # Water errors/critical (red)
        for msg in colors.get('water_error_list', []):
            tooltip.append(f"<br><span style='color:red;'>• {msg}</span>")

        tooltip_text = "".join(tooltip)
        
        # Determine tooltip position based on point's screen position
        vb = self.water_plot.getViewBox()
        current_x_range = vb.viewRange()[0]
        current_point_x = df['DATE TIME'].iloc[idx].timestamp()
        
        # Map point to widget coordinates for x-position
        point_scene = vb.mapViewToScene(QPointF(current_point_x, point_y if point_y is not None else vb.viewRange()[1][0]))
        point_widget = vb.mapToDevice(point_scene)
        global_pos = self.water_plot.mapToGlobal(point_widget.toPoint())
        
        # Position tooltip: center at water plot's global center
        plot_rect = self.water_plot.rect()
        tooltip_x = global_pos.x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)
        tooltip_y = self.water_plot.mapToGlobal(plot_rect.center()).y() - self.water_tooltip.height() // 2
        
        # Check if point is near edge (x-axis only)
        view_width = current_x_range[1] - current_x_range[0]
        relative_pos_x = (current_point_x - current_x_range[0]) / view_width
        
        if relative_pos_x < 0.1:
            tooltip_x = self.water_plot.mapToGlobal(QPoint(0, 0)).x() + (375 if global_pos.x() <= self.geometry().center().x() else -495)  # Left edge
        elif relative_pos_x > 0.9:
            tooltip_x = self.water_plot.mapToGlobal(QPoint(plot_rect.width(), 0)).x() + (375 if global_pos.x() <= self.geometry().center().x() else -495)  # Right edge
        
        tooltip_pos = QPoint(tooltip_x, tooltip_y)
        self.water_tooltip.show_at(tooltip_pos, tooltip_text)





#### DATE FILTERING SECTION HELPER FUNCTIONS--------------------------------------------------------------------------------------------------------------------

    def set_end_to_today(self):
#        print("STARTING: set_end_to_today")
        local_tz = get_localzone()  # Get local timezone
        self.end_date = datetime.now(local_tz).replace(tzinfo=local_tz)
        self.update_date_range()
#        print("FINISHED: set_end_to_today - CALLED: update_date_range")

    def on_date_changed(self):
        # WHEN START/END QDATEEDIT'S ARE CHANGED THIS UPDATES SELF.START_DATE AND SELF.END_DATE
#        print(f"STARTING: on_date_changed")
        local_tz = get_localzone()  # Get local timezone
        self.start_date = self.start_date_edit.date().toPyDate()
        self.end_date = self.end_date_edit.date().toPyDate()
        # Ensure start_date and end_date are timezone-aware
        self.start_date = datetime.combine(self.start_date, datetime.min.time(), tzinfo=local_tz)
        self.end_date = datetime.combine(self.end_date, datetime.max.time(), tzinfo=local_tz)
        self.range_combo.blockSignals(True)
        self.range_combo.setCurrentText("Custom")
        self.range_combo.blockSignals(False)
        self.update_date_range()


    def shift_range_left(self):
        # Ensure start_date and end_date are timezone-aware
        local_tz = get_localzone()
        if self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        
        # Normalize to day bounds
        self.start_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        self.end_date = self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if not self.selected_sid_dates:
            self.show_popup("No data available for this SID")
            return

        earliest_date = self.selected_sid_dates[0]

        # Current range duration
        current_delta = (self.end_date.date() - self.start_date.date()).days + 1
        shift_delta = timedelta(days=current_delta)

        # Proposed new range after shift left
        new_end   = self.end_date   - shift_delta 
        new_start = self.start_date - shift_delta 

        # If the proposed start would be before earliest → snap to earliest
        if new_start < earliest_date:
#            print("shift_left: new_start < earliest_date → snapping and showing popup")
            # Snap start to earliest available date
            snapped_start = earliest_date.replace(hour=0, minute=0, second=0, microsecond=0)
            snapped_end = snapped_start + timedelta(days=current_delta - 1)
            snapped_end = snapped_end.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Apply the snapped range (show earliest possible view)
            self.start_date = snapped_start
            self.end_date   = snapped_end

            self.show_popup(f"No Data Before {self.start_date.strftime('%Y-%m-%d')}")
            self.update_date_range()
            return

        # Normal shift with skip-empty logic
        first_skipped = None
        last_skipped  = None

        while new_end >= earliest_date:
            has_data = any(new_start.date() <= d.date() <= new_end.date() for d in self.selected_sid_dates)

            if has_data:
#                print(f"shift_left: found data after shift \n  before start_date = {self.start_date}, new_start = {new_start} \n  before end_date = {self.end_date}, new_end = {new_end} \n  shift_delta {shift_delta}")
                self.start_date = new_start#.replace(hour=0,   minute=0, second=0, microsecond=0)
                self.end_date   = new_end#.replace(  hour=23, minute=59, second=59, microsecond=999999)
#                print(f"  after start_date = {self.start_date}\n  after end_date = {self.end_date}")
                break

            if first_skipped is None:
                first_skipped = new_end
#                print(f"shift_left: starting skip tracking first_skipped = {first_skipped}")
            last_skipped = new_end
#            print(f"shift_left: starting skip tracking last_skipped = {last_skipped}")

            new_end   -= shift_delta
            new_start -= shift_delta

        else:
            self.show_popup(f"No Data Before {self.start_date.strftime('%Y-%m-%d')}")
            self.update_date_range()
            return

        if first_skipped and last_skipped:
            skip_start = first_skipped.replace(hour=0, minute=0, second=0, microsecond=0)
            skip_end   = last_skipped.replace(hour=23, minute=59, second=59, microsecond=999999)
            self.show_popup(f"Skipped empty range: {skip_end.strftime('%Y-%m-%d')} to {skip_start.strftime('%Y-%m-%d')}")

        self.update_date_range()


    def shift_range_right(self):
        # Ensure start_date and end_date are timezone-aware
        local_tz = get_localzone()
        self.end_date = self.end_date or datetime.now(local_tz).replace(tzinfo=local_tz)
        if self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        
        # Normalize to day bounds
        self.start_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        self.end_date = self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)


        if not self.selected_sid_dates:
            self.show_popup("No data available for this SID")
            return

        today = datetime.now(local_tz).replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=local_tz
        )

        latest_date = self.selected_sid_dates[-1].replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

        # Current range duration
        current_delta = (self.end_date.date() - self.start_date.date()).days + 1
        shift_delta = timedelta(days=current_delta)

        # Proposed new range after shift left
        new_end   = self.end_date   + shift_delta 
        new_start = self.start_date + shift_delta 

        # If the proposed end would be after latest → snap to latest
        if new_end > latest_date:
#            print("shift_right: new_end > latest_date → snapping and showing popup")

            snapped_end   = latest_date
            snapped_start = snapped_end - timedelta(days=current_delta - 1)
            snapped_start = snapped_start.replace(hour=0, minute=0, second=0, microsecond=0)

            # Apply the snapped range (show latest possible view)
            self.start_date = snapped_start
            self.end_date   = snapped_end

            self.show_popup(f"No Data Beyond {self.end_date.strftime('%Y-%m-%d')}")
            self.update_date_range()
            return

        # Normal shift with skip-empty logic
        first_skipped = None
        last_skipped  = None

        while new_end <= latest_date:
            has_data = any(new_start.date() <= d.date() <= new_end.date() for d in self.selected_sid_dates)

            if has_data:
#                print(f"shift_right: found data after shift. \n  new start_date = {new_start} \n  new_end = {new_end}")
                self.start_date = new_start#.replace(hour=0,   minute=0, second=0, microsecond=0)
                self.end_date   = new_end#.replace(  hour=23, minute=59, second=59, microsecond=999999)
                break

            if first_skipped is None:
#                print("shift_right: starting skip tracking")
                first_skipped = new_start
            last_skipped = new_start

            new_end   += shift_delta
            new_start += shift_delta

        else:
#            print("shift_right: reached beyond latest_date without data")
            self.show_popup(f"No Data Beyond {self.end_date.strftime('%Y-%m-%d')}")
            self.update_date_range()
            return

        if first_skipped and last_skipped:
            skip_start = first_skipped.replace(hour=0, minute=0, second=0, microsecond=0)
            skip_end   = last_skipped.replace(hour=23, minute=59, second=59, microsecond=999999)
            self.show_popup(f"Skipped empty range: {skip_start.strftime('%Y-%m-%d')} to {skip_end.strftime('%Y-%m-%d')}")

        self.update_date_range()

    def update_date_range(self):
#        print("STARTING: update_date_range, current pressure x range:", self.pressure_plot.getViewBox().viewRange()[0])
               
        # Sets the date range for data display based on the selected range option
        range_text = self.range_combo.currentText()
        local_tz = get_localzone()  # Get local timezone

        self.left_arrow.setEnabled(True)
        self.right_arrow.setEnabled(True)
        self.start_date_edit.setEnabled(True)
        self.end_date_edit.setEnabled(True)
        
        self.end_date = self.end_date or datetime.now(local_tz).replace(tzinfo=local_tz)
        if range_text == "1 Day":
            self.start_date = self.end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range_text == "3 Days":
            self.start_date = self.end_date - timedelta(days=2)           
        elif range_text == "1 Week":
            self.start_date = self.end_date - timedelta(days=6)         
        elif range_text == "1 Month":
            self.start_date = self.end_date - relativedelta(months=1)
        else:
#            self.start_date = self.end_date - timedelta(days=2)
            pass
        
        # Ensure start_date and end_date are timezone-aware
        if self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        
        self.start_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        self.end_date = self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)
        self.start_date_edit.setDate(QDate(self.start_date.year, self.start_date.month, self.start_date.day))
        self.end_date_edit.setDate(QDate(self.end_date.year, self.end_date.month, self.end_date.day))
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)
        
#        print(f"[update_date_range]: \nSet range to: {self.start_date} - {self.end_date}, \n control bar: {self.start_date_edit.date().toPyDate()} - {self.end_date_edit.date().toPyDate()}")
#        print("\n    update_date_range - CALLING: update_data")
        self.update_data()
        QTimer.singleShot(100, self.reset_zoom)



#### -- ALERTING HELPER FUNCTIONS--------------------------------------------------------------------------------------------------------------------

        
    def get_alert_colors_for_row(self, row):
        """
        Takes a single row (dict from latest_df.iloc[-1]) and returns colors for display.
        - Uses lighter green for safe values
        - Yellow for warnings, red for critical errors
        - Separate warning/error lists for tooltips
        """
        colors = {
            'mag_psi': TEXT_COLOR.name(),
            'avg_mag_psi': TEXT_COLOR.name(),
            'water_diff': TEXT_COLOR.name(),
            'water_in_f': TEXT_COLOR.name(),
            'water_out_f': TEXT_COLOR.name(),
            'wika_psi': TEXT_COLOR.name(),
            'atm_psi': TEXT_COLOR.name(),
            'errors': TEXT_COLOR.name(),
            'error_text': 'No errors',
            'pressure_warning_list': [],
            'pressure_error_list': [],
            'water_warning_list': [],
            'water_error_list': []
        }

        errors = []
        pressure_warnings = []
        pressure_errors = []
        water_warnings = []
        water_errors = []

        # ── Detect defective states first (for suppression) ──────────────────
        wika_defective = False
        atm_defective = False
        water_in_defective = False
        water_out_defective = False

        wika = row.get('wika_psi', None)
        if wika is not None:
            if wika < 10 or wika > 23.3:
                colors['wika_psi'] = CRITICAL_RED.name()
                errors.append("DEFECTIVE WIKA SENSOR")
                pressure_errors.append("DEFECTIVE WIKA SENSOR")
                wika_defective = True
            else:
                colors['wika_psi'] = LIGHT_GREEN.name()

        atm = row.get('atm_psi', None)
        if atm is not None:
            if atm < 10 or atm > 23.3:
                colors['atm_psi'] = CRITICAL_RED.name()
                errors.append("DEFECTIVE ATM. SENSOR")
                pressure_errors.append("DEFECTIVE ATM. SENSOR")
                atm_defective = True
            else:
                colors['atm_psi'] = LIGHT_GREEN.name()

        win = row.get('water_in_f', None)
        if win is not None:
            if win <= -147:
                colors['water_in_f'] = CRITICAL_RED.name()
                errors.append("DEFECTIVE WATER IN PROBE")
                water_errors.append("DEFECTIVE WATER IN PROBE")
                water_in_defective = True
            elif win < 55:
                colors['water_in_f'] = WARNING_YELLOW.name()
                msg = "WATER TEMP IN WARNING <55F"
                errors.append(msg)
                water_warnings.append(msg)
            elif win > 80:
                colors['water_in_f'] = WARNING_YELLOW.name()
                msg = "WATER TEMP IN WARNING >80F"
                errors.append(msg)
                water_warnings.append(msg)
            else:
                colors['water_in_f'] = LIGHT_GREEN.name()

        wout = row.get('water_out_f', None)
        if wout is not None:
            if wout <= -147:
                colors['water_out_f'] = CRITICAL_RED.name()
                errors.append("DEFECTIVE WATER OUT PROBE")
                water_errors.append("DEFECTIVE WATER OUT PROBE")
                water_out_defective = True
            elif wout < 57:
                colors['water_out_f'] = WARNING_YELLOW.name()
                msg = "WATER TEMP OUT WARNING <57F"
                errors.append(msg)
                water_warnings.append(msg)
            elif wout > 105:
                colors['water_out_f'] = WARNING_YELLOW.name()
                msg = "WATER TEMP OUT WARNING >105F"
                errors.append(msg)
                water_warnings.append(msg)
            else:
                colors['water_out_f'] = LIGHT_GREEN.name()

        pressure_sensor_defective = wika_defective or atm_defective
        water_probe_defective = water_in_defective or water_out_defective

        # ── Magnet / Helium pressure ────────────────────────────────────────
        mag = row.get('mag_psi', None)
        if mag is not None:
            if pressure_sensor_defective:
                colors['mag_psi'] = TEXT_COLOR.name()
            else:
                if mag > 1.75 or mag < 0.0:
                    colors['mag_psi'] = CRITICAL_RED.name()
                    msg = "MAGNET QUENCH" if mag > 1.75 else "POSSIBLE QUENCH"
                    errors.append(msg)
                    pressure_errors.append(msg)
                elif mag >= 0.3 and mag <= 0.6:
                    colors['mag_psi'] = LIGHT_GREEN.name()
                else:
                    colors['mag_psi'] = WARNING_YELLOW.name()
                    if mag < 0.3:
                        msg = "MAGNET PRESSURE LOW WARNING <0.3psi"
                        errors.append(msg)
                        pressure_warnings.append(msg)
                    elif mag > 0.6:
                        msg = "MAGNET PRESSURE HIGH WARNING >0.6psi"
                        errors.append(msg)
                        pressure_warnings.append(msg)

        # avg_mag_psi — no suppression
        avg_mag = row.get('avg_mag_psi', None)
        if avg_mag is not None:
            if avg_mag > 1.75 or avg_mag < 0.0:
                colors['avg_mag_psi'] = CRITICAL_RED.name()
            elif avg_mag >= 0.3 and avg_mag <= 0.6:
                colors['avg_mag_psi'] = LIGHT_GREEN.name()
            else:
                colors['avg_mag_psi'] = WARNING_YELLOW.name()

        # ── Water diff ──────────────────────────────────────────────────────
        diff = row.get('water_diff', None)
        if diff is not None:
            if water_probe_defective:
                colors['water_diff'] = TEXT_COLOR.name()
            else:
                if diff < 5:
                    if diff < 2:
                        colors['water_diff'] = CRITICAL_RED.name()
                        msg = "WATER TEMP DELTA ERROR <2F"
                        errors.append(msg)
                        water_errors.append(msg)
                    else:
                        colors['water_diff'] = WARNING_YELLOW.name()
                        msg = "WATER TEMP DELTA WARNING <5F"
                        errors.append(msg)
                        water_warnings.append(msg)
                elif diff > 30:
                    colors['water_diff'] = CRITICAL_RED.name()
                    msg = "WATER TEMP DELTA WARNING >30F"
                    errors.append(msg)
                    water_errors.append(msg)
                else:
                    colors['water_diff'] = LIGHT_GREEN.name()

        # ── Summaries ───────────────────────────────────────────────────────
        if errors:
            colors['errors'] = CRITICAL_RED.name()
            colors['error_text'] = errors[0] if len(errors) == 1 else f"{len(errors)} errors"
        else:
            colors['errors'] = TEXT_COLOR.name()

        # Full lists for tooltips
        colors['pressure_warning_list'] = pressure_warnings
        colors['pressure_error_list']   = pressure_errors
        colors['water_warning_list']    = water_warnings
        colors['water_error_list']      = water_errors

        return colors
    
    


#### DATA COLLECTION SECTION WORKER FUNCTIONS ------------------------------------------------------------------------------------------------------------------------

    def update_data(self):
#        print("STARTING: update_data")
        start_time = time.time()

  ### ========== GLOB TO SEARCH FOR NEW SIDS SECTION =========================================
        all_sid_discovery_files = [] 
        current_sid = self.selected_sid                                
        pattern_new = "*_*_HPM2_Test_data.log"          # existing
        pattern_old = "*_*_HPM2_BTrdr2_test_data.txt"   # new
        all_log_folders = self.compile_log_folders()
        for entry in all_log_folders:
            folder = entry["path"]
            recursive = entry.get("recursive", False)
            if not os.path.exists(folder):
                continue
            matches_new = glob.glob(os.path.join(folder, "**", pattern_new), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_new))
            matches_old = glob.glob(os.path.join(folder, "**", pattern_old), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_old))
            all_sid_discovery_files.extend(matches_new + matches_old)

        sids = set()
        
        for log_file in all_sid_discovery_files:                     
            match = re.match(r"^(\d+)_\d{8}", os.path.basename(log_file))
            if match:
                sids.add(match.group(1))
        new_sids = sorted(sids, key=int)
        if new_sids != self.sid_list:
            self.sid_list = new_sids
            self.sid_combo.blockSignals(True)
            self.sid_combo.clear()
            self.sid_combo.addItems(self.sid_list)
#            print(f"    update_data - found new SID ")
            if current_sid in self.sid_list:
                self.sid_combo.setCurrentText(current_sid)
            else:
                self.selected_sid = self.sid_list[0] if self.sid_list else None
                self.sid_combo.setCurrentText(self.selected_sid if self.selected_sid else "")
                self.cached_df = None
                self.pressure_y_default = [-1, 1]  # Reset y-defaults on SID change
                self.water_y_default = [-1, 1]
            self.sid_combo.blockSignals(False)

  ### ========== GLOB TO GET ALL FILES FOR SELECTED_SID ===========================================
        # Updates gauge, displays, and plots with data from the selected SID
        if not self.selected_sid:
            return
        
        selected_sid_log_files = []
        pattern_new = f"{self.selected_sid}_*_HPM2_Test_data.log"
        pattern_old = f"{self.selected_sid}_*_HPM2_BTrdr2_test_data.txt"
        for entry in all_log_folders:
            folder = entry["path"]
            recursive = entry.get("recursive", False)
            if not os.path.exists(folder):
                continue
            matches_new = glob.glob(os.path.join(folder, "**", pattern_new), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_new))
            matches_old = glob.glob(os.path.join(folder, "**", pattern_old), recursive=recursive) if recursive else glob.glob(os.path.join(folder, pattern_old))
            selected_sid_log_files.extend(matches_new + matches_old)

        # ── Deduplicate: keep only the file with the latest mtime for each date ───────
        date_to_file_and_mtime = {}  # key: 'YYYYMMDD' str → (full_path, mtime)

        for f in selected_sid_log_files:
            match = re.search(r"_(\d{8})_", os.path.basename(f))
            if not match:
                continue
            date_key = match.group(1)  # '20260213'
            try:
                current_mtime = os.path.getmtime(f)
            except Exception:
                continue  # skip unreadable files

            # If we haven't seen this date, or this file is newer
            if date_key not in date_to_file_and_mtime or current_mtime > date_to_file_and_mtime[date_key][1]:
                date_to_file_and_mtime[date_key] = (f, current_mtime)

        # Rebuild list with only the newest file per date
        selected_sid_log_files = [path for path, mtime in date_to_file_and_mtime.values()]

#        print(f"selected_sid_log_files after dedup (newest mtime per date) = {selected_sid_log_files}")

  ### ========== NEEDS PROCESSING SECTION =======================================================
        # Quick early exit: if no files changed since last run, skip everything
        needs_processing = None

#        print(f"    update_data - update_keys\nprev={self.prev_update_key}\nnew={new_update_key}")
        if not needs_processing:
            for f in selected_sid_log_files:
                try:
                    current_mtime = os.path.getmtime(f)
                    prev = self.known_files.get(f, {})
                    if f not in self.known_files or current_mtime > prev.get('mtime', 0):
                        needs_processing = True
#                        print("    update_data - new files = needs_processing True")
                        break
                except Exception:
                    needs_processing = True
#                    print("    update_data - new files except = needs_processing True")
                    break
        
        new_update_key = (self.selected_sid, self.start_date, self.end_date)        
        if new_update_key != getattr(self, "prev_update_key", None):
#            print("    update_data - SID or date changed = needs_processing True")
            needs_processing = True

        if self.is_processing:
#            print("    update_data - self_is_processing True = needs_processing = False")
            needs_processing = False

        if not needs_processing:
#            print("    update_data - Does not need processing. → early exit, skipping processing")
            end_time = time.time()
#            print(f"FINISHED: update_data - took {end_time - start_time:.2f} seconds (skipped)")
            return

        self.is_processing = True
#        print("    update_data - Needs Processing → continuing on with the rest of the function")
 
  ### ========== GAUGE/DISPLAY SECTION ============================================================
    # Find the single newest file by date in filename for gauge/display
        newest_file = None
        newest_mtime = 0
        for f in selected_sid_log_files:
            try:
                mtime = os.path.getmtime(f)
            except Exception:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_file = f
        
        # Only process the newest file for gauge/display if it changed
        latest_df = None
        if newest_file:
            try:
                stat = os.stat(newest_file)
                mtime = stat.st_mtime
                size = stat.st_size
            except Exception:
                mtime = size = 0

            if newest_file:
#                print("    update_data - newest file changed → updating gauge")
                latest_df = self.process_log_file([newest_file])






    # Update gauge and displays with the most recent sample
            if latest_df is not None and not latest_df.empty:
                try:
                    latest = latest_df.iloc[-1]
                    latest_date = latest['DATE TIME']
                    mag_psi = latest['mag_psi']

                    self.gauge.setValue(mag_psi)
                    self.fullscreen_gauge.setValue(mag_psi)

                    # Get colors for this single row
                    colors = self.get_alert_colors_for_row(latest.to_dict())
                    """
                    # Left & Right Displays - color only the Values
                    left_text = (
                        f"                             LATEST<br>"
                        f"{latest_date.strftime(' %Y-%m-%d    %H:%M:%S')}<br>"
                        f"{'Magnet Pressure:':<21} <span style='color:{colors['mag_psi']};'>{mag_psi:>6.2f}</span><br>"
                        f"{'Mag. Avg. Press.:':<22} <span style='color:{colors['avg_mag_psi']};'>{latest['avg_mag_psi']:>6.2f}</span><br>"  # same color as mag_psi
                        f"{'Wika Pressure:':<22} <span style='color:{colors['wika_psi']};'>{latest['wika_psi']:>6.2f}</span><br>"
                        f"{'Atmospheric Press.:':<20} <span style='color:{colors['atm_psi']};'>{latest['atm_psi']:>6.2f}</span>"
                    )
                    self.left_display.setText(left_text)

                    right_text = (
                        f"READING<br>"
                        f"Errors: <span style='color:{colors['errors']};'>{colors['error_text']}</span><br>"
                        f"{'Water Temp Diff:':<20} <span style='color:{colors['water_diff']};'>{latest['water_diff']:>6.2f}</span><br>"
                        f"{'Water Temp In:':<20} <span style='color:{colors['water_in_f']};'>{latest['water_in_f']:>6.2f}</span><br>"
                        f"{'Water Temp Out:':<18} <span style='color:{colors['water_out_f']};'>{latest['water_out_f']:>6.2f}</span><br>"
                        f"{'Scan Pulses:':<21} <span style='color:{TEXT_COLOR.name()};'>{latest['scan_pulses']:>6}</span>"
                    )
                    self.right_display.setText(right_text)
                    """
                    # Left & Right Displays - color the whole line.
                    left_text = (
                        f"<span style='color:{TEXT_COLOR.name()};'>                             LATEST</span><br>"
                        f"<span style='color:{TEXT_COLOR.name()};'>{latest_date.strftime(' %Y-%m-%d    %H:%M:%S')}</span><br>"
                        f"<span style='color:{colors['mag_psi']};'>{'Magnet Pressure:':<21} {mag_psi:>6.2f}</span><br>"
                        f"<span style='color:{colors['avg_mag_psi']};'>{'Mag. Avg. Press.:':<22} {latest['avg_mag_psi']:>6.2f}</span><br>"  # same color as mag_psi
                        f"<span style='color:{colors['wika_psi']};'>{'Wika Pressure:':<22} {latest['wika_psi']:>6.2f}</span><br>"
                        f"<span style='color:{colors['atm_psi']};'>{'Atmospheric Press.:':<20} {latest['atm_psi']:>6.2f}</span>"
                    )
                    self.left_display.setText(left_text)

                    right_text = (
                        f"<span style='color:{TEXT_COLOR.name()};'>READING</span><br>"
                        f"<span style='color:{colors['errors']};'>Errors: {colors['error_text']}</span><br>"
                        f"<span style='color:{colors['water_diff']};'>{'Water Temp Diff:':<20} {latest['water_diff']:>6.2f}</span><br>"
                        f"<span style='color:{colors['water_in_f']};'>{'Water Temp In:':<20} {latest['water_in_f']:>6.2f}</span><br>"
                        f"<span style='color:{colors['water_out_f']};'>{'Water Temp Out:':<18} {latest['water_out_f']:>6.2f}</span><br>"
                        f"<span style='color:{TEXT_COLOR.name()};'>{'Scan Pulses:':<21} {latest['scan_pulses']:>6}</span>"
                    )
                    self.right_display.setText(right_text)                    
                #    """
                except Exception as e:
                    self.log_error(f"Error updating gauge/displays: {e}")
                    self.left_display.setText("Latest data unavailable")
                    self.right_display.setText("Latest data unavailable")






  ### ========== PLOT SECTION ===================================================================
    # Ensure start_date and end_date are timezone-aware
        local_tz = get_localzone()  # Get local timezone    
        if self.start_date and self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date and self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)

    # ── Filter for date range using pre-globbed selected_sid_log_files ─────────────────
        valid_dates = []
        log_files = []
        if self.start_date and self.end_date:
            start_date = self.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = self.end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            for f in selected_sid_log_files:
                match = re.search(r"_(\d{8})_", os.path.basename(f))
                if match:
                    try:
                        file_date = datetime.strptime(match.group(1), '%Y%m%d').replace(tzinfo=local_tz)
                        valid_dates.append(file_date)
                        if start_date <= file_date <= end_date:
                            log_files.append(f)
                    except ValueError:
                        continue
            log_files = sorted(log_files)
#        print(f"log_files = {log_files}")
        # Store sorted list of all available dates for this SID
        self.selected_sid_dates = sorted(valid_dates) if valid_dates else []
        
        # Update known files cache for next check
        for f in selected_sid_log_files:
            try:
                stat = os.stat(f)
                self.known_files[f] = {'mtime': stat.st_mtime, 'size': stat.st_size}
            except Exception:
                pass

        if log_files:
#            print("    update_data - 'if log_files' CALLING: process_log_file.    This updates self.cached_df. (graphs)")
            self.cached_df = self.process_log_file(log_files)
        else:
#            print("    update_data - 'if ELSE log_files' CALLING: self.cached_df = None.")
            self.cached_df = None

        # Decide if we need to downsample based on date range length
        if self.cached_df is not None and not self.cached_df.empty:
            days_visible = (self.end_date - self.start_date).days if self.start_date and self.end_date else 0
            
            if days_visible > 7 and len(self.cached_df) > 20000:  # adjust thresholds
#                print(f"    update_data - Downsampling cached_df: {len(self.cached_df)} → target ~8000 points")
                self.cached_df = self.downsample_with_extremes(self.cached_df, target_points=8000)
                self.w_notes_label.setText(">1 week uses downsampled data")
                self.p_notes_label.setText(">1 week uses downsampled data")
            else:
                self.w_notes_label.setText("")
                self.p_notes_label.setText("")                
#                print("    update_data - No downsampling needed (range ≤ 7 days or few points)")            

        self.prev_update_key = (self.selected_sid, self.start_date, self.end_date)

#        print("    update_data - CALLING: update_plots")
        self.update_plots()        
        QTimer.singleShot(200, self._update_caches)
        self.is_processing = False       
        end_time = time.time()
#        print(f"FINISHED: update_data - took {end_time - start_time:.2f} seconds, this includes timers from here back to Starting: update_data.\n")


# THIS IS A NEW VERSION TO SUPPORT THE NEW and OLD FILES. 
    def process_log_file(self, log_files):
        start_time = time.time()
        if not log_files:
            return None
        dfs = []
        local_tz = get_localzone()
        common_base_cols = ['DATE TIME', 'wika_psi', 'atm_psi', 'water_in_f', 'water_out_f',
                            'scan_pulses', 'water_diff', 'mag_psi']
        for log_file in log_files:
            try:
                # Peek at first line to check for proper header
                with open(log_file, 'r') as f:
                    header = f.readline().strip()
                if 'DATE TIME' in header and ',' in header:
                    # Headered format (newer style)
                    df = pd.read_csv(log_file, parse_dates=['DATE TIME'])
                    if df['DATE TIME'].dt.tz is None:
                        df['DATE TIME'] = df['DATE TIME'].dt.tz_localize(local_tz)
                    else:
                        df['DATE TIME'] = df['DATE TIME'].dt.tz_convert(local_tz)
                    # Ensure only expected columns (safety)
                    if 'scan_pulses' not in df.columns:
                        # Some headered files might lack it — add NaN if missing
                        df['scan_pulses'] = pd.NaT  # or np.nan
                    df = df[common_base_cols[:-1] + ['mag_psi']]  # reorder/select known cols
                else:
                    # Non-header format — detect column count to choose layout
                    temp_df = pd.read_csv(log_file, skiprows=1, header=None, nrows=10)
                    num_cols = temp_df.shape[1]
                    if num_cols == 9:
                        column_names = ['DATETIME', 'wika_psi', 'atm_psi', 'water_in_f', 'water_out_f',
                                        'He_last_read', 'scan_pulses', 'water_diff', 'mag_psi']
                    elif num_cols == 14:
                        column_names = ['DATETIME', 'wika_psi', 'atm_psi', 'water_in_f', 'water_out_f',
                                        'He_last_read', 'scan_pulses', 'rf_gate', 'RESETs_cnt',
                                        'WIKA_p', 'WIKA_delay', 'water_diff', 'mag_psi', '']
                    else:
                        self.log_error(f"Unexpected column count {num_cols} in {log_file}")
                        continue
                    df = pd.read_csv(log_file, names=column_names, skiprows=1, header=None)
                    df['DATETIME'] = df['DATETIME'].astype(str).str.strip()
                    df['DATE TIME'] = pd.to_datetime(df['DATETIME'], format='%Y%m%d %H:%M:%S',
                                                    errors='coerce').dt.tz_localize(local_tz)
                    if df['DATE TIME'].isna().any():
                        df = df.dropna(subset=['DATE TIME'])
                    df = df.drop(columns=['DATETIME', 'He_last_read'], errors='ignore')
                    # Drop old-format extras if present
                    df = df.drop(columns=['rf_gate', 'RESETs_cnt', 'WIKA_p', 'WIKA_delay', ''], errors='ignore')
                # Common processing for both formats
                for col in ['wika_psi', 'atm_psi', 'water_in_f', 'water_out_f', 'water_diff', 'mag_psi']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df['avg_mag_psi'] = df['mag_psi'].rolling(window=10, min_periods=1).mean()
                # Final column selection — ensures identical structure
                df = df[common_base_cols + ['avg_mag_psi']]
                dfs.append(df)
            except Exception as e:
                self.log_error(f"Error processing log file {log_file}: {e}")
                continue
        if not dfs:
            return None
        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values('DATE TIME').drop_duplicates(subset='DATE TIME', keep='last')
        end_time = time.time()
        return df

    def downsample_with_extremes(self, df, target_points=8000):
        """
        Downsample time-series DataFrame while preserving min/max extremes per chunk.
        Returns a new df with ~target_points rows, sorted by time.
        """
        start_time = time.time()
        if len(df) <= target_points:
            return df.copy()
        
        # Target chunk size — aim for ~target_points after keeping min/max
        chunk_size = max(3, len(df) // (target_points // 3))
        
        downsampled_rows = []
        
        numeric_cols = [c for c in df.columns 
                        if c != 'DATE TIME' and pd.api.types.is_numeric_dtype(df[c])]
        
        if not numeric_cols:
            # No numeric data to min/max → just take every Nth point
            return df.iloc[::chunk_size].copy()
        
        for start_idx in range(0, len(df), chunk_size):
            chunk = df.iloc[start_idx : start_idx + chunk_size]
            if chunk.empty:
                continue
            
            # Keep first point
            downsampled_rows.append(chunk.iloc[0])
            
            # Find global min and max across numeric columns
            # stack() → Series with MultiIndex (row_index, column_name)
            stacked = chunk[numeric_cols].stack()
            
            # idxmin/idxmax returns (row_index, column_name)
            min_loc = stacked.idxmin()
            max_loc = stacked.idxmax()
            
            # Extract the actual row index (first element of the tuple)
            min_row_idx = min_loc[0] if isinstance(min_loc, tuple) else min_loc
            max_row_idx = max_loc[0] if isinstance(max_loc, tuple) else max_loc
            
            # Append min row if not already added (compare row index)
            last_row_idx = downsampled_rows[-1].name if downsampled_rows else None
            if min_row_idx != last_row_idx:
                downsampled_rows.append(chunk.loc[min_row_idx])
            
            # Append max row if not already added
            last_row_idx = downsampled_rows[-1].name if downsampled_rows else None
            if max_row_idx != last_row_idx:
                downsampled_rows.append(chunk.loc[max_row_idx])
        
        # Always include last point
        if downsampled_rows and downsampled_rows[-1].name != df.index[-1]:
            downsampled_rows.append(df.iloc[-1])
        
        # Build final df and sort by time
        down_df = pd.DataFrame(downsampled_rows)
        down_df = down_df.sort_values('DATE TIME').reset_index(drop=True)
        end_time = time.time()
#        print(f"FINISHED: downsample_with_extremes - Downsampled from {len(df)} to {len(down_df)} points - \n    downsample_with_extremes took {end_time - start_time} seconds")
        
        return down_df

    def update_plots(self):
#        print("STARTING: update_plots")
        start_time = time.time()
        # Updates the plots with data in the selected date range
        local_tz = get_localzone()  # Get local timezone
        if self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
            # Ensure start_date and end_date are timezone-aware
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=local_tz)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=local_tz)

#        print(f"[update_plots]: \nSet range to: {start_date} - {end_date}, \n control bar: {self.start_date_edit.date().toPyDate()} - {self.end_date_edit.date().toPyDate()}")

        if not self.selected_sid:
            self.clear_plots()
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
#            print("    update_plots - 'not selected_sid, return'")
            return
        
        try:            
            if self.cached_df is None or self.cached_df.empty:
                self.clear_plots()
                self.pressure_plot.enableAutoRange()
                self.water_plot.enableAutoRange()
#                print("    update_plots - 'cached_df is None, return'")
                return
            
            df = self.cached_df[(self.cached_df['DATE TIME'] >= start_date) & (self.cached_df['DATE TIME'] <= end_date)]
            timestamps = df['DATE TIME'].apply(lambda x: x.timestamp()).values
            
            if df.empty:
                self.clear_plots()
                self.pressure_plot.enableAutoRange()
                self.water_plot.enableAutoRange()
#                print("    update_plots - 'df.empty, return'")
                return
            
    # Recalculate y-ranges for visible series to re-scale on checkbox state changes
            pressure_y = []
            for key in self.pressure_lines:
                if self.pressure_checks[key].isChecked():
                    data = df[key].values
                    valid_data = data[~np.isnan(data)]
                    pressure_y.extend(valid_data)
            if pressure_y:
                y_min, y_max = min(pressure_y), max(pressure_y)
                padding = (y_max - y_min) * 0.05
                self.pressure_y_default = [y_min - padding, y_max + padding]
            else:
                self.pressure_y_default = [-1, 1]
            
            water_y = []
            for key in self.water_lines:
                if self.water_checks[key].isChecked():
                    data = df[key].values
                    valid_data = data[~np.isnan(data)]
                    water_y.extend(valid_data)
            if water_y:
                y_min, y_max = min(water_y), max(water_y)
                padding = (y_max - y_min) * 0.05
                self.water_y_default = [y_min - padding, y_max + padding]
            else:
                self.water_y_default = [-1, 1]

    # Track checkbox changes to re-scale specific plot
            pressure_checkboxes_changed = False
            water_checkboxes_changed = False
            for key, line in self.pressure_lines.items():
                new_visible = self.pressure_checks[key].isChecked()
                if line.isVisible() != new_visible:  # Check for any state change
                    pressure_checkboxes_changed = True
                line.setVisible(new_visible)
                if line.isVisible() and not df.empty:
                    data = df[key].values
                    valid_mask = ~np.isnan(data)
                    valid_timestamps = timestamps[valid_mask]
                    valid_data = data[valid_mask]
                    line.setData(x=valid_timestamps, y=valid_data, symbolSize=2.5)
                else:
                    line.setData(x=[], y=[])
            
            for key, line in self.water_lines.items():
                new_visible = self.water_checks[key].isChecked()
                if line.isVisible() != new_visible:  # Check for any state change
                    water_checkboxes_changed = True
                line.setVisible(new_visible)
                if line.isVisible() and not df.empty:
                    data = df[key].values
                    valid_mask = ~np.isnan(data)
                    valid_timestamps = timestamps[valid_mask]
                    valid_data = data[valid_mask]
                    line.setData(x=valid_timestamps, y=valid_data, symbolSize=2.5)
                else:
                    line.setData(x=[], y=[])
            
    # Restore highlights based on navigation mode and focus
            if self.current_point_idx is not None and self.current_point_idx < len(df):
                if self.pressure_plot.hasFocus() and self.is_keyboard_nav and self.selected_series in self.pressure_lines:
                    for key, line in self.pressure_lines.items():
                        if line.isVisible() and self.pressure_checks[key].isChecked():
                            x_data, y_data = line.getData()
                            if x_data is not None and self.current_point_idx < len(x_data):
                                sizes = [2.5] * len(x_data)
                                if key == self.selected_series:
                                    sizes[self.current_point_idx] = 10
                                line.setData(x=x_data, y=y_data, symbolSize=sizes)
                elif self.pressure_plot.hasFocus() and not self.is_keyboard_nav:
                    for key, line in self.pressure_lines.items():
                        if line.isVisible() and self.pressure_checks[key].isChecked():
                            x_data, y_data = line.getData()
                            if x_data is not None and self.current_point_idx < len(x_data):
                                sizes = [2.5] * len(x_data)
                                sizes[self.current_point_idx] = 10
                                line.setData(x=x_data, y=y_data, symbolSize=sizes)
                
                if self.water_plot.hasFocus() and self.is_keyboard_nav and self.selected_series in self.water_lines:
                    for key, line in self.water_lines.items():
                        if line.isVisible() and self.water_checks[key].isChecked():
                            x_data, y_data = line.getData()
                            if x_data is not None and self.current_point_idx < len(x_data):
                                sizes = [2.5] * len(x_data)
                                if key == self.selected_series:
                                    sizes[self.current_point_idx] = 10
                                line.setData(x=x_data, y=y_data, symbolSize=sizes)
                elif self.water_plot.hasFocus() and not self.is_keyboard_nav:
                    for key, line in self.water_lines.items():
                        if line.isVisible() and self.water_checks[key].isChecked():
                            x_data, y_data = line.getData()
                            if x_data is not None and self.current_point_idx < len(x_data):
                                sizes = [2.5] * len(x_data)
                                sizes[self.current_point_idx] = 10
                                line.setData(x=x_data, y=y_data, symbolSize=sizes)
            
            # Set x and y ranges after visibility updates
            self.pressure_plot.getAxis('bottom').setStyle(tickTextOffset=10)
            self.water_plot.getAxis('bottom').setStyle(tickTextOffset=10)

            if pressure_checkboxes_changed:
                self.pressure_plot.setRange(yRange=self.pressure_y_default, padding=0)
            if water_checkboxes_changed:
                self.water_plot.setRange(yRange=self.water_y_default, padding=0)               
            end_time = time.time()
#            print(f"FINISHED: update_plots - took {end_time - start_time:.2f} seconds, pressure check = {pressure_checkboxes_changed}, water check = {water_checkboxes_changed}")            

        except Exception as e:
            self.log_error(f"Error updating plots: {e}")
            self.clear_plots()
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()


    def clear_plots(self):
        """Clear all plot lines + any highlight state."""
        # Clear pressure lines
        for line in self.pressure_lines.values():
            line.setData(x=[], y=[])
            line.setVisible(False)  # optional, but helps avoid hover/click artifacts
        # Clear water lines
        for line in self.water_lines.values():
            line.setData(x=[], y=[])
            line.setVisible(False)
        # Reset navigation/highlight state so you don't try to re-highlight stale indices
        self.current_point_idx = None
        self.selected_series = None
        # Reset ranges to something sane
        self.pressure_y_default = [-1, 1]
        self.water_y_default = [-1, 1]
        # Force the view to redraw immediately
        self.pressure_plot.repaint()
        self.water_plot.repaint()


    def reset_zoom(self):
#        print(f"STARTING: reset_zoom")
        if not self.selected_sid:
            self.clear_plots()
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
#            print("   reset zoom - if not self.selected_sid,  return\n")
            return

        if self.start_date is None or self.end_date is None:
#            print("   reset_zoom - no valid date range, falling back to auto\n")
            self.clear_plots()
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
            return
                
        try: 
            xpadding = 60 * 30
            x_range = [self.start_date.timestamp() - xpadding, self.end_date.timestamp() + xpadding]
#            print("          reset_zoom ------->---------> attemping x-range:", [self.start_date.timestamp(), self.end_date.timestamp()],)            
            self.pressure_plot.setRange(xRange=x_range, yRange=self.pressure_y_default, padding=0)
            self.water_plot.setRange(xRange=x_range, yRange=self.water_y_default, padding=0)
    #        self.pressure_plot.enableAutoRange() # THESE WERE USED FOR TESTING BECAUSE THESE AUTORANGE() ADD SPACE ON LEFT AND RIGHT SIDES OF GRAPH. 
    #        self.water_plot.enableAutoRange()
#            print("FINISHED: reset-zoom - after setRange, - pressure x range:", self.pressure_plot.getViewBox().viewRange()[0],"\n")

        except Exception as e:
            self.log_error(f"Error resetting zoom: {e}")
            self.clear_plots()
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()



DARK_STYLESHEET = """
/* Match what you already do repeatedly:
   - Main window / generic widgets: dark background + text color
   - Buttons/inputs: frame background + text color
   - No added padding, min-width, border-radius
   - No global QFrame borders (prevents format changes)
*/

/* App base */
QMainWindow, QWidget {
    background-color: rgb(30,30,30);
    color: rgb(200,200,200);
}

/* Common controls you were styling inline */
QPushButton,
QLineEdit,
QComboBox,
QDateEdit {
    background-color: rgb(40,40,40);
    color: rgb(200,200,200);
}

/* Label / checkbox text (you set these a lot) */
QLabel {
    color: rgb(200,200,200);
}

/* Optional: ONLY if you had the checkbox indicator custom already.
   If this changes your look, delete this whole block. */
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid rgb(80,80,80);
    background: rgb(40,40,40);
    border-radius: 3px;
}
"""



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
#    app.setStyleSheet(DARK_STYLESHEET) # STILL WORKING ON THIS. IT DELTES THE CHECKBOX CHECKS. 
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())