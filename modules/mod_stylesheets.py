# -------------------------------------------------
"""
Standard QT Stylesheets
Version 1.00 Updated 10/06/25  
"""
# -------------------------------------------------
# BUTTON_STYLE
BUTTON_STYLE = """
    QPushButton {
        background-color: #4A4A4A;
        padding: 4px;
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
        border-radius: 4px;
        border: 1px solid #5A5A5A;
    }
    QPushButton:hover {
        background-color: #2A2A2A;
        border: 1px solid #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #3A3A3A;
    }
    QPushButton:disabled {
        background-color: #606060;
        color: #808080;
    }
"""
# LINE_EDIT_STYLE
LINE_EDIT_STYLE = """
    QLineEdit {
        background-color: #2A2A2A;
        font-size: 12px;
        font-weight: bold;
        color: #E0E0E0;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 2px;
        height: 22px;
    }
    QLineEdit:focus {
        border: 1px solid #FFFFFF;
    }
"""
# STD_LABEL_STYLE
STD_LABEL_STYLE = """
    QLabel {
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
        height: 26px;
    }
"""
# TAB_WIDGET_STYLE
TAB_WIDGET_STYLE = """
    QTabWidget::pane {
        border: 1px solid #5A5A5A;
        background-color: #1A1A1A;
    }
    QTabBar::tab {
        background-color: #2A2A2A;
        color: #E0E0E0;
        border: 1px solid #5A5A5A;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 5px 10px;
        margin-right: 2px;
        font-family: Consolas, Monaco, monospace;
        font-size: 12px;
    }
    QTabBar::tab:selected {
        background-color: #4A4A4A;
        border: 1px solid #5A5A5A;
        border-bottom: none;
    }
    QTabBar::tab:hover {
        border: 1px solid #FFFFFF;
        border-bottom: none;
    }
"""
# TEXT_EDIT_STYLE
TEXT_EDIT_STYLE = """
    QTextEdit {
        background-color: #2A2A2A;
        color: #E0E0E0;
        font-size: 12px;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 2px;
    }
"""
# COMBOBOX_STYLE
COMBOBOX_STYLE = """
    QComboBox {
        background-color: #2A2A2A;
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 2px;
    }
    QComboBox:hover {
        border: 1px solid #FFFFFF;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 1px solid #5A5A5A;
        width: 10px;
        height: 10px;
    }
    QComboBox QAbstractItemView {
        background-color: #2A2A2A;
        color: #E0E0E0;
        selection-background-color: #4A4A4A;
        selection-color: #FFFFFF;
        border: 1px solid #5A5A5A;
    }
"""
# DIALOG_STYLE
DIALOG_STYLE = """
    QMainWindow, QDialog, QWidget, QMessageBox {
        background-color: #1A1A1A;
    }
    QLabel {
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
    }
"""
# CHECKBOX_STYLE
CHECKBOX_STYLE = """
    QCheckBox {
        color: #E0E0E0;
        font-size: 12px;
        font-weight: bold;
        background-color: #1A1A1A;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #5A5A5A;
        background-color: #2A2A2A;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background-color: #4CAF50;
        border: 1px solid #FFFFFF;
    }
    QCheckBox::indicator:hover {
        border: 1px solid #FFFFFF;
    }
"""
# SCROLL_AREA_STYLE
SCROLL_AREA_STYLE = """
    QScrollArea {
        background-color: #1A1A1A;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
    }
    QScrollBar:vertical, QScrollBar:horizontal {
        background-color: #2A2A2A;
        border: 1px solid #5A5A5A;
        border-radius: 2px;
    }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        background-color: #4A4A4A;
        border-radius: 2px;
    }
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
        background-color: #5A5A5A;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        background: none;
    }
"""
# FRAME_STYLE
FRAME_STYLE = """
    QFrame {
        background-color: #2A2A2A;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
    }
"""
# MESSAGE_BOX_STYLE
MESSAGE_BOX_STYLE = """
    QMessageBox {
        background-color: #202020;
    }
    QMessageBox QLabel {
        color: white;
        font-size: 12px;
        font-weight: bold;
    }
    QMessageBox QPushButton {
        background-color: #606060;
        color: white;
        font-size: 11px;
        font-weight: bold;
        border-radius: 4px;
        padding: 5px;
        width: 80px;
        min-width: 80px;
        max-width: 80px;
        text-align: center;
    }
    QMessageBox QPushButton:hover {
        background-color: #303030;
        border: 1px solid #ffffff;
    }
    QMessageBox QPushButton:pressed {
        background-color: #606060;
    }
"""
# PROGRESS_BAR_STYLE
PROGRESS_BAR_STYLE = """
QProgressDialog { background-color: #202020; }
QProgressDialog QLabel { color: white; }
QProgressBar { border: 2px solid #555; border-radius: 5px; background-color: #222; text-align: center; }
QProgressBar::chunk { background-color: lightgray; width: 20px; margin: 1px; }
"""
# -------------------------------------------------