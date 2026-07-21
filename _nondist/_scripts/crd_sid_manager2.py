# ------------------------------------------------------------------------
"""
sid_manager.py
ewilson@us.medical.canon 08/07/25
jsmyser made a few tweaks on 10/03/25
JS_EDITS 25.12.24
JS_EDITS 2026.03.05 Fixed tables from missing data during refresh.
Version 1.03 Updated 07/177/26
"""
# ------------------------------------------------------------------------
import sys
import json
import os
import re
import subprocess  #Added by JS
from typing import Dict, List, Any
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox, QDialog,
    QFormLayout, QHeaderView, QCheckBox, QComboBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon
from crd_embedded import CRDLogger, Styles
import mysql.connector
from cryptography.fernet import Fernet
icon_path = lambda name: os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../html/icons/", name))
# ------------------------------------------------------------------------
class SIDDatabase:
    def __init__(self, filename='../data/siddb.json'):
        self.filename = filename
        self.create_database_if_not_exists()
# ------------------------------------------------------------------------
    def create_database_if_not_exists(self):
        if not os.path.exists(self.filename):
            db = {"index": []}
            with open(self.filename, 'w') as file:
                json.dump(db, file, indent=4)
# ------------------------------------------------------------------------
    def read_database(self) -> Dict[str, List[Any]]:
        try:
            with open(self.filename, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.create_database_if_not_exists()
            return self.read_database()
# ------------------------------------------------------------------------
    def write_database(self, data: Dict[str, List[Any]]):
        with open(self.filename, 'w') as file:
            json.dump(data, file, indent=4)
# ------------------------------------------------------------------------
    def add_entry(self, entry: Dict[str, Any]):
        database = self.read_database()
        database['index'].append(entry)
        self.write_database(database)
# ------------------------------------------------------------------------
    def find_by_sid(self, sid: str) -> List[Dict[str, Any]]:
        database = self.read_database()
        return [entry for entry in database['index'] if entry['sid'] == sid]
# ------------------------------------------------------------------------
    def update_entry(self, old_sid: str, updated_entry: Dict[str, Any]):
        database = self.read_database()
        for i, entry in enumerate(database['index']):
            if entry['sid'] == old_sid:
                database['index'][i] = updated_entry
                break
        self.write_database(database)
# ------------------------------------------------------------------------
    def delete_entry_by_sid(self, sid: str):
        database = self.read_database()
        database['index'] = [entry for entry in database['index'] if entry['sid'] != sid]
        self.write_database(database)
# ------------------------------------------------------------------------
class EntryDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Entry")
        self.setFixedWidth(350)
        self.entry = entry or {}
        self.setStyleSheet(Styles.DIALOG)
        layout = QFormLayout()
        self.sid_input = QLineEdit(self.entry.get('sid', ''))
        self.site_name_input = QLineEdit(self.entry.get('site_name', ''))
        self.sp_ip_input = QLineEdit(', '.join(self.entry.get('sp_ip', [])))
        self.host_ip_input = QLineEdit(', '.join(self.entry.get('host_ip', [])))
        self.display_ip_input = QLineEdit(', '.join(self.entry.get('display_ip', [])))
        self.tunnel_input = QLineEdit(', '.join(self.entry.get('tunnel', [])))
        self.modality_input = QLineEdit(', '.join(self.entry.get('modality', [])))
        self.port_input = QLineEdit(self.entry.get('port', ''))
        self.machine_input = QLineEdit(self.entry.get('machine', ''))
        self.sw_version_input = QLineEdit(self.entry.get('sw_version', ''))
        self.note_input = QLineEdit(', '.join(self.entry.get('note', [])))
        self.sid_input.setStyleSheet(Styles.SID_EDIT_BOX_STYLE)
        for edit in [self.site_name_input, self.sp_ip_input, self.host_ip_input,
                     self.display_ip_input, self.tunnel_input, self.modality_input,
                     self.port_input, self.machine_input, self.sw_version_input,
                     self.note_input]:
            edit.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.sp_ip_input.setToolTip("Enter IPv4 addresses separated by commas, e.g., 192.168.1.1, 10.0.0.1")
        self.host_ip_input.setToolTip("Enter IPv4 addresses separated by commas, e.g., 192.168.1.2, 10.0.0.2")
        self.display_ip_input.setToolTip("Enter IPv4 addresses separated by commas, e.g., 192.168.1.3, 10.0.0.3")
        layout.addRow(self.create_styled_label("SID *:"), self.sid_input)
        layout.addRow(self.create_styled_label("Site Name *:"), self.site_name_input)
        layout.addRow(self.create_styled_label("SP IP:"), self.sp_ip_input)
        layout.addRow(self.create_styled_label("Host IP:"), self.host_ip_input)
        layout.addRow(self.create_styled_label("Display IP:"), self.display_ip_input)
        layout.addRow(self.create_styled_label("Tunnel:"), self.tunnel_input)
        layout.addRow(self.create_styled_label("Modality:"), self.modality_input)
        layout.addRow(self.create_styled_label("Port:"), self.port_input)
        layout.addRow(self.create_styled_label("Machine:"), self.machine_input)
        layout.addRow(self.create_styled_label("SW Version:"), self.sw_version_input)
        layout.addRow(self.create_styled_label("Note:"), self.note_input)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.setStyleSheet(Styles.BUTTON_STYLE)
        cancel_button.setStyleSheet(Styles.BUTTON_STYLE)
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
# ------------------------------------------------------------------------
    def create_styled_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(Styles.STD_LABEL_STYLE)
        return label
# ------------------------------------------------------------------------
    def get_entry(self):
        return {
            'sid': self.sid_input.text(),
            'site_name': self.site_name_input.text(),
            'sp_ip': [ip.strip() for ip in self.sp_ip_input.text().split(',') if ip.strip()],
            'host_ip': [ip.strip() for ip in self.host_ip_input.text().split(',') if ip.strip()],
            'display_ip': [ip.strip() for ip in self.display_ip_input.text().split(',') if ip.strip()],
            'tunnel': [t.strip() for t in self.tunnel_input.text().split(',') if t.strip()],
            'modality': [m.strip() for m in self.modality_input.text().split(',') if m.strip()],
            'port': self.port_input.text(),
            'machine': self.machine_input.text(),
            'sw_version': self.sw_version_input.text(),
            'note': [n.strip() for n in self.note_input.text().split(',') if n.strip()]
        }
# ------------------------------------------------------------------------
class LookupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Site Name Lookup")
        self.resize(900, 500)  #Changed by JS
        self.setStyleSheet(Styles.DIALOG)

        layout = QVBoxLayout()
        site_layout = QHBoxLayout()
        site_label = QLabel("Site Name:")
        site_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        site_layout.addWidget(site_label)
        self.site_input = QLineEdit()
        self.site_input.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.site_input.setMinimumWidth(400)  
        site_layout.addWidget(self.site_input)
        site_layout.addStretch() 
        layout.addLayout(site_layout)
        
        fields_layout = QHBoxLayout()
        
        modality_label = QLabel("Modality:")
        modality_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        modality_label.setFixedWidth(60)
        fields_layout.addWidget(modality_label)
        self.modality_dropdown = QComboBox()
        self.modality_dropdown.addItems(["MR", " "])
        self.modality_dropdown.setStyleSheet(Styles.COMBO_BOX)
        self.modality_dropdown.setFixedWidth(60)
        fields_layout.addWidget(self.modality_dropdown)
        fields_layout.addStretch()  
# PRIMARY CE
        primary_ce_label = QLabel("Primary CE:")
        primary_ce_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        fields_layout.addWidget(primary_ce_label)
        self.primary_ce_input = QLineEdit()
        self.primary_ce_input.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.primary_ce_input.setMinimumWidth(150)
        fields_layout.addWidget(self.primary_ce_input)
        fields_layout.addStretch()  
# SERVICE ZONE
        service_zone_label = QLabel("Service Zone:")
        service_zone_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        fields_layout.addWidget(service_zone_label)
        self.service_zone_input = QLineEdit("Midwest")   
        self.service_zone_input.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.service_zone_input.setMinimumWidth(150)
        fields_layout.addWidget(self.service_zone_input)
        fields_layout.addStretch()
        layout.addLayout(fields_layout)         

        for line_edit in [self.site_input, self.primary_ce_input, self.service_zone_input]:
            line_edit.returnPressed.connect(self.perform_query)

# CONTRACT TYPE  # Added by JS
        contract_layout = QHBoxLayout()
        contract_type_label = QLabel("Contract Type:")
        contract_type_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        contract_layout.addWidget(contract_type_label)
        self.contract_type_checks = {}
        checkbox_layout = QHBoxLayout()
        options = ["Toggle All", "Full Service", "Warranty", "PM", "In-House", "Partnership", "Point of Purchase"]
        for option in options:
            if option == "Toggle All":
                button = QPushButton(option)
                button.setFixedWidth(100)
                button.setIcon(QIcon(icon_path("toggle.png")))
                button.setIconSize(QSize(24, 24))
                button.setStyleSheet(Styles.BUTTON_STYLE)
                button.setDefault(False)
                button.setAutoDefault(False) 
                def toggle_all():
                    all_checked = all(self.contract_type_checks[opt].isChecked() for opt in options if opt != "🔀 Toggle All")
                    for opt in options:
                        if opt != "Toggle All":
                            self.contract_type_checks[opt].setChecked(not all_checked)
                button.clicked.connect(toggle_all)
                checkbox_layout.addWidget(button)
            else:
                check = QCheckBox(option)
                check.setStyleSheet(Styles.WIDGET_STYLE)
                self.contract_type_checks[option] = check
                checkbox_layout.addWidget(check)
        checkbox_group = QGroupBox()
        checkbox_group.setStyleSheet("QGroupBox { border: none; margin: 0; padding: 0; }")
        checkbox_group.setLayout(checkbox_layout)
        checkbox_group.setMinimumWidth(150)
        contract_layout.addWidget(checkbox_group)
        contract_layout.addStretch()
        layout.addLayout(contract_layout)
        
# QUERY BUTTON
        button_layout = QHBoxLayout()
        query_button = QPushButton("🔎 QUERY")
        query_button.setStyleSheet(Styles.BUTTON_STYLE)
        query_button.setFixedWidth(160)
        query_button.clicked.connect(self.perform_query)
        button_layout.addStretch()
        button_layout.addWidget(query_button)

# LOAD TO CRD BUTTON # Added by JS        
        if isinstance(parent, SIDDatabaseWindow) and parent.main_app and type(parent.main_app).__name__ == "DesktopApp":
            load_to_crd_button = QPushButton("📤 Load to CRD")
            load_to_crd_button.setStyleSheet(Styles.BUTTON_STYLE)
            load_to_crd_button.setDefault(False)
            load_to_crd_button.setAutoDefault(False) 
            load_to_crd_button.setFixedWidth(160)
            load_to_crd_button.clicked.connect(self.handle_double_click)
            button_layout.addSpacing(20)
            button_layout.addWidget(load_to_crd_button)
            button_layout.addSpacing(20)
        else:
            button_layout.addSpacing(200)

# ADD TO DATABASE BUTTON  # Added by JS                
        add_to_db_button = QPushButton("➕ Add to SID(s) to Local Database")
        add_to_db_button.setStyleSheet(Styles.BUTTON_STYLE)
        add_to_db_button.setDefault(False)
        add_to_db_button.setAutoDefault(False)         
        add_to_db_button.setFixedWidth(260)
        add_to_db_button.clicked.connect(self.add_to_database)
        button_layout.addWidget(add_to_db_button)
        button_layout.addStretch()
#        button_layout.addSpacing(30)        
        layout.addLayout(button_layout)
        
# GRID  #JS added contract type, QTableWidget.ExtendedSelection, QTableWidget.SelectRows, Sorting, and custom mouse press event.
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(["SID", "Site Name", "Model", "Primary CE", "Service Zone", "Contract Type"])
        self.result_table.setStyleSheet("QTableWidget { border: 1px solid #ccc; } QTableWidget::item { padding: 5px; }")
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.result_table.setSortingEnabled(True)
        def custom_mouse_press_event(event):
            if event.buttons() == Qt.LeftButton and not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                self.result_table.clearSelection()
            QTableWidget.mousePressEvent(self.result_table, event)
        self.result_table.mousePressEvent = custom_mouse_press_event
        self.result_table.setColumnWidth(0, 100)
        self.result_table.setColumnWidth(1, 200) 
        self.result_table.setColumnWidth(2, 200)
        self.result_table.setColumnWidth(3, 150)
        self.result_table.setColumnWidth(4, 150)
        self.result_table.setColumnWidth(5, 150)
        self.result_table.itemDoubleClicked.connect(self.handle_double_click)
        layout.addWidget(self.result_table)
        
# CLOSE
        close_button_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.setStyleSheet(Styles.BUTTON_STYLE)
        close_button.clicked.connect(self.close)
        close_button_layout.addStretch()
        close_button_layout.addWidget(close_button)
        layout.addLayout(close_button_layout)
        self.setLayout(layout)
        
        self.result_table.sortItems(1) # JS_EDITS 2026.03.05 Added to sort by site name. 
# ------------------------------------------------------------------------
    def get_credentials(self):
        try:
            with open("../config/vpn.key", "rb") as key_file:
                key = key_file.read()
            fernet = Fernet(key)
            with open("../config/vpn.enc", "rb") as enc_file:
                encrypted_data = enc_file.read()
            decrypted_data = fernet.decrypt(encrypted_data).decode()
            credentials = {}
            for line in decrypted_data.splitlines():
                line = line.strip()
                if line:
                    key, value = line.split("=", 1)
                    credentials[key.strip()] = value.strip()
            
            return {
                "database": credentials.get("database", ""),
                "host": "10.94.100.239", 
                "passwd": credentials.get("passwd", ""),
                "user": credentials.get("user", "")
            }
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to Load Credentials: {str(e)}")
            return None
# ------------------------------------------------------------------------
    def perform_query(self):  # JS Added contract_type. 
        self.result_table.setRowCount(0)
        site_name = self.site_input.text().strip()
        modality = self.modality_dropdown.currentText().strip()
        primary_ce = self.primary_ce_input.text().strip()
        service_zone = self.service_zone_input.text().strip()
        self.result_table.setSortingEnabled(False) # JS_EDITS 2026.03.05 Added to prevent missing items in table.

        # Get selected items from checkboxes
        contract_type = [opt for opt, check in self.contract_type_checks.items() if check.isChecked() and opt not in ["🔀 Toggle All"]]
    
        
        if not (site_name or modality != " " or primary_ce or service_zone):
            QMessageBox.warning(self, "Warning", "Please Enter One Search Critera (Site Name, Modality, Primary CE, or Service Zone)")
            return
        creds = self.get_credentials()
        if not creds:
            return
        try:
            conn = mysql.connector.connect(
                host=creds["host"],
                user=creds["user"],
                password=creds["passwd"],
                database=creds["database"]
            )
            cursor = conn.cursor()
            query = "SELECT SID, SITE_NAME, MODEL, PRIMARY_CE, SERVICE_ZONE, CONTRACT_TYPE FROM VPN_INSTALLBASE_V"
            params = []
            conditions = []
            
        
            if site_name:
                conditions.append("LOWER(SITE_NAME) LIKE LOWER(%s)")
                params.append(f"%{site_name}%")
            if modality and modality != " ":
                conditions.append("MODALITY = %s")
                params.append(modality)
            if primary_ce:
                conditions.append("LOWER(PRIMARY_CE) LIKE LOWER(%s)")
                params.append(f"%{primary_ce}%")
            if service_zone:
                conditions.append("LOWER(SERVICE_ZONE) LIKE LOWER(%s)")
                params.append(f"%{service_zone}%")
            if contract_type:
                like_conditions = [f"LOWER(CONTRACT_TYPE) LIKE LOWER(%s)" for _ in contract_type]
                conditions.append("(" + " OR ".join(like_conditions) + ")")
                params.extend([f"%{ct}%" for ct in contract_type])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, tuple(params))
            results = cursor.fetchall()
            self.result_table.setRowCount(len(results))
            for row_idx, (sid, site_name, model, primary_ce, service_zone, contract_type) in enumerate(results):
                self.result_table.setItem(row_idx, 0, QTableWidgetItem(str(sid) if sid is not None else ""))
                self.result_table.setItem(row_idx, 1, QTableWidgetItem(str(site_name) if site_name is not None else ""))
                self.result_table.setItem(row_idx, 2, QTableWidgetItem(str(model) if model is not None else ""))
                self.result_table.setItem(row_idx, 3, QTableWidgetItem(str(primary_ce) if primary_ce is not None else ""))
                self.result_table.setItem(row_idx, 4, QTableWidgetItem(str(service_zone) if service_zone is not None else ""))
                self.result_table.setItem(row_idx, 5, QTableWidgetItem(str(contract_type) if contract_type is not None else ""))
            cursor.close()
            conn.close()
            self.result_table.setSortingEnabled(True) # JS_EDITS 2026.03.05 Added to prevent missing items in table.
        except mysql.connector.Error as e:
            QMessageBox.critical(self, "Error", f"Database error: {str(e)}")
# ------------------------------------------------------------------------
    def handle_double_click(self, item=None): # Modified by JS
        try:
            selected_rows = sorted(set(index.row() for index in self.result_table.selectedIndexes()))
            if len(selected_rows) == 0:
                raise ValueError("No row selected")
            if len(selected_rows) > 1:
                raise ValueError("Only one row can be selected")
            row = selected_rows[0]  # Ensure row is an integer
            sid_item = self.result_table.item(row, 0)
            if not sid_item:
                raise ValueError("SID is missing in row")
            sid = sid_item.text()
            parent = self.parent()
            if isinstance(parent, SIDDatabaseWindow) and parent.main_app and type(parent.main_app).__name__ == "DesktopApp":
                if hasattr(parent.main_app, 'edit_box_sid'):
                    parent.main_app.edit_box_sid.setText(sid)
                parent.main_app.query_ip_addresses()
                self.close()                
            else:
                self.add_to_database()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process selection: {str(e)}")

# ------------------------------JS Added add_to_database & query_ip_addresses below ----------------------
    def query_ip_addresses(self, sid):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'crd_connectvpn.py')
            if not os.path.exists(script_path):
                raise OSError(f"Script File Does Not Exist: {script_path}")
            env = os.environ.copy()
            # Use creds_dict if available, else dummy values
            if hasattr(self, 'creds_dict') and self.creds_dict and "SP_WIN10" in self.creds_dict:
                env['SPUSER'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_user", "IV_Service_User")
                env['SPPASS'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_pass", "SU_InnerVision2020")
                env['PORT'] = self.creds_dict["SP_WIN10"].get("credentials", {}).get("host_port", "22") or "22"
            result = subprocess.run(
                [sys.executable, script_path, sid],
                capture_output=True,
                text=True,
                check=True,
                cwd=script_dir,
                timeout=180,
                env=env
            )
            json_data = result.stdout.strip()
            data = json.loads(json_data)
            # Strip PreInstall: from HospName
            if data.get("HospName", "").startswith("PreInstall:"):
                data["HospName"] = data["HospName"][len("PreInstall:"):].strip()
            return data
        except Exception as e:
            raise

    def add_to_database(self):
        errors = []
        successes = []
        selected_rows = sorted(set(index.row() for index in self.result_table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "No rows selected.")
            return
        
        # Suppress QMessageBox and CustomMessageBox popups
        original_exec = QMessageBox.exec_
        def no_op(*args, **kwargs):
            pass
        QMessageBox.exec_ = no_op
        QMessageBox.exec_custom = no_op  # Suppress CustomMessageBox
        
        parent = self.parent()
        for row in selected_rows:
            try:
                sid_item = self.result_table.item(row, 0)
                if not sid_item:
                    raise ValueError(f"SID is missing in row {row + 1}")
                sid = sid_item.text()
                if isinstance(parent, SIDDatabaseWindow) and parent.main_app and type(parent.main_app).__name__ == "DesktopApp":
                    if hasattr(parent.main_app, 'edit_box_sid'):
                        parent.main_app.edit_box_sid.setText(sid)
                    if parent.main_app.query_ip_addresses():
                        parent.main_app.add_to_sid_database()
                        successes.append(f"SID-{sid}")
                        parent.load_entries()  
                    # Check if SID was processed
                    else:
                        raise ValueError("SID processing failed")
                else:
                    # Local processing using SIDDatabase
                    data = self.query_ip_addresses(sid)
                    entry = {
                        "sid": sid,
                        "site_name": data.get("HospName", ""),
                        "sp_ip": [data.get("sp_ip", "")] if data.get("sp_ip", "") else [],
                        "host_ip": [data.get("host_ip", "")] if data.get("host_ip", "") else [],
                        "display_ip": [data.get("display_ip", "")] if data.get("display_ip", "") else [],
                        "tunnel": [data.get("TunnelType", "")] if data.get("TunnelType", "") else [],
                        "modality": [data.get("modality", "")] if data.get("modality", "") else [],
                        "port": data.get("port", ""),
                        "machine": data.get("machine", ""),
                        "sw_version": data.get("sw_version", ""),
                        "note": []
                    }
                    if not entry["sid"]:
                        raise ValueError("SID is Required")
                    existing = parent.database.find_by_sid(sid)
                    if existing:
                        parent.database.update_entry(sid, entry)
                    else:
                        parent.database.add_entry(entry)
                    # Verify entry was added/updated
                    if parent.database.find_by_sid(sid):
                        successes.append(f"SID-{sid}")
                        parent.load_entries()  # Added to refresh
                    else:
                        raise ValueError("SID processing failed")
            except Exception as e:
                errors.append(f"Row {row + 1} SID-{sid}")  # Updated error message
                print(f"Add to DB Failed: Row {row + 1} SID-{sid}: {str(e)}")
        
        # Restore QMessageBox
        QMessageBox.exec_ = original_exec
        # Clean up exec_custom safely
        if hasattr(QMessageBox, 'exec_custom'):
            delattr(QMessageBox, 'exec_custom')
        
        message = []
        if successes:
            message.append(f"SIDs processed successfully: {', '.join(successes)}")
        if errors:
            message.append(f"\nFailed to process: {', '.join(errors)}")
        
        if message:
            QMessageBox.information(self, "Operation Result", "\n".join(message)) if successes and not errors else QMessageBox.critical(self, "Operation Result", "\n".join(message))
        elif not successes:
            QMessageBox.warning(self, "Warning", "No SIDs processed.")

# ------------------------------------------------------------------------
class SIDDatabaseWindow(QWidget):
    close_requested = pyqtSignal()
    def __init__(self, sid_manager=None, main_app=None, tab_widget=None):
        super().__init__()
        self.sid_manager = sid_manager
        self.main_app = main_app
        self.tab_widget = tab_widget
        self.setWindowTitle("SID Database") # Added by JS
        self.setGeometry(100, 100, 900, 500) # Added by JS
        self.database = SIDDatabase()
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        header_layout = QHBoxLayout()
        
        layout.addLayout(header_layout)
        input_layout = QHBoxLayout()
        self.sid_input = QLineEdit()
        self.site_name_input = QLineEdit()
        self.sid_input.setObjectName("sidInput")
        self.site_name_input.setObjectName("siteInput")
        self.sid_input.setPlaceholderText("SID")
        self.site_name_input.setPlaceholderText("SITE")
        self.sid_input.setFixedWidth(125)
        self.site_name_input.setFixedWidth(300)
        self.sid_input.textChanged.connect(self.filter_entries)
        self.site_name_input.textChanged.connect(self.filter_entries)
        sid_label = QLabel("SID:")
        sid_label.setObjectName("inputLabel")
        site_name_label = QLabel("SITE NAME:")
        site_name_label.setObjectName("inputLabel")
        lookup_button = QPushButton("🕵 LOOKUP")
        lookup_button.setStyleSheet(Styles.BUTTON_STYLE)
        lookup_button.setFixedSize(90, 30)
        lookup_button.clicked.connect(self.show_lookup_dialog)
        clear_button = QPushButton("🧹 CLEAR")
        clear_button.setStyleSheet(Styles.BUTTON_STYLE)
        clear_button.setFixedSize(90, 30)
        clear_button.clicked.connect(self.clear_inputs)
  
        input_layout.addWidget(sid_label)
        input_layout.addWidget(self.sid_input)
        input_layout.addWidget(site_name_label)
        input_layout.addWidget(self.site_name_input)
        input_layout.addWidget(lookup_button)
        input_layout.addWidget(clear_button)
        input_layout.addStretch()
        layout.addLayout(input_layout)
        
        self.checkbox_close = QCheckBox("Close SID DATABASE On Selection")
        if self.main_app is not None: # Added by JS
            self.checkbox_close.setChecked(False) # ALWAYS ENABLED
        self.checkbox_close.setStyleSheet("color: white; font-size: 14px;")
        self.checkbox_close.setVisible(False) # ALWAYS HIDDEN
        layout.addWidget(self.checkbox_close)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "SID", "Site Name", "SP IP", "Host IP", "Modality", "Machine", "SW Version"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setSortingEnabled(True)
        if self.main_app is not None: #Added by JS
            self.table.itemClicked.connect(self.populate_main_app)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ ADD")
        edit_btn = QPushButton("📝 EDIT")
        delete_btn = QPushButton("❌ DELETE")
        refresh_btn = QPushButton("🔄 REFRESH")
        export_btn = QPushButton("📤 EXPORT")
        for btn in [add_btn, edit_btn, delete_btn, refresh_btn, export_btn]:
            btn.setFixedHeight(30)
            btn.setFixedWidth(130)
            btn.setStyleSheet(Styles.BUTTON_STYLE)
      
        add_btn.setStyleSheet(Styles.add_button if hasattr(Styles, 'add_button') else Styles.BUTTON_STYLE)
        edit_btn.setStyleSheet(Styles.edit_button if hasattr(Styles, 'edit_button') else Styles.BUTTON_STYLE)
        delete_btn.setStyleSheet(Styles.delete_button if hasattr(Styles, 'delete_button') else Styles.BUTTON_STYLE)
        refresh_btn.setStyleSheet(Styles.refresh_button if hasattr(Styles, 'refresh_button') else Styles.BUTTON_STYLE)
        export_btn.setStyleSheet(Styles.export_button if hasattr(Styles, 'export_button') else Styles.BUTTON_STYLE)
        add_btn.clicked.connect(self.add_entry)
        edit_btn.clicked.connect(self.edit_entry)
        delete_btn.clicked.connect(self.delete_entry)
        refresh_btn.clicked.connect(self.load_entries)
        export_btn.clicked.connect(self.export_to_csv)
        btn_layout.addStretch()
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_entries()
        self.apply_dark_theme()
        self.table.sortItems(1) # JS_EDITS 2026.03.05 Added to sort initial table by site name.

# ------------------------------------------------------------------------
    def show_lookup_dialog(self):
        dialog = LookupDialog(self)
        dialog.exec_()
# ------------------------------------------------------------------------
    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, QColor(64, 64, 64))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)
        self.setStyleSheet("""
            QTableWidget {
                background-color: #202020;
                alternate-background-color: #404040;
                color: white;
            }
            QHeaderView::section {
                background-color: #404040;
                color: white;
                padding: 5px;
                border: 1px solid #4A4A4A;
            }
            QPushButton {
                background-color: #606060;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: red;
            }
            QPushButton:pressed {
                background-color: #AA0000;
            }
            QLabel#inputLabel {
                font-size: 14px !important;
                color: white !important;
                font-weight: bold !important;
            }
            QLabel[text="SID DATABASE"] {
                font-size: 14px;
                font-weight: bold;
                color: white;
                background-color: #353535;
                padding: 10px;
                border-bottom: 2px solid #353535;
            }
            QLineEdit#sidInput, QLineEdit#siteInput {
                background-color: #404040 !important;
                color: white !important;
                border: 1px solid #404040 !important;
                padding: 5px;
                border-radius: 4px;
            }
            QCheckBox {
                color: white;
                font-size: 14px;
            }
        """)
# ------------------------------------------------------------------------
    def clear_inputs(self):
        self.sid_input.clear()
        self.site_name_input.clear()
        self.filter_entries()
# ------------------------------------------------------------------------
    def load_entries(self):
        self.sid_input.clear()
        self.site_name_input.clear()
        self.filter_entries()
        
# ------------------------------------------------------------------------
    def filter_entries(self):
        sid_filter = self.sid_input.text().lower()
        site_filter = self.site_name_input.text().lower()
        self.table.setRowCount(0)
        try:
            database = self.database.read_database()
            entries = database.get('index', [])
            self.table.setSortingEnabled(False) # JS_EDITS 2026.03.05 Added to prevent missing items in table.
            for entry in entries:
                if (not sid_filter or sid_filter in entry.get('sid', '').lower()) and \
                   (not site_filter or site_filter in entry.get('site_name', '').lower()):
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(entry.get('sid', '')))
                    self.table.setItem(row, 1, QTableWidgetItem(entry.get('site_name', '')))
                    self.table.setItem(row, 2, QTableWidgetItem(', '.join(entry.get('sp_ip', []))))
                    self.table.setItem(row, 3, QTableWidgetItem(', '.join(entry.get('host_ip', []))))
                    self.table.setItem(row, 4, QTableWidgetItem(', '.join(entry.get('modality', []))))
                    self.table.setItem(row, 5, QTableWidgetItem(entry.get('machine', '')))
                    self.table.setItem(row, 6, QTableWidgetItem(entry.get('sw_version', '')))
            self.table.resizeColumnsToContents()
            self.table.setSortingEnabled(True) # JS_EDITS 2026.03.05 Added to prevent missing items in table.
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed To Filter Entries: {str(e)}")
# ------------------------------------------------------------------------
    def populate_main_app(self, item):
        try:
            row = self.table.row(item)
            sid_item = self.table.item(row, 0)
            if not sid_item:
                raise ValueError("SID item is missing in the table")
            sid = sid_item.text()
            entries = self.database.find_by_sid(sid)
            if not entries:
                raise ValueError(f"No database entry found for SID: {sid}")
            entry = entries[0]
            site_name_item = self.table.item(row, 1)
            sp_ip_item = self.table.item(row, 2)
            host_ip_item = self.table.item(row, 3)
            modality_item = self.table.item(row, 4)
            machine_item = self.table.item(row, 5)
            sw_version_item = self.table.item(row, 6)
            site_name = site_name_item.text() if site_name_item else entry.get('site_name', '')
            sp_ip = sp_ip_item.text() if sp_ip_item else ', '.join(entry.get('sp_ip', []))
            host_ip = host_ip_item.text() if host_ip_item else ', '.join(entry.get('host_ip', []))
            modality = modality_item.text() if modality_item else ', '.join(entry.get('modality', []))
            machine = machine_item.text() if machine_item else entry.get('machine', '')
            sw_version = sw_version_item.text() if sw_version_item else entry.get('sw_version', '')
            display_ip = ', '.join(entry.get('display_ip', []))
            tunnel = ', '.join(entry.get('tunnel', []))
            port = entry.get('port', '')
            config_content = f"""SID={sid}
SiteName={site_name}
SP_IP={sp_ip}
Host_IP={host_ip}
Display_IP={display_ip}
TunnelType={tunnel}
Modality={modality}
Port={port}
SW_Version={sw_version}
Scanner={machine}
"""
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'current.dat')
            try:
                with open(config_path, 'w') as f:
                    f.write(config_content)
            except Exception as e:
                print(f"Failed to write config file: {str(e)}")
            if self.main_app:
                try:
                    if hasattr(self.main_app, 'edit_box_sid'):
                        self.main_app.edit_box_sid.setText(sid)
                    if hasattr(self.main_app, 'dynamic_header'):
                        self.main_app.dynamic_header.setText(f"{site_name}")
                    if hasattr(self.main_app, 'sp_ip_edit_box'):
                        self.main_app.sp_ip_edit_box.setText(sp_ip)
                    if hasattr(self.main_app, 'sm_ip_edit_box'):
                        self.main_app.sm_ip_edit_box.setText(host_ip)
                    if display_ip:
                        if hasattr(self.main_app, 'MachineName'):
                            self.main_app.MachineName.setText(display_ip)
                        elif hasattr(self.main_app, 'disp_edit_box'):
                            self.main_app.disp_edit_box.setText(display_ip)
                        elif hasattr(self.main_app, 'machine_edit_box'):
                            self.main_app.machine_edit_box.setText(display_ip)
                        if hasattr(self.main_app, 'display_ip_edit_box'):
                            self.main_app.display_ip_edit_box.setText(display_ip)
                    if hasattr(self.main_app, 'tunnel_edit_box'):
                        self.main_app.tunnel_edit_box.setText(tunnel)
                    elif hasattr(self.main_app, 'tunnel_type_edit_box'):
                        self.main_app.tunnel_type_edit_box.setText(tunnel)
                    if hasattr(self.main_app, 'MachineType'):
                        self.main_app.MachineType.setText(modality)
                    elif hasattr(self.main_app, 'modality_edit_box'):
                        self.main_app.modality_edit_box.setText(modality)
                    if hasattr(self.main_app, 'port_edit_box'):
                        self.main_app.port_edit_box.setText(port)
                    elif hasattr(self.main_app, 'port_number_edit_box'):
                        self.main_app.port_number_edit_box.setText(port)
                    if hasattr(self.main_app, 'sw_version_edit_box'):
                        self.main_app.sw_version_edit_box.setText(sw_version)
                    elif hasattr(self.main_app, 'software_version_edit_box'):
                        self.main_app.software_version_edit_box.setText(sw_version)
                    if hasattr(self.main_app, 'machine_edit_box'):
                        self.main_app.machine_edit_box.setText(machine)
                except Exception as e:
                    available_attrs = [attr for attr in dir(self.main_app) if not attr.startswith('_')]
                    raise Exception(f"Failed To Update Main UI: {str(e)}")
            if self.checkbox_close.isChecked():
                self.close_requested.emit()
                self.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed To Populate SID: {str(e)}")
# ------------------------------------------------------------------------
    def export_to_csv(self):
        import csv
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "SID", "Site Name", "SP IP", "Host IP", "Display IP",
                        "Tunnel", "Modality", "Port", "Machine", "SW Version", "Note"
                    ])
                    database = self.database.read_database()
                    for entry in database.get('index', []):
                        writer.writerow([
                            entry.get('sid', ''),
                            entry.get('site_name', ''),
                            ', '.join(entry.get('sp_ip', [])),
                            ', '.join(entry.get('host_ip', [])),
                            ', '.join(entry.get('display_ip', [])),
                            ', '.join(entry.get('tunnel', [])),
                            ', '.join(entry.get('modality', [])),
                            entry.get('port', ''),
                            entry.get('machine', ''),
                            entry.get('sw_version', ''),
                            ', '.join(entry.get('note', []))
                        ])
                QMessageBox.information(self, "Success", "Data exported to CSV.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed To Export CSV: {str(e)}")
# ------------------------------------------------------------------------
    #def on_close(self):
        #self.close_requested.emit()
        #self.close()
# ------------------------------------------------------------------------
    def add_entry(self):
        dialog = EntryDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                entry = dialog.get_entry()
                self.database.add_entry(entry)
                self.load_entries()
                self.sid_input.clear()
                self.site_name_input.clear()
                QMessageBox.information(self, "Success", "Entry Added Successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Database Error: {str(e)}")
# ------------------------------------------------------------------------
    def edit_entry(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Please Select An Entry To Edit")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
            msg.exec_()
            return
        old_sid = self.table.item(current_row, 0).text()
        entries = self.database.find_by_sid(old_sid)
        if not entries:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Entry Not Found")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
            msg.exec_()
            return
        entry = entries[0]
        dialog = EntryDialog(self, entry)
        if dialog.exec_() == QDialog.Accepted:
            try:
                updated_entry = dialog.get_entry()
                self.database.update_entry(old_sid, updated_entry)
                self.load_entries()
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Database error: {str(e)}")
                msg.setIcon(QMessageBox.Critical)
                msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
                msg.exec_()
# ------------------------------------------------------------------------
    def delete_entry(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Please Select a SID to delete")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
            msg.exec_()
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Deletion")
        msg.setText("Are You Sure You Want To Delete This SID?")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
        reply = msg.exec_()
        if reply == QMessageBox.Yes:
            sid = self.table.item(current_row, 0).text()
            try:
                self.database.delete_entry_by_sid(sid)
                self.load_entries()
                msg = QMessageBox(self)
                msg.setWindowTitle("Success")
                msg.setText(f"Entry with SID {sid} has been deleted.")
                msg.setIcon(QMessageBox.Information)
                msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
                msg.exec_()
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Failed To Delete: {str(e)}")
                msg.setIcon(QMessageBox.Critical)
                msg.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
                msg.exec_()
# ------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = SIDDatabaseWindow()
    window.show()
    sys.exit(app.exec_())
# ------------------------------------------------------------------------