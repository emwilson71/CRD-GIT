# --------------------------------------------------------------------------
# X
"""
cping_telnet_menu
Launches cping_telnet sessions
ewilson@us.medical.canon
Version 1.00 Updated 11/12/25 
"""
# --------------------------------------------------------------------------
import sys
import subprocess
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
)
from PyQt5.QtCore import Qt
from mod_stylesheets import BUTTON_STYLE, STD_LABEL_STYLE, COMBOBOX_STYLE
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cPing Telnet Launcher")
        self.setGeometry(100, 100, 300, 200)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        self.label = QLabel("Select Number of Instance(s)")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(STD_LABEL_STYLE)  
        layout.addWidget(self.label)

        self.single_button = QPushButton("Open Single Instance")
        self.single_button.setStyleSheet(BUTTON_STYLE)  
        self.single_button.clicked.connect(self.launch_single)
        layout.addWidget(self.single_button)

        self.combo = QComboBox()
        self.combo.addItems([str(i) for i in range(2, 7)])  
        self.combo.setStyleSheet(COMBOBOX_STYLE)
        layout.addWidget(self.combo)

        self.multi_button = QPushButton("Open Multiple Instances")
        self.multi_button.setStyleSheet(BUTTON_STYLE) 
        self.multi_button.clicked.connect(self.launch_multiple)
        layout.addWidget(self.multi_button)

        self.setStyleSheet("QMainWindow { background-color: #202020; }")
# --------------------------------------------------------------------------
    def launch_single(self):
        try:
            subprocess.Popen([sys.executable, "cping_telnet.py", "--x", "100", "--y", "100"])
            self.close()  
        except FileNotFoundError:
            self.label.setText("ERROR: cping_telnet.py Not Found")
# --------------------------------------------------------------------------
    def launch_multiple(self):
        num_instances = int(self.combo.currentText())
        processes = []
        try:
            for i in range(num_instances):
                x_pos = 100 + i * 100
                y_pos = 100 + i * 100
                proc = subprocess.Popen([
                    sys.executable, "cping_telnet.py",
                    "--x", str(x_pos),
                    "--y", str(y_pos)
                ])
                processes.append(proc)
            self.close()  
        except FileNotFoundError:
            self.label.setText("ERROR: cping_telnet.py Not Found")
# --------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
# --------------------------------------------------------------------------