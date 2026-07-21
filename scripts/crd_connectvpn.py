# ------------------------------------------------------------------------
"""
crd_connectvpn.py (ew)
Connect to mySQL and SP for site information
Version 1.20 Updated 07/10/26
"""
# ------------------------------------------------------------------------
import os
import mysql.connector
import paramiko
import json
import sys
import logging
import socket
import configparser
import ftplib
import io
import re
from PyQt5.QtWidgets import QMessageBox, QLineEdit, QLabel, QApplication, QDialog, QVBoxLayout, QProgressBar, QSpacerItem, QSizePolicy, QPushButton
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from crd_embedded import CustomMessageBox, Paths, CRDLogger
from cryptography.fernet import Fernet
from crd_sid_manager import SIDDatabase
# ------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, '..', 'scripts'))
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
def decrypt_file(enc_file_path, key_file_path, is_json=True):
    tag = "DECRYPT"
    try:
        with open(key_file_path, 'rb') as key_file:
            key = key_file.read()
        fernet = Fernet(key)
        with open(enc_file_path, 'rb') as enc_file:
            encrypted_data = enc_file.read()
        decrypted_data = fernet.decrypt(encrypted_data).decode('utf-8')
        if is_json:
            return json.loads(decrypted_data)
        else:
            config = {}
            for line in decrypted_data.splitlines():
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
            return config
    except Exception as e:
        logger.error(f"[CONNECTVPN] Failed to Decrypt {enc_file_path}: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def read_credentials(ini_data=None):
    tag = "CREDENTIALS"
    enc_file_path = os.path.join(script_dir, '..', 'config', 'user.enc')
    key_file_path = os.path.join(script_dir, '..', 'config', 'user.key')
    
    credential_sets = []
    
    if os.path.exists(enc_file_path) and os.path.exists(key_file_path):
        logger.info(f"[CONNECTVPN] Loading Credentials from {enc_file_path}", extra={"tag": tag})
        creds_dict = decrypt_file(enc_file_path, key_file_path, is_json=True)
        if creds_dict:
            if "SP_WIN10" in creds_dict:
                credential_sets.append({
                    "spuser": creds_dict["SP_WIN10"].get("sp_user", "IV_Service_User"),
                    "sppass": creds_dict["SP_WIN10"].get("sp_pass", "SU_InnerVision2020"),
                    "port": creds_dict["SP_WIN10"].get("host_port", "22"),
                    "source": "SFTP",
                    "protocol": "SFTP"
                })
            if "SP_WIN7" in creds_dict and "credentials" in creds_dict["SP_WIN7"]:
                credential_sets.append({
                    "spuser": creds_dict["SP_WIN7"]["credentials"].get("host_user", "COM_SP"),
                    "sppass": creds_dict["SP_WIN7"]["credentials"].get("host_pass", "IV_TAC_SP"),
                    "port": creds_dict["SP_WIN7"]["credentials"].get("host_port", "21"),
                    "source": "FTP",
                    "protocol": "FTP"
                })
    
    if not credential_sets:
        credential_sets = [
            {"spuser": "IV_Service_User", "sppass": "SU_InnerVision2020", "port": "22", "source": "SFTP", "protocol": "SFTP"},
            {"spuser": "COM_SP", "sppass": "IV_TAC_SP", "port": "21", "source": "FTP", "protocol": "FTP"}
        ]
    return credential_sets
# ------------------------------------------------------------------------
def write_current_dat(data):
    tag = "CURRENT_DAT"
    current_file_path = os.path.join(script_dir, '..', 'config', 'current.dat')
    try:
        with open(current_file_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"[CONNECTVPN] Failed to write to {current_file_path}: {e}", extra={"tag": tag})
# ------------------------------------------------------------------------
def establish_ssh_connection(spip, remote_path, creds_dict, firewall_type=''):
    tag = "CONNECTION"
    
# EDGE-TINA
    if firewall_type.upper() == 'EDGE-TINA':
        logger.info(f"[CONNECTVPN] EDGE-TINA detected - Skipping SFTP and FTP for {spip}", extra={"tag": tag})
        return None
    
# SSH/FTP
    sftp_creds = [c for c in creds_dict if c["protocol"] == "SFTP"]
    ftp_creds = [c for c in creds_dict if c["protocol"] == "FTP"]
    connection_order = sftp_creds + ftp_creds
    
    for credentials in connection_order:
        username = credentials["spuser"]
        password = credentials["sppass"]
        protocol = credentials["protocol"]
        port = int(credentials.get("port", 22 if protocol == "SFTP" else 21))
        source = credentials["source"]
       
        logger.info(f"[CONNECTVPN]  {protocol} Connection ({source}) to {spip}:{port} (timeout 5s)", extra={"tag": tag})
       
        if protocol == "SFTP":
            transport = None
            sftp = None
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                socket.setdefaulttimeout(5)
                transport = paramiko.Transport((spip, port))
                transport.connect(username=username, password=password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                logger.info(f"[CONNECTVPN] SFTP Connection Established to {spip}:{port}", extra={"tag": tag})
               
                dir_path = os.path.dirname(remote_path).replace('\\', '/')
                dir_contents = sftp.listdir(dir_path)
                if "spsite.ini" not in [f.lower() for f in dir_contents]:
                    logger.error(f"[CONNECTVPN] File {remote_path} not found in directory {dir_path}", extra={"tag": tag})
                    raise FileNotFoundError(f"File {remote_path} not found")
               
                with sftp.open(remote_path, 'r') as remote_file:
                    ini_output = remote_file.read().decode('utf-8').strip()
                if not ini_output:
                    logger.error(f"[CONNECTVPN] Empty file: {remote_path}", extra={"tag": tag})
                    raise ValueError(f"Empty file: {remote_path}")
                return ini_output
               
            except (paramiko.SSHException, socket.timeout, paramiko.AuthenticationException, OSError) as sftp_error:
                logger.warning(f"[CONNECTVPN] SFTP Failed {spip}:{port}: {sftp_error}", extra={"tag": tag})
                try:
                    client.connect(spip, username=username, password=password, port=port, timeout=5)
                    check_command = f"dir \"{os.path.dirname(remote_path)}\""
                    stdin, stdout, stderr = client.exec_command(check_command, timeout=5)
                    check_output = stdout.read().decode('utf-8').strip()
                    check_error = stderr.read().decode('utf-8').strip()
                    if check_error or "spsite.ini" not in check_output.lower():
                        raise FileNotFoundError(f"File {remote_path} not found")
                   
                    command = f"type \"{remote_path}\""
                    stdin, stdout, stderr = client.exec_command(command, timeout=5)
                    ini_output = stdout.read().decode('utf-8').strip()
                    if ini_output:
                        logger.info(f"[CONNECTVPN] SINI Data Received via SSH exec", extra={"tag": tag})
                        return ini_output
                except Exception as ssh_error:
                    logger.warning(f"[CONNECTVPN] SSH Fallback Failed: {ssh_error}", extra={"tag": tag})
                finally:
                    if sftp:
                        sftp.close()
                    if transport:
                        transport.close()
                    client.close()
                continue
            finally:
                socket.setdefaulttimeout(None)
               
        elif protocol == "FTP":
            ftp = None
            try:
                ftp = ftplib.FTP(timeout=5)
                ftp.set_pasv(True)
                ftp.connect(spip, port=port)
                ftp.login(user=username, passwd=password)
                logger.info(f"[CONNECTVPN] FTP Connection Established to {spip}:{port}", extra={"tag": tag})
               
                ftp_path = remote_path.replace("C:\\", "").replace("\\", "/")
                ftp_dir = "/".join(ftp_path.split("/")[:-1])
                file_name = ftp_path.split("/")[-1]
                if ftp_dir:
                    ftp.cwd(ftp_dir)
               
                file_content = io.BytesIO()
                ftp.retrbinary(f"RETR {file_name}", file_content.write)
                file_content.seek(0)
                encodings = ['utf-8', 'utf-16', 'latin1']
                for encoding in encodings:
                    try:
                        file_content.seek(0)
                        ini_output = file_content.getvalue().decode(encoding).strip()
                        if ini_output:
                            logger.debug(f"[CONNECTVPN] INI Data Received via FTP", extra={"tag": tag})
                            return ini_output
                    except UnicodeDecodeError:
                        continue
                raise ValueError("Could Not Decode File")
               
            except ftplib.all_errors as ftp_error:
                logger.warning(f"[CONNECTVPN] FTP Failed {spip}:{port}: {ftp_error}", extra={"tag": tag})
                continue
            finally:
                if ftp:
                    try:
                        ftp.quit()
                    except:
                        pass
    logger.error(f"[CONNECTVPN] All Connection Attempts Failed for {spip}", extra={"tag": tag})
    return None
# ------------------------------------------------------------------------
def write_current_dat(data):
    tag = "CURRENT_DAT"
    current_file_path = os.path.join(script_dir, '..', 'config', 'current.dat')
    try:
        with open(current_file_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"[CONNECTVPN] Failed to write to {current_file_path}: {e}", extra={"tag": tag})
# ------------------------------------------------------------------------
# PARSE INI MR ONLY
def parse_ini_data(ini_data, sid=None, existing_modality=None):
    tag = "PARSE"
    try:
        if not ini_data:
            logger.error("[CONNECTVPN] No INI Data Received", extra={"tag": tag})
            return None
        config = configparser.ConfigParser()
        try:
            config.read_string(f"[DEFAULT]\n{ini_data}" if not ini_data.startswith('[') else ini_data)
        except configparser.ParsingError as e:
            logger.error(f"[CONNECTVPN] Failed To Parse INI Data: {e}", extra={"tag": tag})
            return None
        data = {
            "HospName": "",
            "ModalitySystemVersion1": "",
            "MachineName": "",
            "Modality": "MR",
            "ModalityOSVersion": "",
            "RawVersion": ""
        }
        if 'SPSiteInfo' in config.sections():
            data["HospName"] = config.get('SPSiteInfo', 'HospName', fallback=config.get('SPSiteInfo', 'hospname', fallback='')).replace("PreInstall:", "").strip()
        else:
            logger.warning(f"[CONNECTVPN] [SPSiteInfo] section not found", extra={"tag": tag})
        key1 = None
        if 'MR' in config.sections() and config.get('MR', 'KeyMax', fallback='') == '1':
            key1 = config.get('MR', 'Key1', fallback='')
            logger.info(f"[CONNECTVPN] MR Key1 Section: {key1}", extra={"tag": tag})
        if key1 and key1 in config.sections():
            data.update({
                "MachineName": config.get(key1, 'MachineName', fallback=''),
                "Modality": config.get(key1, 'Modality', fallback="MR"),
                "ModalityOSVersion": config.get(key1, 'ModalityOSVersion', fallback=''),
                "ModalitySystemVersion1": config.get(key1, 'ModalitySystemVersion1', fallback=''),
                "RawVersion": config.get(key1, 'ModalitySystemVersion1', fallback=config.get(key1, 'SmVersion', fallback=''))
            })
        else:
            logger.warning(f"[CONNECTVPN] Key1 Section [{key1}] Not Found - falling back to regex", extra={"tag": tag})
            in_mr_section = False
            for line in ini_data.splitlines():
                line = line.strip()
                if re.match(r'\[MR\]', line, re.IGNORECASE):
                    in_mr_section = True
                    continue
                if in_mr_section and re.match(r'\[.*\]', line):
                    in_mr_section = False
                    continue
                if in_mr_section:
                    if re.match(r'Key1\s*=\s*(.+)', line, re.IGNORECASE):
                        key1 = re.match(r'Key1\s*=\s*(.+)', line, re.IGNORECASE).group(1).strip()
                        logger.info(f"[CONNECTVPN] Regex Key1: {key1}", extra={"tag": tag})
            if key1:
                in_key_section = False
                for line in ini_data.splitlines():
                    line = line.strip()
                    if re.match(rf'\[{re.escape(key1)}\]', line, re.IGNORECASE):
                        in_key_section = True
                        continue
                    if in_key_section and re.match(r'\[.*\]', line, re.IGNORECASE):
                        in_key_section = False
                        continue
                    if in_key_section:
                        for field in ['MachineName', 'Modality', 'ModalityOSVersion', 'ModalitySystemVersion1', 'SmVersion']:
                            match = re.match(rf'{field}\s*=\s*(.+)', line, re.IGNORECASE)
                            if match:
                                if field == 'SmVersion':
                                    data["RawVersion"] = match.group(1).strip()
                                else:
                                    data[field] = match.group(1).strip()
        return data
    except Exception as e:
        logger.error(f"[CONNECTVPN] Error Parsing INI Data: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
class LoadingDialog(QDialog):
    def __init__(self, query_thread=None):
        super().__init__()
        self.query_thread = query_thread
        self.setWindowTitle("Loading")
        self.setFixedSize(300, 150)
        dark_style = """
            QDialog {
                background-color: #202020;
            }
            QLabel, QProgressBar, QPushButton {
                color: white;
                font-size: 14px;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                background-color: #222;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: lightgray;
                width: 20px;
                margin: 1px;
            }
            QPushButton {
                background-color: #555;
                border: 1px solid #777;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """
        self.setStyleSheet(dark_style)
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.label = QLabel("Collecting Data From VPN Server")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_operation)
        layout.addWidget(self.cancel_button)
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(layout)
# ------------------------------------------------------------------------
    def set_message(self, message):
        self.label.setText(message)
        QApplication.processEvents()
# ------------------------------------------------------------------------
    def cancel_operation(self):
        tag = "DIALOG"
        logger.info("[CONNECTVPN] Cancel Button Clicked", extra={"tag": tag})
        if self.query_thread and self.query_thread.isRunning():
            logger.info("[CONNECTVPN] Requesting QueryThread Termination", extra={"tag": tag})
            self.query_thread.requestInterruption()
            self.query_thread.wait(1000)
            if self.query_thread.isRunning():
                logger.warning("[CONNECTVPN] QueryThread Did Not Terminate Correctly", extra={"tag": tag})
                self.query_thread.terminate()
                self.query_thread.wait()
        self.reject()
# ------------------------------------------------------------------------
    def closeEvent(self, event):
        self.cancel_operation()
        event.accept()
# ------------------------------------------------------------------------
class QueryThread(QThread):
    update_message = pyqtSignal(str)
    query_finished = pyqtSignal(dict)
    query_failed = pyqtSignal(str)

    def __init__(self, sid, main_app):
        super().__init__()
        self.sid = sid
        self.main_app = main_app
        self.creds_dict = None

    def run(self):
        tag = "QUERY"
        if self.isInterruptionRequested():
            return

        try:
            self.update_message.emit("Collecting Data From VPN Server")
            tams_ips = get_ips(self.sid)
            if not tams_ips:
                self.query_failed.emit(f"No VPN Data Found For SID: {self.sid}")
                return

            firewall_type = tams_ips.get('vpn_type', '')
            port = tams_ips.get('port', '10')

# EDGE-TINA
            if firewall_type.upper() == 'EDGE-TINA':
                sp_ip = f"{self.sid}-IV.edge-vpn.com"
                logger.info(f"[CONNECTVPN] EDGE-TINA Detected - Using Hostname: {sp_ip}", extra={"tag": tag})
            else:
                sp_ip = None
                for key in tams_ips:
                    if key.lower().replace(" ", "") in ['innervisionsp', 'ctinnervisionsp']:
                        sp_ip = tams_ips[key].get('tams_ip', '')
                        logger.info(f"[CONNECTVPN] Found SP Device {key} With IP: {sp_ip}", extra={"tag": tag})
                        break
                if not sp_ip:
                    scan_ip = tams_ips.get('CT Scan', {}).get('tams_ip', '')
                    sm_ip = tams_ips.get('SM', {}).get('tams_ip', '')
                    infinix_ip = tams_ips.get('Infinix DFP', {}).get('tams_ip', '')
                    sp_ip = scan_ip or infinix_ip or sm_ip
                    if not sp_ip:
                        self.query_failed.emit(f"No IP Found for SID: {self.sid}")
                        return

            remote_path = r"C:\InnerVision.dir\Comm.dir\ini.dir\spsite.ini"
            self.creds_dict = read_credentials(ini_data=None)
            self.update_message.emit(f"Trying connection to {sp_ip}")

            ini_output = establish_ssh_connection(
                spip=sp_ip,
                remote_path=remote_path,
                creds_dict=self.creds_dict,
                firewall_type=firewall_type
            )

# current.dat
            if ini_output:
                self.creds_dict = read_credentials(ini_data=ini_output)
                current_data = {
                    "source": self.creds_dict[0]["source"],
                    "spuser": self.creds_dict[0]["spuser"],
                    "port": self.creds_dict[0]["port"],
                    "protocol": self.creds_dict[0]["protocol"],
                    "ini_data": ini_output
                }
                write_current_dat(current_data)

            if not ini_output and firewall_type.upper() != 'EDGE-TINA':
                logger.error(f"[CONNECTVPN] All Connection Attempts Failed for SID {self.sid}", extra={"tag": tag})
                self.query_failed.emit(f"All Connection Attempts Failed for SID {self.sid}")
                return
            ini_data = parse_ini_data(ini_output, sid=self.sid, existing_modality="MR")
            
            if not ini_data:
                logger.info("[CONNECTVPN] No INI Data Parsed - Using defaults", extra={"tag": tag})
                ini_data = {
                    "HospName": "", "ModalitySystemVersion1": "", 
                    "MachineName": "", "Modality": "MR", "RawVersion": ""
                }

            host_ip = tams_ips.get('SM', {}).get('tams_ip', '') or tams_ips.get('Infinix DFP', {}).get('tams_ip', '')

            data = {
                "sp_ip": str(sp_ip),
                "host_ip": str(host_ip) if host_ip else "",
                "TunnelType": str(firewall_type),
                "display_ip": "",
                "HospName": str(ini_data.get("HospName", "")),
                "sw_version": str(ini_data.get("ModalitySystemVersion1", "") or ini_data.get("RawVersion", "")),
                "machine": str(ini_data.get("MachineName", "")),
                "Modality": "MR",
                "sid": str(self.sid),
            }

            logger.info(f"[CONNECTVPN] Query completed successfully for SID {self.sid}", extra={"tag": tag})
            self.query_finished.emit(data)

        except Exception as e:
            logger.error(f"[CONNECTVPN] Query SID {self.sid}: {e}", extra={"tag": tag})
            self.query_failed.emit(f"Query failed: {str(e)}")
# ------------------------------------------------------------------------
def get_ips(sid):
    tag = "DB"
    tams_ips = {}
    connection = None
    cursor = None
    try:
        enc_file_path = os.path.join(script_dir, '..', 'config', 'vpn.enc')
        key_file_path = os.path.join(script_dir, '..', 'config', 'vpn.key')
        if os.path.exists(enc_file_path) and os.path.exists(key_file_path):
            db_config = decrypt_file(enc_file_path, key_file_path, is_json=False)
            if not db_config:
                logger.error(f"[CONNECTVPN] Failed to Decrypt vpn.enc", extra={"tag": tag})
                db_config = {
                    'host': '10.94.100.239',
                    'user': 'vpnscript',
                    'password': '3fi*75Vi)x2p',
                    'database': 'sns'
                }
        logger.debug(f"[CONNECTVPN] Database Config: {db_config}", extra={"tag": tag})
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        sids_to_query = [str(sid), f'9999{sid}' if not str(sid).startswith('9999') else str(sid)]
        query = """
            SELECT snsVpnDevice.device, snsVpnDevice.tams_ip, snsVpnTunnel.vpn_type, snsGlobalSids.sid, sns.snsVpnTui.SPOSName
            FROM snsGlobalSids
            LEFT JOIN snsVpnDevice ON snsGlobalSids.sid_id = snsVpnDevice.sid_id
            LEFT JOIN snsVpnTunnel ON snsGlobalSids.sid_id = snsVpnTunnel.sid_id
            LEFT JOIN sns.snsVpnTui ON snsGlobalSids.sid = sns.snsVpnTui.SID
            WHERE snsGlobalSids.sid IN (%s, %s)
            AND snsVpnDevice.device IN ('SM', 'Infinix DFP', 'InnerVision SP', 'CT Innervision SP')
        """
        cursor.execute(query, sids_to_query)
        results = cursor.fetchall()
        logger.info(f"[CONNECTVPN] Query Results for SID {sid}: {results}", extra={"tag": tag})
        vpn_type = None
        port = "10"
        for device, tams_ip, vt, queried_sid, spos_name in results:
            if vt and not vpn_type:
                vpn_type = vt
            if spos_name and any(w in spos_name.lower() for w in ["windows 7", "window 7"]):
                port = "7"
            tams_ips[device] = {
                'tams_ip': str(tams_ip) if tams_ip else ''
            }
        tams_ips['vpn_type'] = str(vpn_type) if vpn_type else ''
        tams_ips['port'] = port
        if not tams_ips:
            logger.info(f"[CONNECTVPN] No Devices Found for SID {sid}", extra={"tag": tag})
        return tams_ips
    except Exception as e:
        logger.error(f"[CONNECTVPN] get_ips For SID {sid}: {e}", extra={"tag": tag})
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
# ------------------------------------------------------------------------
def save_to_json(sid, main_app):
    tag = "SAVE_JSON"
    try:
        sid_database = SIDDatabase()
        entry = {
            "sid": sid,
            "site_name": main_app.dynamic_header.text() if hasattr(main_app, "dynamic_header") and isinstance(main_app.dynamic_header, QLabel) else "",
            "sp_ip": [ip.strip() for ip in main_app.sp_ip_edit_box.text().split(",") if ip.strip()] if hasattr(main_app, "sp_ip_edit_box") and isinstance(main_app.sp_ip_edit_box, QLineEdit) else [],
            "host_ip": [ip.strip() for ip in main_app.sm_ip_edit_box.text().split(",") if ip.strip()] if hasattr(main_app, "sm_ip_edit_box") and isinstance(main_app.sm_ip_edit_box, QLineEdit) else [],
            "display_ip": [], 
            "tunnel": [t.strip() for t in main_app.tunnel_edit_box.text().split(",") if t.strip()] if hasattr(main_app, "tunnel_edit_box") and isinstance(main_app.tunnel_edit_box, QLineEdit) else [],
            "modality": ["MR"],
            "port": main_app.port_edit_box.text() if hasattr(main_app, "port_edit_box") and isinstance(main_app.port_edit_box, QLineEdit) else "",
            "machine": main_app.edit_boxes.get("machine", QLineEdit()).text() if hasattr(main_app, "edit_boxes") and isinstance(main_app.edit_boxes.get("machine"), QLineEdit) else "",
            "sw_version": main_app.edit_boxes.get("sw_version", QLineEdit()).text() if hasattr(main_app, "edit_boxes") and isinstance(main_app.edit_boxes.get("sw_version"), QLineEdit) else "",
            "note": [n.strip() for n in main_app.note_edit_box.text().split(",") if n.strip()] if hasattr(main_app, "note_edit_box") and isinstance(main_app.note_edit_box, QLineEdit) else []
        }
        existing_entries = sid_database.find_by_sid(sid)
        if existing_entries:
            sid_database.update_entry(sid, entry)
            logger.info(f"[CONNECTVPN] Updated existing entry for SID {sid} in siddb.json", extra={"tag": tag})
        else:
            sid_database.add_entry(entry)
            logger.info(f"[CONNECTVPN] Added new entry for SID {sid} to siddb.json", extra={"tag": tag})
        return True
    except Exception as e:
        logger.error(f"[CONNECTVPN] Failed to save SID {sid} to siddb.json: {e}", extra={"tag": tag})
        return False
# ------------------------------------------------------------------------
def query_sid(sid, main_app=None, creds_dict=None):
    tag = "QUERY_SID"
    app = QApplication.instance() or QApplication(sys.argv)
    thread = QueryThread(sid, main_app)
    dialog = LoadingDialog(query_thread=thread)
    dialog.show()
    thread.update_message.connect(dialog.set_message)
    def on_query_finished(data):
        tag = "UI_UPDATE"
        if main_app:
            try:
                if hasattr(main_app, 'sp_ip_edit_box') and isinstance(main_app.sp_ip_edit_box, QLineEdit):
                    main_app.sp_ip_edit_box.setText(data["sp_ip"])
                if hasattr(main_app, 'sm_ip_edit_box') and isinstance(main_app.sm_ip_edit_box, QLineEdit):
                    main_app.sm_ip_edit_box.setText(data["host_ip"])
                if hasattr(main_app, 'scan_ip_edit_box') and isinstance(main_app.scan_ip_edit_box, QLineEdit):
                    main_app.scan_ip_edit_box.setText(data["host_ip"])
                if hasattr(main_app, 'display_ip_edit_box') and isinstance(main_app.display_ip_edit_box, QLineEdit):
                    main_app.display_ip_edit_box.setText("")  # No CT
                if hasattr(main_app, 'tunnel_edit_box') and isinstance(main_app.tunnel_edit_box, QLineEdit):
                    main_app.tunnel_edit_box.setText(data["TunnelType"])
                if 'sw_version' in main_app.edit_boxes and isinstance(main_app.edit_boxes['sw_version'], QLineEdit):
                    main_app.edit_boxes['sw_version'].setText(data["sw_version"])
                if 'machine' in main_app.edit_boxes and isinstance(main_app.edit_boxes['machine'], QLineEdit):
                    main_app.edit_boxes['machine'].setText(data["machine"])
                if 'Modality' in main_app.edit_boxes and isinstance(main_app.edit_boxes['Modality'], QLineEdit):
                    main_app.edit_boxes['Modality'].setText(data["Modality"])
                if hasattr(main_app, 'port_edit_box') and isinstance(main_app.port_edit_box, QLineEdit):
                    main_app.port_edit_box.setText(data["port"])
                if hasattr(main_app, 'dynamic_header') and isinstance(main_app.dynamic_header, QLabel):
                    hosp_name = data["HospName"]
                    if hosp_name.startswith("PreInstall:"):
                        hosp_name = hosp_name[len("PreInstall:"):].strip()
                    main_app.dynamic_header.setText(hosp_name)
            except Exception as e:
                logger.error(f"[CONNECTVPN] Failed to Update Edit Boxes for SID {sid}: {e}", extra={"tag": tag})
                if main_app:
                    QMessageBox.critical(main_app, "Error", f"Failed to update edit boxes: {e}")
        dialog.accept()
        logger.info("[CONNECTVPN] Outputting JSON data", extra={"tag": tag})
        print(json.dumps(data))
# ------------------------------------------------------------------------
    def on_query_failed(error):
        tag = "QUERY_SID"
        logger.error(f"Query failed: {error}", extra={"tag": tag})
        if main_app:
            QMessageBox.critical(main_app, "Error", f"Query SID {sid} failed: {error}")
        dialog.accept()
        print(f"Error: {error}", file=sys.stderr)
        if thread.isRunning():
            thread.requestInterruption()
            thread.wait(1000)
            if thread.isRunning():
                logger.warning("[CONNECTVPN] Query/Thread Did Not Terminate Properly", extra={"tag": tag})
                thread.terminate()
                thread.wait()
    thread.query_finished.connect(on_query_finished)
    thread.query_failed.connect(on_query_failed)
    thread.start()
    app.exec_()
    if thread.isRunning():
        thread.requestInterruption()
        thread.wait(1000)
        if thread.isRunning():
            logger.warning("[CONNECTVPN] Query/Thread Did Not Terminate Properly", extra={"tag": tag})
            thread.terminate()
            thread.wait()
    return None
# ------------------------------------------------------------------------
def main():
    tag = "MAIN"
    try:
        if len(sys.argv) < 2:
            logger.error("[CONNECTVPN] No SID Provided", extra={"tag": tag})
            sys.exit(1)
        arg = sys.argv[1]
        logger.info(f"[CONNECTVPN] Received SID argument: {arg}", extra={"tag": tag})
        if arg.replace('-', '').isdigit():
            query_sid(arg)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"[CONNECTVPN] Main Function Failed for SID {arg}: {e}", extra={"tag": tag})
        sys.exit(1)
if __name__ == '__main__':
    main()
# ------------------------------------------------------------------------