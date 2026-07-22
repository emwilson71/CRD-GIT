"""
crd_sidebar.py for CRD (ew)
Embedded Sidebar for Diagnostics
Updated to parse 6-field Apptree.dat format (A,B,C,D,E,F,G)
Added double-click execution for tree items
2025.10.14 Added buttons in QTreeWidget and argument support from apptree.dat, JS
Version 1.03 Updated 7/22/26

Changed A
  0 = Hidden
  1 = Visible and Executable
  2 = Always Visible
"""
# ------------------------------------------------------------------------
import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QTreeWidget, QTreeWidgetItem, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from crd_embedded import CRDLogger, Styles
# ------------------------------------------------------------------------
# LOGGING
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
# EMBEDDED SIDEBAR
class AppTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_apptree_data()  
# ------------------------------------------------------------------------
    def init_ui(self):
        self.setStyleSheet(Styles.SIDEBAR_STYLE)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.itemDoubleClicked.connect(self.on_execute)
        self.itemClicked.connect(self.toggle_parent)
# ------------------------------------------------------------------------
    def toggle_parent(self, item, column):
        if item.childCount() > 0: 
            item.setExpanded(not item.isExpanded())
# ------------------------------------------------------------------------
    def load_apptree_data(self, modality=None):
        self.clear()
        logger.debug(f"[SIDEBAR] Loading With Modality: {modality}")
        criteria_met = bool(modality and modality in ["MR", "CT", "VL", "XR"])
        if not criteria_met:
            self._load_flag_2_entries()
            return
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "config", 
            f"{modality.lower()}_apptree.dat"
        )
        if not os.path.exists(file_path):
            logger.error(f"[SIDEBAR] File Not Found: {file_path}")
            return  
        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
            
            parent_items = {} 
            item_count = 0
            
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    logger.warning(f"[SIDEBAR] Line {line_num}: Invalid Format - {line}")
                    continue
                
                flag_a, flag_b, file_modality, path, module_folder, filename = parts[:6]
                argument = parts[6] if len(parts) > 6 else ""
                if flag_a not in ["1", "2"]:
                    continue
                if file_modality != modality:
                    continue
                if not filename or not any(filename.endswith(ext) for ext in [".py", ".pyw", ".exe"]):
                    continue
                if not module_folder or not path:
                    continue
                if not os.path.exists(module_folder):
                    continue    
                path_parts = path.split("/")
                for i, part in enumerate(path_parts):
                    current_path = "/".join(path_parts[:i+1])
                    parent_path = "/".join(path_parts[:i])
                    if current_path in parent_items:
                        continue
                    
                    is_leaf = (i == len(path_parts) - 1)
                    display_name = part
                    
                    item = QTreeWidgetItem([display_name])
                    
                    if is_leaf:
                        item.setData(0, Qt.UserRole, {
                            "A": flag_a,
                            "B": flag_b,
                            "C": file_modality,
                            "D": path,
                            "E": module_folder,
                            "F": filename,
                            "G": argument
                        })
                        item_count += 1
                    else:
                        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

                    if parent_path == "":
                        self.addTopLevelItem(item)
                        item.setExpanded(True)
                    else:
                        if parent_path in parent_items:
                            parent_items[parent_path].addChild(item)
                    
                    parent_items[current_path] = item
            self.update()
            self.viewport().update()
            self.repaint()
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to Load {file_path}: {e}", exc_info=True)

# ------------------------------------------------------------------------
    def _load_flag_2_entries(self):
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        modalities = ["mr", "ct", "vl", "xr"]
        parent_items = {}
        item_count = 0
        try:
            for modality_lower in modalities:
                file_path = os.path.join(config_dir, f"{modality_lower}_apptree.dat")
                if not os.path.exists(file_path):
                    continue
                try:
                    with open(file_path, "r") as file:
                        lines = file.readlines()
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) < 6:
                            continue
                        
                        flag_a, flag_b, file_modality, path, module_folder, filename = parts[:6]
                        argument = parts[6] if len(parts) > 6 else ""
                        if flag_a != "2":
                            continue
                        if not filename or not any(filename.endswith(ext) for ext in [".py", ".pyw", ".exe"]):
                            continue
                        if not module_folder or not path:
                            continue
                        if not os.path.exists(module_folder):
                            logger.debug(f"[SIDEBAR] Module folder not found: {module_folder}")
                            continue

                        path_parts = path.split("/")
                        
                        for i, part in enumerate(path_parts):
                            current_path = "/".join(path_parts[:i+1])
                            parent_path = "/".join(path_parts[:i])
                            
                            if current_path in parent_items:
                                continue
                            
                            is_leaf = (i == len(path_parts) - 1)
                            display_name = part
                            
                            item = QTreeWidgetItem([display_name])
                            
                            if is_leaf:
                                item.setData(0, Qt.UserRole, {
                                    "A": flag_a,
                                    "B": flag_b,
                                    "C": file_modality,
                                    "D": path,
                                    "E": module_folder,
                                    "F": filename,
                                    "G": argument
                                })
                                item_count += 1
                            else:
                                item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                            
                            if parent_path == "":
                                self.addTopLevelItem(item)
                                item.setExpanded(True)
                            else:
                                if parent_path in parent_items:
                                    parent_items[parent_path].addChild(item)
                            
                            parent_items[current_path] = item
                
                except Exception as e:
                    logger.warning(f"[SIDEBAR] Error Reading {file_path}: {e}")
            self.update()
            self.viewport().update()
            self.repaint()
            
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to Load {e}", exc_info=True)
# ------------------------------------------------------------------------
    def on_execute(self, item=None):
        selected_item = item if item else (self.selectedItems()[0] if self.selectedItems() else None)
        if not selected_item:
            return
        data = selected_item.data(0, Qt.UserRole)
        if not data:
            return
        flag_a = data.get("A")
        flag_b = data.get("B")
        module_folder = data.get("E")
        filename = data.get("F")
        argument = data.get("G", "")
        
        if flag_a not in ["1", "2"]:
            logger.error(f"[SIDEBAR] Invalid Flag {flag_a}")
            return
        
        if not module_folder or not filename:
            logger.error(f"[SIDEBAR] Invalid Paths module_folder={module_folder}, filename={filename}")
            return
        
        app_path = os.path.normpath(os.path.join(module_folder, filename))
        
        if not os.path.exists(app_path):
            logger.error(f"[SIDEBAR] App Path Not Found: {app_path}")
            return
        
        if os.path.isdir(app_path):
            logger.error(f"[SIDEBAR] Path is a Directory {app_path}")
            return

        if flag_b == "1":
            self.show_popup(app_path, argument)
        else:
            self.execute_app(app_path, argument)
# ------------------------------------------------------------------------
    def show_popup(self, app_path, argument):
        msg_box = QMessageBox(self)
        msg_box.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
        msg_box.setWindowTitle("Confirmation")
        msg_box.setText("DO YOU WANT TO PROCEED?")
        informative_text = (
            "Can you verify before executing that\n"
            "the customer is not scanning and they\n"
            "acknowledge you are running tests."
        )
        msg_box.setInformativeText(informative_text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        msg_box.setStyleSheet(Styles.BUTTON_STYLE)
        
        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Ok:
            self.execute_app(app_path, argument)
# ------------------------------------------------------------------------
    def execute_app(self, app_path, argument):
        try:
            arg_list = argument.split() if argument else []
            
            if app_path.endswith(".py") or app_path.endswith(".pyw"):
                cmd = ["pythonw", app_path] + arg_list
                subprocess.Popen(cmd, shell=False)
                logger.info(f"[SIDEBAR] Executed: {app_path} with args: {arg_list}")
                
            elif app_path.endswith(".exe"):
                cmd = [app_path] + arg_list
                subprocess.Popen(cmd, shell=False)
                logger.info(f"[SIDEBAR] Executed: {app_path} with args: {arg_list}")
                
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to Execute {app_path}: {e}", exc_info=True)

# ------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
    widget = AppTreeWidget()
    widget.show()
    sys.exit(app.exec_())
# ------------------------------------------------------------------------