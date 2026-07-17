# ----------------------------------------------------------------------
import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
import importlib.util
# ----------------------------------------------------------------------
# NAME TO HEX
COLOR_MAP = {
    "Black": "#000000",
    "Dark Gray": "#202020",
    "Medium Gray": "#606060",
    "Gray": "#808080",
    "Light Gray": "#A0A0A0",
    "White": "#FFFFFF",
    "Soft White": "#F5F5F5",
    "Dark White": "#D3D3D3",
    "Red": "#FF0000",
    "Dark Red": "#8B0000",
    "Yellow": "#FFFF00",
    "Dark Yellow": "#DAA520",
    "Blue": "#0000FF",
    "Light Blue": "#00A2FF",
    "Green": "#00FF00",
    "Light Green": "#90EE90",
}
HEX_TO_NAME = {v: k for k, v in COLOR_MAP.items()}
# ----------------------------------------------------------------------
def load_styles():
    spec = importlib.util.spec_from_file_location("mod_stylesheets", "mod_stylesheets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Styles
# ----------------------------------------------------------------------
class ConfigEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Config Editor")
        self.setGeometry(100, 100, 800, 400)
        self.config = self.load_config()
        self.current_colors = self.config["colors"].copy()
        if "label_text" not in self.current_colors:
            self.current_colors["label_text"] = "#FFFFFF"
        self.styles = load_styles()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
# SAVE BUTTON
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_button = QPushButton("SAVE")
        save_button.clicked.connect(self.save_config)
        button_layout.addWidget(save_button)
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        self.group_layout = QHBoxLayout()
        self.colors_group = QGroupBox(" Colors ")
        self.colors_group.setFixedWidth(400)
        colors_layout = QVBoxLayout(self.colors_group)
        self.color_combos = {}
        for key, hex_value in self.current_colors.items():
            hbox = QHBoxLayout()
            label = QLabel(key.replace("_", " ").capitalize() + ":")
            combo = QComboBox()
            combo.addItems(list(COLOR_MAP.keys()))
            name = HEX_TO_NAME.get(hex_value.upper(), "Custom")
            if name == "Custom":
                combo.addItem(f"Custom: {hex_value}")
                combo.setCurrentText(f"Custom: {hex_value}")
            else:
                combo.setCurrentText(name)
# UPDATE
            combo.currentTextChanged.connect(lambda text, k=key: self.update_color(k, text))
            self.color_combos[key] = combo
            hbox.addWidget(label)
            hbox.addWidget(combo)
            colors_layout.addLayout(hbox)
        self.group_layout.addWidget(self.colors_group)
        self.sample_group = QGroupBox("Sample")
        self.sample_group.setFixedWidth(400)
        
        sample_layout = QVBoxLayout(self.sample_group)
        self.sample_button = QPushButton("BUTTON")
        sample_layout.addWidget(self.sample_button)
        self.sample_label = QLabel("System Labels")
        sample_layout.addWidget(self.sample_label)
        self.sample_edit = QLineEdit("Edit Box Text")
        sample_layout.addWidget(self.sample_edit)
        self.sample_combo = QComboBox()
        self.sample_combo.addItems(["ComboBox", "First", "Second"])
        sample_layout.addWidget(self.sample_combo)
        sample_layout.addStretch()
        self.group_layout.addWidget(self.sample_group)
        main_layout.addLayout(self.group_layout)
        self.apply_theme(self.current_colors)
# ----------------------------------------------------------------------
    def update_color(self, key, text):
        if text.startswith("Custom:"):
            hex_value = text.split(":", 1)[1].strip()
        else:
            hex_value = COLOR_MAP.get(text, self.current_colors[key]) 
        self.current_colors[key] = hex_value
        self.apply_theme(self.current_colors)
# ----------------------------------------------------------------------
    def apply_theme(self, colors):
        button_style = self.styles.BUTTON_STYLE.format(**colors)
        config_button_style = self.styles.CONFIG_BUTTON_STYLE.format(**colors)
        line_edit_style = self.styles.LINE_EDIT_STYLE.format(**colors)
        label_style = self.styles.STD_LABEL_STYLE.format(**colors)
        group_box_style = self.styles.GROUP_BOX.format(**colors)
        combo_box_style = self.styles.COMBO_BOX.format(**colors)
        sample_stylesheet = (
            button_style +
            config_button_style +
            line_edit_style +
            label_style +
            group_box_style +
            combo_box_style
        )
        fixed_colors_group_style = """
            QGroupBox {
                background-color: #202020;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                height: 26px;
            }
            QComboBox {
                background-color: #404040;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                border: none;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                color: #FFFFFF;
                selection-background-color: #606060;
            }
        """
        self.colors_group.setStyleSheet(fixed_colors_group_style)
        self.sample_group.setStyleSheet(sample_stylesheet)
        self.sample_button.setStyleSheet(button_style)
        self.sample_label.setStyleSheet(label_style)
        self.sample_edit.setStyleSheet(line_edit_style)
        self.sample_combo.setStyleSheet(combo_box_style)
        self.setStyleSheet("QMainWindow { background-color: #202020; }")
        QApplication.instance().setStyleSheet("")
# ----------------------------------------------------------------------
    def load_config(self):
        try:
            with open("../config/settings.json", "r") as f:
                config = json.load(f)
                if "colors" not in config:
                    config["colors"] = {}
                if "label_text" not in config["colors"]:
                    config["colors"]["label_text"] = "#FFFFFF"
                return config
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to Load Config: {str(e)}")
            return {"colors": {"label_text": "#FFFFFF"}}
# ----------------------------------------------------------------------
    def save_config(self):
        self.config["colors"] = self.current_colors.copy()
        try:
            with open("../config/settings.json", "w") as f:
                json.dump(self.config, f, indent=4)
            QMessageBox.information(self, "Success", "Config saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to Save Config: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ConfigEditor()
    editor.show()
    sys.exit(app.exec_())
# ----------------------------------------------------------------------