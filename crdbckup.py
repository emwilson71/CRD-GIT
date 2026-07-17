# ----------------------------------------------------------------------  
"""  
Title: Project Save Python  
Description: Saves all .py and .dat files in root and subdirectories
12/17/24 (ew)
Notes:  
"""  
#-----------------------------------------------------------------------  
import os  
import sys
import time
import time  
import re
import zipfile
import traceback
import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,   
                             QLabel, QLineEdit, QPushButton, QTextEdit,   
                             QListWidget, QSizePolicy,QMessageBox)  
from PyQt5.QtCore import Qt, QSize  
from PyQt5.QtGui import QPalette, QColor  
# CLASS PROJECT BACKUP -------------------------------------------------  
class ProjectBackupTool(QWidget):  
    def __init__(self):  
        super().__init__()  
        self.initUI()  
# SETUP UI       
    def initUI(self):   
        self.setStyleSheet("""  
            QWidget {  
                background-color: #2b2b2b;  
                color: #ffffff;  
                font-size: 12px;  
            }  
            QLineEdit, QTextEdit, QListWidget {  
                background-color: #3c3f41;  
                color: #ffffff;  
                border: 1px solid #5a5a5a;  
                padding: 5px;  
            }  
            QPushButton {  
                background-color: #365880;  
                color: #ffffff;  
                border: none;  
                padding: 8px;  
                margin: 5px 0;  
            }  
            QPushButton:hover {  
                background-color: #4b7399;  
            }  
            QLabel {  
                color: #cccccc;  
            }  
        """)  
        
        self.setWindowTitle('PROJECT BACKUP TOOL')  
        self.setGeometry(300, 300, 700, 400)   
        main_layout = QVBoxLayout()  
    
        project_dir_layout = QHBoxLayout()  
        self.rootLabel = QLabel('Project Directory:')  
        project_dir_layout.addWidget(self.rootLabel)  
        
        self.rootPathEdit = QLineEdit(os.getcwd())  
        project_dir_layout.addWidget(self.rootPathEdit)  
        main_layout.addLayout(project_dir_layout)  
    
        content_layout = QHBoxLayout()  
        

        left_layout = QVBoxLayout()  
        self.zipListLabel = QLabel('BACKUP ZIP FILES:')  
        left_layout.addWidget(self.zipListLabel)  
        
        self.zipFileList = QListWidget()  
        self.zipFileList.setFixedWidth(200)  
        self.zipFileList.itemClicked.connect(self.show_version_notes)  
        left_layout.addWidget(self.zipFileList)  
          
        self.populate_zip_list()  
        
        left_widget = QWidget()  
        left_widget.setLayout(left_layout)  
        content_layout.addWidget(left_widget)  
        
        right_layout = QVBoxLayout()  

        original_label = QLabel('FILE NOTES:')  
        right_layout.addWidget(original_label)  

        self.originalNotesView = QTextEdit()  
        self.originalNotesView.setReadOnly(True)  
        self.originalNotesView.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  
        right_layout.addWidget(self.originalNotesView)  
        

        new_label = QLabel('BACKUP NOTES:')  
        right_layout.addWidget(new_label)  
        
        self.newNotesEdit = QTextEdit()  
        self.newNotesEdit.setFixedWidth(450)  
        right_layout.addWidget(self.newNotesEdit)  
        

        self.backupButton = QPushButton('CREATE BACKUP')  
        self.backupButton.clicked.connect(self.create_backup)  
        right_layout.addWidget(self.backupButton)  
        
        right_widget = QWidget()  
        right_widget.setLayout(right_layout)  
        content_layout.addWidget(right_widget)  
        

        main_layout.addLayout(content_layout)  
        self.setLayout(main_layout)  
#-----------------------------------------------------------------------         
    def populate_zip_list(self):  
        self.zipFileList.clear()  
        backup_dir = os.path.join(os.getcwd(), '.backup')   
        if not os.path.exists(backup_dir):  
            return  
        
        zip_files = [  
            (f, os.path.getctime(os.path.join(backup_dir, f)))   
            for f in os.listdir(backup_dir)   
            if f.endswith('.zip') and f.startswith('projectsave')  
        ]  
        
        sorted_zip_files = sorted(zip_files, key=lambda x: x[1])  
        self.zipFileList.addItems([f[0] for f in sorted_zip_files])     
#----------------------------------------------------------------------- 
    def create_backup(self):  
        try:  
            backup_dir = os.path.join(os.getcwd(), '.backup')  
            os.makedirs(backup_dir, exist_ok=True)  
            version = self.get_version_number(backup_dir)  
            root_dir = self.rootPathEdit.text()  
            version_notes = self.newNotesEdit.toPlainText().strip()  
            if not version_notes:  
                  
                version_notes = f"Backup created on {datetime.datetime.now().strftime('%A %m%d%Y %H:%M')}"  
            zip_filename = os.path.join(backup_dir, f'projectsave{version}.zip')  
             
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:  
                zipf.writestr('version.txt', version_notes)  
                files_added = 0  
                for root, dirs, files in os.walk(root_dir):  
                    dirs[:] = [d for d in dirs if not re.match(r'^python', d, re.IGNORECASE)]  
                    for file in files:  
                        file_path = os.path.join(root, file)  
                        if (file.endswith(('.py', '.dat', '.json', '.enc', '.key', '.txt', '.ico', '.html','.png','.jpg')) and   
                            self.should_include_file(file_path, root_dir)):  
                            try:  
                                archive_path = os.path.relpath(file_path, root_dir)  
                                zipf.write(file_path, archive_path)  
                                files_added += 1  
                                print(f"Added file: {file_path}")  
                            
                            except Exception as file_error:  
                                print(f"Error adding file {file_path}: {file_error}")  

                QMessageBox.information(  
                    self,   
                    "Backup Successful",   
                    f"Backup created: {zip_filename}\n"  
                    f"Total files added: {files_added}\n"  
                    f"Version Notes: {version_notes}"  
                )  
            self.populate_zip_list()  
            self.close()  
        
        except Exception as e:  
            QMessageBox.critical(  
                self,   
                "Backup Error",   
                f"An error occurred during backup:\n{str(e)}"  
            )   
            traceback.print_exc()
#-----------------------------------------------------------------------                 
    def show_version_notes(self, item):   
        backup_dir = os.path.join(os.getcwd(), '.backup')  
        zip_path = os.path.join(backup_dir, item.text())  
        try:  
            with zipfile.ZipFile(zip_path, 'r') as zipf:  
                if 'version.txt' in zipf.namelist():  
                    version_notes = zipf.read('version.txt').decode('utf-8')  
                    self.originalNotesView.setPlainText(version_notes)  
                else:  
                    self.originalNotesView.setPlainText("No version notes found.")  
        except Exception as e:  
            self.originalNotesView.setPlainText(f"Error reading version notes: {str(e)}")  
        self.newNotesEdit.clear()  
            
        def get_version_number(self, backup_dir):  
            version = 1  
            while os.path.exists(os.path.join(backup_dir, f'projectsave{version}.zip')):  
                version += 1  
            return version      
#-----------------------------------------------------------------------         
    def should_include_file(self, file_path, root_path):  
        max_file_size = 100 * 1024 * 1024  
        excluded_dir_patterns = [  
            r'python',  
            r'__pycache__',  
            r'\.git',  
            r'\.venv',  
            r'venv',  
            r'env',  
            r'node_modules',  
            r'build',  
            r'dist',  
        ]  
        excluded_extensions = [  
            '.pyc',   
            '.log',   
            '.tmp',   
            '.bak'  
        ]  
        try:  
            if os.path.getsize(file_path) > max_file_size:  
                return False  
        except Exception as e:  
            return False  
        rel_path = os.path.relpath(file_path, root_path)  
        for pattern in excluded_dir_patterns:  
            if re.search(pattern, rel_path, re.IGNORECASE):  
                return False  
        _, ext = os.path.splitext(file_path)  
        if ext.lower() in excluded_extensions:  
            return False  
        return True
#----------------------------------------------------------------------- 
    def get_version_number(self, backup_dir):   
        os.makedirs(backup_dir, exist_ok=True)  
        existing_backups = [  
            f for f in os.listdir(backup_dir)   
            if f.startswith('projectsave') and f.endswith('.zip')  
        ]  
        if not existing_backups:  
            return 1  
        try:  
            versions = [  
                int(f.replace('projectsave', '').replace('.zip', ''))   
                for f in existing_backups  
            ] 
            return max(versions) + 1  
        
        except (ValueError, TypeError):
            
            return int(time.time())
#----------------------------------------------------------------------- 
def main():  
    app = QApplication(sys.argv)  
    app.setStyle("Fusion")  
    palette = QPalette()  
    palette.setColor(QPalette.Window, QColor(53, 53, 53))  
    palette.setColor(QPalette.WindowText, Qt.white)  
    palette.setColor(QPalette.Base, QColor(25, 25, 25))  
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))  
    palette.setColor(QPalette.ToolTipBase, Qt.white)  
    palette.setColor(QPalette.ToolTipText, Qt.white)  
    palette.setColor(QPalette.Text, Qt.white)  
    palette.setColor(QPalette.Button, QColor(53, 53, 53))  
    palette.setColor(QPalette.ButtonText, Qt.white)  
    palette.setColor(QPalette.BrightText, Qt.red)  
    palette.setColor(QPalette.Link, QColor(42, 130, 218))  
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))  
    palette.setColor(QPalette.HighlightedText, Qt.black)  
    app.setPalette(palette)  
    
    backup_tool = ProjectBackupTool()  
    backup_tool.show()  
    sys.exit(app.exec())  

if __name__ == '__main__':  
    main()
#----------------------------------------------------------------------- 