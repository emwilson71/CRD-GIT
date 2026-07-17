"""
crd_stylesheets
Version 1.0 Updated 05/24/25
"""
class Styles:
    BUTTON_STYLE = """
        QPushButton {{
            background-color: {button_background};
            padding: 4px;
            color: {button_text};
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: {button_hover};
            border: 1px solid {button_border};
        }}
        QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        QPushButton:disabled {{
            background-color: {button_disabled};
            color: {button_text_disabled};
        }}
    """
    CONFIG_BUTTON_STYLE = """
        QPushButton {{
            background-color: {button_background};
            padding: 4px;
            color: {button_text};
            font-size: 12px;
            font-weight: bold;
            border-radius: 4px;
            width: 80px;
            min-width: 80px;
            max-width: 80px;
            text-align: center;
        }}
        QPushButton:hover {{
            background-color: {button_hover};
            border: 1px solid {button_border};
        }}
        QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        QPushButton:disabled {{
            background-color: {button_disabled};
            color: {button_text_disabled};
        }}
    """
    LINE_EDIT_STYLE = """
        QLineEdit {{
            background-color: {menu_item_selected};
            font-size: 14px;
            font-weight: bold;
            color: {menu_text};
            border: none;
            height: 22px;
        }}
    """
    STD_LABEL_STYLE = """
        QLabel {{
            color: {label_text};  /* Changed from menu_text to label_text */
            font-size: 12px;
            font-weight: bold;
            height: 26px;
        }}
    """
    GROUP_BOX = """
        QGroupBox {{
            color: {menu_text};
            font-size: 12px;
            font-weight: bold;
            margin-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
        }}
    """
    COMBO_BOX = """
        QComboBox {{
            background-color: {menu_item_selected};
            color: {menu_text};
            font-size: 12px;
            font-weight: bold;
            border: none;
            padding: 5px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {menu_item_selected};
            color: {menu_text};
            selection-background-color: {button_background};
        }}
    """
    MESSAGE_BOX = """  
            QMessageBox {  
                background-color: #404040;  
                color: lightgray;                 
            }  
            QMessageBox QLabel {  
                color: white;             
            }  
            QMessageBox QPushButton {  
                background-color: gray;  
                color: white;               
                border: 1px solid gray;      
                padding: 5px;               
            }  
            QMessageBox QPushButton:hover {  
                background-color: red;  
            }  
        """
    ERROR_LABEL = """
            QLabel{
                color: red;
                font-size: 12px;
                font-weight: bold;
                }
            """
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
    WEB_VIEW_STYLE = """
            QVBoxLayout{
                background-color: #202020;
                border: none;"
                }
             """   