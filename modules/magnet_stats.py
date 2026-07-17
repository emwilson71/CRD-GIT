"""
Version 1.00 Updated 03/10/25    
"""
# ---------------------------------------------------------------------------
# magnet_stats.py X
# Graph Magnet Helium, Shields, Magnet Pressure, and Power
# ewilson@us.medical.canon
# ---------------------------------------------------------------------------
import sys
import os
import paramiko
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QComboBox, QPushButton
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QScreen
from datetime import datetime
import re
import logging
import socket
import tempfile
import shutil
import csv
from mod_stylesheets import DIALOG_STYLE, STD_LABEL_STYLE, BUTTON_STYLE, COMBOBOX_STYLE
from mod_logging import CRDLogger
# ---------------------------------------------------------------------------
class DataFetchThread(QThread):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    config_signal = pyqtSignal(str, str)
    def __init__(self, config_path="../config/current.dat", days=10):
        super().__init__()
        self.logger = CRDLogger("CRD").get_logger()  
        self.logger.setLevel(logging.DEBUG)  
        self.config_path = config_path
        self.days = days
# ---------------------------------------------------------------------------
    def read_config(self):
        config = {}
        try:
            with open(self.config_path, "r") as file:
                for line in file:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        config[key] = value
            return config.get("SP_IP"), config.get("SID"), config.get("SiteName")
        except FileNotFoundError:
            self.logger.error(f"[MOD MAGSTATS] Configuration file not found")
            return None, None, None
        except Exception as e:
            self.logger.error(f"[MOD MAGSTATS] Failed to Read Config File: {e}")
            return None, None, None
# ---------------------------------------------------------------------------
    def run(self):
        self.logger.info("[MOD MAGSTATS] Reading Config")
        sp_ip, sid, site_name = self.read_config()
        if not sp_ip or not sid:
            self.logger.error("[MOD MAGSTATS] Invalid configuration: SP_IP or SID missing")
            return
        self.config_signal.emit(site_name, sid)
        username = "IV_Service_User"
        password = "SU_InnerVision2020"
        target_dir = f"C:\\InnerVision.dir\\M-Power\\{sid}-000\\_tui.dir"
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.status_signal.emit("Connecting to SSH", "blue")
        self.logger.info("[MOD MAGSTATS] Connecting to SSH")
        try:
            ssh.connect(sp_ip, username=username, password=password, timeout=10)
            sftp = ssh.open_sftp()
            self.status_signal.emit("Listing Files", "blue")
            try:
                files = sftp.listdir(target_dir)
            except Exception as e:
                sftp.close()
                ssh.close()
                self.logger.error(f"[MOD MAGSTATS] Failed to Access Directory {target_dir}: {e}")
                return
            acq_files = [f for f in files if f.endswith(".AcqSts")]
            acq_files = sorted(acq_files, reverse=True)[:self.days]
           
# TEMP FIELDS
            temp_dir = tempfile.mkdtemp()
            data = {
                "timestamps": [],
                "helium_levels": [],
                "shield_temps": [],
                "magnet_pressures": [],
                "magnet_pressure_units": [],
                "refrigerator_temps": [],
                "heater_powers": []
            }
# TEMP DOWNLOAD
            local_paths = []
            try:
                for i, file_name in enumerate(acq_files, 1):
                    remote_path = f"{target_dir}\\{file_name}"
                    local_path = os.path.join(temp_dir, file_name)
                    self.status_signal.emit(f"Downloading file {i} of {len(acq_files)}", "blue")
                    sftp.get(remote_path, local_path)
                    local_paths.append(local_path)
               
# PROCESS DOWNLOADS
                for i, local_path in enumerate(local_paths, 1):
                    try:
                        with open(local_path, "r", encoding="ascii", errors="replace") as file:
                            lines = [line.strip('\r\n\x00') for line in file.readlines()]
                            timestamp = None
                            helium_level = None
                            shield_temp = None
                            magnet_pressure = None
                            magnet_pressure_unit = None
                            refrigerator_temp = None
                            heater_power = None
                            helium_found = False
                            line_count_since_helium = 0
                            for line in lines:
                                if helium_found:
                                    line_count_since_helium += 1
                                    if line_count_since_helium <= 10:
                                        pass
                                    if line_count_since_helium > 10:
                                        break
                                if "Helium Level" in line:
                                    match = re.search(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}).*Helium Level (\d+\.\d+)", line)
                                    if match:
                                        timestamp = datetime.strptime(match.group(1), "%Y/%m/%d %H:%M:%S")
                                        helium_level = float(match.group(2))
                                        helium_found = True
                                        line_count_since_helium = 0
                                elif "Shield temperature" in line:
                                    match = re.search(r"Shield temperature (\d+\.?\d*)", line)
                                    if match:
                                        shield_temp = float(match.group(1))
                                elif "Magnet pressure" in line:
                                    match = re.search(r"Magnet pressure (\d+\.\d+)", line)
                                    if match:
                                        pressure = float(match.group(1))
                                        magnet_pressure = pressure
                                        magnet_pressure_unit = "psi" if pressure < 500 else "Pa"
                                elif "Refrigerator" in line:
                                    match = re.search(r"Refrigerator.* (\d+\.\d{1,3})\s*Kelvin", line)
                                    if match:
                                        refrigerator_temp = float(match.group(1))
                                if "watt" in line.lower():
                                    match = re.search(r"(\d+\.\d+)\s*[Ww][Aa]?[Tt][Tt]?[Ss]?", line, re.IGNORECASE)
                                    if match:
                                        heater_power = float(match.group(1))
                                if timestamp and helium_level is not None and shield_temp is not None:
                                    data["timestamps"].append(timestamp)
                                    data["helium_levels"].append(helium_level)
                                    data["shield_temps"].append(shield_temp)
                                    data["magnet_pressures"].append(magnet_pressure if magnet_pressure is not None else 0.0)
                                    data["magnet_pressure_units"].append(magnet_pressure_unit if magnet_pressure_unit is not None else "Pa")
                                    data["refrigerator_temps"].append(refrigerator_temp if refrigerator_temp is not None else 0.0)
                                    data["heater_powers"].append(heater_power if heater_power is not None else 0.0)
                    except Exception as e:
                        self.logger.error(f"[MOD MAGSTATS] Failed to process file {local_path}: {e}")
                        continue
               
# CHECK DATA
                lengths = [len(data["timestamps"]), len(data["helium_levels"]), len(data["shield_temps"]),
                           len(data["magnet_pressures"]), len(data["magnet_pressure_units"]), len(data["refrigerator_temps"]), len(data["heater_powers"])]
                if len(set(lengths)) > 1:
                    self.logger.error("[MOD MAGSTATS] Data Error: Inconsistent data lengths")
                    return
               
# DELETE TEMP FILES
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    self.logger.error(f"[MOD MAGSTATS] Failed to Delete Temp Dir {temp_dir}: {e}")
               
                sftp.close()
                ssh.close()
               
                if data["timestamps"]:
                    self.status_signal.emit("Data Acquired", "green")
                    self.logger.info("[MOD MAGSTATS] Data Acquired")
                    self.data_signal.emit(data)
                else:
                    self.logger.warning("[MOD MAGSTATS] No Matching Data Found")
            except Exception as e:
                sftp.close()
                ssh.close()
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e2:
                    self.logger.error(f"[MOD MAGSTATS] Failed to Delete Temp Dir {temp_dir}: {e2}")
                self.logger.error(f"[MOD MAGSTATS] Failed to download files: {e}")
                return
        except Exception as e:
            ssh.close()
            self.logger.error(f"[MOD MAGSTATS] Failed to Login: {e}")
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = CRDLogger("CRD").get_logger()  
        self.logger.setLevel(logging.DEBUG)  
        self.setWindowTitle("MR Magnet Statistics")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(DIALOG_STYLE)
        self.site_name = "Unknown Site"
        self.sid = "Unknown SID"
        self.latest_data = None
       
        self.status_label = QLabel("Waiting for Data", self)
        self.status_label.setStyleSheet(STD_LABEL_STYLE)
        self.default_label = QLabel("Default 10 ", self)
        self.default_label.setStyleSheet(STD_LABEL_STYLE)
       
        self.days_combo = QComboBox(self)
        self.days_combo.addItems([str(i) for i in range(11, 31)])
        self.days_combo.setFixedWidth(100)
        self.days_combo.setStyleSheet(COMBOBOX_STYLE)
       
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setFixedWidth(100)
        self.refresh_button.setStyleSheet(BUTTON_STYLE)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.separator_label = QLabel(" / ", self)
        self.separator_label.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
       
        self.screenshot_button = QPushButton("Screen Shot", self)
        self.screenshot_button.setFixedWidth(100)
        self.screenshot_button.setStyleSheet(BUTTON_STYLE)
        self.screenshot_button.clicked.connect(self.save_screenshot)
        self.csv_button = QPushButton("CSV", self)
        self.csv_button.setFixedWidth(100)
        self.csv_button.setStyleSheet(BUTTON_STYLE)
        self.csv_button.clicked.connect(self.save_csv)
       
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.status_label)
        top_layout.addStretch()
        top_layout.addWidget(self.default_label)
        top_layout.addWidget(self.days_combo)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.separator_label)
        top_layout.addWidget(self.screenshot_button)
        top_layout.addWidget(self.csv_button)
       
        self.figure, self.axes = plt.subplots(5, 1, figsize=(10, 10), sharex=True)
        self.canvas = FigureCanvas(self.figure)
        self.figure.patch.set_facecolor('#1A1A1A')
        for ax in self.axes:
            ax.set_facecolor('#202020')
            ax.grid(True, color='#606060', linestyle='--', alpha=0.7)
            ax.tick_params(colors='#FFFFFF', labelsize=10)
            ax.spines['top'].set_color('#606060')
            ax.spines['bottom'].set_color('#606060')
            ax.spines['left'].set_color('#606060')
            ax.spines['right'].set_color('#606060')
       
        self.version_label = QLabel("Note: Top Left Displays Status Information", self)
        self.version_label.setStyleSheet(STD_LABEL_STYLE)
       
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.version_label)
        bottom_layout.addStretch()
       
        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.canvas)
        layout.addLayout(bottom_layout)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
       
        self.data_thread = DataFetchThread(config_path="../config/current.dat", days=10)
        self.data_thread.status_signal.connect(self.update_status)
        self.data_thread.data_signal.connect(self.display_plots)
        self.data_thread.error_signal.connect(self.display_error)
        self.data_thread.config_signal.connect(self.update_config)
        self.data_thread.start()
# ---------------------------------------------------------------------------
    def update_config(self, site_name, sid):
        self.site_name = site_name
        self.sid = sid
        self.logger.info(f"[MOD MAGSTATS] site_name: {site_name}, sid: {sid}")
# ---------------------------------------------------------------------------
    def update_status(self, status_text, color):
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: {color};")
# ---------------------------------------------------------------------------
    def refresh_data(self):
        days = int(self.days_combo.currentText())
        self.data_thread = DataFetchThread(config_path="../config/current.dat", days=days)
        self.data_thread.status_signal.connect(self.update_status)
        self.data_thread.data_signal.connect(self.display_plots)
        self.data_thread.error_signal.connect(self.display_error)
        self.data_thread.config_signal.connect(self.update_config)
        self.data_thread.start()
        self.logger.info(f"[MOD MAGSTATS] Refreshing Data With {days} days")
# ---------------------------------------------------------------------------
    def save_screenshot(self):
        try:
            downloads_dir = "../downloads"
            os.makedirs(downloads_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.sid}_{timestamp}_magnetstats.png"
            filepath = os.path.join(downloads_dir, filename)
            screen = QApplication.primaryScreen()
            screenshot = screen.grabWindow(self.winId())
            screenshot.save(filepath, "PNG")
            self.status_label.setText("Screenshot Saved")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: green;")
            self.logger.info(f"[MOD MAGSTATS] Screenshot saved to {filepath}")
        except Exception as e:
            self.status_label.setText("Screenshot Failed")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: red;")
            self.logger.error(f"[MOD MAGSTATS] Failed to save screenshot: {e}")
# ---------------------------------------------------------------------------
    def save_csv(self):
        if not self.latest_data or not self.latest_data["timestamps"]:
            self.status_label.setText("No Data to Export")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: yellow;")
            self.logger.warning("[MOD MAGSTATS] No Data to Export to CSV")
            return
        try:
            downloads_dir = "../downloads"
            os.makedirs(downloads_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.sid}_{timestamp}_magnetstats.csv"
            filepath = os.path.join(downloads_dir, filename)
            with open(filepath, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Timestamp", "Helium Level (%)", "Shield Temperature (K)",
                                "Magnet Pressure", "Magnet Pressure Unit",
                                "Refrigerator Temp (K)", "Heater Power (W)"])
                for ts, hl, st, mp, mpu, rt, hp in zip(
                    self.latest_data["timestamps"],
                    self.latest_data["helium_levels"],
                    self.latest_data["shield_temps"],
                    self.latest_data["magnet_pressures"],
                    self.latest_data["magnet_pressure_units"],
                    self.latest_data["refrigerator_temps"],
                    self.latest_data["heater_powers"]
                ):
                    writer.writerow([
                        ts.strftime("%Y/%m/%d %H:%M:%S"),
                        hl,
                        st,
                        mp if mp != 0.0 else "",
                        mpu if mp != 0.0 else "",
                        rt if rt != 0.0 else "",
                        hp if hp != 0.0 else ""
                    ])
            self.status_label.setText("CSV Saved")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: green;")
            self.logger.info(f"[MOD MAGSTATS] CSV saved to {filepath}")
        except Exception as e:
            self.status_label.setText("CSV Export Failed")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: red;")
            self.logger.error(f"[MOD MAGSTATS] Failed to save CSV: {e}")
# ---------------------------------------------------------------------------
    def display_plots(self, data):
        self.latest_data = data
        try:
            for ax in self.axes:
                ax.clear()
                ax.set_facecolor('#202020')
                ax.grid(True, color='#606060', linestyle='--', alpha=0.7)
                ax.tick_params(colors='#FFFFFF', labelsize=10)
                ax.spines['top'].set_color('#606060')
                ax.spines['bottom'].set_color('#606060')
                ax.spines['left'].set_color('#606060')
                ax.spines['right'].set_color('#606060')
                ax.set_visible(True)
            visible_axes = []
            if not data["timestamps"]:
                self.status_label.setText("No Valid Data Found")
                self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: yellow;")
                self.logger.warning("[MOD MAGSTATS] No Valid Data Found")
                for ax in self.axes:
                    ax.text(0.5, 0.5, "No Data Available", ha="center", va="center", color="yellow", fontsize=10)
                self.axes[0].set_title(f"{self.site_name} - SID {self.sid}", color='#FFFFFF', fontsize=12)
                visible_axes.append(self.axes[0])
            else:
# PLOT HE LEVEL
                if len(data["timestamps"]) > 1 and any(hl != 0.0 for hl in data["helium_levels"]):
                    self.axes[0].plot(data["timestamps"], data["helium_levels"], "c.-", label="Helium Level")
                    self.axes[0].legend(facecolor='#202020', edgecolor='#606060', labelcolor='#FFFFFF')
                    visible_axes.append(self.axes[0])
                else:
                    self.axes[0].set_visible(False)
                self.axes[0].set_title(f"{self.site_name} - SID {self.sid}", color='#FFFFFF', fontsize=12)
# PLOT SHIELD TEMPS
                if len(data["timestamps"]) > 1 and any(st != 0.0 for st in data["shield_temps"]):
                    self.axes[1].plot(data["timestamps"], data["shield_temps"], "r.-", label="Shield Temperature")
                    self.axes[1].legend(facecolor='#202020', edgecolor='#606060', labelcolor='#FFFFFF')
                    visible_axes.append(self.axes[1])
                else:
                    self.axes[1].set_visible(False)
# PLOT MAGNET PRESSURE
                valid_magnet_pressures = [mp for mp, unit in zip(data["magnet_pressures"], data["magnet_pressure_units"]) if mp != 0.0]
                if len(data["timestamps"]) > 1 and valid_magnet_pressures:
                    units = [unit for unit, mp in zip(data["magnet_pressure_units"], data["magnet_pressures"]) if mp != 0.0]
                    common_unit = max(set(units), key=units.count, default="Pa")
                    self.axes[2].plot(data["timestamps"], data["magnet_pressures"], "b.-", label=f"Magnet Pressure ({common_unit})")
                    if common_unit == "Pa":
                        self.axes[2].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x)}"))
                    self.axes[2].legend(facecolor='#202020', edgecolor='#606060', labelcolor='#FFFFFF')
                    visible_axes.append(self.axes[2])
                else:
                    self.axes[2].set_visible(False)
# PLOT 4K SHIELDS
                valid_refrigerator_temps = [rt for rt in data["refrigerator_temps"] if rt != 0.0]
                if len(data["timestamps"]) > 1 and valid_refrigerator_temps:
                    self.axes[3].plot(data["timestamps"], data["refrigerator_temps"], "g.-", label="Refrigerator 4K Temp")
                    self.axes[3].legend(facecolor='#202020', edgecolor='#606060', labelcolor='#FFFFFF')
                    visible_axes.append(self.axes[3])
                else:
                    self.axes[3].set_visible(False)
# PLOT HEATER PWR
                valid_heater_powers = [hp for hp in data["heater_powers"] if hp != 0.0]
                if len(data["timestamps"]) > 1 and valid_heater_powers:
                    self.axes[4].plot(data["timestamps"], data["heater_powers"], "m.-", label="Heater Power")
                    self.axes[4].legend(facecolor='#202020', edgecolor='#606060', labelcolor='#FFFFFF')
                    visible_axes.append(self.axes[4])
                else:
                    self.axes[4].set_visible(False)
                   
            if visible_axes:
                n_visible = len(visible_axes)
                height_per_plot = 1.0 / n_visible
                for i, ax in enumerate(visible_axes):
                    ax.set_position([0.1, 1.0 - (i + 1) * height_per_plot, 0.8, height_per_plot * 0.9])
                    if i == n_visible - 1:
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d-%y'))
                        ax.tick_params(axis='x', labelbottom=True)
                    else:
                        ax.tick_params(axis='x', labelbottom=False)
            self.figure.subplots_adjust(hspace=0)
            self.canvas.draw()
        except Exception as e:
            self.status_label.setText("Plotting Error")
            self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: red;")
            self.logger.error(f"[MOD MAGSTATS] Plotting Error: {e}")
            for ax in self.axes:
                ax.clear()
                ax.set_facecolor('#202020')
                ax.text(0.5, 0.5, f"Plotting Error: {str(e)}", ha="center", va="center", color="red", fontsize=10)
            self.axes[0].set_title(f"{self.site_name} (- SID {self.sid})", color='#FFFFFF', fontsize=12)
            self.canvas.draw()
# ---------------------------------------------------------------------------
    def display_error(self, error_message):
        self.status_label.setText("Failed To Login")
        self.status_label.setStyleSheet(f"{STD_LABEL_STYLE} color: red;")
        self.logger.error(f"[MOD MAGSTATS] Failed To Login: {error_message}")
        for ax in self.axes:
            ax.clear()
            ax.set_facecolor('#202020')
        self.canvas.draw()
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
# ---------------------------------------------------------------------------
