"""X
crd_sidebar.py for CRD
Embedded Sidebar for Diagnostics
Updated to parse new 6-field Apptree.dat format (A,B,C,D,E,F)
Added double-click execution for tree items
Version 1.03 Updated 05/13/25   

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
# ------------------------------------------------------------------------
    def load_apptree_data(self, modality=None):
        self.clear()
        logger.debug(f"[SIDEBAR] Loaded with Modality: {modality}")
        if not modality or modality not in ["MR", "CT", "VL", "XR"]:
            return
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", f"{modality.lower()}_apptree.dat")
        if not os.path.exists(file_path):
            logger.error(f"[SIDEBAR] File {file_path} Not Found")
            return
        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
            parent_items = {}
            item_count = 0
            for line in lines:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                parts = line.split(",")
                if len(parts) < 6:
                    logger.warning(f"[SIDEBAR] Invalid line format in {file_path}: {line}")
                    continue
                flag_a, flag_b, file_modality, path, module_folder, filename = parts
                if file_modality != modality:
                    logger.info(f"[SIDEBAR] Skipping Line {file_modality}")
                    continue
                if not filename or not (filename.endswith(".py") or filename.endswith(".pyw") or filename.endswith(".exe")): # JS Edits. 
                    logger.info(f"[SIDEBAR] Wrong Filename  {file_path}: {filename}")
                    continue
                if not module_folder:
                    continue
                path_parts = path.split("/")
                current_path = ""
                for i, part in enumerate(path_parts):
                    parent_path = "/".join(path_parts[:i])
                    current_path = "/".join(path_parts[:i+1])
                    if current_path not in parent_items:
                        display_name = path_parts[-1] if i == len(path_parts) - 1 else part
                        item = QTreeWidgetItem([display_name])
                        if i == len(path_parts) - 1:
                            item.setData(0, Qt.UserRole, {
                                "A": flag_a,
                                "B": flag_b,
                                "C": file_modality,
                                "D": path,
                                "E": module_folder,
                                "F": filename
                            })
                            item_count += 1
                        if parent_path == "":
                            self.addTopLevelItem(item)
                        else:
                            parent_items[parent_path].addChild(item)
                        parent_items[current_path] = item
            logger.info(f"[SIDEBAR] Loaded {file_path} for modality {modality}, added {item_count} items")
            self.update()
            self.viewport().update()
            self.repaint()
        except Exception as e:
            logger.error(f"[SIDEBAR] Failed to Load {file_path}: {e}")
# ------------------------------------------------------------------------
    def on_execute(self, item=None):
        selected_item = item if item else self.selectedItems()[0] if self.selectedItems() else None
        if not selected_item:
            return
        data = selected_item.data(0, Qt.UserRole)
        if not data:
            return
        flag_a = data.get("A")
        flag_b = data.get("B")
        module_folder = data.get("E")
        filename = data.get("F")
        if flag_a != "1":
            return
        if not module_folder or not filename:
            logger.error(f"[SIDEBAR] Wrong Format module_folder={module_folder}, filename={filename}")
            return
        app_path = os.path.normpath(os.path.join(module_folder, filename))
        if not os.path.exists(app_path):
            return
        if os.path.isdir(app_path):
            return
        if flag_b == "1":
            self.show_popup(app_path)
        else:
            self.execute_app(app_path)
# ------------------------------------------------------------------------
    def show_popup(self, app_path):
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
        msg_box.setStyleSheet(Styles.CONFIG_BUTTON_STYLE)
        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Ok:
            self.execute_app(app_path)
# ------------------------------------------------------------------------
    def execute_app(self, app_path):
        try:
            if app_path.endswith(".py") or app_path.endswith(".pyw"): #JS Edited if block. 
                cmd = ["pythonw", app_path]
                if app_path.endswith("x.py") or app_path.endswith("x.pyw"):  
                    cmd.append("use_current_dat")
                subprocess.Popen(cmd, shell=False)
            elif app_path.endswith(".exe"):
                subprocess.Popen(app_path, shell=False)
        except Exception as e:
            logger.error(f"[SIDEBAR] Executing {app_path}: {e}")
# ------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(Styles.MESSAGE_BOX_STYLE)
    widget = AppTreeWidget()
    widget.show()
    sys.exit(app.exec_())
# ------------------------------------------------------------------------