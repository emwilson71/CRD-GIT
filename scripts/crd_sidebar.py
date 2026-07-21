"""
crd_sidebar.py for CRD (ew)
Embedded Sidebar for Diagnostics
Updated to parse 6-field Apptree.dat format (A,B,C,D,E,F,G)
Added double-click execution for tree items
2025.10.14 Added buttons in QTreeWidget and argument support from apptree.dat, JS
Version 1.03 Refactored 10/25/25 - 3-state flag A, improved logic

Flag A States:
  0 = Hidden (not shown)
  1 = Visible and executable (normal)
  2 = Always visible (even if criteria not met), still executable
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
        """Expand/collapse parent items on single click"""
        if item.childCount() > 0: 
            item.setExpanded(not item.isExpanded())

    def load_apptree_data(self, modality=None):
        """
        Load apptree.dat and build tree structure.
        Flag A: 0=hidden, 1=visible/executable (requires criteria), 2=always visible/executable (bypasses criteria)
        
        If modality is empty/None: load ONLY flag_a=2 entries (criteria bypassed)
        If modality is valid: load both flag_a=1 and flag_a=2 entries
        """
        self.clear()
        logger.debug(f"[SIDEBAR] Loading with Modality: {modality}")
        
        # Determine if criteria is met (modality is set)
        criteria_met = bool(modality and modality in ["MR", "CT", "VL", "XR"])
        
        if not criteria_met:
            # Load ONLY flag_a=2 entries (always-show items) from all modalities
            logger.info(f"[SIDEBAR] Criteria not met (modality empty). Loading flag_a=2 items only.")
            self._load_flag_2_entries()
            return
        
        # Criteria is met: load normal file for this modality (both flag_a=1 and flag_a=2)
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "config", 
            f"{modality.lower()}_apptree.dat"
        )
        
        if not os.path.exists(file_path):
            logger.error(f"[SIDEBAR] File not found: {file_path}")
            return
        
        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
            
            parent_items = {}  # Track created parent items by path
            item_count = 0
            
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip comments and empty lines
                if line.startswith("#") or not line:
                    continue
                
                # Parse fields
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    logger.warning(f"[SIDEBAR] Line {line_num}: Invalid format (need 6+ fields): {line}")
                    continue
                
                flag_a, flag_b, file_modality, path, module_folder, filename = parts[:6]
                argument = parts[6] if len(parts) > 6 else ""
                
                # Check flag A: with criteria met, accept both 1 and 2
                if flag_a not in ["1", "2"]:
                    logger.debug(f"[SIDEBAR] Line {line_num}: Skipped (flag_a={flag_a})")
                    continue
                
                # Check modality matches
                if file_modality != modality:
                    logger.debug(f"[SIDEBAR] Line {line_num}: Modality mismatch ({file_modality} != {modality})")
                    continue
                
                # Validate filename extension
                if not filename or not any(filename.endswith(ext) for ext in [".py", ".pyw", ".exe"]):
                    logger.warning(f"[SIDEBAR] Line {line_num}: Invalid filename: {filename}")
                    continue
                
                # Validate paths exist
                if not module_folder or not path:
                    logger.warning(f"[SIDEBAR] Line {line_num}: Missing module_folder or path")
                    continue
                
                if not os.path.exists(module_folder):
                    logger.warning(f"[SIDEBAR] Line {line_num}: Module folder not found: {module_folder}")
                    continue
                
                # Build tree hierarchy
                path_parts = path.split("/")
                
                for i, part in enumerate(path_parts):
                    current_path = "/".join(path_parts[:i+1])
                    parent_path = "/".join(path_parts[:i])
                    
                    # Skip if already created
                    if current_path in parent_items:
                        continue
                    
                    is_leaf = (i == len(path_parts) - 1)
                    display_name = part
                    
                    item = QTreeWidgetItem([display_name])
                    
                    # Store data only on leaf nodes
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
                        # Parent nodes are selectable but non-executable
                        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                    
                    # Add to tree
                    if parent_path == "":
                        # Top-level item
                        self.addTopLevelItem(item)
                        item.setExpanded(True)
                    else:
                        # Child of existing parent
                        if parent_path in parent_items:
                            parent_items[parent_path].addChild(item)
                    
                    parent_items[current_path] = item
            
            logger.info(f"[SIDEBAR] Loaded {file_path} for {modality}: {item_count} executable items")
            self.update()
            self.viewport().update()
            self.repaint()
            
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to load {file_path}: {e}", exc_info=True)

# ------------------------------------------------------------------------
    def _load_flag_2_entries(self):
        """
        Load ONLY flag_a=2 entries (always-show) from all modality files.
        Used when criteria is not met (modality is empty).
        """
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
                        
                        # ONLY load flag_a=2 entries
                        if flag_a != "2":
                            continue
                        
                        # Validate filename extension
                        if not filename or not any(filename.endswith(ext) for ext in [".py", ".pyw", ".exe"]):
                            continue
                        
                        # Validate paths
                        if not module_folder or not path:
                            continue
                        
                        if not os.path.exists(module_folder):
                            logger.debug(f"[SIDEBAR] Module folder not found: {module_folder}")
                            continue
                        
                        # Build tree hierarchy
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
                    logger.warning(f"[SIDEBAR] Error reading {file_path}: {e}")
            
            logger.info(f"[SIDEBAR] Loaded {item_count} flag_a=2 (always-show) items from all modalities")
            self.update()
            self.viewport().update()
            self.repaint()
            
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to load flag_a=2 entries: {e}", exc_info=True)

# ------------------------------------------------------------------------
    def on_execute(self, item=None):
        """
        Execute application when item is double-clicked.
        Respects flags A and B for visibility and confirmation.
        """
        selected_item = item if item else (self.selectedItems()[0] if self.selectedItems() else None)
        
        if not selected_item:
            logger.error("[SIDEBAR] No item selected")
            return
        
        data = selected_item.data(0, Qt.UserRole)
        
        if not data:
            logger.debug("[SIDEBAR] Item selected is not executable (parent folder)")
            return
        
        flag_a = data.get("A")
        flag_b = data.get("B")
        module_folder = data.get("E")
        filename = data.get("F")
        argument = data.get("G", "")
        
        # Validate flag A (should be 1 or 2 at this point)
        if flag_a not in ["1", "2"]:
            logger.error(f"[SIDEBAR] Invalid flag_a for execution: {flag_a}")
            return
        
        # Validate paths
        if not module_folder or not filename:
            logger.error(f"[SIDEBAR] Invalid paths: module_folder={module_folder}, filename={filename}")
            return
        
        app_path = os.path.normpath(os.path.join(module_folder, filename))
        
        if not os.path.exists(app_path):
            logger.error(f"[SIDEBAR] App path not found: {app_path}")
            return
        
        if os.path.isdir(app_path):
            logger.error(f"[SIDEBAR] Path is a directory, not executable: {app_path}")
            return
        
        # Execute with or without confirmation based on flag B
        if flag_b == "1":
            self.show_popup(app_path, argument)
        else:
            self.execute_app(app_path, argument)

# ------------------------------------------------------------------------
    def show_popup(self, app_path, argument):
        """Show confirmation dialog before executing"""
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
        """
        Execute Python script or EXE with optional arguments.
        Arguments are space-separated in the DAT file.
        """
        try:
            # Parse arguments (space-separated string to list)
            arg_list = argument.split() if argument else []
            
            if app_path.endswith(".py") or app_path.endswith(".pyw"):
                cmd = ["pythonw", app_path] + arg_list
                subprocess.Popen(cmd, shell=False)
                logger.info(f"[SIDEBAR] Executed: {app_path} with args: {arg_list}")
                
            elif app_path.endswith(".exe"):
                cmd = [app_path] + arg_list
                subprocess.Popen(cmd, shell=False)
                logger.info(f"[SIDEBAR] Executed: {app_path} with args: {arg_list}")
            else:
                logger.error(f"[SIDEBAR] Unknown file type: {app_path}")
                
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to execute {app_path}: {e}", exc_info=True)

# ------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
    widget = AppTreeWidget()
    widget.show()
    sys.exit(app.exec_())
# ------------------------------------------------------------------------