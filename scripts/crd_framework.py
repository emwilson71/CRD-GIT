# ----------------------------------------------------------------------
"""X
crd_framework.py for CRD (ew)
Version 1.10 Updated 04/15/25
"""
# ----------------------------------------------------------------------
# LIBRARIES
import sys, os, logging, time, threading  
import configparser, importlib   
import subprocess, socket  
from typing import Optional
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QTabWidget,  
                             QMessageBox, QStackedWidget, QMainWindow, QTreeWidget)  
from PyQt5.QtGui import QColor, QPainter, QBrush  
from PyQt5.QtCore import QSize, Qt, QUrl, QObject, pyqtSignal, QThread
from PyQt5.QtWebEngineWidgets import QWebEngineView
# MODULES
from crd_embedded import CRDLogger
# ----------------------------------------------------------------------
crd_logger = CRDLogger("CRD")  
logger = crd_logger.get_logger()  
# CLASS TAB MANAGER ----------------------------------------------------         
class TabManager:  
    def __init__(self, tab_widget):  
        self.tab_widget = tab_widget  
        self.scripts = {}  
        self.current_script = None  
        self.ini_file_path = os.path.join("..", "config", "tabfiles.ini")  
        
        logging.basicConfig(  
            level=logging.DEBUG, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  
        )  
        self.logger = logging.getLogger(__name__)  
# ADD TABS 
    def add_tabs(self):   
        try:  
            for script_name, script_instance in self.scripts.items():  
                self.tab_widget.addTab(script_instance, script_name)  
        except Exception as e:  
            self.logger.error(f"[FRAMEWORK] Adding Tabs: {e}")
# TAB INIT           
    def init_program_tab(self):  
        try:  
            self.program_tab = QWidget()  
            self.program_tab_layout = QVBoxLayout(self.program_tab)  
            self.script_container = QWidget()  
            self.script_container_layout = QVBoxLayout(self.script_container)  
            self.program_tab_layout.addWidget(self.script_container)           
            self.close_script_button = QPushButton("Close Script")  
            self.close_script_button.setStyleSheet("""  
                QPushButton {  
                    background-color: #404040;  
                    padding: 4px;  
                    color: white;  
                    font-size: 14px;  
                    font-weight: bold;  
                    border-radius: 4px;  
                }  
                QPushButton:hover {  
                    background-color: RED;  
                }  
            """)  
            self.close_script_button.clicked.connect(self.close_current_script)  
            self.close_script_button.setVisible(False)  
            self.program_tab_layout.addWidget(self.close_script_button)  
        
            self.tab_widget.addTab(self.program_tab, "PROGRAM")  
        except Exception as e:  
            self.logger.error(f"[FRAMEWORK] Initializing Program Tab: {e}")
#
    def systemcred_button_click(self):  
        self.close_current_script()  
#
    def close_current_script(self):  
        QtWidgets.QApplication.quit()  
#    
    def load_sid_manager(self):  
        try:  
            if 'sidmanager' not in self.scripts:  
                self.logger.info("[FRAMEWORK] SID Manager Not In Scripts")  
                try:   
                    sid_script = self.load_script('sidmanager')  
                    self.scripts['sidmanager'] = sid_script  
                except Exception as load_error:  
                    self.logger.error(f"[FRAMEWORK] Loading SID Manager Script: {load_error}")  
                    import traceback  
                    traceback.print_exc()  
                    raise   
            sid_script = self.scripts['sidmanager']  
            if self.tab_widget.indexOf(sid_script) == -1:  
                self.tab_widget.addTab(sid_script, "SID Manager")  
            self.tab_widget.setCurrentWidget(sid_script)          
        except Exception as e:  
            self.logger.error(f"[FRAMEWORK] Loading SID Manager: {e}")  
# CHECK IF LOADED
    def is_script_loaded(self):  
        return self.current_script is not None
# ADD SCRIPT TO TAB 
    def add_script(self, script_name, script_instance):  
        try:  
            self.scripts[script_name] = script_instance  
        except Exception as e:  
            self.logger.error(f"[FRAMEWORK] Adding Script {script_name}: {e}")
# LOAD SCRIPT
    def load_script(self, script_name):  
        try:  
            if '.' in script_name:    
                module_path, class_name = script_name.rsplit('.', 1)  
                script_module = importlib.import_module(module_path)  
                script_class = getattr(script_module, class_name.capitalize())  
            else:    
                if script_name == 'main':  
                    script_module = sys.modules[__name__]  
                else:  
                    script_module = importlib.import_module(script_name)  
                script_class = getattr(script_module, script_name.capitalize())  
            script_instance = script_class()  
            return script_instance         
        except (ImportError, AttributeError) as e:  
            self.logger.error(f"[FRAMEWORK] Loading Script {script_name}: {e}")  
            raise  
# LOAD PROGRAM
    def load_program_script(self, script_name):   
        try:   
            self.close_current_script()  
            script_instance = self.scripts.get(script_name)  
            
            if script_instance:  
                for i in reversed(range(self.script_container_layout.count())):   
                    widget = self.script_container_layout.itemAt(i).widget()  
                    if widget:  
                        widget.setParent(None)  
                        widget.deleteLater()   
                self.script_container_layout.addWidget(script_instance)  
                self.current_script = script_instance  
                self.close_script_button.setVisible(True)  
                self.tab_widget.setCurrentWidget(self.program_tab)                
                self.logger.info(f"[FRAMEWORK] Loaded Script: {script_name}")          
        except Exception as e:  
            self.logger.error(f"[FRAMEWORK] Error Loading Script {script_name}: {e}")  
# CLOSE CURRENT SCRIPT
    def close_current_script(self):  
        if self.current_script:  
            try:  
                self.script_container_layout.removeWidget(self.current_script)  
                self.current_script.setParent(None)  
                self.current_script.deleteLater()  
                self.current_script = None  
                self.close_script_button.setVisible(False)                 
            except Exception as e:  
                self.logger.error(f"[FRAMEWORK] Error Closing Script: {e}")  
# BROWSE SCRIPTS
    def get_available_scripts(self):  
        return list(self.scripts.keys())
# ----------------------------------------------------------------------
class WorkerSignals(QObject):  
    finished = pyqtSignal()  
    error = pyqtSignal(str)
# CLASS BUTTON STATE ---------------------------------------------------
class ButtonState:  
    def __init__(self):  
        self.states = {}  
#
    def set_state(self, button_name: str, state: str):  
        self.states[button_name] = state  
#
    def get_state(self, button_name: str) -> Optional[str]:  
        return self.states.get(button_name)
# CLASS APPLICATION FRAMEWORK ------------------------------------------
class ApplicationFramework(QMainWindow):  
    def __init__(self, app_instance):  
        super().__init__()
        self.connectivity_monitor = None  
        self.connectivity_led = None  
        script_dir = os.path.dirname(os.path.abspath(__file__))  
        parent_dir = os.path.dirname(script_dir)  
        debug_html_dirs = [  
            os.path.join(parent_dir, 'html'),  
            os.path.join(script_dir, '..', 'html')  
        ]           
        try:  
            from PyQt5.QtWebEngineWidgets import QWebEngineView  
            web_view_exists = hasattr(self, 'web_view')         
            if web_view_exists and self.web_view is not None:  
                pass    
        except ImportError:    
            self.explore_project_structure() 
            self.app_instance = app_instance  
            try:  
                self.web_view = getattr(app_instance, 'web_view',   
                    QWebEngineView() if hasattr(app_instance, 'init_web_view') else None)               
                self.tab_widget = getattr(app_instance, 'tab_widget',   
                    QTabWidget(app_instance) if hasattr(app_instance, 'init_tabs') else None)  
                self.main_window = app_instance  
                self.tree_widget = getattr(app_instance, 'tree_widget',   
                    QTreeWidget(app_instance))  
                if hasattr(self.tree_widget, 'itemClicked'):  
                    try:  
                        self.tree_widget.itemClicked.disconnect()  
                    except TypeError:  
                        pass    
                    self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)              
            except Exception as e:  
                error_message = f"[FRAMEWORK] Failed To Initialize ApplicationFramework"  
                logging.error(error_message) 
                raise  
            self.setup_additional_components()  
# GRAP HTML FILE FROM FILENAME
    def get_html_file_from_filename(self, filename):  
        try:  
            if filename.endswith('.py'):  
                filename = os.path.splitext(filename)[0]  
            html_base_dir = os.path.join(  
                os.path.dirname(os.path.dirname(__file__)),   
                'html'  
            )  
            filename_variations = [  
                filename,   
                filename.lower(),  
                filename.upper(),  
                filename.replace('_', ''), 
                filename.replace('_', '').lower(),  
                filename.replace('_', '').upper()  
            ]             
            index_html = os.path.join(html_base_dir, 'index.html')  
            return index_html if os.path.exists(index_html) else None         
        except Exception as e:   
            return None
# ----------------------------------------------------------------------
# RUN APP
    def run_application(self, app_path: str, popup: int):  
        try:  
            if popup == 1:  
                result = self.show_popup(app_path)  
                if not result:  
                    return             
            logging.info(f"[FRAMEWORK] Executing: {app_path}")  
            self.execute_app(app_path)        
        except Exception as e:  
            logging.error(f"[FRAMEWORK] Failed to execute application: {e}")  
            self.show_error(str(e))  
# POPUP TO USER
    def show_popup(self, app_path: str) -> bool:  
        msg_box = QMessageBox(self.main_window)  
        msg_box.setWindowTitle("Confirmation")  
        msg_box.setText("DO YOU WANT TO PROCEED?")         
        informative_text = (  
            "Can you verify before executing that\n"  
            "the customer is not scanning and they\n"  
            "acknowledge you are running tests."  
        )  
        msg_box.setInformativeText(informative_text)        
        msg_box.setStandardButtons(  
            QMessageBox.StandardButton.Cancel |   
            QMessageBox.StandardButton.Ok  
        )         
        msg_box.setStyleSheet(  
            "QMessageBox { background-color: white; color: black; }"  
            "QLabel { background-color: white; color: black; }"  
            "QPushButton { background-color: #202020; color: white; border: 1px solid gray; min-width: 100px; }"  
            "QPushButton:hover { background-color: red; }"  
        )  
        
        result = msg_box.exec()  
        return result == QMessageBox.StandardButton.Ok
# ON CLICK HANDLER
    def on_tree_item_clicked(self, item):  
        try:  
            data = item.data(0, Qt.ItemDataRole.UserRole)  
            if data is None: 
                return  
            try:  
                filename, full_path, *rest = data  
                base_filename = os.path.splitext(os.path.basename(full_path))[0]  
            except Exception as unpack_error:   
                return   
        except Exception as e:  
            return
#----------------------------------------------------------------
    def setup_connectivity_monitoring(self, sp_ip):  
        self.connectivity_led = ConnectivityIndicator()  
        self.connectivity_monitor = ConnectionMonitorThread(sp_ip)   
        self.connectivity_monitor.connection_status_changed.connect(  
            self.handle_connection_status  
        )   
        self.connectivity_monitor.start()  
#----------------------------------------------------------------
    def handle_connection_status(self, is_connected):  
        if self.connectivity_led:  
            self.connectivity_led.set_status(is_connected)
# STRIP DIR STRUCTURE 
    def execute_app(self, app_path: str):  
        try:  
            full_path = app_path.replace("/", "\\")             
            if not os.path.exists(full_path):  
                raise FileNotFoundError(f"The File '{full_path}' Does Not Exist.")            
            if full_path.endswith('.py'):  
                result = subprocess.run(  
                    [sys.executable, full_path],   
                    check=True,   
                    capture_output=True,   
                    text=True  
                )  
            elif full_path.endswith('.exe'):  
                result = subprocess.run(  
                    [full_path],   
                    check=True,   
                    capture_output=True,   
                    text=True  
                )  
            else:  
                raise ValueError(f"[FRAMEWORK] Unsupported File Type: '{full_path}'")  
            self.show_execution_output(result.stdout)        
        except FileNotFoundError as fnfe:  
            self.handle_error(f"[FRAMEWORK] File Not Found")        
#----------------------------------------------------------------
    def show_execution_output(self, output: str):  
        msg_box = QMessageBox(self.main_window)  
        msg_box.setWindowTitle("Execution Output")  
        msg_box.setText(output)  
        msg_box.exec()  
#----------------------------------------------------------------
    def handle_error(self, error_message: str):    
        logging.error(error_message)  
        msg_box = QMessageBox(self.main_window)  
        msg_box.setWindowTitle("Error")  
        msg_box.setText(error_message)  
        msg_box.setIcon(QMessageBox.Icon.Critical)  
        msg_box.exec()  
# SHOW THREAD ERROR IF EXISTS
    def show_error(self, error_message: str):  
        logging.error(error_message)  
        msg_box = QMessageBox(self.main_window)  
        msg_box.setWindowTitle("Thread Error")  
        msg_box.setText(error_message)  
        msg_box.setIcon(QMessageBox.Icon.Critical)  
        msg_box.exec()
#----------------------------------------------------------------