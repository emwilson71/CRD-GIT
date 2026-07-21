import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from dateutil.relativedelta import relativedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QLineEdit, QDialog, QCheckBox,
                             QFrame, QSizePolicy, QDateEdit, QSpacerItem)
from PyQt5.QtCore import QTimer, Qt, QRectF, QPointF, QPoint, QDate
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QLinearGradient, QCursor, QPixmap, QPainterPath
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import glob
import re
import time
from tzlocal import get_localzone
import zoneinfo


def get_base_path():
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe), use the directory of the executable
        return os.path.dirname(sys.executable)
    else:
        # Otherwise, use the directory of the Python script
        return os.path.dirname(os.path.abspath(__file__))

LOG_FOLDER = [
    os.path.join(get_base_path(), "logs"),
    "c:/programdata/helium_pressure_monitor",
    "c:/CRD/downloads"
]
#if not os.path.exists(LOG_FOLDER):
#    os.makedirs(LOG_FOLDER)

DEFAULT_CURRENTDB_PATH = "C:/CRD/config/current.dat"

DARK_BG = QColor(30, 30, 30)
TEXT_COLOR = QColor(200, 200, 200)
FRAME_BG = QColor(40, 40, 40)

class CustomTooltip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()}; border: 1px solid {TEXT_COLOR.name()}; padding: 5px;")
        self.setFont(QFont("Arial", 10))
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
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
    def __init__(self, offset=0.0, parent=None):
        super().__init__(parent)
        self.offset = offset
        self.setWindowTitle("Settings")
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")
        layout = QVBoxLayout()
        
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Magnet Gauge Pressure Offset:"))
#        self.offset_input = QLineEdit()
        self.offset_input = QLineEdit(("Future Add On")) # This feature will be added on in the future. 
        self.offset_input.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        offset_layout.addWidget(self.offset_input)
        set_offset_btn = QPushButton("Set")
        set_offset_btn.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()};")
        set_offset_btn.clicked.connect(self.set_offset)
        offset_layout.addWidget(set_offset_btn)
        self.offset_label = QLabel(f"Current Offset: {self.offset:.2f}")
        offset_layout.addWidget(self.offset_label)
        layout.addLayout(offset_layout)
        
        self.setLayout(layout)

    def set_offset(self):
        # This will be used in the future to set the offset in the microcontroller. 
        return

class MainWindow(QMainWindow):
    def __init__(self):
        # Initialize the main window
        super().__init__()

        # Set up window properties
        self.offset = 0.0
        self.errors = "None"
        self.start_date = None
        self.end_date = None
        self.selected_sid = None
        self.sid_list = []
        self.cached_df = None
        self.setWindowTitle("HPM2 Monitor")
        self.setGeometry(0, 0, 1200, 800)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"background-color: {DARK_BG.name()}; color: {TEXT_COLOR.name()};")
        self.section_states = {'gauge': True, 'pressure': True, 'water': True}
        self.is_fullscreen = False
        self.active_graph = None
        self.is_updating = False
        self.current_point_idx = None  # Track current point for arrow navigation
        self.active_plot = None  # Track which plot is active (pressure or water)
        self.pressure_y_default = [-1.05, 2.1]  # Default y-range for pressure plot
        self.water_y_default = [57, 83]  # Default y-range for water plot
        self.last_update_key = None  # Track SID and date range for y-range persistence
        self.is_keyboard_nav = False  # Track if keyboard navigation is active        
        self.selected_series = None # Track closest series for arrow key point selection

        # Initialize tooltips for plots
        self.pressure_tooltip = CustomTooltip(self)
        self.water_tooltip = CustomTooltip(self)

        # Define semi-transparent cursor (global or in __init__)
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor(0, 0, 0, 50))  # 20% opacity black
        painter.drawEllipse(0, 0, 10, 10)  # Small circle
        painter.end()
        self.transparent_cursor = QCursor(pixmap)

        # Set up main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_widget.setLayout(main_layout)

        # Create top control layout
        top_control_layout = QHBoxLayout()
        top_control_layout.setContentsMargins(30, 10, 0, 0)
        settings_btn = QPushButton("Settings")
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
        self.columns_widget.setFixedHeight(135)
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

        # Set up pressure plot section
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
        pressure_layout.addLayout(title_layout)
        self.pressure_plot.setBackground(FRAME_BG)
        self.pressure_plot.getAxis('bottom').setTextPen(TEXT_COLOR)
        self.pressure_plot.getAxis('left').setTextPen(TEXT_COLOR)
        self.pressure_plot.getAxis('bottom').setTickSpacing(major=86400, minor=3600)
        pressure_layout.addWidget(self.pressure_plot)
        self.pressure_section.setLayout(pressure_layout)
        main_layout.addWidget(self.pressure_section)

        # Set up water plot section
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
        water_layout.addLayout(water_title_layout)
        self.water_plot.setBackground(FRAME_BG)
        self.water_plot.getAxis('bottom').setTextPen(TEXT_COLOR)
        self.water_plot.getAxis('left').setTextPen(TEXT_COLOR)
        self.water_plot.getAxis('bottom').setTickSpacing(major=86400, minor=3600)
        water_layout.addWidget(self.water_plot)
        self.water_section.setLayout(water_layout)
        main_layout.addWidget(self.water_section)

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

        # Set up timer for periodic updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5000)  # 5-second interval

        # Check and clear log file if older than today
        self.clear_log_if_needed()        

        # Load initial data
        self.load_sids()
        self.update_data()
        self.update_date_range()





        if len(sys.argv) > 1 and sys.argv[1] == "use_current_dat":
            sid = self.get_current_dat_sid()
            index = self.sid_combo.findText(sid)
            if index != -1:
                self.sid_combo.setCurrentIndex(index)
            else:
                # Optional: Handle if SID not in list (e.g., add it or log a warning)
                print(f"SID {sid} not found in combo box options.")





    def get_current_dat_sid(self):
        """Get the sid from current.dat."""
        try:
            with open(DEFAULT_CURRENTDB_PATH, 'r') as f:
                for line in f:
                    if line.startswith("SID="):
                        return line.strip().split('=', 1)[1]
            return "000"
        except Exception as e:
            print(f"Error reading sid from current.dat: {str(e)}")
            return "000"

    def clear_log_if_needed(self):
        # Clear log file if it was last modified before today
        error_log_file = os.path.join(get_base_path(), "hpm2_app_error.log")
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
        start_time = time.time()
        log_files = []
        for folder in LOG_FOLDER:
            if os.path.exists(folder):
                if folder == os.path.join(get_base_path(), "logs"):
                    # Recursive search for the logs folder
                    folder_files = glob.glob(os.path.join(folder, "**", "*_*_HPM2_Test_data.log"), recursive=True)
                else:
                    # Non-recursive search for the absolute path
                    folder_files = glob.glob(os.path.join(folder, "*_*_HPM2_Test_data.log"))
                log_files.extend(folder_files)
        sids = set()
        for log_file in log_files:
            match = re.match(r"(.+?)_\d{8}_[A-Za-z]+_HPM2_Test_data\.log", os.path.basename(log_file))
            if match:
                sids.add(match.group(1))
        self.sid_list = sorted(sids)
        self.sid_combo.clear()
        self.sid_combo.addItems(self.sid_list)
        if self.sid_list:
            self.selected_sid = self.sid_list[0]
            self.sid_combo.setCurrentText(self.selected_sid)
            self.cached_df = None
            self.update_data()
            self.update_plots()
        end_time = time.time()
####        self.log_error(f"load_sids took {end_time - start_time:.2f} seconds")

    def on_sid_changed(self, sid):
        # Handle SID selection change, reset cache and update data
        if sid:
            self.selected_sid = sid
            self.cached_df = None
            self.last_valid_end_date = None  # Reset to avoid using old SID's date
            self.set_end_to_today()
            self.update_plots()
            self.reset_zoom()  # Reset zoom when SID changes
            

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_fullscreen:
            window_size = self.centralWidget().size()
            gauge_width = max(400, min(int(window_size.width() * 0.95), window_size.width() - 40))
            gauge_height = max(200, min(int((window_size.height() - 240) * 0.8), window_size.height() - 240))
            self.fullscreen_gauge.setMinimumSize(gauge_width, gauge_height)



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

    def log_error(self, message):
        try:
            with open(os.path.join(get_base_path(), "hpm2_app_error.log"), 'a') as f:
                timestamp = datetime.now().strftime('%Y%m%d %H:%M:%S')
                f.write(f"{timestamp} - {message}\n")
                print(f"Log_Error = {message}")
        except Exception as e:
            pass

    def open_settings(self):
        dialog = SettingsDialog(self.offset, self)
        if dialog.exec_():
            self.offset = dialog.get_offset()

#### GRAPH DATA SECTION ----------------------------------------------------------------------------------------------------------------

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
                timestamps = df['DATE TIME'].apply(lambda x: x.timestamp()).values
                if len(timestamps) > 0:
                    # Find closest point in pixel space
                    min_distance = float('inf')
                    new_idx = None
                    closest_series = None
                    mouse_pixel = pos
                    for key, line in self.pressure_lines.items():
                        if line.isVisible() and self.pressure_checks[key].isChecked():
                            y_data = df[key].values
                            valid_mask = ~np.isnan(y_data)
                            valid_timestamps = timestamps[valid_mask]
                            valid_y = y_data[valid_mask]
                            valid_indices = df.index[valid_mask]
                            if len(valid_timestamps) > 0:
                                # Convert data points to pixel coordinates
                                for i, (t, y_val) in enumerate(zip(valid_timestamps, valid_y)):
                                    point_scene = vb.mapViewToScene(QPointF(t, y_val))
                                    point_pixel = vb.mapSceneToView(point_scene)
                                    pixel_x = point_scene.x()
                                    pixel_y = point_scene.y()
                                    distance = np.sqrt((pixel_x - mouse_pixel.x())**2 + (pixel_y - mouse_pixel.y())**2)
                                    if distance < min_distance:
                                        min_distance = distance
                                        new_idx = valid_indices[i]
                                        closest_series = key
                    
                    self.current_point_idx = new_idx
                    self.selected_series = closest_series
                    if new_idx is not None and new_idx < len(df):
                        for key, line in self.pressure_lines.items():
                            x_data, y_data = line.getData()
                            if x_data is not None:
                                line.setData(x=x_data, y=y_data, symbolSize=2.5)
                        
                        tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}"]
                        for key, line in self.pressure_lines.items():
                            if line.isVisible() and self.pressure_checks[key].isChecked():
                                value = df[key].iloc[new_idx]
                                if pd.isna(value):
                                    continue
                                unit = 'psi'
                                tooltip.append(f"{line.name()+':':<21} {value:>6.2f} {unit}")
                                x_data, y_data = line.getData()
                                if x_data is not None and new_idx < len(df):
                                    sizes = [2.5] * len(x_data)
                                    local_idx = np.where((df[key].notna()) & (df.index <= new_idx))[0][-1]
                                    if local_idx < len(x_data):
                                        sizes[local_idx] = 10 # Size of highlighted mouse move point.
                                        line.setData(x=x_data, y=y_data, symbolSize=sizes)
                        
                        tooltip_text = "\n".join(tooltip)
                        self.pressure_tooltip.show_at(tooltip_pos, tooltip_text)
                    else:
                        self.pressure_tooltip.hide()
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
            
            if self.cached_df is not None and not self.cached_df.empty:
                df = self.cached_df[(self.cached_df['DATE TIME'] >= self.start_date) & (self.cached_df['DATE TIME'] <= self.end_date)]
                if df.empty:
                    self.water_tooltip.hide()
                    return
                timestamps = df['DATE TIME'].apply(lambda x: x.timestamp()).values
                if len(timestamps) > 0:
                    # Find closest point in pixel space
                    min_distance = float('inf')
                    new_idx = None
                    closest_series = None
                    mouse_pixel = pos
                    for key, line in self.water_lines.items():
                        if line.isVisible() and self.water_checks[key].isChecked():
                            y_data = df[key].values
                            valid_mask = ~np.isnan(y_data)
                            valid_timestamps = timestamps[valid_mask]
                            valid_y = y_data[valid_mask]
                            valid_indices = df.index[valid_mask]
                            if len(valid_timestamps) > 0:
                                # Convert data points to pixel coordinates
                                for i, (t, y_val) in enumerate(zip(valid_timestamps, valid_y)):
                                    point_scene = vb.mapViewToScene(QPointF(t, y_val))
                                    point_pixel = vb.mapSceneToView(point_scene)
                                    pixel_x = point_scene.x()
                                    pixel_y = point_scene.y()
                                    distance = np.sqrt((pixel_x - mouse_pixel.x())**2 + (pixel_y - mouse_pixel.y())**2)
                                    if distance < min_distance:
                                        min_distance = distance
                                        new_idx = valid_indices[i]
                                        closest_series = key
                    
                    self.current_point_idx = new_idx
                    self.selected_series = closest_series
                    if new_idx is not None and new_idx < len(df):
                        for key, line in self.water_lines.items():
                            x_data, y_data = line.getData()
                            if x_data is not None:
                                line.setData(x=x_data, y=y_data, symbolSize=2.5)
                        
                        tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[new_idx].strftime('%Y-%m-%d %H:%M:%S')}"]
                        for key, line in self.water_lines.items():
                            if line.isVisible() and self.water_checks[key].isChecked():
                                value = df[key].iloc[new_idx]
                                if pd.isna(value):
                                    continue
                                unit = '°F'
                                tooltip.append(f"{line.name()+':':<21} {value:>6.2f} {unit}")
                                x_data, y_data = line.getData()
                                if x_data is not None and new_idx < len(df):
                                    sizes = [2.5] * len(x_data)
                                    local_idx = np.where((df[key].notna()) & (df.index <= new_idx))[0][-1]
                                    if local_idx < len(x_data):
                                        sizes[local_idx] = 10 # Size of highlighted mouse move point.
                                        line.setData(x=x_data, y=y_data, symbolSize=sizes)
                        
                        tooltip_text = "\n".join(tooltip)
                        self.water_tooltip.show_at(tooltip_pos, tooltip_text)
                    else:
                        self.water_tooltip.hide()
                else:
                    self.water_tooltip.hide()
            else:
                self.water_tooltip.hide()
        except Exception as e:
            self.log_error(f"Error in water tooltip: {e}")
            self.water_tooltip.hide()



    def pressure_leave_event(self, event):
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



    def keyPressEvent(self, event):
        if self.active_plot and self.cached_df is not None and not self.cached_df.empty:
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
            lines = self.pressure_lines if self.active_plot == 'pressure' else self.water_lines
            checks = self.pressure_checks if self.active_plot == 'pressure' else self.water_checks
            data_y_range = [min(df[key].min() for key in lines if checks[key].isChecked() and not df[key].isna().all()),
                            max(df[key].max() for key in lines if checks[key].isChecked() and not df[key].isna().all())]
            
            # Only handle Left/Right arrow keys for navigation
            if event.key() in (Qt.Key_Left, Qt.Key_Right):
                self.is_keyboard_nav = True
                
                # Initialize index based on mouse position if None
                if self.current_point_idx is None or self.current_point_idx >= len(timestamps):
                    vb = self.pressure_plot.getViewBox() if self.active_plot == 'pressure' else self.water_plot.getViewBox()
                    cursor_pos = QCursor.pos()
                    cursor_widget = (self.pressure_plot if self.active_plot == 'pressure' else self.water_plot).mapFromGlobal(cursor_pos)
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
                    vb = self.pressure_plot.getViewBox() if self.active_plot == 'pressure' else self.water_plot.getViewBox()
                    cursor_pos = QCursor.pos()
                    cursor_widget = (self.pressure_plot if self.active_plot == 'pressure' else self.water_plot).mapFromGlobal(cursor_pos)
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
                if self.active_plot == 'pressure':
                    self.water_tooltip.hide()
                    for key, line in self.water_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)
                    for key, line in self.pressure_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)
                    self.update_pressure_tooltip(self.current_point_idx, df, self.selected_series)
                    
                    # Track point in x and y directions if zoomed
                    vb = self.pressure_plot.getViewBox()
                    current_x_range = vb.viewRange()[0]  # [x_min, x_max]
                    current_y_range = vb.viewRange()[1]  # [y_min, y_max]
                    current_point_x = timestamps[self.current_point_idx]
                    
                    # Get y-value from selected series
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
                        
                        if relative_pos_y < 0.1:
                            shift = (0.1 - relative_pos_y) * view_height
                            new_y_min = max(data_y_range[0], current_y_range[0] - shift)
                            new_y_max = new_y_min + view_height
                            vb.setYRange(new_y_min, new_y_max, padding=0)
                        elif relative_pos_y > 0.9:
                            shift = (relative_pos_y - 0.9) * view_height
                            new_y_max = min(data_y_range[1], current_y_range[1] + shift)
                            new_y_min = new_y_max - view_height
                            vb.setYRange(new_y_min, new_y_max, padding=0)
                    
                elif self.active_plot == 'water':
                    self.pressure_tooltip.hide()
                    for key, line in self.pressure_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)
                    for key, line in self.water_lines.items():
                        x_data, y_data = line.getData()
                        if x_data is not None:
                            line.setData(x=x_data, y=y_data, symbolSize=2.5)
                    self.update_water_tooltip(self.current_point_idx, df, self.selected_series)
                    
                    # Track point in x and y directions if zoomed
                    vb = self.water_plot.getViewBox()
                    current_x_range = vb.viewRange()[0]
                    current_y_range = vb.viewRange()[1]
                    current_point_x = timestamps[self.current_point_idx]
                    
                    # Get y-value from selected series
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
                        
                        if relative_pos_y < 0.1:
                            shift = (0.1 - relative_pos_y) * view_height
                            new_y_min = max(data_y_range[0], current_y_range[0] - shift)
                            new_y_max = new_y_min + view_height
                            vb.setYRange(new_y_min, new_y_max, padding=0)
                        elif relative_pos_y > 0.9:
                            shift = (relative_pos_y - 0.9) * view_height
                            new_y_max = min(data_y_range[1], current_y_range[1] + shift)
                            new_y_min = new_y_max - view_height
                            vb.setYRange(new_y_min, new_y_max, padding=0)
                
                # Force plot refresh to ensure immediate highlight update
                if self.active_plot == 'pressure':
                    self.pressure_plot.repaint()
                elif self.active_plot == 'water':
                    self.water_plot.repaint()
                
                event.accept()
            else:
                # Pass non-navigation keys to parent without resetting
                super().keyPressEvent(event)
        else:
            self.current_point_idx = None
            self.selected_series = None
            self.is_keyboard_nav = False
            self.pressure_tooltip.hide()
            self.water_tooltip.hide()
            QApplication.restoreOverrideCursor()
            super().keyPressEvent(event)



    def update_pressure_tooltip(self, idx, df, selected_series=None):
        if idx is None or idx >= len(df):
            self.pressure_tooltip.hide()
            return
        
        # Build tooltip text for all checked series, highlight selected series if keyboard nav
        tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[idx].strftime('%Y-%m-%d %H:%M:%S')}"]
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
                    tooltip.append(f"{line.name()+':':<21} {value:>6.2f} {unit}")
                    if x_data is not None and idx < len(x_data):
                        if not self.is_keyboard_nav or key == selected_series:
                            sizes = [2.5] * len(x_data)
                            sizes[idx] = 10
                            line.setData(x=x_data, y=y_data, symbolSize=sizes)
        
        if not tooltip[1:]:  # No series added to tooltip
            self.pressure_tooltip.hide()
            return
        
        tooltip_text = "\n".join(tooltip)
        
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
            tooltip_x = self.pressure_plot.mapToGlobal(QPoint(0, 0)).x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)  # Left edge
        elif relative_pos_x > 0.9:
            tooltip_x = self.pressure_plot.mapToGlobal(QPoint(plot_rect.width(), 0)).x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)  # Right edge
        
        tooltip_pos = QPoint(tooltip_x, tooltip_y)
        self.pressure_tooltip.show_at(tooltip_pos, tooltip_text)

    def update_water_tooltip(self, idx, df, selected_series=None):
        if idx is None or idx >= len(df):
            self.water_tooltip.hide()
            return
        
        # Build tooltip text for all checked series, highlight selected series if keyboard nav
        tooltip = [f"{'Time:'} {df['DATE TIME'].iloc[idx].strftime('%Y-%m-%d %H:%M:%S')}"]
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
                    tooltip.append(f"{line.name()+':':<21} {value:>6.2f} {unit}")
                    if x_data is not None and idx < len(x_data):
                        if not self.is_keyboard_nav or key == selected_series:
                            sizes = [2.5] * len(x_data)
                            sizes[idx] = 10
                            line.setData(x=x_data, y=y_data, symbolSize=sizes)
        
        if not tooltip[1:]:  # No series added to tooltip
            self.water_tooltip.hide()
            return
        
        tooltip_text = "\n".join(tooltip)
        
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
            tooltip_x = self.water_plot.mapToGlobal(QPoint(0, 0)).x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)  # Left edge
        elif relative_pos_x > 0.9:
            tooltip_x = self.water_plot.mapToGlobal(QPoint(plot_rect.width(), 0)).x() + (200 if global_pos.x() <= self.geometry().center().x() else -400)  # Right edge
        
        tooltip_pos = QPoint(tooltip_x, tooltip_y)
        self.water_tooltip.show_at(tooltip_pos, tooltip_text)





#### DATE FILTERING SECTION --------------------------------------------------------------------------------------------------------------------

    def set_end_to_today(self):
        local_tz = get_localzone()  # Get local timezone
        self.end_date = datetime.now(local_tz).replace(tzinfo=local_tz)
        self.cached_df = None
        self.update_data()
        self.update_date_range()

    def get_earliest_data_date(self):
        # Find the earliest date with data for the selected SID
        if not self.selected_sid:
            return None
        log_files = []
        for folder in LOG_FOLDER:
            if os.path.exists(folder):
                if folder == os.path.join(get_base_path(), "logs"):
                    # Recursive search for the logs folder
                    folder_files = glob.glob(os.path.join(folder, "**", f"{self.selected_sid}_*_HPM2_Test_data.log"), recursive=True)
                else:
                    # Non-recursive search for the absolute path
                    folder_files = glob.glob(os.path.join(folder, f"{self.selected_sid}_*_HPM2_Test_data.log"))
                log_files.extend(folder_files)
        earliest_date = None
        for log_file in log_files:
            match = re.search(r'_(\d{8})_[A-Za-z]+_HPM2_Test_data\.log', log_file)
            if match:
                try:
                    file_date = datetime.strptime(match.group(1), '%Y%m%d')
                    if earliest_date is None or file_date < earliest_date:
                        earliest_date = file_date
                except ValueError:
                    continue
        return earliest_date

    def show_skip_popup(self, message):
        # Display a temporary popup message without sound
        popup = QLabel(message, self)
        popup.setStyleSheet(f"background-color: {FRAME_BG.name()}; color: {TEXT_COLOR.name()}; border: 1px solid {TEXT_COLOR.name()}; padding: 5px;")
        popup.setFont(QFont("Arial", 10))
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.adjustSize()
        popup.move(self.rect().center() - popup.rect().center())
        popup.show()
        QTimer.singleShot(2000, popup.hide) # Set time message will be displayed. 

    def on_range_changed(self):
#        print("Ran on_range_change")
        # Handle range combo box changes
        range_text = self.range_combo.currentText()
        local_tz = get_localzone()  # Get local timezone
        if range_text == "Custom":
            return
        
        end_date = datetime.now(local_tz).replace(tzinfo=local_tz)
        if range_text == "1 Day":
            self.start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            self.end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text == "3 Days":
            self.start_date = end_date - timedelta(days=2)
            self.end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text == "1 Week":
            self.start_date = end_date - timedelta(days=6)
            self.end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text == "1 Month":
            self.start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = (self.start_date + relativedelta(months=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text == "1 Year":
            self.start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = (self.start_date + relativedelta(years=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text == "5 Years":
            self.start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(years=4)
            self.end_date = (self.start_date + relativedelta(years=5) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Ensure start_date and end_date are timezone-aware
        if self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        
        # Reset y-defaults and update key to force recalculation
        self.pressure_y_default = [-1, 1]
        self.water_y_default = [-1, 1]
        self.last_update_key = None
        self.cached_df = None
        self.update_data()
        self.update_date_range()

    def on_date_changed(self):
        local_tz = get_localzone()  # Get local timezone
        self.start_date = self.start_date_edit.date().toPyDate()
        self.end_date = self.end_date_edit.date().toPyDate()
        # Ensure start_date and end_date are timezone-aware
        self.start_date = datetime.combine(self.start_date, datetime.min.time(), tzinfo=local_tz)
        self.end_date = datetime.combine(self.end_date, datetime.max.time(), tzinfo=local_tz)
        self.range_combo.blockSignals(True)
        self.range_combo.setCurrentText("Custom")
        self.range_combo.blockSignals(False)
        self.cached_df = None
        self.update_data()
        self.update_plots()
        
    def shift_range_left(self):
        # Shift the date range left, skipping all empty ranges until data is found
        if self.range_combo.currentText() == "Custom":
            return
        local_tz = get_localzone()  # Get local timezone
        self.end_date = self.end_date or datetime.now(local_tz).replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        earliest_date = self.get_earliest_data_date()
        
        range_text = self.range_combo.currentText()
        if range_text == "1 Day":
            delta = timedelta(days=1)
        elif range_text == "3 Days":
            delta = timedelta(days=3)
        elif range_text == "1 Week":
            delta = timedelta(days=7)
        elif range_text == "1 Month":
            delta = relativedelta(months=1)
        elif range_text == "1 Year":
            delta = relativedelta(years=1)
        elif range_text == "5 Years":
            delta = relativedelta(years=5)
        else:
            delta = timedelta(days=7)
        
        new_end_date = self.end_date - delta
        if new_end_date.tzinfo is None:
            new_end_date = new_end_date.replace(tzinfo=local_tz)
        elif range_text == "1 Day":
            new_start_date = new_end_date
        elif range_text == "3 Days":
            new_start_date = new_end_date - timedelta(days=2)
        elif range_text == "1 Week":
            new_start_date = new_end_date - timedelta(days=6)
        elif range_text == "1 Month":
            new_start_date = new_end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_end_date = (new_start_date + relativedelta(months=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text in ["1 Year", "5 Years"]:
            new_start_date = new_end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            new_end_date = (new_start_date + relativedelta(years=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        
        new_start_date = new_start_date.replace(tzinfo=local_tz)
        new_end_date = new_end_date.replace(tzinfo=local_tz)
        
        if earliest_date and new_end_date.date() < earliest_date.date():
            self.show_skip_popup("No earlier data available")
            return
        
        # Skip empty ranges until data is found
        first_skipped_date = None
        last_skipped_date = None
        while new_end_date.date() >= (earliest_date.date() if earliest_date else datetime.min.date()):
            log_files = self.get_log_files_in_range(new_start_date, new_end_date)
            if log_files:
                self.last_valid_end_date = self.end_date
                self.end_date = new_end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                self.start_date = new_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                break
            if first_skipped_date is None:
                first_skipped_date = new_end_date
            last_skipped_date = new_end_date
            new_end_date -= delta
            if range_text == "1 Day":
                new_start_date = new_end_date
            elif range_text == "3 Days":
                new_start_date = new_end_date - timedelta(days=2)
            elif range_text == "1 Week":
                new_start_date = new_end_date - timedelta(days=6)
            elif range_text == "1 Month":
                new_start_date = new_end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                new_end_date = (new_start_date + relativedelta(months=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            elif range_text in ["1 Year", "5 Years"]:
                new_start_date = new_end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                new_end_date = (new_start_date + relativedelta(years=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            new_start_date = new_start_date.replace(tzinfo=local_tz)
            new_end_date = new_end_date.replace(tzinfo=local_tz)
        
        if new_end_date.date() < (earliest_date.date() if earliest_date else datetime.min.date()):
            self.show_skip_popup("No earlier data available")
            return
        
        if first_skipped_date and last_skipped_date:
            skip_start = last_skipped_date.replace(hour=0, minute=0, second=0, microsecond=0)
            skip_end = first_skipped_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            self.show_skip_popup(f"Skipped empty range: {skip_start.strftime('%Y-%m-%d')} to {skip_end.strftime('%Y-%m-%d')}")
        
        self.cached_df = None
        self.update_data()
        self.update_date_range()

    def shift_range_right(self):
        # Shift the date range right, skipping all empty ranges until data is found
        if self.range_combo.currentText() == "Custom":
            return
        local_tz = get_localzone()  # Get local timezone
        self.end_date = self.end_date or datetime.now(local_tz).replace(tzinfo=local_tz)
        if self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        latest_date = datetime.now(local_tz).replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=local_tz)
        
        range_text = self.range_combo.currentText()
        if range_text == "1 Day":
            delta = timedelta(days=1)
        elif range_text == "3 Days":
            delta = timedelta(days=3)
        elif range_text == "1 Week":
            delta = timedelta(days=7)
        elif range_text == "1 Month":
            delta = relativedelta(months=1)
        elif range_text == "1 Year":
            delta = relativedelta(years=1)
        elif range_text == "5 Years":
            delta = relativedelta(years=5)
        else:
            delta = timedelta(days=3)
        
        new_end_date = self.end_date + delta
        if new_end_date.tzinfo is None:
            new_end_date = new_end_date.replace(tzinfo=local_tz)
        if range_text == "1 Day":
            new_start_date = new_end_date
        elif range_text == "3 Days":
            new_start_date = new_end_date - timedelta(days=2)
        elif range_text == "1 Week":
            new_start_date = new_end_date - timedelta(days=6)
        elif range_text == "1 Month":
            new_start_date = new_end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_end_date = (new_start_date + relativedelta(months=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif range_text in ["1 Year", "5 Years"]:
            new_start_date = new_end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            new_end_date = (new_start_date + relativedelta(years=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        
        new_start_date = new_start_date.replace(tzinfo=local_tz)
        new_end_date = new_end_date.replace(tzinfo=local_tz)
        
        if new_end_date > latest_date:
            self.end_date = latest_date
            self.start_date = latest_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if range_text == "3 Days":
                self.start_date = latest_date - timedelta(days=2)     
            elif range_text == "1 Week":
                self.start_date = latest_date - timedelta(days=6)               
            elif range_text == "1 Month":
                self.start_date = latest_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif range_text in ["1 Year", "5 Years"]:
                self.start_date = latest_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.start_date = self.start_date.replace(tzinfo=local_tz)
            self.end_date = self.end_date.replace(tzinfo=local_tz)
            self.show_skip_popup("Cannot go past current date")
            self.cached_df = None
            self.update_data()
            self.update_date_range()
            return
        
        # Skip empty ranges until data is found
        first_skipped_date = None
        last_skipped_date = None
        while new_end_date <= latest_date:
            log_files = self.get_log_files_in_range(new_start_date, new_end_date)
            if log_files:
                self.last_valid_end_date = self.end_date
                self.end_date = new_end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                self.start_date = new_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                break
            if first_skipped_date is None:
                first_skipped_date = new_start_date
            last_skipped_date = new_end_date
            new_end_date += delta
            if range_text == "1 Day":
                new_start_date = new_end_date
            elif range_text == "3 Days":
                new_start_date = new_end_date - timedelta(days=2)
            elif range_text == "1 Week":
                new_start_date = new_end_date - timedelta(days=6)
            elif range_text == "1 Month":
                new_start_date = new_end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                new_end_date = (new_start_date + relativedelta(months=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            elif range_text in ["1 Year", "5 Years"]:
                new_start_date = new_end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                new_end_date = (new_start_date + relativedelta(years=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            new_start_date = new_start_date.replace(tzinfo=local_tz)
            new_end_date = new_end_date.replace(tzinfo=local_tz)
        
        if new_end_date > latest_date:
            self.end_date = latest_date
            self.start_date = latest_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if range_text == "3 Days":
                self.start_date = latest_date - timedelta(days=2)            
            elif range_text == "1 Week":
                self.start_date = latest_date - timedelta(days=6)
            elif range_text == "1 Month":
                self.start_date = latest_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif range_text in ["1 Year", "5 Years"]:
                self.start_date = latest_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.start_date = self.start_date.replace(tzinfo=local_tz)
            self.end_date = self.end_date.replace(tzinfo=local_tz)
            self.show_skip_popup("Cannot go past current date")
            self.cached_df = None
            self.update_data()
            self.update_date_range()
            return
        
        if first_skipped_date and last_skipped_date:
            skip_start = first_skipped_date.replace(hour=0, minute=0, second=0, microsecond=0)
            skip_end = last_skipped_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            self.show_skip_popup(f"Skipped empty range: {skip_start.strftime('%Y-%m-%d')} to {skip_end.strftime('%Y-%m-%d')}")
        
        self.cached_df = None
        self.update_data()
        self.update_date_range()

    def update_date_range(self):
#        print("ran update date range")
        # Sets the date range for data display based on the selected range option
        range_text = self.range_combo.currentText()
        local_tz = get_localzone()  # Get local timezone
        if range_text == "Custom":
            self.left_arrow.setEnabled(False)
            self.right_arrow.setEnabled(False)
            self.start_date_edit.setEnabled(True)
            self.end_date_edit.setEnabled(True)
#            print(f"update_date_range: Custom range, control bar: {self.start_date_edit.date().toPyDate()} - {self.end_date_edit.date().toPyDate()}")
            return
        
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
            self.start_date = self.end_date - timedelta(days=2)
        
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
        
#        print(f"update_date_range: Set range to {self.start_date} - {self.end_date}, control bar: {self.start_date_edit.date().toPyDate()} - {self.end_date_edit.date().toPyDate()}")
        self.cached_df = None
        self.update_data()
        self.update_plots()
        self.reset_zoom()





#### DATA COLLECTION SECTION ------------------------------------------------------------------------------------------------------------------------

    def get_log_files_in_range(self, start_date, end_date):
#        print("Ran get_log_file_in_range")
        start_time = time.time()
        log_files = []
        for folder in LOG_FOLDER:
            if os.path.exists(folder):
                if folder == os.path.join(get_base_path(), "logs"):
                    # Recursive search for the logs folder
                    folder_files = glob.glob(os.path.join(folder, "**", f"{self.selected_sid}_*_HPM2_Test_data.log"), recursive=True)
                else:
                    # Non-recursive search for the absolute path
                    folder_files = glob.glob(os.path.join(folder, f"{self.selected_sid}_*_HPM2_Test_data.log"))
                log_files.extend(folder_files)
        selected_files = []
        local_tz = get_localzone()  # Get local timezone
        # Ensure start_date and end_date are timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=local_tz)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=local_tz)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        for log_file in log_files:
            match = re.search(r'_(\d{8})_[A-Za-z]+_HPM2_Test_data\.log', log_file)
            if match:
                file_date_str = match.group(1)
                try:
                    file_date = datetime.strptime(file_date_str, '%Y%m%d').replace(tzinfo=local_tz)
                    if start_date <= file_date <= end_date:
                        selected_files.append(log_file)
                except ValueError:
                    continue
        end_time = time.time()
####        print(f"get_log_files_in_range took {end_time - start_time:.2f} seconds")
        return sorted(selected_files)

    def process_log_file(self, log_files):
#        print("Ran process_log_file")
        start_time = time.time()
        if not log_files:
            return None
        dfs = []
        local_tz = get_localzone()  # Get local timezone using tzlocal
        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    header = f.readline().strip()
                
                if 'DATE TIME' in header and ',' in header:
                    df = pd.read_csv(log_file, parse_dates=['DATE TIME'])
                    # Ensure DATE TIME is in local timezone
                    if df['DATE TIME'].dt.tz is None:
                        df['DATE TIME'] = df['DATE TIME'].dt.tz_localize(local_tz)
                    else:
                        df['DATE TIME'] = df['DATE TIME'].dt.tz_convert(local_tz)
                    dfs.append(df)
                else:
                    try:
                        df = pd.read_csv(log_file, names=['DATETIME', 'wika_psi', 'atm_psi', 'water_in_f', 'water_out_f',
                                                         'He_last_read', 'scan_pulses', 'water_diff', 'mag_psi'], skiprows=1)
                        df['DATETIME'] = df['DATETIME'].astype(str).str.strip()
                        df['DATE TIME'] = pd.to_datetime(df['DATETIME'], format='%Y%m%d %H:%M:%S', errors='coerce').dt.tz_localize(local_tz)
                        if df['DATE TIME'].isna().any():
                            invalid_rows = df[df['DATE TIME'].isna()]['DATETIME'].to_dict()
                            self.log_error(f"Invalid DATETIME rows in {log_file}: {invalid_rows}")
                            continue
                        for col in ['wika_psi', 'atm_psi', 'water_in_f', 'water_out_f', 'water_diff', 'mag_psi']:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        df['avg_mag_psi'] = df['mag_psi'].rolling(window=10, min_periods=1).mean()
                        df = df.drop(columns=['DATETIME', 'He_last_read'], errors='ignore')
                        dfs.append(df)
                    except Exception as e:
                        self.log_error(f"Legacy log parsing failed for {log_file}: {str(e)}")
                        continue
            except Exception as e:
                self.log_error(f"Error processing log file {log_file}: {e}")
                continue
        if not dfs:
            return None
        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values('DATE TIME').drop_duplicates(subset='DATE TIME', keep='last')
        end_time = time.time()
####        print(f"process_log_file took {end_time - start_time:.2f} seconds")
        return df

    def update_data(self):
#        print("Run Update_Data")
        # Updates gauge, displays, and plots with data from the selected SID
        if not self.selected_sid:
            return
        
        # Store current x and y ranges to prevent timer from resetting zoom
        pressure_x_range = self.pressure_plot.getViewBox().viewRange()[0]
        pressure_y_range = self.pressure_plot.getViewBox().viewRange()[1]
        water_x_range = self.water_plot.getViewBox().viewRange()[0]
        water_y_range = self.water_plot.getViewBox().viewRange()[1]
        current_start_date = self.start_date
        current_end_date = self.end_date
        current_sid = self.selected_sid
        local_tz = get_localzone()  # Get local timezone
        
        # Check for new SIDs
        log_files = []
        for folder in LOG_FOLDER:
            if os.path.exists(folder):
                if folder == os.path.join(get_base_path(), "logs"):
                    # Recursive search for the logs folder
                    folder_files = glob.glob(os.path.join(folder, "**", "*_*_HPM2_Test_data.log"), recursive=True)
                else:
                    # Non-recursive search for the absolute path
                    folder_files = glob.glob(os.path.join(folder, "*_*_HPM2_Test_data.log"))
                log_files.extend(folder_files)
        sids = set()
        for log_file in log_files:
            match = re.match(r"(.+?)_\d{8}_[A-Za-z]+_HPM2_Test_data\.log", os.path.basename(log_file))
            if match:
                sids.add(match.group(1))
        new_sids = sorted(sids)
        if new_sids != self.sid_list:
            self.sid_list = new_sids
            self.sid_combo.blockSignals(True)
            self.sid_combo.clear()
            self.sid_combo.addItems(self.sid_list)
            if current_sid in self.sid_list:
                self.sid_combo.setCurrentText(current_sid)
            else:
                self.selected_sid = self.sid_list[0] if self.sid_list else None
                self.sid_combo.setCurrentText(self.selected_sid if self.selected_sid else "")
                self.cached_df = None
                self.pressure_y_default = [-1, 1]  # Reset y-defaults on SID change
                self.water_y_default = [-1, 1]
                self.last_update_key = None
            self.sid_combo.blockSignals(False)
        
        # Ensure start_date and end_date are timezone-aware
        if self.start_date and self.start_date.tzinfo is None:
            self.start_date = self.start_date.replace(tzinfo=local_tz)
        if self.end_date and self.end_date.tzinfo is None:
            self.end_date = self.end_date.replace(tzinfo=local_tz)
        
        # Fetch all log files for the selected SID to find the most recent sample
        all_log_files = []
        for folder in LOG_FOLDER:
            if os.path.exists(folder):
                if folder == os.path.join(get_base_path(), "logs"):
                    # Recursive search for the logs folder
                    folder_files = glob.glob(os.path.join(folder, "**", f"{self.selected_sid}_*_HPM2_Test_data.log"), recursive=True)
                else:
                    # Non-recursive search for the absolute path
                    folder_files = glob.glob(os.path.join(folder, f"{self.selected_sid}_*_HPM2_Test_data.log"))
                all_log_files.extend(folder_files)
        log_files = self.get_log_files_in_range(
            self.start_date or (datetime.now(local_tz) - timedelta(days=6)).replace(tzinfo=local_tz), 
            self.end_date or datetime.now(local_tz).replace(tzinfo=local_tz)
        )
        
        # Process all logs to find the most recent sample for gauge and displays
        all_df = self.process_log_file(all_log_files) if all_log_files else None
        
        # Update cached_df for plots based on date range
        if log_files:
            self.cached_df = self.process_log_file(log_files)
        else:
            self.cached_df = None
        
        # Update gauge and displays with the most recent sample
        if all_df is not None and not all_df.empty:
            try:
                latest = all_df.iloc[-1]
                latest_date = latest['DATE TIME']
                mag_psi = latest['mag_psi']
                self.gauge.setValue(mag_psi)
                self.fullscreen_gauge.setValue(mag_psi)
                self.left_display.setText(
                    f"                             LATEST\n"
                    f"{latest_date.strftime(' %Y-%m-%d    %H:%M:%S')}\n"
                    f"{'Magnet Pressure:':<21} {mag_psi:>6.2f}\n"
                    f"{'Mag. Avg. Press.:':<22} {latest['avg_mag_psi']:>6.2f}\n"
                    f"{'Wika Pressure:':<22} {latest['wika_psi']:>6.2f}\n"
                    f"{'Atmospheric Press.:':<20} {latest['atm_psi']:>6.2f}"
                )
                self.right_display.setText(
                    f"READING\n"
                    f"Errors: {self.errors}\n"
                    f"{'Water Temp Diff:':<20} {latest['water_diff']:>6.2f}\n"
                    f"{'Water Temp In:':<20} {latest['water_in_f']:>6.2f}\n"
                    f"{'Water Temp Out:':<18} {latest['water_out_f']:>6.2f}\n"
                    f"{'Scan Pulses:':<21} {latest['scan_pulses']:>6}"
                )
            except Exception as e:
                self.log_error(f"Error updating gauge/displays: {e}")
        
        # Store update key to check if SID or date range changed
        update_key = (self.selected_sid, self.start_date, self.end_date)
        self.update_plots()
        self.last_update_key = update_key
        
        # Restore x and y ranges
        self.start_date = current_start_date
        self.end_date = current_end_date
        self.pressure_plot.setRange(xRange=pressure_x_range, yRange=pressure_y_range, padding=0)
        self.water_plot.setRange(xRange=water_x_range, yRange=water_y_range, padding=0)

    def update_plots(self):
#        print("Ran update_plots")
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
        else:
            range_text = self.range_combo.currentText()
            end_date = datetime.now(local_tz).replace(tzinfo=local_tz)
            if range_text == "1 Day":
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif range_text == "3 Days":
                start_date = end_date - timedelta(days=2)
            elif range_text == "1 Week":
                start_date = end_date - timedelta(days=6)
            elif range_text == "1 Month":
                start_date = end_date - relativedelta(months=1)
            elif range_text == "1 Year":
                start_date = end_date - relativedelta(years=1)
            elif range_text == "5 Years":
                start_date = end_date - relativedelta(years=5)
            else:
                start_date = end_date - timedelta(days=6)
            start_date = start_date.replace(tzinfo=local_tz)
            end_date = end_date.replace(tzinfo=local_tz)
        
        x_range = [start_date.timestamp(), end_date.timestamp()]
        
        if not self.selected_sid:
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
            self.pressure_y_default = [-1, 1]
            self.water_y_default = [-1, 1]
            return
        
        log_files = self.get_log_files_in_range(start_date, end_date)
        if not log_files:
            self.cached_df = None
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
            self.pressure_y_default = [-1, 1]
            self.water_y_default = [-1, 1]
            return
        
        try:
            if self.cached_df is None:
                self.cached_df = self.process_log_file(log_files)
            
            if self.cached_df is None or self.cached_df.empty:
                self.pressure_plot.enableAutoRange()
                self.water_plot.enableAutoRange()
                self.pressure_y_default = [-1, 1]
                self.water_y_default = [-1, 1]
                return
            
            df = self.cached_df[(self.cached_df['DATE TIME'] >= start_date) & (self.cached_df['DATE TIME'] <= end_date)]
            timestamps = df['DATE TIME'].apply(lambda x: x.timestamp()).values
            
            if df.empty:
                self.pressure_plot.enableAutoRange()
                self.water_plot.enableAutoRange()
                self.pressure_y_default = [-1, 1]
                self.water_y_default = [-1, 1]
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
            
            # Update last key for SID and date changes
            update_key = (self.selected_sid, self.start_date, self.end_date)
            self.last_update_key = update_key
            
            # Track checkbox changes to re-scale specific plot
            pressure_check_changed = False
            water_check_changed = False
            for key, line in self.pressure_lines.items():
                new_visible = self.pressure_checks[key].isChecked()
                if line.isVisible() != new_visible:  # Check for any state change
                    pressure_check_changed = True
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
                    water_check_changed = True
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
            
####            print(f"pressure check = {pressure_check_changed}, water check = {water_check_changed}")            
            if pressure_check_changed:
                self.pressure_plot.setRange(yRange=self.pressure_y_default, padding=0)
            if water_check_changed:
                self.water_plot.setRange(yRange=self.water_y_default, padding=0)               

        except Exception as e:
            self.log_error(f"Error updating plots: {e}")
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
            self.pressure_y_default = [-1, 1]
            self.water_y_default = [-1, 1]


    def reset_zoom(self):
        if not self.selected_sid:
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()
            return
        
        try:
            x_range = [self.start_date.timestamp(), self.end_date.timestamp()]
            self.pressure_plot.setRange(xRange=x_range, yRange=self.pressure_y_default, padding=0)
            self.water_plot.setRange(xRange=x_range, yRange=self.water_y_default, padding=0)
            self.pressure_plot.getViewBox().setLimits(xMin=x_range[0], xMax=x_range[1])
            self.water_plot.getViewBox().setLimits(xMin=x_range[0], xMax=x_range[1])
        except Exception as e:
            self.log_error(f"Error resetting zoom: {e}")
            self.pressure_plot.enableAutoRange()
            self.water_plot.enableAutoRange()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())