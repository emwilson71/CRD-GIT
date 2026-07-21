"""
---------------------------------------------------------------------------------------------
JSmyser
Version 1.38 Updated 03/31/26
---------------------------------------------------------------------------------------------
"""
VERSION = "Log_Downloader_V1_38"

import sys
import json
import os
import re
import time
import subprocess
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, 
    QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, QMessageBox, QInputDialog, 
    QFileDialog, QCheckBox, QDesktopWidget, QDialog, QDateEdit, QTreeView, QHeaderView,
    QGridLayout, QSplitter
    )
from PyQt5.QtGui import QColor, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer, QDate, QThread, QProcess, QEventLoop
from dateutil.relativedelta import relativedelta
import paramiko  # For SSH/SFTP
from ftplib import FTP, error_perm  # For FTP and permission errors
import fnmatch
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio
import asyncssh
import telnetlib3



# Styling
DARK_BG = QColor(30, 30, 30)
TEXT_COLOR = QColor(200, 200, 200)
FRAME_BG = QColor(40, 40, 40)

# Base directory of the main script (used for relative paths)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default SID Database
DEFAULT_SIDDB_PATH = "c:/CRD/data/siddb.json"

# Default Current Database
DEFAULT_CURRENTDB_PATH = "C:/CRD/config/current.dat"

DEFAULT_FILTERS = [".rm, .acqsts, .slg, *SNAPSHOT.LOG, *_MPlusErrorDispLog*.txt,  ",  
    "SYSLOG_engine*", "*HPM2_Test_data.log", 
    "*_CoolingCabi.txt, *_f70log.txt, *_SVU_*.csv, *_SVUlog.txt, *_MSUP.cab, *_MSUP_V*.gz, *_MSUP2.txt.gz", 
    "20*.CSV", "VisartConditionHistory2.csv, ECOQA*.CSV, PARDB.SITE, RANGECHECKLOG_DQA.TXT, ",
    ]


''' 
    SEE def get_default_remote_locs for DEFAULT_REMOTE_LOCS
'''

DEFAULT_LOCAL_LOCS = ["C:\\CRD\\downloads", "C:\\CANON\\ERRORS",]

EXTERNAL_TOOLS = {
#     ==== SAMPLE ====
#    "Log Analyzer": {    # button name
#     ==== PICK A PATH FORMAT ====
#        "path": "log_analyzer.pyw",    # ← relative, same folder
#        "path": "config_editor.py",                    # ← relative
#        "path": r"C:\MyOtherTools\batch_v2.pyw",       # ← full absolute path (Windows style)
#        "path": os.path.join(self.base_dir, "reports", "generate_report.py"),  # ← explicit relative with subfolder
#        "args": ["--verbose"], # arguments
#        "dynamic_args": ["sid_combo"],
#        "tooltip": "Analyze logs in detail" # popup message
#    },

    "Log Scraper": {
        "path": ["Log_Scraper_V2_x.pyw",
                 "C:\CRD\modules\Log_Scraper_V2_x.pyw"],
        "args": [],
        "dynamic_args": ["local_loc_combo"],
        "tooltip": "Edit configuration"
    },
    "HPM2 Monitor": {
        "path": ["HPM2_Monitor_V1_x.pyw",
                 "C:\CRD\modules\HPM2_Monitor_V1_x.pyw"],
        "args": ["recursive=True"],
    #    "dynamic_args": ["sid_combo"],
        "dynamic_args": ["SID=","path="],        
        "tooltip": "Edit configuration"
    },

    # Add more as needed
}


# Hard-coded usernames and passwords
SP_USER1 = "iv_service_user"
SP_PASS1 = "SU_InnerVision2020"
SP_USER2 = "com_sp"
SP_PASS2 = "IV_TAC_USER"

CREDENTIALS_MAP = {
    ("MR", "*V3*"): ("gpoperator", "gpazumino&goodluck1048", "ftp"),
    ("MR", "*V4*"): ("gpoperator", "gpazumino&goodluck1048", "ftp"),
    ("MR", "*V5*"): ("gpoperator", "gpazumino&goodluck1048", "ftp"),
    ("MR", "*SP*"): ("gpoperator", "gpazumino&goodluck1048", "sftp"),
    ("MR", "*R*"): ("gpoperator", "goodluck", "ftp"),
   # ("MR_V3.x+",): ("gpoperator", "gpazumino&goodluck1048", "sftp"),
   # ("MR_V2.5-",): ("gpoperator", "goodluck", "ftp"),
   # ("MR",): ("default_mr_user", "default_mr_pass", "ftp"),
    # Add more as needed
}

# Config file
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "log_downloader.json")

# APP_CONFIG ALLOWS ARGUMENTS TO CONFIGURE APP. 
APP_CONFIG = {
    "log_scraper": {
        "show_rows": ["sid", "filechecks", "date", "local", "download", "status"], # "sid", "filechecks", "ip", "remote", "filter", "date", "local", "download", "status"
        "defaults": {
            "ip_type": "sp_ip",  # "sp_ip", "host_ip", "display_ip", or "custom:user:pass"
            "remote_loc": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
#            "local_loc": "", # I don't want to set this to blank. 
            "file_filter": ".rm, .acqsts, .slg, *SNAPSHOT.LOG, *_MPlusErrorDispLog*.txt, SYSLOG_engine*,",
            "protocol": "sftp", # "sftp", "ftp"
            "date_filter_enabled": True,
            "quick_date": "1 day", # "1 day", "3 days", "1 week", "1 month", "1 year", "5 years"
            "set_end_today": True,
            "overwrite": True,
            "timed": False,
            "period": "6am daily", # "1min", "5min", "15min", "30min", "1hr", "4hr", "8hr", "6am daily"
            "start_download": False,
            "filechecks": [],
            "filemode": ""
        }
    },
        "hpm2_re-rev": {
        "show_rows": ["sid", "date", "local", "download", "status"], # "sid", "filechecks", "ip", "remote", "filter", "date", "local", "download", "status"
        "defaults": {
            "ip_type": "sp_ip",  # "sp_ip", "host_ip", "display_ip", or "custom:user:pass"
            "remote_loc": "C:/ProgramData/Helium_Pressure_Monitor",
            "local_loc": "C:/CRD/downloads",
            "file_filter": "*HPM2_Test_data.log",
            "protocol": "sftp", # "sftp", "ftp"
            "date_filter_enabled": True,
            "quick_date": "3 days", # "1 day", "3 days", "1 week", "1 month", "1 year", "5 years"
            "set_end_today": True,
            "overwrite": True,
            "timed": True,
            "period": "1min", # "1min", "5min", "15min", "30min", "1hr", "4hr", "8hr", "6am daily"
            "start_download": True,
            "filechecks": [],
            "filemode": "Custom Filter"
        }
    }
}

FILE_CHECKS = {
    "MR": [
        {
            "title": "(Run && DL) SaveLog ",
            "run_command_mode": True,
            "run_user": "host_ip", 
            "command_to_run": {
                ">V3*R*": "csh -c 'savelog'", # THIS WILL COVER GP
                "<V3*R*": "cmd /c savelog", # THIS WILL COVER M-POWER >=V2.x
#                "<V3*R*": "csh -c 'savelog'", # THIS WILL COVER M-POWER >=V2.x. 
#                               CMD IS WHAT WORKED WITH M-POWER >=V2.x. THIS CAN BE DELETED.
                "*SP*": "cmd /c savelog-remote",  # THIS WILL COVER ANYTHING M-POWER >=V3
                "default": "cmd /c savelog"
            },       
            "watch_folder": True,
            "usertype": "host_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/image/savelog",
                "<V6*SP*": "C:/image/savelog",
                ">=V3*R*": "C:/tmp",
                "<V3*R*": "C:/image/savelog",
                "default": "C:/image/savelog"
            },            
            "file_filter": "savelog.7z, savelog.zip",
        },        
        {
            "title": "(Run && DL) Snapshot Log",
            "run_command_mode": True,
            "run_user": "host_ip", 
            "command_to_run": {
                ">V3*R*": "cd /d C:\\gp\\bin & csh -c 'ivSysLog'", # THIS WILL COVER GP
                "<V3*R*": "snapshot_tosp", # THIS WILL COVER M-POWER >=V2.x
                "*SP*": "snapshot_tosp",  # THIS WILL COVER ANYTHING M-POWER >=V3
                "default": "snapshot_tosp"
            },       
            "watch_folder": True,
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },            
            "file_filter": "*SNAPSHOT.LOG",
        },        
        {
            "title": "Acqman Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": ".acqsts"
        },      
        {
            "title": "Autosavelog (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "autosavelog*"
        },
        {
            "title": "Cooling Cabinet Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*_CoolingCabi.txt"
        },  
        {
            "title": "DQA - Visart Condition History (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "VisartConditionHistory2.csv"
        },              
        {
            "title": "ECOQA Files (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "ECOQA*.CSV"
        },
        {
            "title": "F70 Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*_f70log.txt"
        },                        
        {
            "title": "HPM Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": "C:/ProgramData/Helium_Pressure_Monitor",
            "file_filter": "*HPM2_Test_data.log, *HPM2_BTrdr2_test_data.txt"
        },
        {
            "title": "Magnet Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir/20??",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir/20??",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir/20??",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir/20??",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir/20??"
            },            
            "file_filter": "*_SVU_*.csv, *_MSUP.cab, *_MSUP_V*.gz, *_MSUP2.txt.gz, "
        },        
        {
            "title": "MPlusErrorDispLog (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*_MPlusErrorDispLog*.txt"
        },
        {
            "title": "PARDB Site Files (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "PARDB.SITE"
        },
        {
            "title": "Range Check DQA Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "RANGECHECKLOG_DQA.TXT"
        },        
        {
            "title": "RM Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": ".rm"
        },
        {
            "title": "Scan Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "202?????.CSV"
        },        
        {
            "title": "Snapshot Logs (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*SNAPSHOT.LOG",
        },        
        {
            "title": "SYSLOG Engine (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "SYSLOG_engine*"
        },        
        {
            "title": "SYSTEMLOG.SLG (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": ".slg"
        },
        {
            "title": "SVUlog.txt (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*_SVUlog.txt"
        },
        {
            "title": "Temp and Humidity Files (SP)",
            "usertype": "sp_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "<V6*SP*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                ">=V3*R*": "C:/InnerVision.dir/Excelart/{sid}-000/_tui.dir",
                "<V3*R*": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
                "default": "C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir"
            },
            "file_filter": "*TL?.CSV"
        },
        {
            "title": "Acqman Logs (SM)",
            "usertype": "host_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/MRMPlus/tmp/ACQMAN",
                "<V6*SP*": "C:/usr/tmp/acqman",
                ">=V3*R*": "C:/usr/tmp/acqman",
                "<V3*R*": "C:/usr/tmp/acqman",
                "default": "C:/usr/tmp/acqman"
            },
            "file_filter": "acqman-status*"
        },  
        {
            "title": "GCoilTemp Current Log (SM)",
            "usertype": "host_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/MRMPlus/data/preScan/",
                "<V6*SP*": "C:/MRMPlus/data/preScan/",
                ">=V3*R*": "C:/MRMPlus/data/preScan/",
                "<V3*R*": "C:/gp/data/preScan/",
                "default": "C:/gp/data/preScan/"
            },
            "file_filter": "GCoilTemp*.log"
        },    
        {
            "title": "GCoilTemp Older Logs (SM)",
            "usertype": "host_ip",
            "remote_loc": {
                ">=V6*SP*": "C:/MRMPlus/data/preScan/gcoiltemp/",
                "<V6*SP*": "C:/MRMPlus/data/preScan/gcoiltemp/",
                ">=V3*R*": "C:/MRMPlus/data/preScan/gcoiltemp/",
                "<V3*R*": "C:/gp/data/preScan/gcoiltemp/",
                "default": "C:/gp/data/preScan/gcoiltemp/"
            },
            "file_filter": "GCoilTemp*.log"
        },                  
      
    ]
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "siddb_path": DEFAULT_SIDDB_PATH,
            "custom_filters": [],
            "remote_locations": [],
            "local_locations": [],
            "last_selections": {
                "sid": "",
                "ip_type": "sp_ip",
                "ip": "",
                "username": "",
                "remote_loc": "",
                "local_loc": os.getcwd(),
                "file_filter": "",
                "filemode": "File Checks",  # Added for mode selector
                "protocol": "sftp",
                "date_filter_enabled": False,
                "start_date": "",
                "end_date": "",
                "quick_date": "",
                "incremental_download": False,
                "timed_download": False,
                "incremental_period": "6am daily",
                "filechecks": [],
            },
            "app_mode": {}
        }
    
    # Merge APP_CONFIG into app_mode
    config["app_mode"].update(APP_CONFIG)
    # Include FILE_CHECKS in config but don't save it
    config["file_checks"] = FILE_CHECKS
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_siddb(path):
    sid_dict = {}
    # Load siddb.json if it exists
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        for entry in data.get("index", []):
            sid = entry.get("sid")
            if sid:
                sid_dict[sid] = entry

    # Load current.dat and append to sid_dict
    if os.path.exists(DEFAULT_CURRENTDB_PATH):
        try:
            with open(DEFAULT_CURRENTDB_PATH, 'r') as f:
                lines = f.readlines()
            # Parse key-value pairs
            entry = {}
            for line in lines:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()  # Normalize keys
                    value = value.strip()
                    # Map current.dat keys to siddb.json keys
                    key_map = {
                        "sid": "sid",
                        "sitename": "site_name",
                        "sp_ip": "sp_ip",
                        "host_ip": "host_ip",
                        "display_ip": "display_ip",
                        "tunneltype": "tunnel",
                        "modality": "modality",
                        "port": "port",
                        "sw_version": "sw_version",
                        "scanner": "machine"
                    }
                    if key in key_map:
                        entry[key_map[key]] = value
            sid = entry.get("sid")
            if sid:
                # Add or update entry in sid_dict, ensuring list fields
                sid_dict[sid] = {
                    "sid": sid,
                    "site_name": entry.get("site_name", f"Site {sid}"),
                    "sp_ip": [entry.get("sp_ip", "")] if entry.get("sp_ip") else [],
                    "host_ip": [entry.get("host_ip", "")] if entry.get("host_ip") else [],
                    "display_ip": [entry.get("display_ip", "")] if entry.get("display_ip") else [],
                    "tunnel": [entry.get("tunnel", "")] if entry.get("tunnel") else [],
                    "modality": [entry.get("modality", "")] if entry.get("modality") else [],
                    "note": [],  # Default empty list for note
                    "port": entry.get("port", ""),
                    "machine": entry.get("machine", ""),
                    "sw_version": entry.get("sw_version", "")
                }
               
        except Exception as e:
            MainWindow.update_status(f"Error loading {DEFAULT_CURRENTDB_PATH}: {str(e)}")
    return sid_dict

def get_credentials(ip_type, entry):
    if ip_type == "sp_ip":
        return [(SP_USER1, SP_PASS1, "sftp"), (SP_USER2, SP_PASS2, "ftp")]
    elif ip_type in ["host_ip", "display_ip"]:
        modality = (entry.get("modality") or [""])[0]
        machine = entry.get("machine", "").title()
        sw_version = entry.get("sw_version", "")


        # === 1. Try specific: (modality, machine, sw_version) ===
        for key, creds in CREDENTIALS_MAP.items():
            if len(key) != 3:
                continue
            m, mach, sw = key
            if (m == modality and
                mach.title() == machine and
                fnmatch.fnmatch(sw_version, sw)):
                return [creds]

        # === 2. Try: (modality, sw_version) ===
        for key, creds in CREDENTIALS_MAP.items():
            if len(key) != 2:
                continue
            m, sw = key
            if m == modality and fnmatch.fnmatch(sw_version, sw):
                return [creds]

        # === 3. Fallback: (modality,) ===
        for key, creds in CREDENTIALS_MAP.items():
            if len(key) != 1:
                continue
            (m,) = key
            if m == modality:
                return [creds]

        return [] # NOT Using These Defaults [("default_user", "default_pass", "sftp")]

    elif ip_type == "Custom User":
        return [] # NOT Using These Defaults [("default_user", "default_pass", "sftp")]

    # === Handle custom ip_type like MR_V3.x+ ===
    for key, creds in CREDENTIALS_MAP.items():
        if len(key) == 1 and key[0] == ip_type:
            return [creds]

    return [] # NOT Using These Defaults [("default_user", "default_pass", "sftp")]



#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------



class LogDownloader:
    def __init__(self, sid_or_site, file_filter, remote_loc, local_loc, protocol="sftp"):
        self.sid_or_site = sid_or_site
        self.file_filter = file_filter
        self.remote_loc = remote_loc.replace("SID", sid_or_site) if sid_or_site != "Custom IP" else remote_loc
        self.local_loc = local_loc
        self.protocol = protocol
        self.config = load_config()
        self.siddb = load_siddb(self.config["siddb_path"])
        self.sid = self.resolve_sid()
        self.entry = self.siddb.get(self.sid, {}) if self.sid != "Custom IP" else {}
        self.ip = None
        self.ip_type = None
        self.username = None
        self.password = None
        self.sftp = None
        self.ftp = None
        self.date_filter = {}  # Initialize date_filter
        self.dir_cache = None  # Cache for directory listing
        self._conn = None        # ← shared connection
        self._sftp = None        # ← shared SFTP client
        self._ftp = None         # ← shared FTP client
        self.max_concurrent = 4
        self.command_to_run = None
        self.run_user_ip_type = None
        self.run_command_mode = False
        self.watch_folder = False   
        self._ip_map = {}          # {ip_type: ip_address}
        self._cred_map = {}        # {ip_type: (username, password)}               

#        print(f"LogDownloader _init_, ip_type= {self.ip_type}, _ip_map= {self._ip_map}, cred_map= {self._cred_map}, self.entry-site_name= {self.entry.get('site_name', '')}")
        
    def resolve_sid(self):
        if self.sid_or_site == "Custom IP":
            return "Custom IP"
        if not self.siddb:
            return self.sid_or_site
        if self.sid_or_site in self.siddb:
            return self.sid_or_site
        for sid, entry in self.siddb.items():
            if entry.get("site_name") == self.sid_or_site:
                return sid
        return self.sid_or_site

    def set_ip(self, ip, ip_type):
        self.ip = ip
        self.ip_type = ip_type

    def set_credentials(self, username, password):
        self.username = username
        self.password = password

    def set_ip_and_credentials(self, ip_type, ip, username=None, password=None):
        """Store IP and (optional) explicit credentials for a given ip_type."""
        if isinstance(ip, (list, tuple)):
            ip = ip[0] if ip else ""
        ip = str(ip).strip()
        if not ip:
            return

        self._ip_map[ip_type] = ip

        if username is not None and password is not None:
            self._cred_map[ip_type] = (username, password)      

    def try_connect(self, status_callback=None):
        if not self.username or not self.password:
            if status_callback:
                status_callback("Error: No username or password")
            return False

        if self.protocol == "sftp":
            try:
                transport = paramiko.Transport((self.ip, 22))
                transport.connect(username=self.username, password=self.password)
                self.sftp = paramiko.SFTPClient.from_transport(transport)
                if status_callback:
                    status_callback("Connection Established")
                    QApplication.processEvents()
                return True
            except paramiko.AuthenticationException:
                msg = f"SFTP Auth failed: Bad username/password for {self.username}@{self.ip}"
                print(msg)
                if status_callback:
                    status_callback(msg)
                return False
            except Exception as e:
                msg = f"SFTP Error: {e}"
                print(msg)
                if status_callback:
                    status_callback(msg)
                return False

        elif self.protocol == "ftp":
            try:
                self.ftp = FTP(self.ip)
                self.ftp.login(self.username, self.password)
                if status_callback:
                    status_callback("Connection Established")
                    QApplication.processEvents()
                return True
            except Exception as e:
                msg = f"FTP Error: {e}"
                print(msg)
                if status_callback:
                    status_callback(msg)
                return False

        return False




    async def list_remote_dir(self, path):
        """
        List remote directory.
        SFTP: reuses self._sftp (fast)
        FTP:  uses ftplib 
        """
        files = []
        file_dates = {}
        file_sizes = {}

        if self.protocol == "sftp":
            if self._sftp is not None:
                try:
                    attrs = await self._sftp.readdir(path)
                    files = [attr.filename for attr in attrs]
                    file_dates = {attr.filename: datetime.fromtimestamp(attr.attrs.mtime) for attr in attrs}
                    file_sizes = {attr.filename: attr.attrs.size for attr in attrs}
                    return files, file_dates, file_sizes
                except Exception as e:
                    raise ValueError(f"Error listing SFTP directory, Check Path {path}, {e}")

            # Fallback
            async with asyncssh.connect(self.ip, port=22, username=self.username, password=self.password, known_hosts=None) as conn:
                async with conn.start_sftp_client() as sftp:
                    try:
                        attrs = await sftp.readdir(path)
                        files = [attr.filename for attr in attrs]
                        file_dates = {attr.filename: datetime.fromtimestamp(attr.attrs.mtime) for attr in attrs}
                        file_sizes = {attr.filename: attr.attrs.size for attr in attrs}
                        return files, file_dates, file_sizes
                    except Exception as e:
                        raise ValueError(f"Error listing SFTP directory, Check Path {path} {str(e)}")

        else:  # FILTER FTP
            def _ftp_list():
                ftp = FTP(timeout=30)
                try:
                    ftp.connect(self.ip, 21)
                    ftp.login(self.username, self.password)
                    lines = []
                    ftp.retrlines(f'LIST {path}', lines.append)
                    for line in lines:
                        parts = line.split()
                        if len(parts) < 9:
                            continue
                        name = ' '.join(parts[8:])
                        try:
                            size = int(parts[4])
                        except:
                            size = 0
                        month_str = parts[5]
                        day = int(parts[6])
                        time_or_year = parts[7]
                        month = ['Jan','Feb','Mar','Apr','May','Jun',
                                 'Jul','Aug','Sep','Oct','Nov','Dec'].index(month_str) + 1
                        if ':' in time_or_year:
                            hour, minute = map(int, time_or_year.split(':'))
                            year = datetime.now().year
                        else:
                            year = int(time_or_year)
                            hour = minute = 0
                        try:
                            mtime = datetime(year, month, day, hour, minute)
                        except:
                            mtime = datetime.now()
                        files.append(name)
                        file_dates[name] = mtime
                        file_sizes[name] = size
                except Exception as e:
                    raise ValueError(f"Error listing FTP directory, Check Path {path} {str(e)}")
            
                finally:
                    ftp.quit()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _ftp_list)
        return files, file_dates, file_sizes

    def parse_filter(self, filter_str):
        extensions_input = [item.strip() for item in filter_str.split(',') if item.strip()]
        self.extensions = {ext.lstrip('.').lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and ext.startswith('.') and '*' not in ext and '?' not in ext and '[' not in ext}
        self.exclude_extensions = {ext[1:].lstrip('.').lower() for ext in extensions_input if ext.startswith('-.') and '*' not in ext and '?' not in ext and '[' not in ext}
        self.extension_patterns = {ext.lstrip('.').lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and ext.startswith('.') and ('*' in ext or '?' in ext or '[' in ext)}
        self.exclude_extension_patterns = {ext[1:].lstrip('.').lower() for ext in extensions_input if ext.startswith('-.') and ('*' in ext or '?' in ext or '[' in ext)}
        self.include_folders = {ext.strip('/').lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and ext.startswith('/') and ext.endswith('/') and '*' not in ext and '?' not in ext and '[' not in ext}
        self.exclude_folders = {ext[1:].strip('/').lower() for ext in extensions_input if ext.startswith('-/') and ext.endswith('/') and '*' not in ext and '?' not in ext and '[' not in ext}
        self.include_folder_patterns = {ext.strip('/').lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and ext.startswith('/') and ext.endswith('/') and ('*' in ext or '?' in ext or '[' in ext)}
        self.exclude_folder_patterns = {ext[1:].strip('/').lower() for ext in extensions_input if ext.startswith('-/') and ext.endswith('/') and ('*' in ext or '?' in ext or '[' in ext)}
        self.include_files = {ext.lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and not ext.startswith(('.', '/')) and '/' not in ext and '*' not in ext and '?' not in ext and '[' not in ext}
        self.exclude_files = {ext[1:].lower() for ext in extensions_input if ext.startswith('-') and not ext.startswith(('-/', '-.', ':')) and '/' not in ext and '*' not in ext and '?' not in ext and '[' not in ext}
        self.include_file_patterns = {ext.lower() for ext in extensions_input if ext and not ext.startswith(('-', ':')) and not ext.startswith(('.', '/')) and '/' not in ext and ('*' in ext or '?' in ext or '[' in ext)}
        self.exclude_file_patterns = {ext[1:].lower() for ext in extensions_input if ext.startswith('-') and not ext.startswith(('-/', '-.', ':')) and '/' not in ext and ('*' in ext or '?' in ext or '[' in ext)}
        self.date_filter = {}
        for item in extensions_input:
            if item.startswith(":date:"):
                try:
                    # Extract the date range
                    date_str = item[6:].strip()
                    if not date_str:
                        raise ValueError("Empty date range")
                    # Split into parts
                    parts = date_str.split('-')
                    if len(parts) != 6:
                        raise ValueError("Invalid date format, expected YYYY-MM-DD-YYYY-MM-DD or YYYY-M-D-YYYY-M-D")
                    # Construct start and end dates with zero-padding
                    start = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                    end = f"{int(parts[3]):04d}-{int(parts[4]):02d}-{int(parts[5]):02d}"
                    # Validate date format
                    datetime.strptime(start, '%Y-%m-%d')
                    datetime.strptime(end, '%Y-%m-%d')
                    self.date_filter = {"start": start, "end": end}
                except (ValueError, TypeError) as e:
                    self.date_filter = {}

    def is_within_date_range(self, file_name, file_date, parse_filename_dates=True):
        if self.watch_folder or not self.date_filter or not self.date_filter.get("start") or not self.date_filter.get("end"):
            return True
        try:
            # Try parsing timestamp from filename
            if parse_filename_dates:
                basename = os.path.basename(file_name)
                timestamp_match = re.search(r'_(\d{8})[_]', basename) or re.search(r'^(\d{8})', basename)
                if timestamp_match:
                    ts = timestamp_match.group(1)
                    if len(ts) >= 4:
                        if len(ts) == 4:
                            ts = ts + '0101'  # Year only -> Jan 1
                        elif len(ts) == 6:
                            ts = ts + '01'    # YYYYMM -> YYYYMM01
                        elif len(ts) >= 8:
                            ts = ts[:8]       # YYYYMMDD or longer -> YYYYMMDD
                        try:
                            year = int(ts[:4])
                            month = int(ts[4:6]) if len(ts) >= 6 else 1
                            day = int(ts[6:8]) if len(ts) >= 8 else 1
                            file_date_from_name = datetime(year, month, day)
                            start_date = datetime.strptime(self.date_filter["start"], '%Y-%m-%d')
                            end_date = datetime.strptime(self.date_filter["end"], '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
                            if start_date <= file_date_from_name <= end_date:
                                return True
                        except ValueError:
                            print("DEBUG: Error parsing date from filename: %s" % ts)
            # Fallback to file modification date (mtime)
            start_date = datetime.strptime(self.date_filter["start"], '%Y-%m-%d')
            end_date = datetime.strptime(self.date_filter["end"], '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            if start_date <= file_date <= end_date:
                return True
            # Fallback to creation time (ctime) is not applicable for SFTP; skipping
            return False
        except (ValueError, TypeError) as e:
            return True

    def apply_filter(self, file):
        file_name = os.path.basename(file).lower()
        file_ext = os.path.splitext(file_name)[1].lower()[1:] if os.path.splitext(file_name)[1] else ''
        file_dir = os.path.normpath(os.path.dirname(file)).lower()

        # Folder filters
        folder_match = True
        if self.include_folders or self.include_folder_patterns:
            folder_match = False
            for folder in self.include_folders:
                folder = folder.lower().strip(os.sep)
                if folder in [part.lower() for part in file_dir.split(os.sep)]:
                    folder_match = True
                    break
            if not folder_match:
                for pattern in self.include_folder_patterns:
                    for dir_part in file_dir.split(os.sep):
                        if fnmatch.fnmatch(dir_part.lower(), pattern.lower()):
                            folder_match = True
                            break
                    if folder_match:
                        break
            if not folder_match:
                return False

        if self.exclude_folders:
            if any(folder.lower().strip(os.sep) in [part.lower() for part in file_dir.split(os.sep)] for folder in self.exclude_folders):
                return False
        if self.exclude_folder_patterns:
            if any(fnmatch.fnmatch(dir_part.lower(), pattern.lower()) for pattern in self.exclude_folder_patterns for dir_part in file_dir.split(os.sep)):
                return False

        # File and extension filters with OR logic
        file_or_ext_match = False
        # File filters
        if self.include_files and file_name in self.include_files:
            file_or_ext_match = True
        elif self.include_file_patterns:
            for pattern in self.include_file_patterns:
                if fnmatch.fnmatch(file_name, pattern.lower()):
                    file_or_ext_match = True
                    break
        # Extension filters
        if not file_or_ext_match and (self.extensions or self.extension_patterns):
            if self.extensions and file_ext and file_ext in self.extensions:
                file_or_ext_match = True
            elif self.extension_patterns and file_ext:
                for pattern in self.extension_patterns:
                    if fnmatch.fnmatch(file_ext, pattern.lower()):
                        file_or_ext_match = True
                        break
        # If no file or extension filters are specified, allow all files; otherwise, require a match
        if not self.include_files and not self.include_file_patterns and not self.extensions and not self.extension_patterns:
            file_or_ext_match = True
        if not file_or_ext_match:
            return False

        # Apply exclusion filters
        if self.exclude_files and file_name in self.exclude_files:
            return False
        if self.exclude_file_patterns:
            if any(fnmatch.fnmatch(file_name, pattern.lower()) for pattern in self.exclude_file_patterns):
                return False
        if self.exclude_extensions and file_ext and file_ext in self.exclude_extensions:
            return False
        if self.exclude_extension_patterns and file_ext:
            if any(fnmatch.fnmatch(file_ext, pattern.lower()) for pattern in self.exclude_extension_patterns):
                return False

        return True



    def download_logs(self,
                      incremental=False,
                      status_callback=None,
                      max_concurrent=4,
                      connect_timeout=30,
                      download_timeout=300,
                      parse_filename_dates=True,
                      list_only=False,
                      cancel_event=None,
                      wait_interval=10,
                      wait_timeout=300):
        self.max_concurrent = max_concurrent
        t0 = time.time()
        try:
            async def async_download():
                num_files = size_bytes = skip_files = 0
                files = file_dates = file_sizes = None

                # ================== CONNECT ONCE ==================
                if not self.username or not self.password:
                    # === GET CREDENTIALS FROM MAP ===
                    creds_list = get_credentials(self.ip_type, self.entry)
                    if not creds_list:
                        raise ValueError(f"No credentials for {self.ip_type}")
                    username, password, protocol = creds_list[0]
                    self.set_credentials(username, password)
                    self.protocol = protocol
                    print(f"[CRED] Using {username} via {protocol}")

                # === TRY CONNECT ===
                if not self.try_connect(status_callback):
                    raise ValueError("Failed to connect")
                t1 = time.time()
                print(f"Connection time: {(t1 - t0):.2f} seconds")

                # ---- OPEN SHARED CONNECTION ----
                if self.protocol == "sftp":
                    if self._conn is None:
                        self._conn = await asyncssh.connect(
                            self.ip, port=22,
                            username=self.username, password=self.password,
                            known_hosts=None, connect_timeout=connect_timeout
                        )
                        self._sftp = await self._conn.start_sftp_client()
                        print("SFTP connection opened")

                # ================================================

                try:
                    self.parse_filter(self.file_filter)
                except Exception as e:
                    raise ValueError(f"Filter error: {e}")
                t2 = time.time()
                print(f"Parse filter time: {(t2 - t1):.2f} seconds")

                # === EARLY NORMALIZATION + WILDCARD RESOLUTION ===
                raw_locs = getattr(self, 'remote_locs', [self.remote_loc])
                resolved_locs = []

                for loc in raw_locs:
                    
                    norm_loc = loc.replace('\\', '/').lower().strip()
                    
                    if not norm_loc:
                        # Empty → default root
                        norm_loc = "/c:/" if self.protocol == "sftp" else "/c/"
                    
                    print(f"norm_loc = {norm_loc}")
                    if self.protocol == "sftp":
                        if self.ip_type in ("sp_ip", "host_ip"):
                            if norm_loc.startswith('c:'):
                                norm_loc = norm_loc[2:]
                                norm_loc = '/c:/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c/'):
                                norm_loc = norm_loc[3:]
                                norm_loc = '/c:/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c:/'):
                                norm_loc = norm_loc[4:]
                                norm_loc = '/c:/' + norm_loc.lstrip('/')
                            else:
                                norm_loc
                        else:
                            norm_loc

                    elif self.protocol == "ftp":
                        if self.ip_type == "sp_ip":
                            if norm_loc.startswith('c:'):
                                norm_loc = norm_loc[2:]
                                norm_loc = '/c/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c/'):
                                norm_loc = norm_loc[3:]
                                norm_loc = '/c/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c:/'):
                                norm_loc = norm_loc[4:]
                                norm_loc = '/c/' + norm_loc.lstrip('/')
                            else:
                                norm_loc
                        
                        elif self.ip_type == "host_ip":
                            if norm_loc.startswith('c:'):
                                norm_loc = norm_loc[2:]
                                norm_loc = '/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c/'):
                                norm_loc = norm_loc[3:]
                                norm_loc = '/' + norm_loc.lstrip('/')
                            elif norm_loc.startswith('/c:/'):
                                norm_loc = norm_loc[4:]
                                norm_loc = '/' + norm_loc.lstrip('/')
                            else:
                                norm_loc
                        else:
                            norm_loc
                    else:                       
                        norm_loc
                
                    # Check for ? or [ only (no *)
                    if any(c in norm_loc for c in '?['):
                        parent_dir, pattern = os.path.split(norm_loc)
                        if not pattern:
                            parent_dir, pattern = norm_loc, '?'
                        pattern = pattern.lower()
                        list_dir = parent_dir or '.'

                        try:
                            # List parent directory
                            fl, fd, fs = await self.list_remote_dir(list_dir)

                            # Update status
                            if status_callback:
                                status_callback(f"Scanning folders in {list_dir} for pattern '{pattern}'...")
                                QApplication.processEvents()

                            if cancel_event and cancel_event.is_set():
                                return 0, 0, 0, 0, "Cancelled"

                            if self.protocol == "sftp":
                                if self._sftp is not None:
                                    attrs = await self._sftp.readdir(list_dir)
                                else:
                                    async with asyncssh.connect(self.ip, port=22, username=self.username, password=self.password, known_hosts=None) as conn:
                                        async with conn.start_sftp_client() as sftp:
                                            attrs = await sftp.readdir(list_dir)
                                for attr in attrs:
                                    if cancel_event and cancel_event.is_set():
                                        return 0, 0, 0, 0, "Cancelled"
                                    if (fnmatch.fnmatch(attr.filename.lower(), pattern) and
                                        (attr.attrs.permissions & 0o040000)):
                                        resolved_locs.append(os.path.join(list_dir, attr.filename))
                                        # Keep UI responsive every 10 matches
                                        if len(resolved_locs) % 10 == 0:
                                            if status_callback:
                                                status_callback(f"Found {len(resolved_locs)} matching folders...")
                                            QApplication.processEvents()
                            else:  # FTP
                                for name in fl:
                                    if cancel_event and cancel_event.is_set():
                                        return 0, 0, 0, 0, "Cancelled"
                                    if name.endswith('/') and fnmatch.fnmatch(name[:-1].lower(), pattern):
                                        resolved_locs.append(os.path.join(list_dir, name[:-1]))
                                        # Keep UI responsive every 10 matches
                                        if len(resolved_locs) % 10 == 0:
                                            if status_callback:
                                                status_callback(f"Found {len(resolved_locs)} matching folders...")
                                            QApplication.processEvents()
                        except Exception as e:
                            print(f"Error resolving wildcard {loc}: {e}")
                    else:
                        resolved_locs.append(norm_loc)

                remote_locs = resolved_locs

                # === HELPER: List + filter ===
                async def list_and_filter():
                    total_files = 0
                    files = []
                    file_dates = {}
                    file_sizes = {}
                    for loc in remote_locs:
                        fl, fd, fs = await self.list_remote_dir(loc)
                        total_files += len(fl)
                        for f in fl:
                            full = os.path.join(loc, f)
                            if self.apply_filter(os.path.basename(full)) and \
                               self.is_within_date_range(os.path.basename(full), fd.get(f), parse_filename_dates):
                                files.append(full)
                                file_dates[full] = fd.get(f)
                                file_sizes[full] = fs.get(f)
                    return files, file_dates, file_sizes, total_files

                t3 = time.time()
# IF SELF.WATCH_FOLDER =============================================================
                if self.watch_folder:
                    print("Waiting for new file matching filter...")
                    seen_files = {}  # Now tracks (mtime, size) tuple per file path
                    wait_start = time.time()

                    # === GET BASELINE (ignore existing files or detect changes) ===
                    baseline_files, baseline_dates, baseline_sizes, _ = await list_and_filter()
                    
                    telnet_reader = telnet_writer = None
                    # Store initial state: file_path → (mtime, size)
                    for f in baseline_files:
                        seen_files[f] = (baseline_dates[f], baseline_sizes[f])

                    # ---- RUN COMMAND SMARTLY (reuse conn if possible) ----
                    if (self.run_command_mode and self.command_to_run and self.run_user_ip_type):
                        print(f"Command_To_Run: {self.command_to_run} on {self.run_user_ip_type}")

                        try:
                            output, success, telnet_reader, telnet_writer  = await self.run_command(self.command_to_run, status_callback=status_callback)
                            
                            if not success:
                                raise RuntimeError("Command failed or returned unexpected output")
                        
                        except Exception as e:
                            error_text = f"Command failed: {e}"
                            print(error_text)
                            if status_callback:
                                status_callback(error_text)
                            if telnet_writer is not None:
                                try:
                                    telnet_writer.write("exit\r\n")
                                    await telnet_writer.drain()
                                    telnet_writer.close()
                                    await telnet_writer.wait_closed()
                                except:
                                    pass
                            raise  # Re-raise to abort download

                        finally:
                            # If watch_folder is NOT active, close the connection immediately
                            if not self.watch_folder and telnet_writer is not None:
                                try:
                                    telnet_writer.write("exit\r\n")
                                    await telnet_writer.drain()
                                    telnet_writer.close()
                                    await telnet_writer.wait_closed()
                                    print("[TELNET] connection closed (watch_folder not active)")
                                except:
                                    pass

                    # === MONITOR LOOP: Detect new OR modified files (by mtime or size) ===
                    while True:
                        if cancel_event and cancel_event.is_set():
                            if telnet_writer is not None:
                                try:
                                    telnet_writer.write("exit\r\n")
                                    await telnet_writer.drain()
                                    telnet_writer.close()
                                    await telnet_writer.wait_closed()
                                except:
                                    pass
                            return 0, 0, 0, 0, "Cancelled"
                        if wait_timeout and (time.time() - wait_start) > wait_timeout:
                            if telnet_writer is not None:
                                try:
                                    telnet_writer.write("exit\r\n")
                                    await telnet_writer.drain()
                                    telnet_writer.close()
                                    await telnet_writer.wait_closed()
                                except:
                                    pass
                            return 0, 0, 0, 0, "Wait timeout"
                        # === CRITICAL: Temporarily remove :date: from filter string ===
                        original_filter = self.file_filter
                        if ":date:" in self.file_filter:
                            # Remove everything from :date: onward
                            self.file_filter = self.file_filter.split(":date:")[0].rstrip(",")
                        try:
                            cur_files, cur_dates, cur_sizes, total_cur = await list_and_filter()
                        finally:
                            # Always restore original filter string
                            self.file_filter = original_filter

                        # Build current state dict: file_path → (mtime, size)
                        current_state = {f: (cur_dates[f], cur_sizes[f]) for f in cur_files}

                        # Find new files OR files where mtime or size changed
                        changed_files = [
                            f for f in cur_files
                            if f not in seen_files or seen_files[f] != current_state[f]
                        ]

                                   # Find new files OR files where mtime or size changed
                        changed_files = [
                            f for f in cur_files
                            if f not in seen_files or seen_files[f] != current_state[f]
                        ]

                        if changed_files:
                            print(f"Potential change detected: {len(changed_files)} file(s): "
                                  f"{[os.path.basename(f) for f in changed_files]}")

                            # === EXTRA SAFETY: Re-check after short delay to avoid temporary/flashing files ===
                            await asyncio.sleep(1.5)  # Wait 1.5 seconds for file to stabilize

                            # Re-list the directory with the same broad filter
                            try:
                                cur_files2, cur_dates2, cur_sizes2, _ = await list_and_filter()
                            finally:
                                self.file_filter = original_filter  # Restore again just in case

                            current_state2 = {f: (cur_dates2[f], cur_sizes2[f]) for f in cur_files2}

                            # Keep only files that are STILL present and match the final filter (including date if any)
                            stable_files = [
                                f for f in changed_files
                                if f in cur_files2 and
                                   self.apply_filter(os.path.basename(f)) and
                                   self.is_within_date_range(os.path.basename(f), cur_dates2.get(f), parse_filename_dates=True)
                            ]

                            if stable_files:
                                print(f"Confirmed stable matching file(s): "
                                      f"{[os.path.basename(f) for f in stable_files]}")
                                filtered_files = stable_files
                                file_dates = {f: cur_dates2[f] for f in stable_files}
                                file_sizes = {f: cur_sizes2[f] for f in stable_files}
                                break
                            else:
                                print("Temporary/flashing file disappeared or doesn't match final filter — ignoring")
                                # Update seen_files with the latest stable state to avoid re-triggering
                                seen_files.update(current_state2)

                        else:
                            # No changes → update seen_files with current state
                            seen_files.update(current_state)

                        
                        if status_callback:
                            elapsed = int(time.time() - wait_start)
                            status_callback(f"Waiting for new or modified file... {elapsed}s")
                        QApplication.processEvents()
                        await asyncio.sleep(0)
                    if telnet_writer is not None:
                        try:
                            telnet_writer.write("exit\r\n")
                            await telnet_writer.drain()
                            telnet_writer.close()
                            await telnet_writer.wait_closed()
                            print("[TELNET] connection closed after file detected")
                        except Exception as e:
                            print(f"[TELNET] error closing connection: {e}")

                    t4 = time.time()
                    wait_time = t4 - t3
                    print(f"\nWait Time: {wait_time:.2f} seconds")
                    print(f"File listing time: {(t3 - t2):.2f} seconds")  # First list
                    print(f"Total files before filter: {total_cur}")
                    print(f"Files after filter: {len(filtered_files)}")
                    print(f"Filtering time: {(t4 - t3):.2f} seconds\n")

                else:
                    # === NORMAL MODE ===
                    filtered_files, file_dates, file_sizes, total_files = await list_and_filter()
                    t4 = time.time()
                    print(f"\nFile listing time: {(t3 - t2):.2f} seconds")
                    print(f"Total files before filter: {total_files}")
                    print(f"Files after filter: {len(filtered_files)}")
                    print(f"Filtering time: {(t4 - t3):.2f} seconds\n")

                if list_only:
                    return filtered_files, 0, 0, 0, None

                if not filtered_files:
                    print("if not filtered")
                    return 0, 0, 0, 0, "No files matched search criteria"

                total_num_filtered_files = len(filtered_files)

# FROM HERE TO NEXT ===== CAN BE SCRAPPED. =============================================
                # Calculate total size in bytes from the filtered files
                total_file_size_bytes = sum(file_sizes.get(f, 0) for f in filtered_files)
                # Convert to human-readable format
                if total_file_size_bytes >= 50 * 1024 * 1024:  # 50 MB
                    size_str = f"{total_file_size_bytes / (1024 * 1024):.2f} MB"
                    warning = " and it could take a while..."
                else:
                    size_str = f"{total_file_size_bytes / (1024 * 1024):.2f} MB"
                    warning = "..."

#                if status_callback: # THIS WAS SCRAPPED FOR THE CALLBACK IN DEF DOWNLOAD_ONE. KEPT THE IDEA JUST IN CASE.
#                    status_callback(f"Downloading {total_num_filtered_files} file(s) ({size_str}){warning}")
#                    QApplication.processEvents()
                print(f"Downloading {total_num_filtered_files} file(s) ({size_str}){warning}")
# SCRAP FROM HERE UP TO NEXT ====== CAN BE SCRAPPED. =============================================
 
                 
                os.makedirs(self.local_loc, exist_ok=True)

                # ================== DOWNLOAD ONE (UNCHANGED) ==================
                async def download_one(file):
                    nonlocal num_files, size_bytes, skip_files
                    basename = os.path.basename(file)                   
                    local = os.path.join(self.local_loc, basename)
                    r_size = file_sizes.get(file, 0)
                    r_mtime = file_dates.get(file, datetime.now())

                    if incremental and os.path.exists(local):
                        if (datetime.fromtimestamp(os.path.getmtime(local)) >= r_mtime and
                            os.path.getsize(local) == r_size):
                            if status_callback:
#                                status_callback(f"Skipping {basename} because it already exist.")
                                status_callback(f"File(s) already exist.")
                                QApplication.processEvents()
                                skip_files += 1
                            return

                    if cancel_event and cancel_event.is_set():
                        return
                    
                    if status_callback:
                        status_callback(f"Downloading {total_num_filtered_files - num_files - skip_files} more file(s). Total size = ({size_str}). Working on {basename} ({r_size/1024:.1f} KB)")
                        QApplication.processEvents()                     

                    start = time.time()
                    try:
                        if self.protocol == "sftp":
                            try:
                                await asyncio.wait_for(
                                    self._sftp.get(file, local),
                                    timeout=download_timeout
                                )
                            except asyncio.TimeoutError:
                                raise RuntimeError(f"SFTP download timed out after {download_timeout} seconds")
                            except Exception as e:
                                raise RuntimeError(f"SFTP download failed: {e}")

                        else:
                            def _ftp_download():
                                try:
                                    ftp = FTP(timeout=download_timeout)
                                    ftp.connect(self.ip, 21)
                                    ftp.login(self.username, self.password)
                                    dir_path = os.path.dirname(file)
                                    if dir_path and dir_path != '.':
                                        ftp.cwd(dir_path)
                                    with open(local, 'wb') as f:
                                        ftp.retrbinary(f'RETR {basename}', f.write)
                                    ftp.quit()
                                except Exception as inner_e:
                                    # Re-raise as RuntimeError so outer except catches it consistently
                                    raise RuntimeError(f"FTP download failed: {inner_e}") from inner_e

                            loop = asyncio.get_event_loop()
                            try:
                                await asyncio.wait_for(
                                    loop.run_in_executor(None, _ftp_download),
                                    timeout=download_timeout
                                )
                            except asyncio.TimeoutError:
                                raise RuntimeError(f"FTP download timed out after {download_timeout} seconds")

                        os.utime(local, (r_mtime.timestamp(), r_mtime.timestamp()))
                        took = time.time() - start
                        speed = r_size / 1024 / took if took > 0 else 0
#                        print(f"Downloaded {basename} — {r_size/1024:.1f} KB in {took:.2f}s ({speed:.1f} KB/s)")
#                        if status_callback:
#                            status_callback(f"Downloaded {basename} — {r_size/1024:.1f} KB in {took:.2f}s ({speed:.1f} KB/s)")
#                            QApplication.processEvents()
                        num_files += 1
                        size_bytes += os.path.getsize(local)
                    except Exception as e:
                        print(f"FAILED {basename}: {e}")
                        raise

                # === CONCURRENT DOWNLOAD ===
                t_download_start = time.time()
                sem = asyncio.Semaphore(max_concurrent)
                async def limited(f):
                    async with sem:
                        await download_one(f)

                await asyncio.gather(*[limited(f) for f in filtered_files])
                download_time = time.time() - t_download_start

                run_time = time.time() - t0
                print(f"Total download loop time: {download_time:.2f} seconds, "
                      f"Total Run Time: {run_time:.2f} seconds")
                
                return num_files, size_bytes, download_time, run_time, None

            result = asyncio.run(async_download())
            self.close()
            return result

        except Exception as e:
            error_msg = f"Error: {e}"
            print(f"FATAL ERROR: {error_msg}")
            if status_callback:
                status_callback(error_msg)
                QApplication.processEvents()
            self.close()
            return 0, 0, 0, 0, error_msg

######## NOT USED OR NOT NEEDED ######## 
    """
    async def wait_for_new_files(self, baseline_files, timeout=300):
        # Wait for new files only (ignore date_filter).
        # Apply file_filter only to new files.
        # Timeout after X seconds (default 5 minutes).
        seen = set(baseline_files)
        start_time = time.time()
        interval = 5  # seconds

        while time.time() - start_time < timeout:
            if self.cancel_event and self.cancel_event.is_set():
                return []

            # Temporarily disable date filter for this listing
            original_date_filter = getattr(self, 'date_filter', None)
            self.date_filter = None

            try:
                current_files, cur_dates, cur_sizes, total = await self.list_and_filter()
            finally:
                # Always restore original date_filter
                self.date_filter = original_date_filter

            new_files = [f for f in current_files if f not in seen]

            if new_files:
                # Now apply file_filter ONLY to the new files
                filtered_new = []
                for f in new_files:
                    name = os.path.basename(f).lower()
                    pattern = self.file_filter.lower()
                    if pattern.startswith('*'):
                        pattern = '.' + pattern
                    if fnmatch.fnmatch(name, pattern) or pattern in name:
                        filtered_new.append(f)

                if filtered_new:
                    print(f"Found {len(filtered_new)} new matching file(s): {[os.path.basename(f) for f in filtered_new]}")
                    return filtered_new

                # If none matched filter, keep waiting (don't add to seen yet)
                seen.update(current_files)
            else:
                seen.update(current_files)

            if self.status_callback:
                elapsed = int(time.time() - start_time)
                self.status_callback(f"Waiting for new file... {elapsed}s / {timeout}s")

            await asyncio.sleep(interval)

        print("Timeout: No new matching file appeared within 5 minutes")
        return []
    """


    async def run_command(self, command, timeout=60, expected_output=None, status_callback=None):
        """
        Run command via SSH or Telnet based on protocol in credentials.
        Reuses connection when possible.
        """
        reuse_conn = (
            self.run_user_ip_type and
            self.run_user_ip_type == self.ip_type and
            self._conn is not None and
            self.protocol == "sftp"  # Only reuse if we used SSH for download
        )

        full_cmd = command
        print(f"FULL_CMD = {full_cmd}")

        if reuse_conn:
            print(f"Reusing existing SSH connection ({self.ip_type})")
            try:
                if status_callback:
                    status_callback("Connected and Running Command")
                    QApplication.processEvents()                
                result = await self._conn.run(full_cmd, timeout=300)
                output = result.stdout + result.stderr
                success = result.exit_status == 0
                if expected_output and expected_output not in output:
                    success = False
                print(f"SSH Output:\n{output}")
                return output, success, None, None
            except Exception as e:
                print(f"SSH Reuse failed: {e}")
                

        # === NEW CONNECTION — RESPECT PROTOCOL ===
        print(f"Creating new connection for {self.run_user_ip_type}")

        run_ip = self._ip_map.get(self.run_user_ip_type)
        if not run_ip:
            raise RuntimeError(f"No IP for run_user: {self.run_user_ip_type}")


        saved_creds = self._cred_map.get(self.run_user_ip_type)
        #saved_creds = None
        if not saved_creds:
            creds_list = get_credentials(self.run_user_ip_type, self.entry)
            if not creds_list:
                raise RuntimeError(f"No credentials for {self.run_user_ip_type}")
            username, password, protocol = creds_list[0]
            print(f"run user= {self.run_user_ip_type}, self.entry-site_name= {self.entry.get('site_name', '')}")
            print(f"PROTOCOL_if = {protocol}")
        else:
            username, password = saved_creds
            # Get protocol from main cred_store if saved
            cred_info = self.cred_store.get(self.run_user_ip_type)
            protocol = cred_info["protocol"] if cred_info else "sftp"
            print(f"PROTOCOL_else = {protocol}")
        
        
        # === TELNET (protocol == "ftp") ===
        if protocol == "ftp":
            print(f"Using TELNET on {run_ip}:23")
            reader = writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    telnetlib3.open_connection(run_ip, port=23),
                    timeout=15
                )
                print("[TELNET] Connected and Logging in")
                if status_callback:
                    status_callback("Connected and Logging in")
                    QApplication.processEvents()

# ============ def READ_UNTIL===========                    
                async def read_until(prompt, timeout=10):
                    if isinstance(prompt, str):
                        prompts = [prompt]
                    else:
                        prompts = prompt                      
                    buffer = ""
                    start = time.time()
                    while time.time() - start < timeout:
                        try:
                            chunk = await asyncio.wait_for(reader.read(1024), timeout=1)
                            
                            if not chunk:
                                return buffer, False
                            chunk = chunk.replace('\r', '').replace('\0', '')
                            buffer += chunk
                            print(f"[TELNET LOGGING IN] {chunk.strip()}")

                            # ← CHANGED: check any prompt in the list
                            if any(p in buffer for p in prompts):
                                return buffer, True
                        except asyncio.TimeoutError:
                            pass
                    return buffer, False
                
                # Login
                buffer, found = await read_until("login:", 15)
                if not found:
                    return f"Login prompt not found. Got: {buffer}", False, reader, writer
                writer.write(username + "\r\n")
                await writer.drain()
                
                buffer, found = await read_until("password:", 10)
                if not found:
                    return f"Password prompt not found. Got: {buffer}", False, reader, writer
                writer.write(password + "\r\n")
                await writer.drain()
                
                buffer, found = await read_until(["$", "#", ">"], 10)  # 10s max is plenty
                if not any(p in buffer for p in ["$", "#", ">"]):
                    return f"Shell prompt not found. Got: {buffer}", False, reader, writer

                if status_callback:
                    status_callback("Running command")
                    QApplication.processEvents()
                print("[TELNET] Logged in and Running Command")

                # Execute command
                writer.write(full_cmd + "\r\n")
                await writer.drain()
                print(f"[TELNET] await drain complete")
                output = ""
                start = time.time()
                while time.time() - start < timeout:
                    try:
                        
                        chunk = await asyncio.wait_for(reader.read(1024), timeout=5)
                        if not chunk:
                            break
                        chunk = chunk.replace('\r', '').replace('\0', '')
                        output += chunk
                        print(f"[TELNET OUTPUT] {chunk.strip()}")
                        if expected_output and expected_output in output:
                            break
                    except asyncio.TimeoutError:
                        print(f"[TELNET] Exiting command loop")
                        break

                print(f"[TELNET OUTPUT]\n {output}")
                success = (expected_output is None) or (expected_output in output)

                if not self.watch_folder:
                    writer.write("exit\r\n")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    print(f"[TELNET] connection closed")                
                return output, success, reader, writer

            except Exception as e:
                if writer is not None:
                    try:
                        writer.write("exit\r\n")
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                    except:
                        pass
                return f"Telnet failed: {e}", False, None, None

        # === SSH (default) ===
        else:
            print(f"Using SSH on {run_ip}")
            try:
                async with asyncssh.connect(
                    run_ip, port=22,
                    username=username,
                    password=password,
                    known_hosts=None,
                    connect_timeout=10
                ) as conn:
                    print("[SSH] Connected and Running Command")
                    if status_callback:
                        status_callback("Connected and Running Command")
                        QApplication.processEvents()
                    result = await conn.run(full_cmd, timeout=timeout)
                    output = result.stdout + result.stderr
                    success = result.exit_status == 0
                    if expected_output and expected_output not in output:
                        success = False
                    print(f"[SSH OUTPUT]\n{output}")
                    return output, success, None, None
            except Exception as e:
                raise RuntimeError(f"SSH failed: {e}")



    def close(self):
        """Close shared connection — call after download"""
        if self.protocol == "sftp":
            if self._sftp:
                try:
                    self._sftp.exit()
                except:
                    pass
                self._sftp = None
                print("SFTP: Connection closed")
            if self._conn:
                try:
                    self._conn.close()
                    asyncio.get_event_loop().run_until_complete(self._conn.wait_closed())
                except:
                    pass
                self._conn = None
                print("SFTP: Shared connection closed")
        else:
            if self._ftp:
                try:
                    asyncio.get_event_loop().run_until_complete(self._ftp.quit())
                except:
                    pass
                self._ftp = None
            print("FTP: Connection closed")




#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------








class RemoteFileDialog(QDialog): # THIS OPENS WHEN THE BROWSE BUTTON IS CLICKED. 
    def __init__(self, parent, ip, protocol, username, password, ip_type=None, initial_path="/"):
        super().__init__(parent)
        self.setWindowTitle("Browse Remote File System")
        self.ip = ip
        self.protocol = protocol
        self.ip_type = ip_type
        self.username = username
        self.password = password
        self.selected_path = ""
        self.selected_files = ""  # Store comma-separated files and folders
        self.client = None
        self.current_path = self.normalize_path(initial_path)  # Normalize path
        self.sort_by = "Date"  # Track and set default sort state. 
        self.root_item = None  # Store root item for expansion
        self._cached_file_list = None 
        self._cached_path = None
        # TEST VARIABLES
        self._in_populate = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        layout = QVBoxLayout()
        # Path input layout with up button
        path_layout = QHBoxLayout()
        self.up_button = QPushButton("↑")
#        self.up_button.setText("↑")
        self.up_button.clicked.connect(self.navigate_up)
#        self.up_button.setFocusPolicy(Qt.NoFocus)  # optional but safe
        path_layout.addWidget(self.up_button)
        self.path_edit = QLineEdit()
        self.path_edit.setText(self.current_path)
        self.path_edit.returnPressed.connect(self.navigate_to_path)
        path_layout.addWidget(self.path_edit)
        self.sort_button = QPushButton("Sort: Date")
        self.sort_button.clicked.connect(self.toggle_sort)
#        self.sort_button.setFocusPolicy(Qt.NoFocus)
        path_layout.addWidget(self.sort_button)
        layout.addLayout(path_layout)

        splitter = QSplitter(Qt.Horizontal)

        self.left_tree = QTreeView()
        self.left_tree.setIndentation(10)  # Maintain chevrons with minimal spacing
        self.left_tree.setSelectionMode(QTreeView.SingleSelection)
        self.left_model = QStandardItemModel(0, 1)  # Only one column: Name
        self.left_model.setHorizontalHeaderLabels(["Folder Name"])
        self.left_tree.setModel(self.left_model)
        self.left_tree.setHeaderHidden(False)
        self.left_tree.setColumnWidth(0, 150)  # Optional starting width, will stretch anyway
        self.left_tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.left_tree.setExpandsOnDoubleClick(True)
        self.left_tree.setItemsExpandable(True)
        loading_left = QStandardItem("Loading directory...")
        loading_left.setSelectable(False)
        self.left_model.appendRow(loading_left)        
        splitter.addWidget(self.left_tree)

        self.right_tree = QTreeView()
        self.right_tree.setIndentation(10)  # Maintain chevrons with minimal spacing
        self.right_tree.setSelectionMode(QTreeView.MultiSelection)  # Enable multi-selection
        self.right_model = QStandardItemModel(0, 2)  # Two columns: Name, Modified
        self.right_model.setHorizontalHeaderLabels(["File/Folder Name", "Date Modified"])
        self.right_tree.setModel(self.right_model)
        self.right_tree.setHeaderHidden(False)
        self.right_tree.setColumnWidth(0, 300)  # Name column
        self.right_tree.setColumnWidth(1, 150)  # Modified column
        self.right_tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.right_tree.setExpandsOnDoubleClick(True) 
#        self.right_tree.setItemsExpandable(True)
        loading_right_name = QStandardItem("Loading...")
        loading_right_date = QStandardItem("")
        loading_right_name.setSelectable(False)
        self.right_model.appendRow([loading_right_name, loading_right_date])                
        splitter.addWidget(self.right_tree)
        splitter.setStretchFactor(0, 0)   # Left widget: no stretching
        splitter.setStretchFactor(1, 1)   # Right widget: takes all extra space

        # Optional: give the left side a sensible initial width
        splitter.setSizes([200, 400])     # Left ~200px, right gets the rest

        layout.addWidget(splitter)

        # Buttons
        button_box = QHBoxLayout()
        note_label = QLabel("New File Filter")
        note_label.setStyleSheet("font-size: 14px; color: #E0E0E0; padding: 2px;")
        button_box.addWidget(note_label)
        self.new_file_filter = QLineEdit()
        self.new_file_filter.setText(self.selected_files)
        button_box.addWidget(self.new_file_filter)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
#        ok_btn.setFocusPolicy(Qt.NoFocus)
#        cancel_btn.setFocusPolicy(Qt.NoFocus)
        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

        self.setLayout(layout)
        self.setMinimumSize(700, 600)


        QTimer.singleShot(200, self._load_content)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Only allow Enter in the path_edit
            if self.path_edit.hasFocus():
                self.navigate_to_path()
            # Ignore Enter everywhere else — no default button activation
            event.accept()
            return
        super().keyPressEvent(event)

    def _load_content(self):
        """Load everything after the window is visible."""
        self.initialize_connection()

        if self.client is None:
            return
        try:
            self.populate_directories(self.current_path)
            self.populate_contents(self.current_path)
            # Connect signals for navigation
            self.left_tree.expanded.connect(self.on_left_expanded)
            self.right_tree.expanded.connect(self.on_right_expanded)
            self.left_tree.clicked.connect(self.on_left_expanded)
            self.right_tree.selectionModel().selectionChanged.connect(self.on_right_selected_files)            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load directory:\n{str(e)}")
            if self.client:
                self.client.close()
                self.client = None         


    def initialize_connection(self):
        # Initialize connection
        self.setCursor(Qt.WaitCursor)
        try:
            if self.protocol == "sftp":
                t0 = time.time()
                transport = paramiko.Transport((self.ip, 22))
                transport.connect(username=self.username, password=self.password)
                self.client = paramiko.SFTPClient.from_transport(transport)
                print(f"  Using sFTP Connection, took {time.time() - t0} to connect")
            else:  # ftp
                t0 = time.time()
                self.client = FTP(self.ip)
                self.client.login(user=self.username, passwd=self.password)
                print(f"  Using FTP Connection, took {time.time() - t0} to connect")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
            self.reject()
            return
        finally:
            self.setCursor(Qt.ArrowCursor)  # Restore normal cursor

    def ensure_connected(self):
        """Make sure we have a working client, reconnect if necessary."""
        if self.client is None:
            self.initialize_connection()
            return

        try:
            if self.protocol == "ftp":
                self.client.voidcmd("NOOP")
            elif self.protocol == "sftp":
                self.client.stat('.')
            return

        except Exception as e:
            print(f"Connection check failed: {e}")
            try:
                self.client.close()
            except:
                pass
            self.client = None
            self.initialize_connection()

# ==============================================================================

    def populate_directories(self, path="/", parent_item=None, select_after=True):
        print("STARTING: populate_directories")
        t0 = time.time()
        self.setCursor(Qt.WaitCursor)
        self.ensure_connected()
        original_path = path
        path = self.normalize_path(path)
        
        # Determine correct root for this connection
        root_path = "/c:/" if self.protocol == "sftp" else "/c/"
        root_path = self.normalize_path(root_path)
        file_list = []
        self._in_populate = True
        try:
            if parent_item is None:
                print(f"    populate_directories - Model Cleared, path = {path}")
                self.left_model.clear()
                self.left_model.setHorizontalHeaderLabels(["Folder Name"])
                parent_item = self.left_model.invisibleRootItem()

                # Always create root item
                root_item = QStandardItem(root_path)
                root_item.setData(root_path, Qt.UserRole)
                root_item.setData(True, Qt.UserRole + 1)
                parent_item.appendRow(root_item)
                self.left_tree.expand(self.left_model.indexFromItem(root_item))

                # Default: we'll populate under root
                target_parent = root_item

                # Try to list the requested path first
                
                try:
                    t1 = time.time()
                    if self.protocol == "sftp":
                        file_list = self.client.listdir_attr(path)
                        
                    else:
                        self.client.retrlines(f"LIST {path}", lambda x: file_list.append(x))
                    
                    self._cached_file_list = file_list
                    self._cached_path = path
                    # SUCCESS: path is valid → safe to build full hierarchy
                    if path != root_path:
                        rel_path = path[len(root_path):].strip("/")
                        components = [c for c in rel_path.split("/") if c]
                        current_item = root_item
                        accumulated = root_path
                        for comp in components:
                            full_path = accumulated.rstrip("/") + "/" + comp
                            full_path = self.normalize_path(full_path)
                            node = QStandardItem(comp)
                            node.setData(full_path, Qt.UserRole)
                            node.setData(True, Qt.UserRole + 1)
                            current_item.appendRow(node)
                            node.appendRow(QStandardItem())
                            current_item = node
                            accumulated = full_path
                            self.left_tree.expand(self.left_model.indexFromItem(node))
                        target_parent = current_item
                    print(f"  Populate_Directories: File Listing and Build Hierarchy took {time.time() - t1}")
                except Exception:
                    # FAILED: path invalid → fall back to root
                    extra_message = ""
                    if self.ip_type == "Custom User":
                        extra_message = ("\n\nCheck the following:"
                        "\nVerify you are using the correct protocol" 
                        "\n  SM's are protocol dependant" 
                        "\nNext check the start of the path" 
                        "\n  It should be as follows:"
                        "\n   ftp: SP = /c/, SM = / \n   sftp: SP = c:/, SM = c:/ ")

                    QMessageBox.warning(self, "Directory Not Accessible",
                                        f"Cannot access:\n{original_path}{extra_message}\n\nFalling back to root directory.")
                    path = root_path
                    self.current_path = root_path
                    self.path_edit.setText(root_path)
                    self.up_button.setEnabled(False)

                    # List root contents instead
                    if self.protocol == "sftp":
                        file_list = self.client.listdir_attr(root_path)
                    else:
                        self.client.cwd(root_path)
                        self.client.retrlines(f"LIST {root_path}", lambda x: file_list.append(x))

                    # Do NOT build hierarchy — target_parent stays as root_item

            else:
                target_parent = parent_item
                file_list = []
                print(f"    populate directories - path = {path}")
                try:
                    if self.protocol == "sftp":
                        file_list = self.client.listdir_attr(path)
                    else:
                        self.client.retrlines(f"LIST {path}", lambda x: file_list.append(x))
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Cannot access directory:\n{path}\n{str(e)}")
                    parent_item.appendRow(QStandardItem())  # restore dummy
                    return

            # Now populate the children under target_parent using file_list
            if target_parent.rowCount() > 0:
                target_parent.removeRows(0, target_parent.rowCount())
            t2 = time.time()
            for item in file_list:
                name = item.filename if self.protocol == "sftp" else item.split()[-1]
                is_dir = (item.st_mode & 0o40000) if self.protocol == "sftp" else item.startswith("d")
                if not is_dir:
                    continue

                child_path = path.rstrip("/") + "/" + name
                child_path = self.normalize_path(child_path)

                dir_item = QStandardItem(name)
                dir_item.setData(child_path, Qt.UserRole)
                dir_item.setData(True, Qt.UserRole + 1)
                target_parent.appendRow(dir_item)
                dir_item.appendRow(QStandardItem(""))  # dummy
            print(f"  Populate_Directories: file listing under target parent took {time.time() - t2}")
            self.left_model.sort(0, Qt.AscendingOrder)
            self.left_tree.header().setStretchLastSection(True)

            # Ensure selection matches current path

            if select_after:
                self.select_path_in_tree(self.left_model, self.left_tree, self.current_path)

            print(f"Entire Populate_Directories took {time.time() - t0}")
        except Exception as e:
            QMessageBox.critical(self, "Critical Error",
                                 f"Failed to load directory tree:\n{str(e)}")
            if self.client:
                self.client.close()
                self.client = None
        finally:
            self.setCursor(Qt.ArrowCursor)  # Restore normal cursor  
            self._in_populate = False         

    def populate_contents(self, path="/", parent_item=None):
        print("STARTING: populate_contents")
        self.setCursor(Qt.WaitCursor)
        t0 = time.time()
        self.ensure_connected()

        path = self.normalize_path(path)
        root_path = "/c:/" if self.protocol == "sftp" else "/c/"
        root_path = self.normalize_path(root_path)
        file_list = []
        self._in_populate = True
        try:
            if parent_item is None:
                self.right_model.clear()
                self.right_model.setHorizontalHeaderLabels(["File/Folder Name", "Date Modified"])
                parent_item = self.right_model.invisibleRootItem()
            if (hasattr(self, '_cached_path') and 
                self._cached_path == path and 
                self._cached_file_list is not None):
                file_list = self._cached_file_list
                print("    populate_contents: using cached file list")
            else:
                print("    populate_contents: doing fresh listing")
                try:
                    if self.protocol == "sftp":
                        file_list = self.client.listdir_attr(path)
                    else:
                        self.client.retrlines(f"LIST {path}", lambda x: file_list.append(x))
                except Exception:
                    # Silent fallback — directories already warned
                    path = root_path
                    self.current_path = root_path  # Keep in sync

                    if self.protocol == "sftp":
                        file_list = self.client.listdir_attr(root_path)
                    else:
                        self.client.cwd(root_path)
                        self.client.retrlines(f"LIST {root_path}", lambda x: file_list.append(x))
                self._cached_file_list = file_list
                self._cached_path = path
            if parent_item.rowCount() > 0:
                parent_item.removeRows(0, parent_item.rowCount())

            for item in file_list:
                name = item.filename if self.protocol == "sftp" else item.split()[-1]
                is_dir = (item.st_mode & 0o40000) if self.protocol == "sftp" else item.startswith("d")

                # mtime parsing
                if self.protocol == "sftp":
                    mtime = datetime.fromtimestamp(item.st_mtime)
                else:
                    try:
                        parts = item.split()
                        date_str = " ".join(parts[5:8]) if len(parts) >= 8 else ""
                        try:
                            mtime = datetime.strptime(date_str, "%b %d %Y %H:%M")
                            mtime = mtime.replace(year=datetime.now().year)
                        except ValueError:
                            mtime = datetime.strptime(date_str, "%b %d %Y")
                    except:
                        mtime = datetime.now()

                child_path = path.rstrip("/") + "/" + name
                child_path = self.normalize_path(child_path)

                name_item = QStandardItem(name)
                name_item.setData(child_path, Qt.UserRole)
                name_item.setData(is_dir, Qt.UserRole + 1)
                name_item.setData(mtime, Qt.UserRole + 2)
                date_item = QStandardItem(mtime.strftime("%Y-%m-%d %H:%M"))

                parent_item.appendRow([name_item, date_item])

                if is_dir:
                    name_item.appendRow([QStandardItem(""), QStandardItem("")])

            if self.sort_by == "name":
                self.right_model.sort(0, Qt.AscendingOrder)
            else:
                self.right_model.sort(1, Qt.DescendingOrder)

            if parent_item == self.right_model.invisibleRootItem():
                self.right_tree.header().setStretchLastSection(False)
                self.right_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
                self.right_tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
                self.right_tree.setColumnWidth(1, 150)
            print(f"Entire Populate_Contents took {time.time() - t0}")
        except Exception as e:
            QMessageBox.critical(self, "Critical Error",
                                 f"Failed to load file list:\n{str(e)}")
            if self.client:
                self.client.close()
                self.client = None
        finally:
            self.setCursor(Qt.ArrowCursor)  # Restore normal cursor
            self._in_populate = False


# ================= HELPER FUNCTIONS =============================================================

    def toggle_sort(self):
        self.sort_by = "date" if self.sort_by == "name" else "name"
        self.sort_button.setText(f"Sort: {'Date' if self.sort_by == 'date' else 'Name'}")
        self.populate_contents(self.current_path)
            


    def normalize_path(self, path: str) -> str:
#        """
#        Normalize any incoming path to the internal SFTP/FTP format we use everywhere.
#        Rules:
#        - Always use forward slashes
#        - Ensure leading slash
#        - For FTP on Windows (sp_ip): convert C:\ or C:/ → /C/
#        - For FTP on Unix (host_ip): strip any leading C: entirely
#        - For SFTP: keep as-is but ensure leading /
#        """

        if self.protocol == "sftp":
            path = path.replace('\\', '/').lower().strip().strip('/')#.lstrip('/').rstrip('/')
        else:
            path = path.replace('\\', '/').lower().strip()

        if not path:
            # Empty → default root
            return "/c:/" if self.protocol == "sftp" else "/c/"

        if self.protocol == "sftp":
            if hasattr(self, 'ip_type'):  # ip_type is set before dialog creation
                if self.ip_type in ("sp_ip", "host_ip"):
                    # Unix FTP server → ignore any C: prefix
                    if path.startswith('c:'):
                        path = path[2:]
                        return 'c:' + path
                    elif path.startswith('/c/'):
                        path = path[3:]
                        return 'c:' + path
                    elif path.startswith('/c:/'):
                        path = path[4:] 
                        return 'c:' + path                      
                    return path        
                else:
                    return path      
            else:
                # Safety fallback if ip_type not available
                return path
            
        # FTP specific handling based on ip_type
        if hasattr(self, 'ip_type'):  # ip_type is set before dialog creation
            if self.ip_type == "sp_ip":
                if path.startswith('c:'):
                    path = path[2:]
                    return '/c/' + path.lstrip('/')
                elif path.startswith('/c/'):
                    path = path[3:]
                    return '/c/' + path.lstrip('/')
                elif path.startswith('/c:/'):
                    path = path[4:] 
                    return '/c/' + path.lstrip('/')
                return path
            elif self.ip_type == "host_ip":
                if path.startswith('c:'):
                    path = path[2:]
                    return '/' + path.lstrip('/')
                elif path.startswith('/c/'):
                    path = path[3:]
                    return '/' + path.lstrip('/')
                elif path.startswith('/c:/'):
                    path = path[4:]
                    return '/' + path.lstrip('/')
                return path
            else:
                return path
        else:
            # Safety fallback if ip_type not available
            return path


    def select_path_in_tree(self, model, tree, target_path):
        print(f"STARTING: select_path_in_tree")
        t0 = time.time()
        target_path = self.normalize_path(target_path)
#        print(f"start SPIT: target_path = {target_path}")
        
        def find_item(parent_item, components):
            if not components:
                return parent_item
            for row in range(parent_item.rowCount()):
                child = parent_item.child(row, 0)
#                print(f"child1 {child.data(Qt.UserRole)}")
                if child and child.text().strip().lower() == components[0].strip().lower():
#                    print(f"child2 {child.data(Qt.UserRole)}")
                    # Lazy-load if only dummy child exists
                    if child.rowCount() == 1 and child.child(0, 0) and child.child(0, 0).text() == "":
                        print(f"child3 {child.data(Qt.UserRole)}")
                        child_path = child.data(Qt.UserRole)
                        child_path = self.normalize_path(child_path)
                        self.populate_directories(child_path, child, select_after=False)
                    return find_item(child, components[1:])
            return None

        root_path = "c:" if self.protocol == "sftp" else "/c/"
        rel = target_path[len(root_path):] if target_path.startswith(root_path) else target_path
        components = [c for c in rel.strip("/").split("/") if c]

        start_item = model.item(0, 0)  # root item
        if target_path == root_path:
            components = []
        item = find_item(start_item, components)
        if item:
            idx = model.indexFromItem(item)
            tree.setCurrentIndex(idx)
            # Expand all parents
            parent_idx = idx.parent()
            while parent_idx.isValid():
                tree.expand(parent_idx)
                parent_idx = parent_idx.parent()
                tree.scrollTo(idx, QTreeView.PositionAtTop)
                vertical_scrollbar = tree.verticalScrollBar()
                if vertical_scrollbar:
                    if vertical_scrollbar.maximum() - vertical_scrollbar.value() > 4:
                        vertical_scrollbar.setValue(vertical_scrollbar.value() - 4)               
        print(f"    target_path = {target_path} \n    root_path = {root_path} \n    rel = {rel} \n    found folder = {item.data(Qt.UserRole)}, \n    select_path_in_tree took {time.time() - t0}\nFinished: select_path_in_tree\n")


    def _navigate_to_path_success(self, path):
        """Common code run after successful navigation from any source."""
        # THIS IS USED IN ON_(LEFT, RIGHT)_EXPANDED FUNCTIONS. 
        print("STARTING: _navigate_to_path_success")
        self.current_path = path
        self.path_edit.setText(path)
        root_path = "c:" if self.protocol == "sftp" else "/c/"
        self.up_button.setEnabled(self.current_path != root_path)


# ==================== NAVIGATION FUNCTIONS ==========================================================

    def on_left_expanded(self, index):
        if getattr(self, "_in_populate", False):
            print("SKIPPED: on_left_expanded")
            return
        print("STARTING: on_left_expanded")        
        self.ensure_connected()
        item = self.left_model.itemFromIndex(index)
        if not item or not item.data(Qt.UserRole + 1):
            return

        path = item.data(Qt.UserRole)
        path = self.normalize_path(path)

        try:
            if self.protocol == "sftp":
                self.client.stat(path)
            else:
                self.client.cwd(path)
                self.client.cwd(self.current_path)  # return to current

            if item.rowCount() > 0:
                item.removeRows(0, item.rowCount())

            self._navigate_to_path_success(path)
            self.populate_directories(path, parent_item=item)
            self.populate_contents(path)

        except Exception:
            QMessageBox.critical(self, "Error", f"Directory no longer exists:\n{path}")
            if item.rowCount() == 0:
                item.appendRow(QStandardItem(""))  # restore dummy
            if self.client:
                self.client.close()
                self.client = None

    def on_right_expanded(self, index):
        if getattr(self, "_in_populate", False):
            print("SKIPPED: on_right_expanded")
            return
        print("STARTING: on_right_expanded")     
        self.ensure_connected()
        item = self.right_model.itemFromIndex(index)
        if not item or not item.data(Qt.UserRole + 1):
            return

        path = item.data(Qt.UserRole)
        path = self.normalize_path(path)
        try:
            if self.protocol == "sftp":
                self.client.stat(path)
            else:
                self.client.cwd(path)
                self.client.cwd(self.current_path)

            if item.rowCount() > 0:
                item.removeRows(0, item.rowCount())

            print(f"on_right_expanded: path = {path}")
            print(f"on_right_expanded is STARTING - _navigate_to_path_success")
            self._navigate_to_path_success(path)
            print(f"on_right_expanded is STARTING - populate_directories with path {path}")
            self.populate_directories(path)#, parent_item=item) I REMOVED THIS PARENT ITEM SO IT REBUILDS FROM SCRATCH.
            print(f"on_right_expanded is STARTING - populate_contents")
            self.populate_contents(path)

        except Exception:
            QMessageBox.critical(self, "Error", f"Directory no longer exists:\n{path}")
            if item.rowCount() == 0:
                item.appendRow(QStandardItem(""))  # restore dummy
            if self.client:
                self.client.close()
                self.client = None  

    def navigate_up(self):
        print("STARTING: navigate_up")
        self.ensure_connected()
        root_path = "c:" if self.protocol == "sftp" else "/c/"
        if self.current_path == root_path:
            return
        # Calculate parent directory, then normalize it properly
        parent_path_raw = os.path.dirname(self.current_path.rstrip('/'))
        parent_path = self.normalize_path(parent_path_raw)
        # If normalizing brought us below root, force root
        if not parent_path or parent_path == "." or parent_path == "/":
            parent_path = root_path
        try:
            if self.protocol == "sftp":
                self.client.stat(parent_path)
            else:  # ftp
                self.client.cwd(parent_path)
            self.current_path = parent_path
            self.path_edit.setText(parent_path)
            self.up_button.setEnabled(self.current_path != root_path)

            self.populate_contents(self.current_path)
            self.select_path_in_tree(self.left_model, self.left_tree, self.current_path)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to navigate up to {parent_path}: {str(e)}")
            if self.client:
                self.client.close()
                self.client = None

    def navigate_to_path(self):
        print("STARTING: navigate_to_path")
        """ Navigates to self typed path """
        self.ensure_connected()
        raw_path = self.path_edit.text().strip().lower()
        if not raw_path:
            return
        path = self.normalize_path(raw_path)
        print(f"navigate_to_path - raw_path = {raw_path}, path = {path}")
        try:
            if self.protocol == "sftp":
                self.client.stat(path)
            else:  # ftp
                self.client.cwd(path)
            self.current_path = path
            self.path_edit.setText(path)
            root_path = "c:" if self.protocol == "sftp" else "/c/"
            self.up_button.setEnabled(self.current_path != root_path)

            self.populate_contents(self.current_path)
            self.select_path_in_tree(self.left_model, self.left_tree, self.current_path)
    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid or inaccessible directory:\n{raw_path}")
            if self.client:
                self.client.close()
                self.client = None


# ============ SELECTING FILES FOR NEW FILE FILTER ============================================

    def on_right_selected_files(self, selected, deselected):
        _, selected_files = self.get_selected_path()
        self.new_file_filter.setText(selected_files)

    def get_selected_path(self):
        selected_indexes = self.right_tree.selectedIndexes()
        if not selected_indexes:
            return self.current_path, ""
        selected_items = []
        for index in selected_indexes:
            item = self.right_model.itemFromIndex(index)
            if item:
                is_dir = item.data(Qt.UserRole + 1)
                path = item.data(Qt.UserRole)
                if path:
                    name = os.path.basename(path)
                    if is_dir:
                        selected_items.append(f"/{name}/")
                    else:
                        selected_items.append(name)
        selected_files_str = ",".join(selected_items) if selected_items else ""
        return self.current_path, selected_files_str

    def accept(self):
        self.selected_path, self.selected_files = self.get_selected_path()
        super().accept()

# =============== CLOSE THE BROWSE WINDOW =========================================================
    def reject(self):
        print("Connection Closed")
        if self.client:
            self.client.close()
            self.client = None
        super().reject()






#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------







class MainWindow(QMainWindow):
    def __init__(self, *args):
        super().__init__()
        self.setWindowTitle(VERSION)

        # Parse args
        self.mode = "full"
        self.use_current_dat = False
        for arg in args:
            if arg in APP_CONFIG:
                self.mode = arg
                self.setWindowTitle(f"{VERSION} (mode = {self.mode})")
        print(f"Initialize Modes Received = {args}")

        # Load config only if running as main script
        if __name__ == "__main__":
            self.config = load_config() # This loads the last state at app close. 
        else:
            self.config = {
                "siddb_path": DEFAULT_SIDDB_PATH,
                "custom_filters": [],
                "remote_locations": [],
                "local_locations": [],
                "last_selections": {
                    "sid": "",
                    "ip_type": "sp_ip",
                    "ip": "",
                    "username": "",
                    "remote_loc": "",
                    "local_loc": os.getcwd(),
                    "file_filter": "",
                    "protocol": "sftp",
                    "date_filter_enabled": False,
                    "start_date": "",
                    "end_date": "",
                    "quick_date": "",
                    "incremental_download": False,
                    "timed_download": False,
                    "incremental_period": "6am daily",
                    "filechecks": [],
                    "filemode": ""
                },
                "app_mode": {}
            }

        self.app_config = self.config["app_mode"].get(self.mode, {})
        self.siddb = load_siddb(self.config["siddb_path"])
        self.file_checks = self.config.get("file_checks", FILE_CHECKS).get("MR", [])  # Default to MR modality
        self.entry = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        # === STORE ALL CREDENTIALS ===
        self.cred_store = {}

        # Initialize LogDownloader
        self.downloader = LogDownloader(
            self.config["last_selections"].get("sid", ""),
            self.config["last_selections"].get("file_filter", ""),
            self.config["last_selections"].get("remote_loc", ""),
            self.config["last_selections"].get("local_loc", os.getcwd()),
            self.config["last_selections"].get("protocol", "sftp")
        )
        self.downloader.set_ip(
            self.config["last_selections"].get("ip", ""),
            self.config["last_selections"].get("ip_type", "sp_ip")
        )
        if self.config["last_selections"].get("username", "") and self.config["last_selections"].get("password", ""):
            self.downloader.set_credentials(
                self.config["last_selections"].get("username", ""),
                self.config["last_selections"].get("password", "")
            )

        # Apply modernized stylesheet
        self.set_stylesheet(theme="dark")        

        # Center on main screen
        self.center_on_screen()

        layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)  # Increase row spacing
        self.form_layout.setLabelAlignment(Qt.AlignRight)  # Align labels close to widgets

        # Initialize Show Rows
        self.show_sid = True
        self.show_filechecks = True
        self.show_ip = True
        self.show_remote = True
        self.show_filter = True
        self.show_date = True
        self.show_local = True
        self.show_download = True
        self.show_status = True

        # Set initial row visibility based on mode
        self.hide_rows_by_mode()
#        print(f"Show __init__ flags: sid={self.show_sid}, filechecks={self.show_filechecks}, ip={self.show_ip}, remote={self.show_remote}, filter={self.show_filter}, date={self.show_date}, local={self.show_local}, download={self.show_download}, status={self.show_status}")

        # SID/Site/SIDDB-Path Row
        self.sid_combo = QComboBox()
        self.populate_sid_combo("site_name")
        self.sid_combo.currentIndexChanged.connect(self.load_all_credentials)
        self.sort_button = QPushButton("Sort by SID")
        self.sort_button.clicked.connect(self.toggle_sort)
        self.sort_button.setFixedWidth(125)
        self.change_siddb_btn = QPushButton("Change SIDDB Path")
        self.change_siddb_btn.clicked.connect(self.change_siddb_path)
        self.change_siddb_btn.setFixedWidth(125)
        sid_hbox = QHBoxLayout()
        sid_hbox.addWidget(self.sid_combo)
        sid_hbox.addWidget(self.sort_button)
        sid_hbox.addWidget(self.change_siddb_btn)
        if self.show_sid:
            self.form_layout.addRow("SID/Site:", sid_hbox)

        # Filechecks Row
        self.filecheck_checkboxes = []
        self.filecheck_configs = {}
        self.filechecks_hbox = QHBoxLayout()
        self.filechecks_hbox.addSpacing(30)
        self.filecheck_label = QLabel("File Checks:")
        self.filecheck_label.setAlignment(Qt.AlignRight | Qt.AlignTop)  # Align label right and top
        self.filechecks_grid = QGridLayout()
        self.filechecks_grid.setSpacing(10)  # Match form_layout spacing
        columns = 5  # Number of checkboxes per row
        for i, check in enumerate(self.file_checks):
            checkbox = QCheckBox(check["title"])
            checkbox.setChecked(check["title"] in self.config["last_selections"].get("filechecks", self.app_config.get("defaults", {}).get("filechecks", [])))
            checkbox.stateChanged.connect(self.update_cycle_checks_btn)  # Update filecheck_filter on change
            self.filecheck_checkboxes.append(checkbox)
            self.filecheck_configs[check["title"]] = {
                "usertype": check["usertype"],
                "remote_loc": check["remote_loc"],
                "file_filter": check["file_filter"],
                "command_to_run": check.get("command_to_run"),
                "run_user": check.get("run_user"),
                "run_command_mode": check.get("run_command_mode", False),
                "watch_folder": check.get("watch_folder", False)
            }
            row = i // columns
            col = i % columns
            self.filechecks_grid.addWidget(checkbox, row, col)
        self.show_custom_btn = QPushButton("Show Custom")
        self.show_custom_btn.clicked.connect(self.toggle_custom_rows)
        self.show_custom_btn.setFixedWidth(120)
        # Create buttons to check and clear checkboxes
        self.cycle_check_btn = QPushButton("Check All")
        self.cycle_check_btn.clicked.connect(self.cycle_checks)
        self.cycle_check_btn.setFixedWidth(120)
        self.filemode_combo = QComboBox()
        self.filemode_combo.addItems(["File Checks", "Custom Filter", "Append to Custom"])
        self.filemode_combo.setFixedWidth(120)
        # Stack buttons vertically
        buttons_vbox = QVBoxLayout()
        buttons_vbox.addWidget(self.show_custom_btn)
        buttons_vbox.addWidget(self.cycle_check_btn)
        buttons_vbox.addWidget(self.filemode_combo)
        buttons_vbox.setAlignment(Qt.AlignTop)
        self.filechecks_hbox.addLayout(self.filechecks_grid)
        self.filechecks_hbox.addLayout(buttons_vbox)
        self.form_layout.addRow(self.filecheck_label, self.filechecks_hbox)
        # IP Type, IP, Protocol, Username, and Password Row
        self.ip_hbox = QHBoxLayout()
        self.ip_hbox.addSpacing(0)
        self.ip_type_combo = QComboBox()
#        self.ip_type_combo.addItems(["sp_ip", "host_ip", "display_ip"])  # Exclude Custom User initially
        self.ip_type_combo.setFixedWidth(90)
        self.ip_hbox.addWidget(QLabel("Custom User Type:"))
        self.ip_hbox.addWidget(self.ip_type_combo)
        self.ip_hbox.addSpacing(60)
        self.ip_edit = QLineEdit()
        self.ip_edit.setFixedWidth(120)  # Size for IP address
        self.ip_edit.setEnabled(True)  # Always editable
        self.ip_edit.textChanged.connect(self.refresh_ip_type_combo)
        self.ip_hbox.addWidget(QLabel("Custom IP:"))
        self.ip_hbox.addWidget(self.ip_edit)
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["sftp", "ftp"])
        self.ip_hbox.addWidget(QLabel("Custom Protocol:"))
        self.ip_hbox.addWidget(self.protocol_combo)
        
        self.username_edit = QLineEdit()
        self.username_edit.setFixedWidth(150)  
        self.username_edit.textChanged.connect(self.refresh_ip_type_combo)
        self.ip_hbox.addWidget(QLabel("Custom Username:"))
        self.ip_hbox.addWidget(self.username_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setFixedWidth(150)  
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.textChanged.connect(self.refresh_ip_type_combo)
        self.ip_hbox.addWidget(QLabel("Custom Password:"))
        self.ip_hbox.addWidget(self.password_edit)
        self.ip_hbox.addStretch(2)
        if self.show_ip:
            self.form_layout.addRow(self.ip_hbox)

        # Remote Location Row
        self.remote_loc_combo = QComboBox()
        self.remote_loc_combo.setEditable(True)
        self.remote_loc_combo.addItems(self.config.get("remote_locations", []) + self.get_default_remote_locs())
        self.remote_loc_combo.setMinimumWidth(500)
        remote_browse_btn = QPushButton("Browse")
        remote_browse_btn.clicked.connect(self.browse_remote)
        remote_browse_btn.setFixedWidth(108)
        remote_save_btn = QPushButton("Save Preset")
        remote_save_btn.clicked.connect(self.save_remote_loc)
        remote_save_btn.setFixedWidth(106)
        remote_delete_btn = QPushButton("Delete Preset")
        remote_delete_btn.clicked.connect(self.delete_remote_loc)
        remote_delete_btn.setFixedWidth(107)
        remote_hbox = QHBoxLayout()
        remote_hbox.addWidget(self.remote_loc_combo)
        remote_hbox.addWidget(remote_browse_btn)
        remote_hbox.addWidget(remote_save_btn)
        remote_hbox.addWidget(remote_delete_btn)
        if self.show_remote:
            self.form_layout.addRow("Remote Folder:", remote_hbox)

        # File Filter Row
        self.filter_combo = QComboBox()
        self.filter_combo.setEditable(True)
        self.filter_combo.addItems(self.config.get("custom_filters", []) + DEFAULT_FILTERS)
        self.filter_combo.setMinimumWidth(500)
        filter_info_btn = QPushButton("Filter Info")
        filter_info_btn.clicked.connect(self.show_filter_info)
        filter_info_btn.setFixedWidth(108)
        filter_save_btn = QPushButton("Save Preset")
        filter_save_btn.clicked.connect(self.save_filter)
        filter_save_btn.setFixedWidth(106)
        filter_delete_btn = QPushButton("Delete Preset")
        filter_delete_btn.clicked.connect(self.delete_filter)
        filter_delete_btn.setFixedWidth(107)
        filter_hbox = QHBoxLayout()
        filter_hbox.addWidget(self.filter_combo)
        filter_hbox.addWidget(filter_info_btn)
        filter_hbox.addWidget(filter_save_btn)
        filter_hbox.addWidget(filter_delete_btn)
        if self.show_filter:
            self.form_layout.addRow("Custom File Filter:", filter_hbox)

        # Date filter Row
        self.date_filter_widget = QWidget()
        date_filter_layout = QHBoxLayout()
        date_filter_layout.addSpacing(100)
        date_filter_layout.setContentsMargins(0,0,0,0) 
        self.date_filter_var = QCheckBox("Filter by Date")
        date_filter_layout.addWidget(self.date_filter_var)
        date_filter_layout.addWidget(QLabel("Start:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setFixedWidth(100)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.start_date_edit.dateChanged.connect(self.on_date_change)
        date_filter_layout.addWidget(self.start_date_edit)
        date_filter_layout.addWidget(QLabel("End:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setFixedWidth(100)
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.end_date_edit.dateChanged.connect(self.on_date_change)
        date_filter_layout.addWidget(self.end_date_edit)
        set_end_today_btn = QPushButton("Set End to Today")
        set_end_today_btn.clicked.connect(self.set_end_to_today)
        set_end_today_btn.setFixedWidth(108)
        date_filter_layout.addWidget(set_end_today_btn)
        date_filter_layout.addWidget(QLabel("Range from End:"))
        self.quick_date_combo = QComboBox()
        self.quick_date_combo.setFixedWidth(100)
        self.quick_date_combo.addItems(["", "1 day", "3 days", "1 week", "1 month", "1 year", "5 years"])
        self.quick_date_combo.currentTextChanged.connect(self.on_quick_date_select)
        self.from_combo = False
        date_filter_layout.addWidget(self.quick_date_combo)
        left_btn = QPushButton("◀")
        left_btn.clicked.connect(lambda: self.cycle_range(-1))
        left_btn.setFixedWidth(30)
        right_btn = QPushButton("▶")
        right_btn.clicked.connect(lambda: self.cycle_range(1))
        right_btn.setFixedWidth(30)
        date_filter_layout.addWidget(left_btn)
        date_filter_layout.addWidget(right_btn)        
        date_filter_layout.addStretch(2)
        self.date_filter_widget.setLayout(date_filter_layout)
        if self.show_date:
            self.form_layout.addRow(self.date_filter_widget)
        
        # Local Location Row
        self.local_loc_combo = QComboBox()
        self.local_loc_combo.setEditable(True)
        self.local_loc_combo.addItems(self.config.get("local_locations", []) + DEFAULT_LOCAL_LOCS)
        self.local_loc_combo.setMinimumWidth(500)
        local_browse_btn = QPushButton("Browse")
        local_browse_btn.clicked.connect(self.browse_local)
        local_browse_btn.setFixedWidth(52)
        create_folder_btn = QPushButton("Create Folder")
        create_folder_btn.clicked.connect(self.create_folder)
        create_folder_btn.setFixedWidth(90)        
        local_save_btn = QPushButton("Save Preset")
        local_save_btn.clicked.connect(self.save_local_loc)
        local_save_btn.setFixedWidth(80)
        local_delete_btn = QPushButton("Delete Preset")
        local_delete_btn.clicked.connect(self.delete_local_loc)
        local_delete_btn.setFixedWidth(88)
        local_hbox = QHBoxLayout()
        local_hbox.addWidget(self.local_loc_combo)
        local_hbox.addWidget(local_browse_btn)
        local_hbox.addWidget(create_folder_btn)        
        local_hbox.addWidget(local_save_btn)
        local_hbox.addWidget(local_delete_btn)
        if self.show_local:
            self.form_layout.addRow("Save Folder:", local_hbox)

        # Download button with timed and overwrite checkboxes
        self.download_hbox = QHBoxLayout()
        self.download_hbox.addSpacing(110)
        self.timed_check = QCheckBox("Timed Download")
        self.timed_check.toggled.connect(self.on_timed_check_toggled)
        self.period_combo = QComboBox()
        self.period_combo.addItems(["6am daily", "8hr", "4hr", "1hr", "30min", "15min", "5min", "1min", "custom"])
        self.period_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.overwrite_check = QCheckBox("Overwrite only if different")
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download_files)
        self.download_btn.setMinimumWidth(200)  # Larger button
        self.download_btn.setStyleSheet("font-size: 15px; font-weight: bold")
        self.open_folder_btn = QPushButton("Open Save Folder")
        self.open_folder_btn.clicked.connect(self.open_save_folder)
        self.show_all = QPushButton("Show All Rows")  # Initial text
        self.show_all.setFixedWidth(120)  # Consistent size
        self.show_all.clicked.connect(self.toggle_rows)  # Connect to new toggle method
        self.is_showing_all = False  # Track toggle state
        self.download_hbox.addWidget(self.timed_check)
        self.download_hbox.addWidget(self.period_combo)
        self.download_hbox.addWidget(self.overwrite_check)
        self.download_hbox.addWidget(self.download_btn)
        self.download_hbox.addSpacing(10)
        self.download_hbox.addWidget(self.open_folder_btn)
        self.download_hbox.addSpacing(50)

        # Create and add external tools buttons dynamically
        self.add_external_tool_buttons()
     
        
        
        
        self.download_hbox.addStretch(2)
        if self.mode != "full":
            self.download_hbox.addWidget(self.show_all)  # Add button if not in full mode
        if self.show_download:
            self.form_layout.addRow(self.download_hbox)

        #Status Update Row
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        if self.show_status:
            self.form_layout.addRow(self.status_label)

        self.is_downloading = False  # Track active download
        self.inc_timer = QTimer()
        self.inc_timer.timeout.connect(self.download_files) # Timeout event to start new download. 
        self.current_sort = "site_name"
        self.cancel_event = asyncio.Event()

        # Load last selections only if running as main script
        if __name__ == "__main__":
            print(f"Loading last selection")
            self.from_combo = True  # Prevent on_date_change from clearing
            self.quick_date_combo.blockSignals(True)  # Block combo signals
            self.sid_combo.blockSignals(True)
            self.ip_type_combo.blockSignals(True)
            self.ip_edit.blockSignals(True)
            
            last = self.config.get("last_selections", {})
            last_sid = last.get("sid", "")
            if last_sid in self.siddb or last_sid == "Custom IP":
                display_text = self.siddb.get(last_sid, {}).get("site_name", "Unknown") + f" ({last_sid})" if last_sid != "Custom IP" else "Custom IP"
                self.sid_combo.setCurrentText(display_text)
            self.filemode_combo.setCurrentText(last.get("filemode", "File Checks"))
            self.ip_type_combo.setCurrentText(last.get("ip_type", "sp_ip"))
            self.ip_edit.setText(last.get("ip", ""))
            self.username_edit.setText(last.get("username", ""))
            self.password_edit.setText(last.get("password", ""))
            self.remote_loc_combo.setCurrentText(last.get("remote_loc", ""))
            self.local_loc_combo.setCurrentText(last.get("local_loc", os.getcwd()))
            self.filter_combo.setCurrentText(last.get("file_filter", ""))
            self.protocol_combo.setCurrentText(last.get("protocol", "sftp"))
            self.start_date_edit.setDate(QDate.fromString(last.get("start_date", ""), 'yyyy-MM-dd'))
            self.end_date_edit.setDate(QDate.fromString(last.get("end_date", ""), 'yyyy-MM-dd'))
            self.quick_date_combo.setCurrentText(last.get("quick_date", ""))
            self.date_filter_var.setChecked(last.get("date_filter_enabled", False)) 
            # Moved date_filter_var.setChecked below quick_date_combo.setCurrentText because it was
            # still triggering self.quick_date_combo.currentTextChanged.connect(self.on_quick_date_select)
            # even though the signals were blocked and was checking date_filter_var 
            # no matter what was in the last selection.
            self.overwrite_check.setChecked(last.get("incremental_download", False))
            self.timed_check.setChecked(last.get("timed_download", False))
            self.period_combo.setCurrentText(last.get("incremental_period", "6am daily"))

            self.ip_edit.blockSignals(False)
            self.ip_type_combo.blockSignals(False)
            self.sid_combo.blockSignals(False)
            self.quick_date_combo.blockSignals(False)
            self.from_combo = False  # Reset after all date operations


        layout.addLayout(self.form_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        if not self.show_filechecks:
            for checkbox in self.filecheck_checkboxes:
                checkbox.hide()
            self.show_custom_btn.hide()
            self.filecheck_label.hide()
            self.filemode_combo.hide()
            self.cycle_check_btn.hide()
        if not self.show_filter:
            self.filemode_combo.setCurrentText("File Checks")
            self.filemode_combo.hide() 

        self.show_custom_btn.setText("Hide Custom" if self.show_ip and self.show_remote and self.show_filter else "Show Custom")


        # SETUP UI BASED ON APP_MODE
        self.set_mode_defaults()
        self.load_all_credentials()
        self.update_cycle_checks_btn()
        
        # Auto-download popup
        if self.app_config.get("defaults", {}).get("start_download", False):
            QTimer.singleShot(100, self.prompt_start_download)

        if len(sys.argv) > 1 and sys.argv[1] == "use_current_dat":
            sid = self.use_current_dat_sid()
            index = self.sid_combo.findData(sid)
            if index >= 0:
                
                self.sid_combo.setCurrentIndex(index)
            else:
                self.update_status(f"SID {sid} not found in sid_combo, using default")
                sid = "000"    

## ========== CREATE EXTERNAL TOOL BUTTONS ======================================================
    def add_external_tool_buttons(self):
        """Dynamically create and add buttons for all external tools"""
        for tool_name, config in EXTERNAL_TOOLS.items():
            # Find the first existing path (supports multiple path entries)
            script_path = None
            for possible_path in config.get("path", []):  # handle both str and list
                path_to_check = possible_path
                if not os.path.isabs(path_to_check):
                    path_to_check = os.path.join(BASE_DIR, path_to_check)
                path_to_check = os.path.normpath(path_to_check)
#                print(f"Checking '{tool_name}': {path_to_check} → exists? {os.path.isfile(path_to_check)}")
                if os.path.isfile(path_to_check):
                    script_path = path_to_check
                    break

            if script_path is None:
#                print(f"Skipped missing tool '{tool_name}': no valid path found")
                continue

            # Create button
            btn = QPushButton(tool_name)
            btn.setToolTip(config.get("tooltip", ""))
            btn.setFixedWidth(110)
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda checked, name=tool_name: self.launch_external_tool(name))

            # Add right after download_btn (or wherever you want in the layout)
            self.download_hbox.addWidget(btn)

            # Optional: keep reference if needed later
            # self.tool_buttons = getattr(self, 'tool_buttons', {})
            # self.tool_buttons[tool_name] = btn

    def launch_external_tool(self, tool_name):
        """Launch the selected external tool with current runtime values"""
        config = EXTERNAL_TOOLS.get(tool_name)
        if not config:
            print(f"Tool '{tool_name}' not found in EXTERNAL_TOOLS")
            return

        # Find valid script path (same logic as above)
        script_path = None
        for possible_path in config.get("path", []):
            path_to_check = possible_path
            if not os.path.isabs(path_to_check):
                path_to_check = os.path.join(BASE_DIR, path_to_check)
            path_to_check = os.path.normpath(path_to_check)

            if os.path.isfile(path_to_check):
                script_path = path_to_check
                break

        if script_path is None:
            print(f"Cannot launch '{tool_name}': no valid path found")
            return

        try:
            # Use pythonw on Windows for no console
            if sys.platform == "win32":
                python_exe = "pythonw.exe"
            else:
                python_exe = sys.executable

            # Build command
            cmd = [python_exe, script_path]

            # Add static args from config
            cmd.extend(config.get("args", []))

            for dynamic_type in config.get("dynamic_args", []):
                if dynamic_type == "local_loc_combo":
                    cmd.append(self.local_loc_combo.currentText().strip())
                elif dynamic_type == "sid_combo":
                    cmd.append(f"sid_combo={self.sid_combo.currentText()}")
                elif dynamic_type == "SID=":
                    s = self.sid_combo.currentText().split("(")[1]
                    sid = s.rstrip(")")
                    cmd.append(f"SID={sid}")
                elif dynamic_type == "path=":
                    cmd.append(f"path={self.local_loc_combo.currentText().strip()}")

            # Launch
            subprocess.Popen(cmd, shell=False)

            print(f"Launched: {tool_name} → {script_path} with args: {cmd[2:]}")

        except Exception as e:
            print(f"Failed to launch {tool_name}: {e}")



    # Optional: call this if files might appear/disappear during runtime
    def refresh_tool_buttons_visibility(self):
        for tool_name, config in self.external_tools.items():
            full_path = os.path.join(self.base_dir, config["path"])
            visible = os.path.isfile(full_path)
            self.tool_buttons[tool_name].setVisible(visible)




# SETUP UI BASED ON APP_MODE
    def hide_rows_by_mode(self, show_rows=None):
        """Set row visibility flags based on app_config show_rows."""
        show_rows = show_rows or self.app_config.get("show_rows", [
            "sid", "filechecks", 
#            "ip", "remote", "filter", ## This comment hides these by default because these will not show. 
            "date", "local", "download", "status"])

#        print(f"ran, hide_rows_by_mode. Show Rows = {show_rows}")
        
        # Reset all show flags to False
        self.show_sid = False
        self.show_filechecks = False
        self.show_ip = False
        self.show_remote = False
        self.show_filter = False
        self.show_date = False
        self.show_local = False
        self.show_download = False
        self.show_status = False
        
        # Set flags to True for rows in show_rows
        for row_name in show_rows:
            if row_name == "sid":
                self.show_sid = True
            elif row_name == "filechecks":
                self.show_filechecks = True
            elif row_name == "ip":
                self.show_ip = True
            elif row_name == "remote":
                self.show_remote = True
            elif row_name == "filter":
                self.show_filter = True
            elif row_name == "date":
                self.show_date = True
            elif row_name == "local":
                self.show_local = True
            elif row_name == "download":
                self.show_download = True
            elif row_name == "status":
                self.show_status = True
           

    def set_mode_defaults(self):
        """Set defaults from app_config."""
        defaults = self.app_config.get("defaults", {})
        print(f"start, set_mode_defaults, DEFAULTS = {defaults}")


# FIX NEEDED =======================================================================================================
# BELOW NEED TO ADD  ==if filechecks in defaults== TO SET_MODE_DEFAULTS
        print(f"NEED TO ADD  ==if filechecks in defaults== TO SET_MODE_DEFAULTS--------------------------------------------------------------")
        
        # File Checks
#        if "filechecks" in defaults:
        
        if "filemode" in defaults:
            self.filemode_combo.setCurrentText((defaults["filemode"]))
        
        # IP Type (custom:user:pass)
        if "ip_type" in defaults:
            ip_type = defaults["ip_type"]
            if ip_type.startswith("custom"):
                _, user, pwd = ip_type.split(":", 2)
                self.ip_type_combo.setCurrentText("Custom User")
                self.username_edit.setText(user)
                self.password_edit.setText(pwd)
            else:
                self.ip_type_combo.setCurrentText(ip_type)
        
        # Remote
        if "remote_loc" in defaults:
            remote = defaults["remote_loc"].format(sid=self.sid_combo.currentData() or "000", cwd=os.getcwd())
            self.remote_loc_combo.setCurrentText(remote)
        
        # Local
        if "local_loc" in defaults:
            local = defaults["local_loc"].format(sid=self.sid_combo.currentData() or "000", cwd=os.getcwd())
            self.local_loc_combo.setCurrentText(local)
        
        # File Filter
        if "file_filter" in defaults:
            self.filter_combo.setCurrentText(defaults["file_filter"])
        
        # Date Filter
        self.from_combo = True  # Prevent on_date_change from clearing
        self.quick_date_combo.blockSignals(True)  # Block combo signals
        self.start_date_edit.blockSignals(True)  # Block date signals
        self.end_date_edit.blockSignals(True)    # Block date signals
        if defaults.get("date_filter_enabled", False):
            self.date_filter_var.setChecked(True)
        if defaults.get("set_end_today", False):
            self.set_end_to_today()
        if "quick_date" in defaults:
            self.quick_date_combo.setCurrentText(defaults["quick_date"])               
            self.on_quick_date_select(self.quick_date_combo.currentText)
        self.quick_date_combo.blockSignals(False)
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)
        self.from_combo = False  # Reset after all date operations


        # Download Options
        if "timed" in defaults:
            self.timed_check.setChecked(defaults.get("timed", False))
        
        if "period" in defaults:
            self.period_combo.setCurrentText(defaults["period"])

        if "overwrite" in defaults:
            self.overwrite_check.setChecked(defaults.get("overwrite", False))


    def toggle_rows(self):
#        print("start, toggle_rows")
        """Toggle between showing all rows and default rows, rebuilding the layout."""
        if self.is_showing_all:
            # Collapse to default rows
            self.hide_rows_by_mode()  # Uses app_config default
            self.show_all.setText("Show All Rows")
            self.is_showing_all = False
            # Sync show_custom_btn with custom row visibility
            self.show_ip = False
            self.show_remote = False
            self.show_filter = False
            self.show_custom_btn.setText("Show Custom")
            self.filemode_combo.setVisible(self.show_filter)
        else:
            # Show all rows
            self.hide_rows_by_mode(show_rows=["sid", "filechecks", "ip", "remote", "filter", "date", "local", "download", "status"])
            self.show_all.setText("Hide Rows")
            self.is_showing_all = True
            self.show_custom_btn.setText("Hide Custom")
            self.filemode_combo.setVisible(self.show_filter)
        self.rebuild_form_layout()  # Rebuild the form layout
#        print(f"toggle_rows: show_all={self.show_all.text()}, show_custom_btn={self.show_custom_btn.text()}, show_ip={self.show_ip}, show_remote={self.show_remote}, show_filter={self.show_filter}")

    def toggle_custom_rows(self):
#        print("start, toggle_custom_rows")
        """Toggle visibility of custom rows (ip, remote, filter) and mode combo."""
        self.show_ip = not self.show_ip
        self.show_remote = not self.show_remote
        self.show_filter = not self.show_filter
        self.show_custom_btn.setText("Hide Custom" if self.show_ip else "Show Custom")
        self.filemode_combo.setVisible(self.show_filter)  # Sync filemode_combo visibility
        # Update is_showing_all to reflect row visibility
        if self.show_ip and self.show_remote and self.show_filter:
            self.is_showing_all = all([self.show_sid, self.show_filechecks, self.show_date, self.show_local, self.show_download, self.show_status])
            self.show_all.setText("Hide Rows" if self.is_showing_all else "Show All Rows")
        else:
            self.is_showing_all = False
            self.show_all.setText("Show All Rows")
        self.rebuild_form_layout()  # Rebuild the form layout
#        print(f"toggle_custom_rows: show_all={self.show_all.text()}, show_custom_btn={self.show_custom_btn.text()}, show_ip={self.show_ip}, show_remote={self.show_remote}, show_filter={self.show_filter}")

    def rebuild_form_layout(self):
        """Rebuild the form layout based on current show_* flags, ensuring download row is included."""
#        print(f"rebuild_form_layout: all flags: sid={self.show_sid}, filechecks={self.show_filechecks}, ip={self.show_ip}, remote={self.show_remote}, filter={self.show_filter}, date={self.show_date}, local={self.show_local}, download={self.show_download}, status={self.show_status}")
#        print(f"start, rebuild_form_layout")

        # Store widgets to prevent deletion
        widgets = [
            self.sid_combo, self.sort_button, self.change_siddb_btn,
            self.ip_type_combo, self.ip_edit, self.protocol_combo, self.username_edit, self.password_edit,
            self.date_filter_widget, self.date_filter_var, self.start_date_edit, self.end_date_edit,
            self.quick_date_combo, self.timed_check, self.period_combo, self.overwrite_check, self.download_btn,
            self.show_all, self.status_label, self.remote_loc_combo, self.filter_combo, self.local_loc_combo,
            self.show_custom_btn, self.cycle_check_btn, self.filemode_combo, self.filecheck_label
        ] + self.filecheck_checkboxes

        # Hide filecheck checkboxes if not shown to prevent overlay
        if not self.show_filechecks:
            for checkbox in self.filecheck_checkboxes:
                checkbox.setVisible(False) 

        # Disable updates and hide central widget to prevent flickering
        self.setUpdatesEnabled(False)
        central_widget = self.centralWidget()
        if central_widget:
            central_widget.hide()
        
        # Clear existing form layout safely
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # Detach widget without deleting
            elif item.layout():
                layout = item.layout()
                while layout.count():
                    sub_item = layout.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().setParent(None)
                    elif sub_item.layout():
                        sub_item.layout().setParent(None)
                layout.setParent(None)  # Detach layout without deleting
        if self.form_layout.count() != 0:
            raise RuntimeError(f"Form layout not cleared, {self.form_layout.count()} items remain")
#        print(f"rebuild_form_layout: Cleared form_layout, count={self.form_layout.count()}")

        # Clear and recreate form layout
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)  # Restore spacing from __init__
        self.form_layout.setLabelAlignment(Qt.AlignRight)  # Restore alignment from __init__

        # SID/Site/SIDDB-Path Row
        if self.show_sid:
            sid_hbox = QHBoxLayout()
            sid_hbox.addWidget(self.sid_combo)
            sid_hbox.addWidget(self.sort_button)
            sid_hbox.addWidget(self.change_siddb_btn)
            self.form_layout.addRow("SID/Site:", sid_hbox)

        # Filechecks Row
        if self.show_filechecks:
            filechecks_hbox = QHBoxLayout()
            filechecks_hbox.addSpacing(30)
            filechecks_label = QLabel("File Checks:")
            filechecks_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            filechecks_grid = QGridLayout()
            filechecks_grid.setSpacing(10)  # Match form_layout spacing
            columns = 5  # Number of checkboxes per row
            for i, checkbox in enumerate(self.filecheck_checkboxes):
                row = i // columns
                col = i % columns
                checkbox.blockSignals(True)  # Block signals to reduce popup artifacts
                checkbox.setVisible(True)  # Ensure checkbox is visible
                filechecks_grid.addWidget(checkbox, row, col)
                checkbox.blockSignals(False)
            self.show_custom_btn.setVisible(True)
            self.filemode_combo.setVisible(self.show_filter)  # Show filemode_combo only if filter row is visible
            self.cycle_check_btn.setVisible(True)
            buttons_vbox = QVBoxLayout()
            buttons_vbox.addWidget(self.show_custom_btn)
            buttons_vbox.addWidget(self.cycle_check_btn)
            buttons_vbox.addWidget(self.filemode_combo)
            buttons_vbox.setAlignment(Qt.AlignTop)
            filechecks_hbox.addLayout(filechecks_grid)
            filechecks_hbox.addLayout(buttons_vbox)
            self.form_layout.addRow(filechecks_label, filechecks_hbox)


        # IP Type, IP, Protocol, Username, and Password Row
        if self.show_ip:
            self.ip_hbox = QHBoxLayout()
            self.ip_hbox.addSpacing(0)
#            self.ip_type_combo = QComboBox()
#            self.ip_type_combo.addItems(["sp_ip", "host_ip", "display_ip"])  # Exclude Custom User initially
#            self.ip_type_combo.setFixedWidth(90)
            self.ip_hbox.addWidget(QLabel("Custom User Type:"))
            self.ip_hbox.addWidget(self.ip_type_combo)
            self.ip_hbox.addSpacing(60)
#            self.ip_edit = QLineEdit()
#            self.ip_edit.setFixedWidth(120)  # Size for IP address
            self.ip_edit.textChanged.connect(self.refresh_ip_type_combo)
            self.ip_edit.setEnabled(True)  # Always editable
            self.ip_hbox.addWidget(QLabel("Custom IP:"))
            self.ip_hbox.addWidget(self.ip_edit)
            self.protocol_combo = QComboBox()
            self.protocol_combo.addItems(["sftp", "ftp"])
            self.ip_hbox.addWidget(QLabel("Custom Protocol:"))
            self.ip_hbox.addWidget(self.protocol_combo)
#            self.username_edit = QLineEdit()
#            self.username_edit.setFixedWidth(150)  
            self.username_edit.textChanged.connect(self.refresh_ip_type_combo)
            self.ip_hbox.addWidget(QLabel("Custom Username:"))
            self.ip_hbox.addWidget(self.username_edit)
#            self.password_edit = QLineEdit()
#            self.password_edit.setFixedWidth(150)  
            self.password_edit.setEchoMode(QLineEdit.Password)
            self.password_edit.textChanged.connect(self.refresh_ip_type_combo)
            self.ip_hbox.addWidget(QLabel("Custom Password:"))
            self.ip_hbox.addWidget(self.password_edit)
            self.ip_hbox.addStretch(2)            
            self.form_layout.addRow(self.ip_hbox)
        # Remote Location Row
        if self.show_remote:
            remote_hbox = QHBoxLayout()
            remote_hbox.addWidget(self.remote_loc_combo)
            remote_browse_btn = QPushButton("Browse")
            remote_browse_btn.clicked.connect(self.browse_remote)
            remote_browse_btn.setFixedWidth(108)
            remote_save_btn = QPushButton("Save Preset")
            remote_save_btn.clicked.connect(self.save_remote_loc)
            remote_save_btn.setFixedWidth(106)
            remote_delete_btn = QPushButton("Delete Preset")
            remote_delete_btn.clicked.connect(self.delete_remote_loc)
            remote_delete_btn.setFixedWidth(107)
            remote_hbox.addWidget(remote_browse_btn)
            remote_hbox.addWidget(remote_save_btn)
            remote_hbox.addWidget(remote_delete_btn)
            self.form_layout.addRow("Remote Folder:", remote_hbox)

        # File Filter Row
        if self.show_filter:
            filter_hbox = QHBoxLayout()
            filter_hbox.addWidget(self.filter_combo)
            filter_info_btn = QPushButton("Filter Info")
            filter_info_btn.clicked.connect(self.show_filter_info)
            filter_info_btn.setFixedWidth(108)
            filter_save_btn = QPushButton("Save Preset")
            filter_save_btn.clicked.connect(self.save_filter)
            filter_save_btn.setFixedWidth(106)
            filter_delete_btn = QPushButton("Delete Preset")
            filter_delete_btn.clicked.connect(self.delete_filter)
            filter_delete_btn.setFixedWidth(107)
            filter_hbox.addWidget(filter_info_btn)
            filter_hbox.addWidget(filter_save_btn)
            filter_hbox.addWidget(filter_delete_btn)
            self.form_layout.addRow("Custom File Filter:", filter_hbox)

        # Date Filter Row
        if self.show_date:
            self.form_layout.addRow(self.date_filter_widget)

        # Local Location Row
        if self.show_local:
            local_hbox = QHBoxLayout()
            local_hbox.addWidget(self.local_loc_combo)
            local_browse_btn = QPushButton("Browse")
            local_browse_btn.clicked.connect(self.browse_local)
            local_browse_btn.setFixedWidth(52)
            create_folder_btn = QPushButton("Create Folder")
            create_folder_btn.clicked.connect(self.create_folder)
            create_folder_btn.setFixedWidth(90)
            local_save_btn = QPushButton("Save Preset")
            local_save_btn.clicked.connect(self.save_local_loc)
            local_save_btn.setFixedWidth(80)
            local_delete_btn = QPushButton("Delete Preset")
            local_delete_btn.clicked.connect(self.delete_local_loc)
            local_delete_btn.setFixedWidth(88)
            local_hbox.addWidget(local_browse_btn)
            local_hbox.addWidget(create_folder_btn)
            local_hbox.addWidget(local_save_btn)
            local_hbox.addWidget(local_delete_btn)
            self.form_layout.addRow("Save Folder:", local_hbox)

        # Download Button Row
        if self.show_download:
            # Recreate download_hbox to ensure all widgets are included
            self.download_hbox = QHBoxLayout()
            self.download_hbox.addSpacing(110)
            self.download_hbox.addWidget(self.timed_check)
            self.download_hbox.addWidget(self.period_combo)
            self.download_hbox.addWidget(self.overwrite_check)
            self.download_hbox.addWidget(self.download_btn)
            self.download_hbox.addSpacing(10)
            self.download_hbox.addWidget(self.open_folder_btn)
            self.download_hbox.addSpacing(50)

            # Create and add external tools buttons dynamically
            self.add_external_tool_buttons()            
            self.download_hbox.addStretch(2)
            if self.mode != "full":
                self.download_hbox.addWidget(self.show_all)
            self.form_layout.addRow(self.download_hbox)

        # Status Label Row
        if self.show_status:
            self.form_layout.addRow(self.status_label)

        # Set up central widget with new form layout
        if not central_widget:
            central_widget = QWidget()
            layout = QVBoxLayout()
            central_widget.setLayout(layout)
            self.setCentralWidget(central_widget)
        central_widget.layout().addLayout(self.form_layout)

        # Re-enable updates and resize window
        central_widget.show()
        self.setUpdatesEnabled(True)
        central_widget.adjustSize()  # Adjust central widget to layout size
        self.adjustSize()  # Adjust window to central widget size
        self.update()  # Force repaint
        QApplication.processEvents()  # Process pending events




## =========== HELPER FUNCTIONS ================================================================================

    def load_all_credentials(self):
#        print(f"start, load_all_credentials")
        sid = self.sid_combo.currentData()
        if not sid:
            self.cred_store = {}
            return

        self.entry = self.siddb.get(sid, {})
        self.cred_store = {}
#        print(f"start load_all_credentials and self.entry-site_name= {self.entry.get('site_name', '')}")
        # === ALL POSSIBLE IP TYPES ===
        ip_types = ["sp_ip", "host_ip", "display_ip"]

        for ip_type in ip_types:
            # Skip if no IP in siddb
            ips = self.entry.get(ip_type, [])
            if not ips:
                continue

            # === GET CREDENTIALS (with protocol) ===
            creds_list = get_credentials(ip_type, self.entry)
            if not creds_list:
                self.update_status(f"SID-{sid} ''{ip_type}'' failed to load credentials. Check siddb.json for missing modality, machine, or sw_version.")
                continue  # No credentials → skip

            username, password, protocol = creds_list[0]

            # === STORE IN CRED STORE ===
            self.cred_store[ip_type] = {
                "ip": ips[0],
                "username": username,
                "password": password,
                "protocol": protocol
            }    
        self.refresh_ip_type_combo
        self.refresh_remote_loc_combo()        

    def cycle_checks(self):
        # Cycle the "Check All / Uncheck All" button behavior

        if self.cycle_check_btn.text() == "Check All":
            # Button says "Check All" → user wants to check everything
            for checkbox in self.filecheck_checkboxes:
                checkbox.setChecked(True)
            self.cycle_check_btn.setText("Uncheck All")
        else:
            # Button says "Uncheck All" → user wants to uncheck everything
            for checkbox in self.filecheck_checkboxes:
                checkbox.setChecked(False)
            self.cycle_check_btn.setText("Check All")

    def update_cycle_checks_btn(self):
        # Cycle the "Check All / Uncheck All" button behavior
        all_checked = all(cb.isChecked() for cb in self.filecheck_checkboxes)

        if all_checked:
            # All are checked → uncheck everything and change button to "Check All"
            self.cycle_check_btn.setText("Uncheck All")
        else:
            self.cycle_check_btn.setText("Check All")                        

# SID/SITE ROW FUNCTIONS ----------------------------------------------------------------------------------------------

    def use_current_dat_sid(self):
        """Get the sid from current.dat."""
        try:
            with open(DEFAULT_CURRENTDB_PATH, 'r') as f:
                for line in f:
                    if line.startswith("SID="):
                        return line.strip().split('=', 1)[1]
            return "000"
        except Exception as e:
            self.update_status(f"Error reading sid from current.dat: {str(e)}")
            return "000"

    def populate_sid_combo(self, sort_by):
        self.sid_combo.clear()

        def to_int_safe(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return float('inf')
        
        items = []
        for sid, entry in self.siddb.items():
            site_name = entry.get("site_name", "Unknown")
            items.append((f"{site_name} ({sid})", sid))
        if sort_by == "site_name":
            items.sort(key=lambda x: x[0].lower())
        else:
            items.sort(key=lambda x: to_int_safe(x[1]))
        for display, sid in items:
            self.sid_combo.addItem(display, sid)

  # This is to the SID/Site sort order. ----------------------------------------------------------------------
    def toggle_sort(self):
        self.current_sort = "site_name" if self.current_sort == "sid" else "sid"
        self.sort_button.setText("Sort by Site Name" if self.current_sort == "sid" else "Sort by SID")
        self.populate_sid_combo(self.current_sort)

  # Part of change SIDDB Path button. ---------------------------------------------------------- 

    def set_siddb_default(self, path_edit=None): 
        self.config["siddb_path"] = DEFAULT_SIDDB_PATH
        save_config(self.config)
        self.siddb = load_siddb(DEFAULT_SIDDB_PATH)
        self.populate_sid_combo(self.current_sort)
        if path_edit:
            path_edit.setText(DEFAULT_SIDDB_PATH)

    def change_siddb_path(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("SIDDB Path")
        dialog.resize(200, 120)
        layout = QVBoxLayout()
        label = QLabel("SIDDB Path (Enter new path to change):")
        path_edit = QLineEdit()
        path_edit.setText(self.config["siddb_path"])
        layout.addWidget(label)
        layout.addWidget(path_edit)
        button_layout = QHBoxLayout()
        default_btn = QPushButton("Set to Default")
        default_btn.clicked.connect(lambda: self.set_siddb_default(path_edit))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.close)
        ok_btn = QPushButton("Change")
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(default_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        if dialog.exec_():
            new_path = path_edit.text()
            self.config["siddb_path"] = new_path
            save_config(self.config)
            self.siddb = load_siddb(new_path)
            self.populate_sid_combo(self.current_sort)


# FILE CHECKS ROW FUNCTIONS ----------------------------------------------------------------------

    def resolve_command_to_run(self, cfg, entry):
        """
        Resolve command_to_run based on sw_version.
        Only enhances configs where command_to_run is a dict.
        For strings → returns as-is (old behavior).
        Fully backward compatible.
        """
        cmd_config = cfg.get("command_to_run")

        # === OLD FORMAT: plain string or None → return as-is ===
        if not isinstance(cmd_config, dict):
            return cmd_config  # Could be str or None → perfect

        # Only host_ip uses version logic (or any usertype — safe either way)
        sw_version = entry.get("sw_version", "").upper()

        # Extract major version
        version_match = re.search(r"V(\d+\.?\d*)", sw_version)
        major_version = float(version_match.group(1)) if version_match else 0.0
        has_sp = "SP" in sw_version
        has_r = "R" in sw_version

        print(f"[resolve_command] sw_version={sw_version}, major={major_version}, SP={has_sp}, R={has_r}")

        for pattern, command in cmd_config.items():
            if pattern == "default":
                continue

            pattern_up = pattern.upper()

            if pattern_up == ">V3*R*" and major_version > 3.0 and has_r:
                print(f"[MATCH COMMAND] >V3*R* → {command}")
                return command
            elif pattern_up == "<V3*R*" and major_version < 3.0 and has_r:
                print(f"[MATCH COMMAND] <V3*R* → {command}")
                return command
            elif pattern_up == "*SP*" and has_sp:
                print(f"[MATCH COMMAND] *SP* → {command}")
                return command

        # Default fallback
        default_cmd = cmd_config.get("default", "")
        print(f"[DEFAULT COMMAND] → {default_cmd}")
        return default_cmd
    

# IP/USER TYPE ROW FUNCTIONS----------------------------------------------------------------------

# RESET_IP_TYPE ISN'T CALLED FROM ANYWHERE. IT CAN PROBABLY BE DELETED. <<<<
    def reset_ip_type(self):
#        print(f"start, reset_ip_type")
        try:
            current = self.ip_type_combo.currentText()
            if current not in ["sp_ip", "host_ip", "display_ip", "Custom User"]:
                self.ip_type_combo.setCurrentText("sp_ip")
        except Exception as e:
            self.update_status(f"Error resetting IP type: {str(e)}")


# THIS WILL PROBABLY BE REMOVED <<<< <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    def handle_ip_change(self):
#        print(f"start, handle_ip_change")
        try:
            if self.ip_edit.text().strip() and not self.ip_edit.hasFocus():
#                print(f"if return, handle_ip_change")
                return
            if self.ip_edit.text().strip():
                self.update_status("Custom IP selected")
                print(f"Ran, handle_ip_change")    
        except Exception as e:
            self.update_status(f"Error handling IP change: {str(e)}")

# THIS WILL PROBABLY BE REMOVED <<<< <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    def update_ip_type(self):
        # If Username/Password or ip_type changes then update. 
#        print(f"start, update_ip_type")
        try:
            if hasattr(self, "username_edit") and hasattr(self, "password_edit") and (self.username_edit.text().strip() and self.password_edit.text().strip()) and self.ip_edit.text().strip():
                self.ip_type_combo.blockSignals(True)
                if "Custom User" not in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                    self.ip_type_combo.addItem("Custom User")
                self.ip_type_combo.setCurrentText("Custom User")
                self.ip_type_combo.blockSignals(False)
                self.update_status("Using custom IP/username/password")
            else:
                self.ip_type_combo.blockSignals(True)
                if "Custom User" in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                    self.ip_type_combo.removeItem("Custom User")
                self.ip_type_combo.setCurrentText("sp_ip")
                self.ip_type_combo.blockSignals(False)

        except Exception as e:
            self.update_status(f"Error updating credentials: {str(e)}")



    def refresh_ip_type_combo(self):
        """
        Rebuilds the ip_type_combo to only show:
        - Available IP types from current SID (those with non-empty IP list)
        - + "Custom User" only if all 3 custom fields are filled
        """
        # Quick guard - make sure widgets exist
        if not all(hasattr(self, attr) for attr in ["ip_edit", "username_edit", "password_edit"]):
            return
                
        sid = self.sid_combo.currentData()
        if not sid:
            self.ip_type_combo.clear()
            return

        entry = self.siddb.get(sid, {})
        
        # Define all possible "normal" IP types (add more if you ever get new ones)
        possible_types = ["sp_ip", "host_ip", "display_ip"]  # ← extend this list as needed
        
        # Collect only those that have at least one IP
        available_types = [
            t for t in possible_types
            if entry.get(t) and isinstance(entry[t], list) and len(entry[t]) > 0
        ]
        
        # Check custom user fields
        custom_ip = self.ip_edit.text().strip()
        custom_user = self.username_edit.text().strip()
        custom_pw = self.password_edit.text().strip()
        
        use_custom = bool(custom_ip and custom_user and custom_pw)
        
        # Now rebuild the combo
        self.ip_type_combo.blockSignals(True)
        self.ip_type_combo.clear()
        
        # Add normal available types
        for t in available_types:
            self.ip_type_combo.addItem(t)
        
        # Add Custom User only if credentials are complete
        if use_custom:
            self.ip_type_combo.addItem("Custom User")
        
        # Select something sensible
        if self.ip_type_combo.count() > 0:
            # Prefer Custom User if it was just added, otherwise first available
            if use_custom and self.ip_type_combo.findText("Custom User") != -1:
                self.ip_type_combo.setCurrentText("Custom User")
            else:
                self.ip_type_combo.setCurrentText(available_types[0] if available_types else "")
        else:
            # Rare case: no IPs at all → maybe show placeholder
            self.ip_type_combo.addItem("No IP available")
            self.ip_type_combo.setCurrentIndex(0)
        
        self.ip_type_combo.blockSignals(False)
        
        # Optional feedback
        if use_custom:
            self.update_status("Custom credentials ready – 'Custom User' Selected")
        elif not available_types:
            self.update_status("Warning: This SID has no configured IP addresses")



# REMOTE LOCATION HELPER FUNCTIONS ---------------------------------------------------------------------

    def get_default_remote_locs(self):
        sid = self.sid_combo.currentData() # Get the current SID for the _tui path.
        if not sid or sid == "Custom IP": # Ask for SID if using Custom IP. 
                self.update_status("Enter a valid SID in _tui folder path")
                sid = "Enter_SID"
    # HERE IS THE NEW REMOTE LOCATIONS SHORTCUT LIST
        return [
            f"C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir/",
            "C:/ProgramData/Helium_Pressure_Monitor"
        ]

    def refresh_remote_loc_combo(self):
#        print(f"start, refresh_remote_loc_combo")
        # Store current selection if needed
        current_text = self.remote_loc_combo.currentText()
        
        # Clear and repopulate remote_loc_combo with updated paths
        self.remote_loc_combo.clear()
        self.remote_loc_combo.addItems(self.config.get("remote_locations", []) + self.get_default_remote_locs())
        
        # Optionally restore previous selection if it still exists
        index = self.remote_loc_combo.findText(current_text)
        # === Extract base path (only if ends with "_tui.dir/") ===
        extra_path = ""
        if "_tui.dir/" in current_text:
            parts = current_text.split("_tui.dir/", 1)
            extra_path = parts[1] if len(parts) > 1 else ""
        if "_tui" in current_text:
            index = 0
        if index >= 0:
            self.remote_loc_combo.setCurrentIndex(index)
            # Append the extra path if it exists
            if extra_path:
                base_text = self.remote_loc_combo.currentText()
                self.remote_loc_combo.setEditText(base_text + extra_path)           
        else:
            self.remote_loc_combo.setCurrentText(current_text)

    def resolve_remote_loc(self, cfg, entry, sid):
        """
        Resolve remote_loc based on sw_version.
        Returns string with .format(sid=...) already applied when needed.
        Fully backward compatible.
        """

        loc_config = cfg.get("remote_loc")

        # === OLD FORMAT: plain string → return with sid formatted ===
        if isinstance(loc_config, str):
            return loc_config.format(sid=sid)

        # === NEW FORMAT: dict with version rules ===
        sw_version = entry.get("sw_version", "").upper()

        # Extract major version number (handles V7.0, V12.0, etc.)
        version_match = re.search(r"V(\d+\.?\d*)", sw_version)
        major_version = float(version_match.group(1)) if version_match else 0.0
        has_sp = "SP" in sw_version
        has_r = "R" in sw_version

        print(f"[resolve_remote_loc] sw_version={sw_version}, major={major_version}, SP={has_sp}, R={has_r}")

        # Try each rule
        for pattern, path in loc_config.items():
            if pattern == "default":
                continue

            pattern_up = pattern.upper()

            if pattern_up == ">=V6*SP*" and major_version >= 6.0 and has_sp:
                print(f"[MATCH] >=V6*SP* → {path} major_version = {major_version}")
                return path.format(sid=sid)
            elif pattern_up == "<V6*SP*" and major_version < 6.0 and has_sp:
                print(f"[MATCH] <V6*SP* → {path} major_version = {major_version}")
                return path.format(sid=sid)
            elif pattern_up == ">=V3*R*" and major_version >= 3.0 and has_r:
                print(f"[MATCH] >=V3*R* → {path} major_version = {major_version}")
                return path.format(sid=sid)
            elif pattern_up == "<V3*R*" and major_version < 3.0 and has_r:
                print(f"[MATCH] <V3*R* → {path} major_version = {major_version}")
                return path.format(sid=sid)
        # Default fallback
        default_path = loc_config.get("default", "/tmp")
        print(f"[DEFAULT] → {default_path}")
        return default_path.format(sid=sid)



# REMOTE LOCATION ROW FUNCTIONS ---------------------------------------------------------------------

    def browse_remote(self):
        """Browse remote file system and update remote_loc_combo and filter_combo."""
        sid = self.sid_combo.currentText().split(" (")[-1].rstrip(")") if "(" in self.sid_combo.currentText() else self.sid_combo.currentText()
        ip_type = self.ip_type_combo.currentText()

        # ── 1. Determine which credentials to use ───────────────────────────────
        if ip_type == "Custom User":
            # ── Custom User mode: ALWAYS prefer the edit boxes ──
            ip       = self.ip_edit.text().strip()
            username = self.username_edit.text().strip()
            password = self.password_edit.text().strip()
            protocol = self.protocol_combo.currentText()

        else:
            # ── Normal mode: ALWAYS prefer cred_store if available ──
            cred = self.cred_store.get(ip_type)
            if cred and isinstance(cred, dict) and cred.get("ip"):
                ip       = cred["ip"]
                username = cred.get("username", "")
                password = cred.get("password", "")
                protocol = cred.get("protocol", self.protocol_combo.currentText())
            else:
                self.update_status(f"No valid credentials found for {ip_type}")
                return

        # Quick validation before proceeding
        if not ip:
            self.update_status("Error", "No IP address available")
            return

        if not username or not password:
            # Only prompt if really missing (mostly custom case)
            username, ok = QInputDialog.getText(self, "Credentials Required",
                                            "Enter username:", QLineEdit.Normal, username)
            if not ok or not username.strip():
                self.update_status("Username is required")
                return

            password, ok = QInputDialog.getText(self, "Credentials Required",
                                            "Enter password:", QLineEdit.Password, "")
            if not ok or not password.strip():
                self.update_status("Password is required")
                return

        # ── Proceed with dialog ─────────────────────────────────────────────────
        initial_path = self.remote_loc_combo.currentText().strip()

        dialog = RemoteFileDialog(self, ip, protocol, username, password, ip_type, initial_path)
        dialog.setStyleSheet(self.styleSheet())

        if dialog.exec_():
            selected_path = dialog.selected_path
            if selected_path:
                self.remote_loc_combo.setCurrentText(selected_path)
                # Add if new
                if selected_path not in [self.remote_loc_combo.itemText(i) for i in range(self.remote_loc_combo.count())]:
                    self.remote_loc_combo.addItem(selected_path)

            if dialog.selected_files:
                self.filter_combo.setCurrentText(dialog.selected_files)

    def save_remote_loc(self):
        current = self.remote_loc_combo.currentText().strip()
        if current and current not in self.config["remote_locations"]:
            self.config["remote_locations"].append(current)
            self.remote_loc_combo.clear()
            self.remote_loc_combo.addItems(self.config["remote_locations"] + self.get_default_remote_locs())
            self.remote_loc_combo.setCurrentText(current)
            save_config(self.config)

    def delete_remote_loc(self):
        current = self.remote_loc_combo.currentText().strip()
        if current in self.get_default_remote_locs():
            self.update_status("Cannot delete hardcoded remote folder preset")
            return
        if current in self.config["remote_locations"]:
            self.config["remote_locations"].remove(current)
            self.remote_loc_combo.clear()
            self.remote_loc_combo.addItems(self.config["remote_locations"] + self.get_default_remote_locs())
            self.remote_loc_combo.setCurrentText("")
            if __name__ == "__main__":
                save_config(self.config)
            self.update_status(f"Deleted remote folder preset: {current}")


# FILE FILTER ROW FUNCTIONS -----------------------------------------------------------------------------------------------------------

    def show_filter_info(self):
        info = """
Filter Types and Instructions:
- Extensions: '.txt' or '-.txt' (include/exclude specific extensions)
- Ext. Patterns: 'log*.txt' or '-log*.txt' (include/exclude files matching patterns)
- Folders: '/path/' or '-/path/' (include/exclude specific folders)
- Folder Patterns: '/log*/' or '-/log*/' (include/exclude folders matching patterns)
- Files: 'file.txt' or '-file.txt' (include/exclude specific files)
- File Patterns: 'file*.txt' or '-file*.txt' (include/exclude files matching patterns)
- Date Filter: ':date:YYYY-MM-DD-YYYY-MM-DD' (e.g., :date:2023-01-01-2023-12-31)
Separate multiple filters with commas.
Example: .txt,-.log,/logs/,file*.txt
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Filter Instructions")
        msg.setText(info)
        msg.setStyleSheet(f"""
            QMessageBox {{ background-color: {DARK_BG.name()}; }}
            QMessageBox QLabel {{ color: {TEXT_COLOR.name()}; }}
        """)
        msg.exec_()

    def save_filter(self):
        current = self.filter_combo.currentText().strip()
        if current and current not in self.config["custom_filters"]:
            self.config["custom_filters"].append(current)
            self.filter_combo.clear()
            self.filter_combo.addItems(self.config["custom_filters"] + DEFAULT_FILTERS)
            self.filter_combo.setCurrentText(current)
            save_config(self.config)

    def delete_filter(self):
        current = self.filter_combo.currentText().strip()
        if current in DEFAULT_FILTERS:
            self.update_status("Cannot delete hardcoded filter preset")
            return
        if current in self.config["custom_filters"]:
            self.config["custom_filters"].remove(current)
            self.filter_combo.clear()
            self.filter_combo.addItems(self.config["custom_filters"] + DEFAULT_FILTERS)
            self.filter_combo.setCurrentText("")
            if __name__ == "__main__":
                save_config(self.config)
            self.update_status(f"Deleted filter preset: {current}")




# FILTER BY DATE ROW FUNCTIONS ---------------------------------------------------------------------

    def on_date_change(self): # CLEARS THE QUICK_DATE_COMBO BOX
        try:
            start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
            end_date = self.end_date_edit.date().toString('yyyy-MM-dd')
            # Validate dates
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                self.quick_date_combo.blockSignals(True)
                # Only clear if NOT from combo box!
                if not getattr(self, 'from_combo', False):
                    self.quick_date_combo.setCurrentText("")
#                    print(f"on_date_change, Cleared the Combo Box")
                self.quick_date_combo.blockSignals(False)
            except ValueError:
                self.update_status("Invalid date format")
        except Exception as e:
            self.update_status(f"Error validating dates: {str(e)}")

    def set_end_to_today(self):
        # Block signals to prevent on_date_change clearing combo
        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)
        self.quick_date_combo.blockSignals(True)
        self.from_combo = True  # Prevent on_date_change from clearing combo        
        try:
            self.end_date_edit.setDate(QDate.currentDate())
            self.date_filter_var.setChecked(True)
            self.on_quick_date_select(self.quick_date_combo.currentText())
        except Exception as e:
            self.update_status(f"Error setting end date: {str(e)}")
        
        # Unblock signals
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)
        self.quick_date_combo.blockSignals(False)
        self.from_combo = False            

    def on_quick_date_select(self, text):  # SETS THE START DATE BASED ON THE COMBO SELECTION.
#        print(f"start on_quick_date_select -> quick_date_combo text = {text}")
        try:
            end_date = self.end_date_edit.date()
            if not end_date.isValid():
                end_date = QDate.currentDate()
            if text == "1 day":
                start_date = end_date
            elif text == "3 days":
                start_date = end_date.addDays(-2)                    
            elif text == "1 week":
                start_date = end_date.addDays(-6)
            elif text == "1 month":
                start_date = end_date.addMonths(-1)
            elif text == "1 year":
                start_date = end_date.addYears(-1)
            elif text == "5 years":
                start_date = end_date.addYears(-5)
            else:
#                print("on_quick_date_select: skipping set start_date")
                return
#            print(f"start date = {start_date.toString()}, end date = {end_date.toString()}")
            self.from_combo = True  # Prevent on_date_change from clearing combo
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
            self.date_filter_var.setChecked(True)
            self.from_combo = False  # Reset flag
            
        except Exception as e:
            self.update_status(f"Error setting date preset: {str(e)}")


    def cycle_range(self, direction=-1):
        """Shift end date by combo range, cap at today, set start date relative to it."""
        range_text = self.quick_date_combo.currentText()
        if not range_text or range_text == "":
            self.update_status("Select a range first")
            return
        
        # Block signals to prevent on_date_change clearing combo
        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)
        self.quick_date_combo.blockSignals(True)
        self.from_combo = True  # Prevent on_date_change from clearing combo
        
        try:
            # Get current end date
            end_date = self.end_date_edit.date()
            if not end_date.isValid():
                end_date = QDate.currentDate()
            
            # Shift end date using on_quick_date_select logic
            if range_text == "1 day":
                new_end = end_date.addDays(1 * direction)
            elif range_text == "3 days":
                new_end = end_date.addDays(3 * direction)
            elif range_text == "1 week":
                new_end = end_date.addDays(7 * direction)
            elif range_text == "1 month":
                new_end = end_date.addMonths(1 * direction)
            elif range_text == "1 year":
                new_end = end_date.addYears(1 * direction)
            elif range_text == "5 years":
                new_end = end_date.addYears(5 * direction)
            else:
                return
            
            # Cap end date at today for forward shifts
            today = QDate.currentDate()
            if direction > 0 and new_end > today:
                new_end = today
            
            # Set start date relative to new_end (like on_quick_date_select)
            if range_text == "1 day":
                new_start = new_end
            elif range_text == "3 days":
                new_start = new_end.addDays(-2)
            elif range_text == "1 week":
                new_start = new_end.addDays(-6)
            elif range_text == "1 month":
                new_start = new_end.addMonths(-1)
            elif range_text == "1 year":
                new_start = new_end.addYears(-1)
            elif range_text == "5 years":
                new_start = new_end.addYears(-5)
            
            # Update dates
            self.end_date_edit.setDate(new_end)
            self.start_date_edit.setDate(new_start)
            self.date_filter_var.setChecked(True)
            
            # Status
            self.update_status(f"Shifted {range_text} {'back' if direction < 0 else 'forward'}")
        
        except Exception as e:
            self.update_status(f"Error shifting dates: {str(e)}")
        
        # Unblock signals
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)
        self.quick_date_combo.blockSignals(False)
        self.from_combo = False


# FILTER ROW FUNCTIONS --------------------------------------------------------------------------------------------------

    def build_filter_string(self, file_filters):
        """Build filter string based on filemode_combo, using filecheck_filter, filter_combo, or combined_filter."""
        try:
            filter_str = file_filters #""
#            if filemode == "File Checks":
#                filter_str = self.filecheck_filter.strip()



            if self.date_filter_var.isChecked() and self.start_date_edit.text() and self.end_date_edit.text():
                # Validate date format
                datetime.strptime(self.start_date_edit.text(), '%Y-%m-%d')
                datetime.strptime(self.end_date_edit.text(), '%Y-%m-%d')
                date_str = f":date:{self.start_date_edit.text()}-{self.end_date_edit.text()}"
                filter_str = f"{filter_str},{date_str}" if filter_str else date_str
            elif self.date_filter_var.isChecked() and (not self.start_date_edit.text() or not self.end_date_edit.text()):
                self.update_status("Both start and end dates required for date filter")
                self.date_filter_var.setChecked(False)
            return filter_str
        except ValueError:
            self.update_status("Invalid date format; date filter ignored")
            return filter_str




# LOCAL LOCATION ROW FUNCTIONS ----------------------------------------------------------------------------------------------

    def browse_local(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Local Directory", self.local_loc_combo.currentText())
        if folder:
            self.local_loc_combo.setCurrentText(folder)

    def create_folder(self):
        try:
            sid = self.sid_combo.currentData()
            
            site_1 = re.findall(r'\b\w+\b', self.sid_combo.currentText().split('(')[0])
            site_2 = site_1[:3]
            site_name = ' '.join(site_2)

            if not sid or sid == "Custom IP":
                dialog_sitename, ok1 = QInputDialog.getText(self, 'Input Dialog', 'Please enter Site Name')
                if ok1:
                    site_name = dialog_sitename
                else:
                    site_name = "" 

                dialog_sid, ok2 = QInputDialog.getText(self, 'Input Dialog', 'Please enter SID:')
                if ok2:  # User clicked 'OK'
                    sid = dialog_sid
                else:
                    sid = ""
                          
            description, ok = QInputDialog.getText(self, 'Input Dialog', 'Enter Short Problem Description:')
            if ok:  # User clicked 'OK'
                problem = description
            else:
                problem = ""    
            
            now = datetime.now().strftime("%Y.%m.%d")
            folder_name = f"{now}_{site_name}_SID-{sid} ~ {problem} ~"
            full_path = os.path.join(self.local_loc_combo.currentText() or os.getcwd(), folder_name)
            self.local_loc_combo.setCurrentText(full_path)
            self.update_status(f"Created folder path: {full_path}")
        except Exception as e:
            self.update_status(f"Error creating folder path: {str(e)}")

    def save_local_loc(self):
        current = self.local_loc_combo.currentText().strip()
        if current and current not in self.config["local_locations"]:
            self.config["local_locations"].append(current)
            self.local_loc_combo.clear()
            self.local_loc_combo.addItems(self.config["local_locations"] + DEFAULT_LOCAL_LOCS)
            self.local_loc_combo.setCurrentText(current)
            save_config(self.config)

    def delete_local_loc(self):
        current = self.local_loc_combo.currentText().strip()
        if current in DEFAULT_LOCAL_LOCS:
            self.update_status("Cannot delete hardcoded local location preset")
            return
        if current in self.config["local_locations"]:
            self.config["local_locations"].remove(current)
            self.local_loc_combo.clear()
            self.local_loc_combo.addItems(self.config["local_locations"] + DEFAULT_LOCAL_LOCS)
            self.local_loc_combo.setCurrentText("")
            if __name__ == "__main__":
                save_config(self.config)
            self.update_status(f"Deleted local location preset: {current}")            


# TIMED/DOWNLOAD FUNCTIONS --------------------------------------------------------------------------

    def on_timed_check_toggled(self, checked):
        if self.inc_timer.isActive():
            self.inc_timer.stop()
            self.download_btn.setText("Download")
            self.update_status("Timed download option disabled")

    def format_size(self, bytes_size):
        """Convert bytes to human-readable format (e.g., KB, MB, GB)."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.2f} TB"

    def download_files(self):
        """Download files based on selected mode: File Checks, Custom Filter, or Append to Custom."""
        error_msg = None
        total_num_files = 0
        total_size_bytes = 0
        total_download_time = 0
        total_run_time = 0
        num_files = 0
        size_bytes = 0

        if self.is_downloading or self.inc_timer.isActive():
            self.is_downloading = False  # Signal to abort download
            self.cancel_event.set()  # Signal cancellation
            if self.inc_timer.isActive():
                self.inc_timer.stop()
                self.download_btn.setText("Download")
                self.update_status("Timed download stopped")
                return  # Exit after stopping timed download
            else:
                self.update_status("Download aborted")
                return

        try:
            # Handle custom period input for timed download
            period = self.period_combo.currentText() if self.timed_check.isChecked() else None
            if self.timed_check.isChecked() and period == "custom":
                period, ok = QInputDialog.getText(self, "Custom Period", "Enter custom period (minutes):")
                if not ok or not period:
                    self.timed_check.setChecked(False)
                    self.update_status("Timed download cancelled")
                    return
                try:
                    period = int(period)
                except ValueError:
                    self.timed_check.setChecked(False)
                    self.update_status("Invalid custom period")
                    return

            # Get current SID
            sid = self.sid_combo.currentData()
            usertype = self.ip_type_combo.currentText()
            if not sid:
                if not usertype == "Custom User":
                    self.update_status("Error: Please select a valid SID or use Custom IP")
                    return
            
            # Use Custom IP and Password
            
            if usertype == "Custom User":
                # === STORE IN CRED STORE ===
                self.cred_store["Custom User"] = {
                    "ip": self.ip_edit.text().strip(),
                    "username": self.username_edit.text().strip(),
                    "password": self.password_edit.text().strip(),
                    "protocol": self.protocol_combo.currentText()
                }

            self.is_downloading = True
            self.download_btn.setText("Abort Download")
            self.update_status("Download started")
            self.cancel_event.clear()  # Reset cancellation

            # Determine download mode
            filemode = self.filemode_combo.currentText()
            downloads = []
            if filemode == "File Checks":
                if not any(cb.isChecked() for cb in self.filecheck_checkboxes):
                    self.update_status("Error: No file checks selected in File Checks mode")
                    self.is_downloading = False
                    self.download_btn.setText("Download")
                    return

                for checkbox in self.filecheck_checkboxes:
                    if checkbox.isChecked():
                        cfg = self.filecheck_configs[checkbox.text()]
                        downloads.append({
                            "usertype": cfg["usertype"],
                            "remote_loc": self.resolve_remote_loc(cfg, self.siddb.get(sid, {}), sid).rstrip('/\\'),
                            "file_filter": cfg["file_filter"],
                            "title": checkbox.text(),
                            "command_to_run": self.resolve_command_to_run(cfg, self.siddb.get(sid, {})),
                            "run_user": cfg.get("run_user"),
                            "run_command_mode": cfg.get("run_command_mode", False),
                            "watch_folder": cfg.get("watch_folder", False)
                        })
                        # ---- NEW: store IP (and optional explicit creds) for every ip_type ----
                        # main usertype
                        # FILE CHECKS WON'T EVER USE SELF.IP_EDIT SO ITS COMMENTED OUT HERE. <<<<
                        main_ip = self.siddb.get(sid, {}).get(cfg["usertype"])# or self.ip_edit.text() 
                        self.downloader.set_ip_and_credentials(cfg["usertype"], main_ip)
                        # run-user ip_type (if different)
                        run_type = cfg.get("run_user")
                        if run_type and run_type != cfg["usertype"]:
                            run_ip = self.siddb.get(sid, {}).get(run_type)
                            if run_ip:
                                self.downloader.set_ip_and_credentials(run_type, run_ip)

            elif filemode == "Custom Filter":
                if not self.filter_combo.currentText().strip():
                    self.update_status("Error: Custom file filter is empty in Custom Filter mode")
                    self.is_downloading = False
                    self.download_btn.setText("Download")
                    return
                downloads.append({
                    "usertype": self.ip_type_combo.currentText(),
                    "remote_loc": self.remote_loc_combo.currentText().rstrip('/\\'),
                    "file_filter": self.filter_combo.currentText(),
                    "title": "Custom"
                })
            elif filemode == "Append to Custom":
                if not self.filter_combo.currentText().strip() and not any(checkbox.isChecked() for checkbox in self.filecheck_checkboxes):
                    self.update_status("Error: No file checks or custom filter selected in Append to Custom mode")
                    self.is_downloading = False
                    self.download_btn.setText("Download")
                    return

                # Always add the custom filter entry if there is one (even if no checkboxes are selected)
                if self.filter_combo.currentText().strip():
                    downloads.append({
                        "usertype": self.ip_type_combo.currentText(),
                        "remote_loc": self.remote_loc_combo.currentText().rstrip('/\\'),
                        "file_filter": self.filter_combo.currentText(),
                        "title": "Custom"
                    })

                # Add all selected file-check configs (same as File Checks mode)
                if any(checkbox.isChecked() for checkbox in self.filecheck_checkboxes):
                    for checkbox in self.filecheck_checkboxes:
                        if checkbox.isChecked():
                            config = self.filecheck_configs[checkbox.text()]
                            downloads.append({
                                "usertype": config["usertype"],
                                "remote_loc": self.resolve_remote_loc(config, self.siddb.get(sid, {}), sid).rstrip('/\\'),
                                "file_filter": config["file_filter"],
                                "title": checkbox.text(),
                                "command_to_run": self.resolve_command_to_run(config, self.siddb.get(sid, {})),
                                "run_user": config.get("run_user"),
                                "run_command_mode": config.get("run_command_mode", False),
                                "watch_folder": config.get("watch_folder", False)
                            })
                            # Store IP and credentials for main usertype
                            # FILE CHECKS WON'T EVER USE SELF.IP_EDIT SO ITS COMMENTED OUT HERE. <<<<
                            main_ip = self.siddb.get(sid, {}).get(config["usertype"])# or self.ip_edit.text()
                            self.downloader.set_ip_and_credentials(config["usertype"], main_ip)

                            # Store IP for run_user if different
                            run_type = config.get("run_user")
                            if run_type and run_type != config["usertype"]:
                                run_ip = self.siddb.get(sid, {}).get(run_type)
                                if run_ip:
                                    self.downloader.set_ip_and_credentials(run_type, run_ip)

            # === GROUP BY usertype ===
            grouped_downloads = {}
            command_configs = []  # NEW: Collect all configs with run_command_mode=True
            for download in downloads:
                key = download["usertype"]
                if key not in grouped_downloads:
                    grouped_downloads[key] = []
                grouped_downloads[key].append(download)

                # NEW: If this config needs to run command first, collect it separately
                if download.get("run_command_mode", False):
                    command_configs.append(download)
            
#            print(f"\n\ngrouped_downloads = \n{grouped_downloads}\n\n")
            # === VERIFICATION CHECK (unchanged, runs on remaining groups) ===
            needs_verification = False
            for usertype, configs in grouped_downloads.items():
                if usertype == "host_ip":
                    needs_verification = True
                    break
                for config in configs:
                    if config.get("run_user") == "host_ip":
                        needs_verification = True
                        break
                if needs_verification:
                    break

            if needs_verification:
                reply = QMessageBox.question(
                    self,
                    "Verification Required",
                    "Can you verify before executing that\n"
                    "the customer is not scanning and they\n"
                    "acknowledge you are running tests.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    self.update_status("Command cancelled — verification not confirmed.")
                    return

            # === RUN ALL run_command_mode=True configs FIRST (independently) ===
            for cfg in command_configs:
                # Set up downloader for this specific command run
                cred = self.cred_store.get(cfg["usertype"])
                if not cred:
                    self.update_status(f"No credentials for {cfg['usertype']} (command run)")
                    continue

                self.downloader.ip = cred["ip"]
                self.downloader.ip_type = cfg["usertype"]
                self.downloader.username = cred["username"]
                self.downloader.password = cred["password"]
                self.downloader.protocol = cred["protocol"]
                self.downloader.entry = self.entry
                self.downloader.local_loc = self.local_loc_combo.currentText()
                self.downloader.sid = sid

                # Set the command and run_user
                self.downloader.command_to_run = cfg.get("command_to_run")
                self.downloader.run_user_ip_type = cfg.get("run_user")
                self.downloader.run_command_mode = True
                self.downloader.watch_folder = cfg.get("watch_folder", False)

                # Remote locs and filter (even if just for command)
                remote_locs = [cfg["remote_loc"]]
                self.downloader.remote_locs = remote_locs
                self.downloader.file_filter = cfg["file_filter"]

                self.update_status(f"Running command for {cfg['title']}...")
                QApplication.processEvents()

                # Run download_logs — it will execute the command first (and download if watch_folder)
                # Runs in a background thread so the GUI stays responsive.
                future = self.executor.submit(
                    self.downloader.download_logs,
                    incremental=self.overwrite_check.isChecked(),
                    status_callback=self.update_status,
                    cancel_event=self.cancel_event
                )
                # Wait for the result while keeping the GUI alive
                while not future.done():
                    QApplication.processEvents()
                    time.sleep(0.01)

                num_files, size_bytes, download_time, run_time, error_msg = future.result()


                
                print(f"Command Ran and File(s) Downloaded, num_files = {num_files}, total_size = {size_bytes/1024:.1f} KB, download_time = {download_time:.2f} seconds")
                
                if error_msg:
                    self.update_status(error_msg)
                    print(f"Command run error: {error_msg}")
                    continue

                total_num_files = total_num_files + num_files
                total_size_bytes = total_size_bytes + size_bytes
                total_download_time = total_download_time + download_time
                total_run_time = total_run_time + run_time

            # === REMOVE command_mode configs from grouped_downloads (already processed) ===
            cleaned_grouped = {}
            for usertype, configs in grouped_downloads.items():
                remaining = [c for c in configs if not c.get("run_command_mode", False)]
                if remaining:
                    cleaned_grouped[usertype] = remaining
            grouped_downloads = cleaned_grouped
# =============== PROCESS EACH GROUP (now only non-command_mode) ===============================================================
            for usertype, configs in grouped_downloads.items():
                cred = self.cred_store.get(usertype)
                if not cred:
                    self.update_status(f"No credentials for {usertype}")
                    continue

                self.downloader.ip = cred["ip"]
                self.downloader.ip_type = usertype
                self.downloader.username = cred["username"]
                self.downloader.password = cred["password"]
                self.downloader.protocol = cred["protocol"]
                self.downloader.entry = self.entry

                self.downloader.local_loc = self.local_loc_combo.currentText()
                self.downloader.sid = sid

                remote_locs = list(set(config["remote_loc"] for config in configs))
                file_filters = ",".join(config["file_filter"] for config in configs)
                
                self.downloader.file_filter = self.build_filter_string(file_filters)
                self.downloader.remote_locs = remote_locs
                print(f"remote_locs = {remote_locs}, \nfile_filter = {self.downloader.file_filter}")

                # === NO COMMAND RUN HERE — already handled earlier ===
                self.downloader.command_to_run = None
                self.downloader.run_command_mode = False
                self.downloader.watch_folder = False

                self.update_status(f"Downloading {', '.join(c['title'] for c in configs)} from {', '.join(remote_locs)}...")
                QApplication.processEvents()

                # Run download_logs in a background thread so the GUI stays responsive
                future = self.executor.submit(
                    self.downloader.download_logs,
                    incremental=self.overwrite_check.isChecked(),
                    status_callback=self.update_status,
                    cancel_event=self.cancel_event
                )
                # Wait for the result while keeping the GUI alive
                while not future.done():
                    QApplication.processEvents()
                    time.sleep(0.01)

                num_files, size_bytes, download_time, run_time, error_msg = future.result()


                print(f"Downloaded, num_files = {num_files}, total_size = {size_bytes/1024:.1f} KB, download_time = {download_time:.2f} seconds")
                
                if error_msg:
                    self.update_status(error_msg)
                    print(f"error msg = {error_msg}")
                    continue
                
                if num_files == 0 and size_bytes == 0:
                    continue
                
                total_num_files = total_num_files + num_files
                total_size_bytes = total_size_bytes + size_bytes
                total_download_time = total_download_time + download_time
                total_run_time = total_run_time + run_time


            # === TIMED DOWNLOAD (unchanged) ===
            if self.timed_check.isChecked():
                interval = None
                if period == "6am daily":
                    now = datetime.now()
                    next_6am = datetime(now.year, now.month, now.day, 6, 0)
                    if now.hour >= 6:
                        next_6am += timedelta(days=1)
                    interval = int((next_6am - now).total_seconds() * 1000)
                    self.inc_timer.setInterval(24 * 60 * 60 * 1000)
                elif period == "8hr":
                    interval = int(8 * 60 * 60 * 1000)
                elif period == "4hr":
                    interval = int(4 * 60 * 60 * 1000)
                elif period == "1hr":
                    interval = int(60 * 60 * 1000)
                elif period == "30min":
                    interval = int(30 * 60 * 1000)
                elif period == "15min":
                    interval = int(15 * 60 * 1000)
                elif period == "5min":
                    interval = int(5 * 60 * 1000)
                elif period == "1min":
                    interval = int(60 * 1000)
                elif isinstance(period, int):
                    interval = int(period * 60 * 1000)
                if interval:
                    self.inc_timer.setInterval(interval)
                    self.inc_timer.setSingleShot(True)
                    self.inc_timer.start()
                    self.download_btn.setText("Stop Timed Download")
        


        finally:
            if error_msg:
                self.update_status(error_msg)
                print(f"error msg = {error_msg}")
            elif num_files == 0 and size_bytes == 0:
                print(f"0 Files")                 
            else:               
                throughput = total_size_bytes / total_download_time / 1024 if total_download_time > 0 else 0
                unit = "KB/s"
                if throughput >= 1024:
                    throughput /= 1024
                    unit = "MB/s"
                
                time_parts = []
                hours = int(total_download_time // 3600)
                if hours > 0:
                    time_parts.append(f"{hours} hr(s)")
                    total_download_time %= 3600
                minutes = int(total_download_time // 60)
                if minutes > 0:
                    time_parts.append(f"{minutes} min(s)")
                    total_download_time %= 60
                seconds = total_download_time
                time_parts.append(f"{seconds:.2f} sec(s)")
                time_str = ", ".join(time_parts)
                
                run_time_parts = []
                run_hours = int(total_run_time // 3600)
                if run_hours > 0:
                    run_time_parts.append(f"{run_hours} hr(s)")
                    total_run_time %= 3600
                run_minutes = int(total_run_time // 60)
                if run_minutes > 0:
                    run_time_parts.append(f"{run_minutes} min(s)")
                    total_run_time %= 60
                run_seconds = total_run_time
                run_time_parts.append(f"{run_seconds:.2f} sec(s)")
                run_time_str = ", ".join(run_time_parts)

                self.update_status(f"DOWNLOAD COMPLETE: Processed {total_num_files} file(s) ({self.format_size(total_size_bytes)}) at {throughput:.2f} {unit} in {time_str}. Total Run Time was {run_time_str}.")
            
            self.is_downloading = False
            if not self.inc_timer.isActive():
                self.download_btn.setText("Download")
            QApplication.processEvents()

    def open_save_folder(self):
        path_str = self.local_loc_combo.currentText()#.strip()
        if not path_str:
            self.update_status("No path selected")
            return

        path = os.path.abspath(path_str)  # normalize + make absolute
        original = path
        print(f"open_save_folder - path = {path}")
        # Go up until we find an existing directory
        while path and not os.path.exists(path):
            path = os.path.dirname(path)

        # If we found nothing valid → use C:\
        if not path or not os.path.isdir(path):
            path = "C:\\"
            self.update_status(f"Path didn't exist:\n{original}\n\nOpened C:\\ instead")

        try:
            os.startfile(path)
        except Exception as e:
            self.update_status(f"Failed to open:\n{path}\nError: {e}")

   
    def prompt_start_download(self):
        """Show popup to start download."""
        reply = QMessageBox.question(self, "Start Download",
                                    "Would you like to start downloading logs now?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            new_folder = QMessageBox.question(self, "Create Folder",
                                    "Would you like to create a new folder?",
                                    QMessageBox.Yes | QMessageBox.No)
            if new_folder == QMessageBox.Yes:
                self.create_folder()
            self.download_files()


    def update_status(self, message):
        self.status_label.setText(message)
#        current_width = self.width() # Captures width before resize. 
#        self.adjustSize() # Resizes if status message wraps.
#        self.resize(current_width, self.sizeHint().height()) # Keeps current width but causes flashing. 

    def center_on_screen(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 3, (screen.height() - size.height()) // 2)

    def closeEvent(self, event):
        # Save config only if running as main script
        if __name__ == "__main__":
            self.config["last_selections"] = {
                "sid": self.sid_combo.currentData() or "",
                "filechecks": [cb.text() for cb in self.filecheck_checkboxes if cb.isChecked()],
                "filemode": self.filemode_combo.currentText(),  # Added
                "ip_type": self.ip_type_combo.currentText().split(" (")[0],
                "ip": self.ip_edit.text(),
                "username": self.username_edit.text(),
                "remote_loc": self.remote_loc_combo.currentText(),
                "local_loc": self.local_loc_combo.currentText(),
                "file_filter": self.filter_combo.currentText(),
                "protocol": self.protocol_combo.currentText(),
                "date_filter_enabled": self.date_filter_var.isChecked(),
                "start_date": self.start_date_edit.text(),
                "end_date": self.end_date_edit.text(),
                "quick_date": self.quick_date_combo.currentText(),
                "incremental_download": self.overwrite_check.isChecked(),
                "timed_download": self.timed_check.isChecked(),
                "incremental_period": self.period_combo.currentText(),
            
              #  "password": self.password_edit.text(),
              #  "filemode": self.filemode_combo.currentText()
            }
            save_config(self.config)
        if self.inc_timer.isActive():
            self.inc_timer.stop()
        self.executor.shutdown(wait=True)
        super().closeEvent(event)



    def set_stylesheet(self, theme="dark"):
        """Apply stylesheet for light or dark theme."""
        themes = {
            "dark": {
                "main_bg": "#2E2E2E",  # Dark charcoal
                "border": "#666666",   # Muted gray
                "text": "#E0E0E0",     # Off-white text
                "input_bg": "#4A4A4A", # Darker frame
                "focus_border": "#4FC3F7",  # Light blue focus
                "focus_bg": "#555555",      # Slightly lighter focus
                "hover_bg": "#4FC3F7",      # Light blue hover
                "pressed_bg": "#0288D1",    # Darker blue pressed
                "select_bg": "#4FC3F7",     # Light blue selection
                "select_text": "#2E2E2E"    # Dark text on selection
            },
            "light": {
                "main_bg": "#FFFFFF",  # White
                "border": "#CCCCCC",   # Light gray
                "text": "#333333",     # Dark text
                "input_bg": "#F5F5F5", # Light gray frame
                "focus_border": "#2196F3",  # Blue focus
                "focus_bg": "#E0E0E0",      # Lighter gray focus
                "hover_bg": "#2196F3",      # Blue hover
                "pressed_bg": "#1976D2",    # Darker blue pressed
                "select_bg": "#2196F3",     # Blue selection
                "select_text": "#FFFFFF"    # White text on selection
            }
        }
        colors = themes.get(theme, themes["dark"])
        
        self.setStyleSheet(f"""
            QHeaderView {{
                border-bottom: 1px solid {colors['border']};
                padding: 2px;
            }}
            
            QMainWindow {{
                background-color: {colors['main_bg']};
                border: 1px solid {colors['border']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QLineEdit, QComboBox, QDateEdit {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 3px;
            }}
            QComboBox QLineEdit {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                border: none;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 1px solid {colors['focus_border']};
                background-color: {colors['focus_bg']};
            }}
            QCalendarWidget {{
                background-color: {colors['main_bg']};
                color: {colors['text']};
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                padding: 2px;
            }}
            QCalendarWidget QAbstractItemView::item {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                selection-background-color: {colors['select_bg']};
                selection-color: {colors['select_text']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                selection-background-color: {colors['select_bg']};
                selection-color: {colors['select_text']};
            }}
            QPushButton {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover_bg']};
                color: {colors['select_text']};
            }}
            QPushButton:pressed {{
                background-color: {colors['pressed_bg']};
            }}
            QMessageBox, QDialog {{
                background-color: {colors['main_bg']};
            }}
            QMessageBox QLabel, QDialog QLabel {{
                color: {colors['text']};
            }}
            QCheckBox {{
                color: {colors['text']};
            }}
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(*sys.argv[1:])  # PASS ALL ARGS!
    window.show()
    sys.exit(app.exec_())