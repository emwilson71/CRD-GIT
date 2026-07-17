import sys
import json
import os
import re
import time
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, 
    QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, QMessageBox, QInputDialog, 
    QFileDialog, QCheckBox, QDesktopWidget, QDialog, QDateEdit, QTreeView, QHeaderView
    )
from PyQt5.QtGui import QColor, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer, QDate
from dateutil.relativedelta import relativedelta
import paramiko  # For SSH/SFTP
from ftplib import FTP  # For FTP
import fnmatch
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio
import asyncssh

# Styling
DARK_BG = QColor(30, 30, 30)
TEXT_COLOR = QColor(200, 200, 200)
FRAME_BG = QColor(40, 40, 40)

# Default SID Database
DEFAULT_SIDDB_PATH = "c:/CRD/data/siddb.json"

# Default Current Database
DEFAULT_CURRENTDB_PATH = "C:/CRD/config/current.dat"

DEFAULT_FILTERS = [".rm, .acqsts, .slg, *SNAPSHOT.LOG, *_MPlusErrorDispLog*.txt,  ",  
    "SYSLOG_engine*", "*HPM2_Test_data.log", 
    "*_CoolingCabi.txt, *_f70log.txt, *_SVU_*.csv, *_SVUlog.txt, *_MSUP.cab, *_MSUP_V*.gz, *_MSUP2.txt.gz", 
    "20*.CSV", "VisartConditionHistory2.csv, ECOQA*.CSV, PARDB.SITE, RANGECHECKLOG_DQA.TXT, ",
    ]


# SEE def get_default_remote_locs for DEFAULT_REMOTE_LOCS


DEFAULT_LOCAL_LOCS = ["C:\\CANON\\ERRORS", "C:\\CRD\\downloads",]

# Hard-coded usernames and passwords
SP_USER1 = "iv_service_user"
SP_PASS1 = "SU_InnerVision2020"
SP_USER2 = "sp_user2"
SP_PASS2 = "sp_pass2"

CREDENTIALS_MAP = {
    ("MR", "Win10", "V8.0SP*"): ("mr_user", "mr_pass"),
    ("MR_V3.x+",): ("mr_v3_user", "mr_v3_pass"),
    ("MR",): ("default_mr_user", "default_mr_pass"),
    # Add more as needed
}

# Config file
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "log_downloader.json")



def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
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
            "incremental_period": "6am daily"
        }
    }

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
        return [(SP_USER1, SP_PASS1), (SP_USER2, SP_PASS2)]
    elif ip_type in ["host_ip", "display_ip"]:
        modality = entry.get("modality", [""])[0]
        machine = entry.get("machine", "").title()  # Normalize to title case
        sw_version = entry.get("sw_version", "")
        # Try specific match with wildcard
        for (m, mach, sw), creds in CREDENTIALS_MAP.items():
            if m == modality and mach.title() == machine and fnmatch.fnmatch(sw_version, sw):
                return [creds]
        # Try modality and sw_version match
        for (m, sw), creds in CREDENTIALS_MAP.items():
            if m == modality and fnmatch.fnmatch(sw_version, sw):
                return [creds]
        # Fallback to modality only
        for (m,), creds in CREDENTIALS_MAP.items():
            if m == modality:
                return [creds]
        return [("default_user", "default_pass")]
    elif ip_type == "Custom User":
        return [("default_user", "default_pass")]
    # Handle custom ip_type like MR_V3.x+
    for (custom_type,), creds in CREDENTIALS_MAP.items():
        if ip_type == custom_type:
            return [creds]
    return [("default_user", "default_pass")]



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
        self.entry = self.siddb.get(self.sid) if self.sid != "Custom IP" else {}
        self.ip = None
        self.ip_type = None
        self.username = None
        self.password = None
        self.sftp = None
        self.ftp = None
        self.date_filter = {}  # Initialize date_filter
        self.dir_cache = None  # Cache for directory listing

#        print(f"logdownloader {self.siddb}")

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

    def try_connect(self, status_callback=None):
        if self.protocol == "sftp":
            transport = paramiko.Transport((self.ip, 22))
            credentials = [(self.username, self.password)] if self.username and self.password else get_credentials(self.ip_type, self.entry)
            for user, pw in credentials:
                try:
                    transport.connect(username=user, password=pw)
                    self.sftp = paramiko.SFTPClient.from_transport(transport)
                    self.username = user
                    self.password = pw
                    if status_callback:
                        status_callback("Connected to remote host")
                    return True
                except paramiko.AuthenticationException:
                    continue
            return False
        elif self.protocol == "ftp":
            self.ftp = FTP(self.ip)
            credentials = [(self.username, self.password)] if self.username and self.password else get_credentials(self.ip_type, self.entry)
            for user, pw in credentials:
                try:
                    self.ftp.login(user, pw)
                    self.username = user
                    self.password = pw
                    if status_callback:
                        status_callback("Connected to remote host")
                    return True
                except:
                    continue
            return False
        return False

    async def list_remote_dir(self, path):
        files = []
        file_dates = {}
        file_sizes = {}
        if self.protocol == "sftp":
            async with asyncssh.connect(self.ip, port=22, username=self.username, password=self.password, known_hosts=None) as conn:
                async with conn.start_sftp_client() as sftp:
                    try:
                        attrs = await sftp.readdir(path)
                        files = [attr.filename for attr in attrs]
                        file_dates = {attr.filename: datetime.fromtimestamp(attr.attrs.mtime) for attr in attrs}
                        file_sizes = {attr.filename: attr.attrs.size for attr in attrs}
                    except Exception as e:
                        raise ValueError(f"Error listing SFTP directory: {str(e)}")
        elif self.protocol == "ftp":
            ftp = FTP(self.ip)
            try:
                ftp.login(self.username, self.password)
                files = ftp.nlst(path)
                file_dates = {f: datetime.now() for f in files}
                file_sizes = {f: 0 for f in files}  # Fallback
            except Exception as e:
                raise ValueError(f"Error listing FTP directory: {str(e)}")
            finally:
                ftp.quit()
        # Store in cache
        self.dir_cache = {
            'files': files,
            'file_dates': file_dates,
            'file_sizes': file_sizes
        }
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
        if not self.date_filter or not self.date_filter.get("start") or not self.date_filter.get("end"):
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

    def download_logs(self, incremental=False, period=None, status_callback=None, chunk_size=131072, max_concurrent=4, parse_filename_dates=True, list_only=False, cancel_event=None, use_cache=False):
        t0 = time.time()
        try:
            async def async_download():
                num_files = 0
                total_size_bytes = 0
                # Connect to SFTP
                if self.protocol == "sftp":
                    try:
                        # Ensure credentials are set
                        if not self.username or not self.password:
                            if not self.try_connect(status_callback):
                                raise ValueError("Connection failed: No valid credentials")
                        async with asyncssh.connect(self.ip, port=22, username=self.username, password=self.password, known_hosts=None) as conn:
                            t1 = time.time()
                            print(f"Connection time: {(t1 - t0):.2f} seconds")
                            if status_callback:
                                status_callback("Connected to SFTP server")
                                QApplication.processEvents()

                            # Parse filters
                            try:
                                self.parse_filter(self.file_filter)
                            except Exception as e:
                                print(f"Filter parsing error: {str(e)}")
                                raise
                            t2 = time.time()
                            print(f"Parse filter time: {(t2 - t1):.2f} seconds")

                            # Get file list
                            files = []
                            file_dates = {}
                            file_sizes = {}
                            print(f"use_cache: {use_cache}, dir_cache: {self.dir_cache is not None}, cache_size: {len(self.dir_cache['files']) if self.dir_cache else 0}")
                            if use_cache and self.dir_cache:
                                files = self.dir_cache['files']
                                file_dates = self.dir_cache['file_dates']
                                file_sizes = self.dir_cache['file_sizes']
                                if status_callback:
                                    status_callback(f"Using saved file list: {len(files)} files")
                                    QApplication.processEvents()
                                # Refresh metadata for filtered files
                                async with conn.start_sftp_client() as sftp:
                                    for f in files:
                                        if self.apply_filter(f) and self.is_within_date_range(f, file_dates.get(f), parse_filename_dates):
                                            try:
                                                attr = await sftp.stat(os.path.join(self.remote_loc, f))
                                                file_dates[f] = datetime.fromtimestamp(attr.mtime)
                                                file_sizes[f] = attr.size
                                            except Exception as e:
                                                print(f"Error refreshing metadata for {f}: {str(e)}")
                            else:
                                t_list_start = time.time()
                                if use_cache and not self.dir_cache:
                                    print("Cache empty, populating cache")
                                    if status_callback:
                                        status_callback("Populating File List")
                                        QApplication.processEvents()
                                try:
                                    files, file_dates, file_sizes = await self.list_remote_dir(self.remote_loc)
                                except asyncssh.SFTPError as e:
                                    if "No such file" in str(e):
                                        print(f"File download error1: Error listing SFTP directory: No such file")
                                        if status_callback:
                                            status_callback("Error: Remote location does not exist")
                                        return 0, 0, 0
                                    raise
                                print(f"Server list response time: {(time.time() - t_list_start):.2f} seconds")
                                print(f"Retrieved {len(files)} files from remote directory")
                            t3 = time.time()
                            print(f"File listing time: {(t3 - t2):.2f} seconds")

                            # Apply filters
                            try:
                                filtered_files = []
                                if not isinstance(files, list):
                                    raise ValueError(f"File list is not iterable: {files}")
                                print("Starting filtering")
                                if cancel_event and cancel_event.is_set():
                                    print("Cancellation detected before filtering")
                                    raise asyncio.CancelledError("Download aborted")
                                for i, f in enumerate(files):
                                    if i % 1000 == 0 and cancel_event and cancel_event.is_set():
                                        print(f"Cancellation detected after {i} files")
                                        raise asyncio.CancelledError("Download aborted")
                                    apply_result = self.apply_filter(f)
                                    date_result = self.is_within_date_range(f, file_dates.get(f), parse_filename_dates=parse_filename_dates)
                                    if apply_result is None or date_result is None:
                                        continue
                                    if apply_result and date_result:
                                        filtered_files.append(f)
                                print(f"Filtered {len(filtered_files)} out of {len(files)} files")
                                if not isinstance(filtered_files, list):
                                    raise ValueError("Filtered files is not a list")
                            except Exception as e:
                                print(f"Filtering error: {str(e)}")
                                raise
                            t4 = time.time()
                            print(f"Filtering time: {(t4 - t3):.2f} seconds")

                            if list_only:
                                return filtered_files, 0, 0  # Return filtered files without downloading

                            if status_callback:
                                status_callback(f"Found {len(filtered_files)} files to download...")
                                QApplication.processEvents()

                            # Use provided local_loc directly; no automatic folder creation
                            full_local = self.local_loc
                            os.makedirs(full_local, exist_ok=True)

                            async def download_file(file):
                                nonlocal num_files, total_size_bytes
                                t_file_start = time.time()
                                coro_id = id(asyncio.current_task())
                                print(f"Coroutine ID: {coro_id} starting download")
                                remote_path = os.path.join(self.remote_loc, file)
                                local_path = os.path.join(full_local, file)
                                remote_size = file_sizes.get(file, 0)
                                remote_mtime = file_dates.get(file, datetime.now())
                                print(f"File size: {file_sizes.get(file, 0)} bytes")

                                should_download = True
                                if incremental and os.path.exists(local_path):
                                    local_size = os.path.getsize(local_path)
                                    local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))
                                    # Check if file was likely downloaded with paramiko (mtime updated later)
                                    paramiko_downloaded = (local_mtime.date() < datetime.now().date())
                                    print(f"local_mtime={local_mtime}, remote_mtime={remote_mtime}, local_size={local_size}, remote_size={remote_size}, paramiko_downloaded={paramiko_downloaded}")
                                    if local_mtime >= remote_mtime and local_size == remote_size:
                                        should_download = False
                                        if status_callback:
                                            status_callback(f"Skipping file {file} (no changes)")
                                            QApplication.processEvents()
                                    else:
                                        should_download = True
                                        if local_mtime < remote_mtime:
                                            print(f"downloading file because mtime is different (local: {local_mtime}, remote: {remote_mtime})")
                                        if local_size != remote_size:
                                            print(f"downloading file because size is different (local: {local_size}, remote: {remote_size})")
                                        if status_callback:
                                            status_callback(f"Downloading file {file} (newer or different size)")
                                            QApplication.processEvents()
                                elif incremental:
                                    print(f"downloading file because local file missing")
                                    if status_callback:
                                        status_callback(f"Downloading file {file} (missing locally)")
                                        QApplication.processEvents()

                                if should_download:
                                    print(f"Checking cancellation: {cancel_event.is_set() if cancel_event else False}")
                                    if cancel_event and cancel_event.is_set():
                                        raise asyncio.CancelledError("Download aborted")
                                    if status_callback:
                                        status_callback(f"Downloading file {file}...")
                                        QApplication.processEvents()
                                    try:
                                        async with conn.start_sftp_client() as sftp:
                                            t_file_open = time.time()
                                            print(f"Server response time: {(t_file_open - t_file_start):.2f} seconds")
                                            print(f"File open time: {(t_file_open - t_file_start):.2f} seconds")
                                            t_network_start = time.time()
                                            await sftp.get(remote_path, local_path)
                                            t_network_end = time.time()
                                            data_size = os.path.getsize(local_path)
                                            print(f"Total bytes read: {data_size} bytes, expected: {remote_size} bytes")
                                            if data_size != remote_size:
                                                print(f"Warning: Downloaded size {data_size} does not match expected size {remote_size}")
                                            print(f"Network transfer time: {(t_network_end - t_network_start):.2f} seconds")
                                            print(f"Network bandwidth: {(data_size / (t_network_end - t_network_start) / 1024):.2f} KB/s")
                                        t_file_transfer = time.time()
                                        print(f"File transfer time: {(t_file_transfer - t_file_open):.2f} seconds")
                                        print(f"Bandwidth: {(data_size / (t_file_transfer - t_file_open) / 1024):.2f} KB/s")
                                        # Preserve remote file's modification time
                                        os.utime(local_path, (remote_mtime.timestamp(), remote_mtime.timestamp()))
                                        t_file_utime = time.time()
                                        print(f"File utime time: {(t_file_utime - t_file_transfer):.2f} seconds")
                                        num_files += 1
                                        total_size_bytes += data_size
                                    except Exception as e:
                                        print(f"File download error2: {str(e)}")

                            # Run downloads concurrently
                            try:
                                if max_concurrent > 1:
                                    await asyncio.gather(*[download_file(file) for file in filtered_files[:max_concurrent]])
                                    for file in filtered_files[max_concurrent:]:
                                        await download_file(file)
                                else:
                                    for file in filtered_files:
                                        await download_file(file)
                                t5 = time.time()
                                total_download_time = t5 - t4
                                print(f"Total download loop time: {total_download_time:.2f} seconds")

                                # Store filtered files in cache for next run
                                if use_cache:
                                    self.dir_cache = {
                                        'files': files,
                                        'file_dates': file_dates,
                                        'file_sizes': file_sizes
                                    }
                                    print("Updated dir_cache with current file list")

                                print(f"Total execution time: {(t5 - t0):.2f} seconds")
                                return num_files, total_size_bytes, total_download_time
                            except asyncio.CancelledError:
                                if status_callback:
                                    status_callback("Download aborted")
                                print("Download aborted")
                                return 0, 0, 0
                    except Exception as e:
                        print(f"File download error1: {str(e)}")
                        if status_callback:
                            status_callback(f"Error: {str(e)}")
                        return 0, 0, 0
                elif self.protocol == "ftp":
                    files = []
                    file_dates = {}
                    file_sizes = {}
                    ftp = FTP(self.ip)
                    ftp.login(self.username, self.password)
                    t1 = time.time()
                    print(f"Connection time: {(t1 - t0):.2f} seconds")

                    try:
                        self.parse_filter(self.file_filter)
                    except Exception as e:
                        print(f"Filter parsing error: {str(e)}")
                        ftp.quit()
                        raise
                    t2 = time.time()
                    print(f"Parse filter time: {(t2 - t1):.2f} seconds")

                    print(f"use_cache: {use_cache}, dir_cache: {self.dir_cache is not None}, cache_size: {len(self.dir_cache['files']) if self.dir_cache else 0}")
                    if use_cache and self.dir_cache:
                        files = self.dir_cache['files']
                        file_dates = self.dir_cache['file_dates']
                        file_sizes = self.dir_cache['file_sizes']
                        if status_callback:
                            status_callback(f"Using saved file list: {len(files)} files")
                            QApplication.processEvents()
                        # Note: FTP doesn't easily support refreshing metadata like SFTP
                    else:
                        t_list_start = time.time()
                        if use_cache and not self.dir_cache:
                            print("Cache empty, populating cache")
                            if status_callback:
                                status_callback("Populating File List")
                                QApplication.processEvents()
                        files, file_dates, file_sizes = await self.list_remote_dir(self.remote_loc)
                        print(f"Server list response time: {(time.time() - t_list_start):.2f} seconds")
                        print(f"Retrieved {len(files)} files from remote directory")
                    t3 = time.time()
                    print(f"File listing time: {(t3 - t2):.2f} seconds")

                    try:
                        filtered_files = []
                        if not isinstance(files, list):
                            ftp.quit()
                            raise ValueError(f"File list is not iterable: {files}")
                        print("Starting filtering")
                        if cancel_event and cancel_event.is_set():
                            print("Cancellation detected before filtering")
                            ftp.quit()
                            raise asyncio.CancelledError("Download aborted")
                        for i, f in enumerate(files):
                            if i % 1000 == 0 and cancel_event and cancel_event.is_set():
                                print(f"Cancellation detected after {i} files")
                                ftp.quit()
                                raise asyncio.CancelledError("Download aborted")
                            apply_result = self.apply_filter(f)
                            date_result = self.is_within_date_range(f, file_dates.get(f), parse_filename_dates=parse_filename_dates)
                            if apply_result is None or date_result is None:
                                continue
                            if apply_result and date_result:
                                filtered_files.append(f)
                        print(f"Filtered {len(filtered_files)} out of {len(files)} files")
                        if not isinstance(filtered_files, list):
                            ftp.quit()
                            raise ValueError("Filtered files is not a list")
                    except Exception as e:
                        print(f"Filtering error: {str(e)}")
                        ftp.quit()
                        raise
                    t4 = time.time()
                    print(f"Filtering time: {(t4 - t3):.2f} seconds")

                    if list_only:
                        ftp.quit()
                        return filtered_files, 0, 0

                    if status_callback:
                        status_callback(f"Found {len(filtered_files)} files to download...")
                        QApplication.processEvents()

                    full_local = self.local_loc
                    os.makedirs(full_local, exist_ok=True)

                    connection_pool = queue.Queue(max_concurrent)
                    for _ in range(max_concurrent):
                        ftp = FTP(self.ip)
                        ftp.login(self.username, self.password)
                        connection_pool.put(ftp)

                    def download_file(file):
                        nonlocal num_files, total_size_bytes
                        t_file_start = time.time()
                        print(f"Thread ID: {threading.get_ident()} starting download")
                        remote_path = os.path.join(self.remote_loc, file)
                        local_path = os.path.join(full_local, file)
                        remote_size = file_sizes.get(file, 0)
                        remote_mtime = file_dates.get(file, datetime.now())
                        print(f"File size: {file_sizes.get(file, 0)} bytes")

                        should_download = True
                        if incremental and os.path.exists(local_path):
                            local_size = os.path.getsize(local_path)
                            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))
                            # Check if file was likely downloaded with paramiko (mtime updated later)
                            paramiko_downloaded = (local_mtime.date() < datetime.now().date())
                            print(f"local_mtime={local_mtime}, remote_mtime={remote_mtime}, local_size={local_size}, remote_size={remote_size}, paramiko_downloaded={paramiko_downloaded}")
                            if local_mtime >= remote_mtime and local_size == remote_size:
                                should_download = False
                                if status_callback:
                                    status_callback(f"Skipping file {file} (no changes)")
                                    QApplication.processEvents()
                            else:
                                should_download = True
                                if local_mtime < remote_mtime:
                                    print(f"downloading file because mtime is different (local: {local_mtime}, remote: {remote_mtime})")
                                if local_size != remote_size:
                                    print(f"downloading file because size is different (local: {local_size}, remote: {remote_size})")
                                if status_callback:
                                    status_callback(f"Downloading file {file} (newer or different size)")
                                    QApplication.processEvents()
                        elif incremental:
                            print(f"downloading file because local file missing")
                            if status_callback:
                                status_callback(f"Downloading file {file} (missing locally)")
                                QApplication.processEvents()

                        if should_download:
                            print(f"Checking cancellation: {cancel_event.is_set() if cancel_event else False}")
                            if cancel_event and cancel_event.is_set():
                                raise asyncio.CancelledError("Download aborted")
                            if status_callback:
                                status_callback(f"Downloading file {file}...")
                                QApplication.processEvents()
                            try:
                                print(f"Thread ID: {threading.get_ident()} acquiring connection")
                                conn = connection_pool.get()
                                print(f"Thread ID: {threading.get_ident()} acquired connection")
                                try:
                                    with open(local_path, 'wb') as local_f:
                                        t_file_open = time.time()
                                        print(f"File open time: {(t_file_open - t_file_start):.2f} seconds")
                                        conn.retrbinary(f"RETR {remote_path}", lambda data: local_f.write(data, chunk_size))
                                        t_file_transfer = time.time()
                                        print(f"File transfer time: {(t_file_transfer - t_file_open):.2f} seconds")
                                        print(f"Bandwidth: {(file_sizes.get(file, 0) / (t_file_transfer - t_file_open) / 1024):.2f} KB/s")
                                    num_files += 1
                                    total_size_bytes += file_sizes.get(file, 0)
                                finally:
                                    print(f"Thread ID: {threading.get_ident()} releasing connection")
                                    connection_pool.put(conn)
                            except Exception as e:
                                print(f"File download error3: {str(e)}")

                    try:
                        if max_concurrent > 1:
                            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                                executor.map(download_file, filtered_files)
                        else:
                            for file in filtered_files:
                                download_file(file)
                        t5 = time.time()
                        total_download_time = t5 - t4
                        print(f"Total download loop time: {total_download_time:.2f} seconds")

                        # Store filtered files in cache for next run
                        if use_cache:
                            self.dir_cache = {
                                'files': files,
                                'file_dates': file_dates,
                                'file_sizes': file_sizes
                            }
                            print("Updated dir_cache with current file list")

                        print(f"Total execution time: {(t5 - t0):.2f} seconds")
                        return num_files, total_size_bytes, total_download_time
                    except asyncio.CancelledError:
                        while not connection_pool.empty():
                            conn = connection_pool.get()
                            conn.quit()
                        if status_callback:
                            status_callback("Download aborted")
                        print("Download aborted")
                        return 0, 0, 0

            # Run async function in PyQt's synchronous context
            def run_async(coro):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            if self.protocol == "sftp":
                return run_async(async_download())
            else:
                return async_download()  # FTP is synchronous
        except Exception as e:
            if status_callback:
                status_callback(f"Download failed: {str(e)}")
            print(f"Exception occurred: {str(e)}")
            return 0, 0, 0



#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------



class RemoteFileDialog(QDialog): # THIS OPENS WHEN THE BROWSE BUTTON IS CLICKED. 
    def __init__(self, parent, ip, protocol, username, password, initial_path="/"):
        super().__init__(parent)
        self.setWindowTitle("Browse Remote File System")
        self.ip = ip
        self.protocol = protocol
        self.username = username
        self.password = password
        self.selected_path = ""
        self.selected_files = ""  # Store comma-separated files and folders
        self.client = None
        self.current_path = initial_path.replace("\\", "/")  # Normalize path
        self.sort_by = "name"  # Track sort state
        self.root_item = None  # Store root item for expansion
        if self.protocol == "sftp":
            match = re.match(r'^([a-z]):/', self.current_path.lower())
            if match:
                drive_lower = match.group(1)
                self.current_path = "/" + self.current_path[3:].lower()  # Convert Drive:/ to /drive_lower:/...

        # Initialize connection
        try:
            if self.protocol == "sftp":
                transport = paramiko.Transport((self.ip, 22))
                transport.connect(username=self.username, password=self.password)
                self.client = paramiko.SFTPClient.from_transport(transport)
            else:  # ftp
                self.client = FTP(self.ip)
                self.client.login(user=self.username, passwd=self.password)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
            self.reject()
            return

        layout = QVBoxLayout()
        # Path input layout with up button
        path_layout = QHBoxLayout()
        self.up_button = QPushButton("↑")
        self.up_button.clicked.connect(self.navigate_up)
        path_layout.addWidget(self.up_button)
        self.path_edit = QLineEdit()
        self.path_edit.setText(self.to_display_path(self.current_path))
        self.path_edit.returnPressed.connect(self.navigate_to_path)
        path_layout.addWidget(self.path_edit)
        self.sort_button = QPushButton("Sort: Name")
        self.sort_button.clicked.connect(self.toggle_sort)
        path_layout.addWidget(self.sort_button)
        layout.addLayout(path_layout)

        self.tree = QTreeView()
        self.tree.setIndentation(10)  # Maintain chevrons with minimal spacing
        self.tree.setSelectionMode(QTreeView.MultiSelection)  # Enable multi-selection
        self.model = QStandardItemModel(0, 2)  # Two columns: Name, Modified
        self.model.setHorizontalHeaderLabels(["Name", "Modified"])
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(False)
        self.tree.setColumnWidth(0, 300)  # Name column
        self.tree.setColumnWidth(1, 150)  # Modified column
        layout.addWidget(self.tree)

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
        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

        self.setLayout(layout)
        self.setMinimumSize(700, 600)

        # Populate file system with initial path
        self.populate_file_system(self.current_path)

        # Connect signals for navigation
        self.tree.doubleClicked.connect(self.on_double_click)
        self.tree.expanded.connect(self.on_expanded)
        self.tree.selectionModel().selectionChanged.connect(self.update_selected_files)

    def update_selected_files(self, selected, deselected):
        _, selected_files = self.get_selected_path()
        self.new_file_filter.setText(selected_files)

    def to_display_path(self, sftp_path):
        """Convert SFTP path to Windows-style display path."""
        sftp_path = sftp_path.replace("\\", "/")
        match = re.match(r'^/([a-z]):/', sftp_path.lower())
        if match:
            drive_lower = match.group(1)
            start = match.end()
            rest = sftp_path[start:]
            if not rest.startswith('/'):
                rest = '/' + rest
            display_path = f"{drive_lower.upper()}:{rest}"
            return display_path
        return sftp_path

    def toggle_sort(self):
        self.sort_by = "date" if self.sort_by == "name" else "name"
        self.sort_button.setText(f"Sort: {'Date' if self.sort_by == 'date' else 'Name'}")
        self.populate_file_system(self.current_path)

    def populate_file_system(self, path="/", parent_item=None):
        try:
            # Normalize path: ensure forward slashes, handle any drive for SFTP
            path = path.replace("\\", "/")
            if self.protocol == "sftp":
                if not path.startswith("/"):
                    path = "/" + path
                match = re.match(r'^/([a-z]):/', path.lower())
                if match:
                    drive_lower = match.group(1)
                    start = match.end()
                    rest = path[start:]
                    if rest.startswith("/"):
                        rest = rest[1:]
                    path = f"/{drive_lower}:/{rest}"
            if parent_item is None:
                self.model.clear()
                self.model.setHorizontalHeaderLabels(["Name", "Modified"])
                parent_item = self.model.invisibleRootItem()
                self.current_path = path
                self.path_edit.setText(self.to_display_path(path))
                # Build hierarchy from root to path
                root_path = "/" if self.protocol == "sftp" else "C:/"
                root_item = QStandardItem("/" if self.protocol == "sftp" else "C:")
                root_item.setData(root_path, Qt.UserRole)
                root_item.setData(True, Qt.UserRole + 1)  # Mark as directory
                parent_item.appendRow([root_item, QStandardItem("")])
                self.tree.setExpanded(self.model.indexFromItem(root_item), True)  # Expand root
                current_item = root_item
                accumulated_path = root_path
                # Split path into components for tree display
                drive_lower = None
                drive_upper = None
                if self.protocol == "sftp":
                    match = re.match(r'^/([a-z]):/', path.lower())
                    if match:
                        drive_lower = match.group(1)
                        drive_upper = drive_lower.upper()
                        start = match.end()
                        rest = path[start:]
                        root_item.setText(drive_upper + ":")
                        root_item.setData(f"/{drive_lower}:/", Qt.UserRole)
                        accumulated_path = f"/{drive_lower}:/"
                        components = [c for c in rest.split("/") if c]
                    else:
                        components = [c for c in path.split("/")[1:] if c]
                else:
                    components = [c for c in path.replace("C:/", "").split("/") if c]
                # Create and expand nodes for initial path
                for component in components:
                    if self.protocol == "sftp":
                        full_path = accumulated_path.rstrip('/') + '/' + component.lstrip('/')
                    else:
                        full_path = os.path.join(accumulated_path.rstrip('/'), component).rstrip('/')
                    item_node = QStandardItem(component)
                    item_node.setData(full_path, Qt.UserRole)
                    item_node.setData(True, Qt.UserRole + 1)  # Mark as directory
                    current_item.appendRow([item_node, QStandardItem("")])
                    # Add dummy child to enable chevron
                    dummy = QStandardItem("")
                    item_node.appendRow([dummy, QStandardItem("")])
                    current_item = item_node
                    accumulated_path = full_path
                    # Expand this node
                    self.tree.setExpanded(self.model.indexFromItem(item_node), True)
                parent_item = current_item

            # Populate directory contents
            file_list = []
            if self.protocol == "sftp":
                file_list = self.client.listdir_attr(path)
            else:  # ftp
                self.client.retrlines(f"LIST {path}", lambda x: file_list.append(x))

            # Clear existing children (remove dummy if present)
            if parent_item.rowCount() > 0:
                parent_item.removeRows(0, parent_item.rowCount())
            for item in file_list:
                name = item.filename if self.protocol == "sftp" else item.split()[-1]
                is_dir = item.st_mode & 0o40000 if self.protocol == "sftp" else item.startswith("d")
                # Get modification time
                if self.protocol == "sftp":
                    mtime = datetime.fromtimestamp(item.st_mtime)
                else:  # ftp
                    try:
                        parts = item.split()
                        date_str = " ".join(parts[5:8]) if len(parts) >= 8 else ""
                        try:
                            mtime = datetime.strptime(date_str, "%b %d %H:%M")
                            mtime = mtime.replace(year=datetime.now().year)
                        except ValueError:
                            try:
                                mtime = datetime.strptime(date_str, "%b %d %Y")
                            except ValueError:
                                mtime = datetime.now()
                    except (ValueError, IndexError):
                        mtime = datetime.now()
                # Normalize child paths correctly: force / for SFTP
                if self.protocol == "sftp":
                    child_path = path.rstrip('/') + '/' + name.lstrip('/')
                else:
                    child_path = os.path.join(path.rstrip('/'), name).rstrip('/')
                if self.protocol == "sftp" and not child_path.startswith("/"):
                    child_path = "/" + child_path
                item_node = QStandardItem(name)
                item_node.setData(child_path, Qt.UserRole)
                item_node.setData(is_dir, Qt.UserRole + 1)
                item_node.setData(mtime, Qt.UserRole + 2)
                date_item = QStandardItem(mtime.strftime("%Y-%m-%d %H:%M") if mtime else "")
                parent_item.appendRow([item_node, date_item])
                if is_dir:
                    # Add dummy child to enable expander
                    dummy = QStandardItem("")
                    item_node.appendRow([dummy, QStandardItem("")])
            # Apply sorting
            if self.sort_by == "name":
                self.model.sort(0, Qt.AscendingOrder)
            else:  # date
                self.model.sort(1, Qt.DescendingOrder)
            # Set column widths
            self.tree.header().setStretchLastSection(False)  # Prevent last column stretch
            self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)  # Name column stretches
            self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)  # Modified column resizable
            self.tree.setColumnWidth(1, 150)  # Modified column width
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to list directory {path}: {str(e)}")
            self.reject()

    def on_double_click(self, index):
        item = self.model.itemFromIndex(index)
        if not item:
            return
        is_dir = item.data(Qt.UserRole + 1)
        if is_dir:
            path = item.data(Qt.UserRole)
            if not path:
                return
            # Verify directory exists
            try:
                if self.protocol == "sftp":
                    self.client.stat(path)
                else:  # ftp
                    self.client.cwd(path)
                self.current_path = path
                self.path_edit.setText(self.to_display_path(path))
                root_path = "/" if self.protocol == "sftp" else "C:/"
                self.up_button.setEnabled(self.current_path != root_path)
                # Clear and populate only this item's children for smoother navigation
                if item.rowCount() > 0:
                    item.removeRows(0, item.rowCount())
                self.tree.clearSelection()  # Prevent selection on double-click
                self.populate_file_system(path, parent_item=item)
                self.tree.setExpanded(index, True)  # Expand the clicked folder
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Directory does not exist: {path}")
        else:
            return

    def on_expanded(self, index):
        item = self.model.itemFromIndex(index)
        if not item:
            return
        is_dir = item.data(Qt.UserRole + 1)
        if is_dir:
            path = item.data(Qt.UserRole)
            if not path:
                return
            # Verify directory exists
            try:
                if self.protocol == "sftp":
                    self.client.stat(path)
                else:  # ftp
                    self.client.cwd(path)
                    self.client.cwd(self.current_path)  # Return to original path
                # Clear dummy child and populate real contents for this item only
                if item.rowCount() > 0:
                    item.removeRows(0, item.rowCount())
                self.populate_file_system(path, parent_item=item)
                # Update current_path and display if this is the new focus
                self.current_path = path
                self.path_edit.setText(self.to_display_path(path))
                root_path = "/" if self.protocol == "sftp" else "C:/"
                self.up_button.setEnabled(self.current_path != root_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Directory does not exist: {path}")
                if item.rowCount() == 0:
                    dummy = QStandardItem("")
                    item.appendRow(dummy)  # Restore dummy child

    def navigate_up(self):
        root_path = "/" if self.protocol == "sftp" else "C:/"
        if self.current_path == root_path:
            return
        parent_path = os.path.dirname(self.current_path).replace("\\", "/")
        if not parent_path or parent_path == ".":
            parent_path = root_path  # Ensure we don't go below root
        try:
            if self.protocol == "sftp":
                self.client.stat(parent_path)
            else:  # ftp
                self.client.cwd(parent_path)
            self.current_path = parent_path
            self.path_edit.setText(self.to_display_path(parent_path))
            self.up_button.setEnabled(self.current_path != root_path)
            self.populate_file_system(self.current_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to navigate up to {parent_path}: {str(e)}")

    def navigate_to_path(self):
        path = self.path_edit.text().strip().replace("\\", "/")
        if not path:
            return
        try:
            if self.protocol == "sftp":
                self.client.stat(path)
            else:  # ftp
                self.client.cwd(path)
            self.current_path = path
            self.path_edit.setText(self.to_display_path(path))
            root_path = "C:/" if self.protocol == "ftp" else "/"
            self.up_button.setEnabled(self.current_path != root_path)
            self.populate_file_system(self.current_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid directory: {path}")

    def get_selected_path(self):
        selected_indexes = self.tree.selectedIndexes()
        if not selected_indexes:
            return self.current_path, ""
        selected_items = []
        for index in selected_indexes:
            item = self.model.itemFromIndex(index)
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

    def reject(self):
        if self.client:
            if self.protocol == "sftp":
                self.client.close()
            else:
                self.client.quit()
            self.client = None
        super().reject()



#### -------------------------------------------------------------------------------------------------------
#### -------------------------------------------------------------------------------------------------------



class MainWindow(QMainWindow):
    def __init__(self, sid=None):
        super().__init__()
        self.setWindowTitle("Log Downloader")
        
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
                    "incremental_period": "6am daily"
                }
            }
      
        self.siddb = load_siddb(self.config["siddb_path"])

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
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2E2E2E;  /* Dark charcoal */
                border: 1px solid #666666;  /* Muted gray border for window */
            }
            QLabel {
                color: #E0E0E0;  /* Off-white text */
            }
            QLineEdit, QComboBox, QDateEdit {
                background-color: #4A4A4A;  /* Darker frame */
                color: #E0E0E0;  /* Off-white text */
                border: 1px solid #666666;  /* Muted gray border */
                border-radius: 4px;  /* Subtle rounding */
                padding: 3px;
            }
            QComboBox QLineEdit {
                background-color: #4A4A4A;  /* Ensure editable combo matches */
                color: #E0E0E0;
                border: none;  /* Remove inner border */
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 1px solid #4FC3F7;  /* Light blue focus */
                background-color: #555555;  /* Slightly lighter on focus */
            }
            QCalendarWidget {
                background-color: #2E2E2E;  /* Match main background */
                color: #E0E0E0;  /* Off-white text */
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #4A4A4A;  /* Match input background */
                color: #E0E0E0;  /* Off-white header text */
                padding: 2px;
            }
            QCalendarWidget QAbstractItemView::item {
                background-color: #4A4A4A;  /* Match input background */
                color: #E0E0E0;  /* Off-white text for all days */
                selection-background-color: #4FC3F7;  /* Light blue selection */
                selection-color: #2E2E2E;  /* Dark text on selection */
            }
            QComboBox QAbstractItemView {
                background-color: #4A4A4A;  /* Match combo box dropdown background */
                color: #E0E0E0;  /* Off-white text */
                selection-background-color: #4FC3F7;  /* Light blue selection */
                selection-color: #2E2E2E;  /* Dark text on selection */
            }
            QPushButton {
                background-color: #4A4A4A;  /* Darker frame */
                color: #E0E0E0;  /* Off-white text */
                border: 1px solid #666666;  /* Muted gray border */
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4FC3F7;  /* Light blue hover */
                color: #2E2E2E;  /* Dark text on hover */
            }
            QPushButton:pressed {
                background-color: #0288D1;  /* Darker blue when pressed */
            }
            QMessageBox, QDialog {
                background-color: #2E2E2E;  /* Match main background */
            }
            QMessageBox QLabel, QDialog QLabel {
                color: #E0E0E0;  /* Off-white text */
            }
            QCheckBox {
                color: #E0E0E0;  /* Off-white text */
            }
        """)

        # Center on main screen
        self.center_on_screen()

        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setSpacing(10)  # Increase row spacing
        form_layout.setLabelAlignment(Qt.AlignRight)  # Align labels close to widgets

        # SID/Site/SIDDB-Path Row
        self.sid_combo = QComboBox()
        self.populate_sid_combo("site_name")
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
        form_layout.addRow("SID/Site:", sid_hbox)

        # IP Type, IP, Protocol, Username, and Password Row
        ip_hbox = QHBoxLayout()
        ip_hbox.addSpacing(25)
        ip_hbox.setSpacing(5)  # Reduce spacing for tight label-widget pairing
        self.ip_type_combo = QComboBox()
        self.ip_type_combo.addItems(["sp_ip", "host_ip", "display_ip"])  # Exclude Custom User initially
        self.ip_type_combo.setFixedWidth(90)
        ip_hbox.addWidget(QLabel("IP/User Type:"))
        ip_hbox.addWidget(self.ip_type_combo)
        self.ip_edit = QLineEdit()
        self.ip_edit.setFixedWidth(120)  # Size for IP address
        self.ip_edit.setEnabled(True)  # Always editable
        ip_hbox.addWidget(QLabel("IP:"))
        ip_hbox.addWidget(self.ip_edit)
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["sftp", "ftp"])
        ip_hbox.addWidget(QLabel("Protocol:"))
        ip_hbox.addWidget(self.protocol_combo)
        ip_hbox.addSpacing(30)

        # Username and Password section
        self.username_edit = QLineEdit()
        self.username_edit.setFixedWidth(150)  
        self.username_edit.textChanged.connect(self.update_ip_type)
        ip_hbox.addWidget(QLabel("Custom Username:"))
        ip_hbox.addWidget(self.username_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setFixedWidth(150)  
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.textChanged.connect(self.update_ip_type)
        ip_hbox.addWidget(QLabel("Custom Password:"))
        ip_hbox.addWidget(self.password_edit)
        ip_hbox.addStretch(2)
        form_layout.addRow(ip_hbox)

        self.ip_manually_edited = False
        self.ip_edit.textChanged.connect(self.handle_ip_change)
        self.ip_type_combo.currentIndexChanged.connect(self.update_ip)
        self.sid_combo.currentIndexChanged.connect(self.update_ip)
        
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
        form_layout.addRow("Remote Location:", remote_hbox)

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
        form_layout.addRow("File Filter:", filter_hbox)

        # Date filter Row
        self.date_filter_widget = QWidget()
        date_filter_layout = QHBoxLayout()
        date_filter_layout.addSpacing(100) 
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
        date_filter_layout.addWidget(QLabel("Range from End:"))
        self.quick_date_combo = QComboBox()
        self.quick_date_combo.setFixedWidth(100)
        self.quick_date_combo.addItems(["", "1 day", "3 days", "1 week", "1 month", "1 year", "5 years"])
        self.quick_date_combo.currentTextChanged.connect(self.on_quick_date_select)
        date_filter_layout.addWidget(self.quick_date_combo)
        set_end_today_btn = QPushButton("Set End to Today")
        set_end_today_btn.clicked.connect(self.set_end_to_today)
        set_end_today_btn.setFixedWidth(108)
        date_filter_layout.addWidget(set_end_today_btn)
        date_filter_layout.addStretch(2)
        self.date_filter_widget.setLayout(date_filter_layout)
        form_layout.addRow(self.date_filter_widget)
        
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
        form_layout.addRow("Local Location:", local_hbox)

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
        self.download_btn.clicked.connect(self.download)
        self.download_btn.setMinimumWidth(400)  # Larger button
        self.download_hbox.addWidget(self.timed_check)
        self.download_hbox.addWidget(self.period_combo)
        self.download_hbox.addWidget(self.overwrite_check)
        self.download_hbox.addWidget(self.download_btn)
        self.download_hbox.addStretch(2)
        form_layout.addRow(self.download_hbox)

        #Status Update Row
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)

        layout.addLayout(form_layout)
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.is_downloading = False  # Track active download
        self.inc_timer = QTimer()
        self.inc_timer.timeout.connect(self.inc_download)
        self.current_sort = "site_name"
        self.ip_manually_edited = False
        self.cancel_event = asyncio.Event()
        # Load last selections only if running as main script
        if __name__ == "__main__":
            last = self.config.get("last_selections", {})
            last_sid = last.get("sid", "")
            self.sid_combo.blockSignals(True)
            if last_sid in self.siddb or last_sid == "Custom IP":
                display_text = self.siddb.get(last_sid, {}).get("site_name", "Unknown") + f" ({last_sid})" if last_sid != "Custom IP" else "Custom IP"
                self.sid_combo.setCurrentText(display_text)
            self.sid_combo.blockSignals(False)
            self.ip_type_combo.blockSignals(True)
            self.ip_type_combo.setCurrentText(last.get("ip_type", "sp_ip"))
            self.ip_type_combo.blockSignals(False)
            self.ip_edit.blockSignals(True)
            self.ip_edit.setText(last.get("ip", ""))
            self.ip_edit.blockSignals(False)
            self.username_edit.setText(last.get("username", ""))
            self.password_edit.setText(last.get("password", ""))
            self.remote_loc_combo.setCurrentText(last.get("remote_loc", ""))
            self.local_loc_combo.setCurrentText(last.get("local_loc", os.getcwd()))
            self.filter_combo.setCurrentText(last.get("file_filter", ""))
            self.protocol_combo.setCurrentText(last.get("protocol", "sftp"))
            self.date_filter_var.setChecked(last.get("date_filter_enabled", False))
            self.start_date_edit.setDate(QDate.fromString(last.get("start_date", ""), 'yyyy-MM-dd'))
            self.end_date_edit.setDate(QDate.fromString(last.get("end_date", ""), 'yyyy-MM-dd'))
            self.quick_date_combo.setCurrentText(last.get("quick_date", ""))
            self.overwrite_check.setChecked(last.get("incremental_download", False))
            self.timed_check.setChecked(last.get("timed_download", False))
            self.period_combo.setCurrentText(last.get("incremental_period", "6am daily"))
            # Update IP after setting all selections
            self.update_ip()

        if len(sys.argv) > 1 and sys.argv[1] == "use_current_dat":
            sid = self.get_current_dat_sid()
            index = self.sid_combo.findData(sid)
            if index >= 0:
                self.sid_combo.blockSignals(True)
                self.sid_combo.setCurrentIndex(index)
                self.sid_combo.blockSignals(False)
                self.update_ip()
            else:
                self.update_status(f"SID {sid} not found in sid_combo, using default")
                sid = "000"

    def center_on_screen(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 3, (screen.height() - size.height()) // 2)


# SID/SITE ROW FUNCTIONS ----------------------------------------------------------------------------------------------

    def get_current_dat_sid(self):
        """Get the sid from current.dat."""
        try:
            with open(DEFAULT_CURRENTDB_PATH, 'r') as f:
                for line in f:
                    if line.startswith("SID="):
                        return line.strip().split('=', 1)[1]
            return "000"
        except Exception as e:
            print(f"Error reading sid from current.dat: {str(e)}")
            return "000"

    def populate_sid_combo(self, sort_by):
        self.sid_combo.clear()
        items = []
        for sid, entry in self.siddb.items():
            site_name = entry.get("site_name", "Unknown")
            items.append((f"{site_name} ({sid})", sid))
        if sort_by == "site_name":
            items.sort(key=lambda x: x[0].lower())
        else:
            items.sort(key=lambda x: x[1])
        for display, sid in items:
            self.sid_combo.addItem(display, sid)
        self.sid_combo.addItem("Custom IP", "Custom IP")

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


# IP/USER TYPE ROW FUNCITONS----------------------------------------------------------------------

    def update_ip(self):
        try:
            sid = self.sid_combo.currentData()
            self.refresh_remote_loc_combo()
            if sid == "Custom IP":
                return
            # Reset ip_manually_edited when a new SID is selected
            if self.ip_manually_edited and sid in self.siddb:
                self.ip_manually_edited = False
            entry = self.siddb.get(sid, {})
            # Include Custom User only if username/password is set
            available_ip_types = [t for t in ["sp_ip", "host_ip", "display_ip"] if entry.get(t, [])]
            if self.username_edit.text().strip() or self.password_edit.text().strip():
                available_ip_types.append("Custom User")
            # Update ip_type_combo with signals blocked to prevent loops
            current_ip_type = self.ip_type_combo.currentText()
            self.ip_type_combo.blockSignals(True)
            self.ip_type_combo.clear()
            self.ip_type_combo.addItems(available_ip_types)
            # Always respect user selection if valid
            if current_ip_type in available_ip_types:
                self.ip_type_combo.setCurrentText(current_ip_type)
            elif "sp_ip" in available_ip_types:
                self.ip_type_combo.setCurrentText("sp_ip")
            elif available_ip_types:
                self.ip_type_combo.setCurrentText(available_ip_types[0])
            else:
                self.ip_type_combo.setCurrentText("")
            self.ip_type_combo.blockSignals(False)
            ip_type = self.ip_type_combo.currentText()
            if ip_type == "Custom User":
                return
            ips = entry.get(ip_type, [])
            if not self.ip_manually_edited and ips:
                self.ip_edit.setText(ips[0])
                self.ip_edit.repaint()  # Force UI update
                self.update_status(f"IP updated for {sid}/{ip_type}")
            elif not ips:
                self.ip_edit.setText("")
                self.ip_edit.repaint()  # Force UI update
                self.update_status(f"No IP found for {sid}/{ip_type}")
        except Exception as e:
            self.update_status(f"Error updating IP: {str(e)}")

    def reset_ip_type(self):
        try:
            current = self.ip_type_combo.currentText()
            if current not in ["sp_ip", "host_ip", "display_ip", "Custom User"]:
                self.ip_type_combo.setCurrentText("sp_ip")
        except Exception as e:
            self.update_status(f"Error resetting IP type: {str(e)}")

    def handle_ip_change(self):
        try:
            if self.ip_edit.text().strip() and not self.ip_edit.hasFocus():
                return
            if self.ip_edit.text().strip():
                self.sid_combo.blockSignals(True)
                self.sid_combo.setCurrentText("Custom IP")
                self.sid_combo.blockSignals(False)
                self.ip_manually_edited = True
                self.update_status("Custom IP selected")
        except Exception as e:
            self.update_status(f"Error handling IP change: {str(e)}")

    def update_ip_type(self):
        try:
            if hasattr(self, "username_edit") and hasattr(self, "password_edit") and (self.username_edit.text().strip() or self.password_edit.text().strip()):
                self.ip_type_combo.blockSignals(True)
                if "Custom User" not in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                    self.ip_type_combo.addItem("Custom User")
                self.ip_type_combo.setCurrentText("Custom User")
                self.ip_type_combo.blockSignals(False)
                self.update_status("Using custom username/password")
                print("DEBUG: Set ip_type_combo to Custom User due to username/password input")
            else:
                self.ip_type_combo.blockSignals(True)
                if "Custom User" in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                    self.ip_type_combo.removeItem(self.ip_type_combo.findText("Custom User"))
                # Add MR_V3.x+ for Custom IP
                sid = self.sid_combo.currentData()
                if sid == "Custom IP":
                    if "MR_V3.x+" not in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                        self.ip_type_combo.addItem("MR_V3.x+")
                else:
                    if "MR_V3.x+" in [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]:
                        self.ip_type_combo.removeItem(self.ip_type_combo.findText("MR_V3.x+"))
                # Explicitly set to sp_ip if available
                available_ip_types = [self.ip_type_combo.itemText(i) for i in range(self.ip_type_combo.count())]
                if "sp_ip" in available_ip_types:
                    self.ip_type_combo.setCurrentText("sp_ip")
                elif available_ip_types:
                    self.ip_type_combo.setCurrentText(available_ip_types[0])
                else:
                    self.ip_type_combo.setCurrentText("")
                self.ip_type_combo.blockSignals(False)
                self.update_ip()  # Trigger IP update after reverting
                self.update_status("Using default credentials for IP type")
                print("DEBUG: Reverted ip_type_combo to default credentials")
            self.ip_edit.setEnabled(True)  # Ensure IP field is always editable
        except Exception as e:
            self.update_status(f"Error updating credentials: {str(e)}")


# REMOTE LOCATION ROW FUNCITONS ---------------------------------------------------------------------

    def get_default_remote_locs(self):
        # Get the current SID from sid_combo, fallback to '000' if none selected
        sid = self.sid_combo.currentData()
        if not sid or sid == "Custom IP":
                self.update_status("Enter a valid SID in _tui folder path")
                sid = "Enter_SID"
    # HERE IS THE NEW REMOTE LOCS SHORTCUT LIST
        return [
            f"C:/InnerVision.dir/M-POWER/{sid}-000/_tui.dir",
            "C:/ProgramData/Helium_Pressure_Monitor"
        ]

    def refresh_remote_loc_combo(self):
        # Store current selection if needed
        current_text = self.remote_loc_combo.currentText()
        # Clear and repopulate remote_loc_combo with updated paths
        self.remote_loc_combo.clear()
        self.remote_loc_combo.addItems(self.config.get("remote_locations", []) + self.get_default_remote_locs())
        # Optionally restore previous selection if it still exists
        index = self.remote_loc_combo.findText(current_text)
        if index >= 0:
            self.remote_loc_combo.setCurrentIndex(index)

    def browse_remote(self):
        """Browse remote file system and update remote_loc_combo and filter_combo."""
        ip = self.ip_edit.text().strip()
        protocol = self.protocol_combo.currentText()
        username = ""
        password = ""
        sid = self.sid_combo.currentText().split(" (")[-1].rstrip(")") if "(" in self.sid_combo.currentText() else self.sid_combo.currentText()
        ip_type = self.ip_type_combo.currentText()

        # Check if username_edit and password_edit exist
        if not hasattr(self, "username_edit") or not hasattr(self, "password_edit"):
            QMessageBox.critical(self, "Error", "Username or password field not initialized")
            return

        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        # Use siddb credentials if username/password are empty and not Custom IP
        if not username and not password and (sid == "Custom IP" or sid in self.siddb):
            entry = {}  # Empty entry for Custom IP
            credentials = get_credentials(ip_type, entry)
            if credentials:
                username, password = credentials[0]
            else:
                # Prompt for credentials if CREDENTIALS_MAP has no match
                username, ok = QInputDialog.getText(self, "Credentials", "Enter username:", QLineEdit.Normal, "")
                if not ok or not username:
                    self.update_status("Username required for Custom IP")
                    return
                password, ok = QInputDialog.getText(self, "Credentials", "Enter password:", QLineEdit.Password, "")
                if not ok or not password:
                    self.update_status("Password required for Custom IP")
                    return

        if not ip:
            QMessageBox.critical(self, "Error", "Please enter an IP address")
            return

        if not username or not password:
            QMessageBox.critical(self, "Error", "Username or password cannot be empty")
            return

        # Get initial path from remote_loc_combo
        initial_path = self.remote_loc_combo.currentText().strip()
        if not initial_path:
            initial_path = "C:\\" if protocol == "ftp" else "/"

        # Create and show the remote file dialog with initial path
        dialog = RemoteFileDialog(self, ip, protocol, username, password, initial_path)
        dialog.setStyleSheet(self.styleSheet())  # Apply main window stylesheet
        if dialog.exec_():
            self.remote_loc_combo.setCurrentText(dialog.selected_path)
            if dialog.selected_files:
                self.filter_combo.setCurrentText(dialog.selected_files)
            # Add to remote_loc_combo if not already present
            if dialog.selected_path and dialog.selected_path not in [self.remote_loc_combo.itemText(i) for i in range(self.remote_loc_combo.count())]:
                self.remote_loc_combo.addItem(dialog.selected_path)

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
            self.update_status("Cannot delete hardcoded remote location preset")
            return
        if current in self.config["remote_locations"]:
            self.config["remote_locations"].remove(current)
            self.remote_loc_combo.clear()
            self.remote_loc_combo.addItems(self.config["remote_locations"] + self.get_default_remote_locs())
            self.remote_loc_combo.setCurrentText("")
            if __name__ == "__main__":
                save_config(self.config)
            self.update_status(f"Deleted remote location preset: {current}")


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

    def on_date_change(self):
        try:
            start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
            end_date = self.end_date_edit.date().toString('yyyy-MM-dd')
            # Validate dates
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                self.quick_date_combo.blockSignals(True)
                self.quick_date_combo.setCurrentText("")  # Clear preset on manual edit
                self.quick_date_combo.blockSignals(False)
            except ValueError:
                self.update_status("Invalid date format")
        except Exception as e:
            self.update_status(f"Error validating dates: {str(e)}")

    def on_quick_date_select(self, text):
        try:
            if text and text != "":
                # Use end_date_edit as reference, fallback to today
                end_date = self.end_date_edit.date()
                if not end_date.isValid():
                    end_date = QDate.currentDate()
                    print(f"DEBUG: Using end_date_edit as reference: {end_date.toString('yyyy-MM-dd')}")
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
                    return
                self.start_date_edit.setDate(start_date)
                self.end_date_edit.setDate(end_date)
                self.date_filter_var.setChecked(True)
            # Do not clear dates if text is empty, preserve existing values
        except Exception as e:
            self.update_status(f"Error setting date preset: {str(e)}")

    def set_end_to_today(self):
        try:
            self.end_date_edit.setDate(QDate.currentDate())
            self.date_filter_var.setChecked(True)
            self.on_date_change()  # Trigger date validation
        except Exception as e:
            self.update_status(f"Error setting end date: {str(e)}")

    def build_filter_string(self):
        try:
            filter_str = self.filter_combo.currentText().strip()
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
            return self.filter_combo.currentText().strip()


# LOCAL LOCATION ROW FUNCTIONS ----------------------------------------------------------------------------------------------

    def browse_local(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Local Directory", self.local_loc_combo.currentText())
        if folder:
            self.local_loc_combo.setCurrentText(folder)

    def create_folder(self):
        try:
            sid = self.sid_combo.currentData()
            if not sid or sid == "Custom IP":
                self.update_status("Enter a valid SID in folder path")
                sid = "000"
            now = datetime.now().strftime("%Y.%m.%d")
            folder_name = f"{now}__SID-{sid} ~  ~"
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

    def download(self):
        if self.is_downloading or self.inc_timer.isActive():
            self.is_downloading = False  # Signal to abort download
            self.cancel_event.set()  # Signal cancellation
            if self.inc_timer.isActive():
                self.inc_timer.stop()
                self.download_btn.setText("Download")
                self.update_status("Timed download stopped")
            else:
                self.update_status("Download aborted")
            return

        try:
            # Handle custom period input for timed download before starting
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

            self.is_downloading = True
            self.download_btn.setText("Abort Download")
            self.update_status("Download started")
            self.cancel_event.clear()  # Reset cancellation
            # Update downloader settings instead of creating new instance
            self.downloader.sid = self.sid_combo.currentData()
            self.downloader.file_filter = self.build_filter_string()
            self.downloader.remote_loc = self.remote_loc_combo.currentText()
            self.downloader.local_loc = self.local_loc_combo.currentText()
            self.downloader.protocol = self.protocol_combo.currentText()
            self.downloader.set_ip(self.ip_edit.text(), self.ip_type_combo.currentText().split(" (")[0])
            if self.username_edit.text().strip() and self.password_edit.text().strip():
                self.downloader.set_credentials(self.username_edit.text(), self.password_edit.text())
            num_files, total_size_bytes, total_download_time = self.downloader.download_logs(
                incremental=self.overwrite_check.isChecked(),
                status_callback=self.update_status,
                cancel_event=self.cancel_event
            )
            throughput = total_size_bytes / total_download_time / 1024  # KB/s
            unit = "KB/s"
            if throughput >= 1024:
                throughput /= 1024  # Convert to MB/s
                unit = "MB/s"
            # Format elapsed time as hr(s), min(s), sec(s)
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
            if seconds > 0 or not time_parts:  # Include seconds if no other units
                time_parts.append(f"{seconds:.2f} sec(s)")
            time_str = ", ".join(time_parts)
            self.update_status(f"Download finished. Downloaded {num_files} files ({self.format_size(total_size_bytes)}) at {throughput:.2f} {unit} in {time_str}.")
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
                    self.inc_timer.start()
                    self.download_btn.setText("Stop Timed Download")
                    self.update_status("Timed download started")
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
        finally:
            self.is_downloading = False
            self.download_btn.setText("Download")
            QApplication.processEvents()  # Update UI

    def inc_download(self):
        if not self.is_downloading:
            try:
                self.is_downloading = True
                self.download_btn.setText("Abort Download")
                self.update_status("Timed download started")
                QApplication.processEvents()  # Update UI
                # Update downloader settings instead of creating new instance
                self.downloader.sid = self.sid_combo.currentData()
                self.downloader.file_filter = self.build_filter_string()
                self.downloader.remote_loc = self.remote_loc_combo.currentText()
                self.downloader.local_loc = self.local_loc_combo.currentText()
                self.downloader.protocol = self.protocol_combo.currentText()
                self.downloader.set_ip(self.ip_edit.text(), self.ip_type_combo.currentText().split(" (")[0])
                if self.username_edit.text().strip() and self.password_edit.text().strip():
                    self.downloader.set_credentials(self.username_edit.text(), self.password_edit.text())
                num_files, total_size_bytes, total_download_time = self.downloader.download_logs(
                    incremental=self.overwrite_check.isChecked(),
                    period=self.period_combo.currentText(),
                    status_callback=self.update_status
                )
                throughput = total_size_bytes / total_download_time / 1024  # KB/s
                unit = "KB/s"
                if throughput >= 1024:
                    throughput /= 1024  # Convert to MB/s
                    unit = "MB/s"
                # Format elapsed time as hr(s), min(s), sec(s)
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
                if seconds > 0 or not time_parts:  # Include seconds if no other units
                    time_parts.append(f"{seconds:.2f} sec(s)")
                time_str = ", ".join(time_parts)
                self.update_status(f"Download finished. Downloaded test {num_files} files ({self.format_size(total_size_bytes)}) at {throughput:.2f} {unit} in {time_str}.")
            except Exception as e:
                self.update_status(f"Error: {str(e)}")
            finally:
                self.is_downloading = False
                if not self.inc_timer.isActive():
                    self.download_btn.setText("Download")
                else:
                    self.download_btn.setText("Stop Timed Download")
                QApplication.processEvents()  # Update UI


    def update_status(self, message):
        self.status_label.setText(message)
#        current_width = self.width() # Captures width before resize. 
#        self.adjustSize() # Resizes if status message wraps.
#        self.resize(current_width, self.sizeHint().height()) # Keeps current width but causes flashing. 

    def closeEvent(self, event):
        # Save config only if running as main script
        if __name__ == "__main__":
            self.config["last_selections"] = {
                "sid": self.sid_combo.currentData() or "",
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
                "incremental_period": self.period_combo.currentText()
            }
            save_config(self.config)
        if self.inc_timer.isActive():
            self.inc_timer.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())