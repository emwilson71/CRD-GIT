# ------------------------------------------------------------------------
"""X
crd_matrix.py
Decodes sw versions and passwords for connectivity
ewilson@us.medical.canon 05/24/25
jsmyser "changed port =" on 2025.12.16. See JS Edit.
Version 1.00 Updated 12/16/25  

"""
# ------------------------------------------------------------------------
# LIBRARIES
import json
import os, re, logging, time
import subprocess
import xml.etree.ElementTree as ET
import tempfile
import uuid
from contextlib import contextmanager
import shlex
import shutil
import socket
import urllib.parse
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import QMessageBox
from contextlib import contextmanager
# MODULES
from crd_embedded import CustomMessageBox, Paths, CRDLogger, Styles
import crd_sp_rdp
# ------------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
STORED_CREDENTIALS = None
# ------------------------------------------------------------------------
# SETTING FROM CONFIG PAGE
def load_settings():
    settings_path = os.path.join("..", "config", "settings.json")
    if not os.path.exists(settings_path):
        logger.error(f"[MATRIX] Settings File Not Found {settings_path}")
        raise FileNotFoundError(f"Settings File Not Found at {settings_path}")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            
        return settings.get("paths", {})
    except Exception as e:
        logger.error(f"Failed To Load Settings: {str(e)}")
        
# ------------------------------------------------------------------------
def load_key():
    key_path = os.path.join("..", "config", "user.key")
    if not os.path.exists(key_path):
        logger.error(f"[MATRIX] Encryption Key Missing {key_path}")
        raise FileNotFoundError(f"Encryption Key Missing {key_path}")
    with open(key_path, "rb") as key_file:
        key = key_file.read()
        if len(key) != 44:
            logger.error(f"[MATRIX] Invalid Encryption Key {key_path}")
            raise ValueError(f"Invalid Encryption Key {key_path}")
        return key
# ------------------------------------------------------------------------
def decrypt_credentials():
    global STORED_CREDENTIALS
    enc_path = os.path.join("..", "config", "user.enc")
    if not os.path.exists(enc_path):
        logger.error(f"[MATRIX] Encrypted File Not Found {enc_path}")
        raise FileNotFoundError(f"Encrypted File Not Found {enc_path}")
    key = load_key()
    fernet = Fernet(key)
    with open(enc_path, "rb") as enc_file:
        encrypted_data = enc_file.read()
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data)
        STORED_CREDENTIALS = json.dumps(credentials, indent=2)
        return credentials
    except Exception as e:
        logger.error(f"[MATRIX] Decryption Failed: {str(e)}")
        raise ValueError(f"Decryption Failed: {str(e)}")
# ------------------------------------------------------------------------
def create_filezilla_site_config(username, password, host, port, protocol="ftp"):
    tag = "FILEZILLA_CONFIG"
    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xml', prefix='filezilla_site_')
        root = ET.Element("FileZilla3")
        servers = ET.SubElement(root, "Servers")
        server = ET.SubElement(servers, "Server")
        ET.SubElement(server, "Host").text = host
        ET.SubElement(server, "Port").text = str(port)
        ET.SubElement(server, "Protocol").text = "0" if protocol == "sftp" else "1" 
        ET.SubElement(server, "Type").text = "0"
        ET.SubElement(server, "User").text = username
        ET.SubElement(server, "Pass").text = password 
        ET.SubElement(server, "Logontype").text = "1"
        ET.SubElement(server, "TimezoneOffset").text = "0"
        ET.SubElement(server, "PasvMode").text = "MODE_DEFAULT"
        ET.SubElement(server, "MaximumMultipleConnections").text = "0"
        ET.SubElement(server, "EncodingType").text = "Auto"
        ET.SubElement(server, "BypassProxy").text = "0"
        tree = ET.ElementTree(root)
        with open(temp_path, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
        with open(temp_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
            logger.debug(f"[MATRIX] Generated FileZilla XML config: {xml_content}")
        return temp_path
    except Exception as e:
        logger.error(f"Failed To Create FileZilla Config: {e}", extra={"tag": tag})
        raise
# ------------------------------------------------------------------------
def parse_sw_version(sw_version):
    if not sw_version:
        logger.error("[MATRIX] Software Version is Required")
        raise ValueError("Software Version is Required")
# GP CHECK
    if 'r' in sw_version.lower():
        return "MR_GP"
# MP CHECK
    cleaned_version = sw_version.strip().rstrip('*').replace("SM", "").replace("V", "").replace("v", "").strip()
    match = re.match(r'(\d+)', cleaned_version)
    if not match:
        logger.error(f"[MATRIX] Invalid SW Version Format: {cleaned_version}")
        raise ValueError(f"Invalid SW Version Format: {sw_version}")
    major_version = int(match.group(1))
    if major_version >= 6:
        return "MR_MP6+"
    elif major_version in [3, 4, 5]:
        return "MR_MP3-5"
    elif major_version == 2:
        return "MR_MP2"
    else:
        logger.error(f"[MATRIX] Unsupported SW Version: {sw_version}")
# ------------------------------------------------------------------------
def get_credentials(feature, button, host_ip=None, sw_version=None):
    tag = "CREDENTIALS"
    credentials_data = decrypt_credentials()
    current_file_path = os.path.join("..", "config", "current.dat")
    port = "10"  
    try:
        with open(current_file_path, 'r', encoding='utf-8') as f:
            config_data = f.read()
            for line in config_data.splitlines():
                if line.startswith('Port='):
                    port = line.split('=', 1)[1].strip()
                    break
    except Exception as e:
        logger.warning(f"[MATRIX] Failed to read Port from {current_file_path}: {e}, using default Port={port}", extra={"tag": tag})

    if feature == "SP:" and button.upper() in ["RDP", "TERM", "SFTP", "FTP"]:
        win10_creds = credentials_data.get("SP_WIN10", {})
        win7_creds = credentials_data.get("SP_WIN7", {}).get("credentials", {})
        creds_list = []
        for os_type, creds_dict, user_key, pass_key, alt_pass_key in [
            ("SP_WIN10", win10_creds, "sp_user", "sp_pass", "host_pass"),
            ("SP_WIN7", win7_creds, "host_user", "host_pass", "password")
        ]:
            username = creds_dict.get(user_key, "")
            password = creds_dict.get(pass_key, creds_dict.get(alt_pass_key, ""))
            if not username or not password:
                continue
            default_port = "3389" if button.upper() == "RDP" else "22" if button.upper() in ["SFTP", "FTP"] else "23"
            port_value = creds_dict.get("host_port", creds_dict.get("alt_port", default_port))
            if button.upper() == "TERM" and port_value not in ["22", "23"]:
                port_value = "23" if creds_dict.get("alt_port") == "23" else "22"
            if button.upper() in ["SFTP", "FTP"]:
                port_value = "22" if os_type == "SP_WIN10" else "21"
            creds_list.append({
                "os_type": os_type,
                "username": username,
                "password": password,
                "host": host_ip or "",
                "port": port_value
            })
        if not creds_list:
            logger.error(f"[MATRIX] No Credentials Found for {feature} {button}", extra={"tag": tag})
            raise ValueError(f"No Credentials Found for {feature} {button}")
        if button.upper() in ["TERM", "SFTP", "FTP"]:
            if port == "10":
                return [cs for cs in creds_list if cs["os_type"] == "SP_WIN10"] + [cs for cs in creds_list if cs["os_type"] != "SP_WIN10"]
            elif port == "7":
                return [cs for cs in creds_list if cs["os_type"] == "SP_WIN7"] + [cs for cs in creds_list if cs["os_type"] != "SP_WIN7"]
            else:
                logger.warning(f"[MATRIX] Unknown Port value: {port}, returning all credentials", extra={"tag": tag})
                return creds_list
        return creds_list
    
    elif feature == "SM:" and button.upper() in ["TERM", "SFTP"]:
        if not sw_version:
            logger.error(f"[MATRIX] Software Version Required For SM {button}", extra={"tag": tag})
            raise ValueError(f"Software Version Required For SM {button}")
        try:
            credential_set = parse_sw_version(sw_version)
        except ValueError as e:
            logger.error(f"[MATRIX] Failed To Parse SW Version: {str(e)}", extra={"tag": tag})
            raise
        creds_dict = credentials_data.get(credential_set, {}).get("credentials", {})
        if not creds_dict:
            logger.error(f"[MATRIX] No Credentials Found For {credential_set}", extra={"tag": tag})
            raise ValueError(f"No Credentials Found For {credential_set}")
        username = creds_dict.get("host_user", "")
        password = creds_dict.get("host_pass", "")
        if not username or not password:
            raise ValueError(f"Missing Username Or Password")
        default_port = "22" if credential_set == "MR_MP6+" else "21"
        port = creds_dict.get("host_port", creds_dict.get("alt_port", default_port))
        if not port:
            port = default_port
        if button.upper() == "SFTP" and credential_set != "MR_MP6+" and port == "23":
            port = "21"
        creds_list = [{
            "os_type": credential_set,
            "username": username,
            "password": password,
            "host": host_ip or "",
            "port": port
        }]
        return creds_list
    else:
        logger.error(f"[MATRIX] Unsupported feature or button: {feature} {button}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def handle_feature_button_click(feature, button_text, host_ip, parent=None, sw_version=None):
    if host_ip:
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, host_ip) or not all(0 <= int(octet) <= 255 for octet in host_ip.split('.')):
            if parent:
                msg_box = CustomMessageBox()
                msg_box.warning(parent, "Error", "Invalid Host IP format")
            return False
    else:
        if parent:
            msg_box = CustomMessageBox()
            msg_box.warning(parent, "Error", "Host IP Is Empty")
        return False
    try:
        paths = load_settings()
    except Exception as e:
        logger.error(f"[MATRIX] Failed To Load Settings: {str(e)}")
        return False
# ------------------------------------------------------------------------
# SP RDP - COMPLETED
    def parse_config(file_path):
        config = {}
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config[key] = value
            return config
        except FileNotFoundError:
            logger.error(f"[MATRIX] Config File {file_path} not found.")
            raise
        except Exception as e:
            logger.error(f"[MATRIX] Parsing Config File {file_path}: {str(e)}")
            raise

    @contextmanager
    def timeout(seconds):
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(seconds)
        try:
            yield
        finally:
            socket.setdefaulttimeout(original_timeout)

    def check_rdp_connectivity(sp_ip, port=3389, timeout_seconds=2):
        try:
            with timeout(timeout_seconds):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((sp_ip, port))
            return True
        except (socket.timeout, socket.error) as e:
            logger.error(f"[MATRIX] RDP Connectivity Check Failed for {sp_ip}:{port}: {str(e)}")
            return False

    if feature == "SP:" and button_text.upper() == "RDP":
        config_file_path = "../config/current.dat"
        try:
            config = parse_config(config_file_path)
        except Exception as e:
            logger.error(f"[MATRIX] Failed to Load Config: {str(e)}")
            return False
        sp_ip = config.get('SP_IP')
        if not sp_ip:
            logger.error(f"[MATRIX] SP_IP not found in config file.")
            return False
        if not check_rdp_connectivity(sp_ip):
            logger.error(f"[MATRIX] RDP Server {sp_ip} is Unreachable")
            return False
        try:
            port = int(config.get('Port') or 10) #JS Edit. 
        except ValueError:
            logger.error(f"[MATRIX] RDP get Port Failed")
            return False
        if port == 10:
            username = "IV_Service_User"
            password = "SU_InnerVision2020"
            logger.info(f"[MATRIX] Selected Windows 10 credentials for {sp_ip}")
        else:
            username = "COM_SP"
            password = "IV_TAC_SP"
            logger.info(f"[MATRIX] Selected Windows 7 credentials for {sp_ip}")
        try:
            crd_sp_rdp.launch_rdp(sp_ip, username, password)
            return True
        except Exception as e:
            logger.error(f"[MATRIX] RDP Launch Failed with {username}: {str(e)}")
            return False
# ------------------------------------------------------------------------
# SM TERM
    elif feature == "SM:" and button_text.upper() == "TERM":
        tag = "SM_TERM"
        putty_path = paths.get("putty", "")
        if not putty_path or not os.path.exists(putty_path):
            logger.warning(f"[MATRIX] PuTTY Not Found", extra={"tag": tag})
        config_file_path = "../config/current.dat"
        try:
            config = parse_config(config_file_path)
        except Exception as e:
            logger.error(f"[MATRIX] Failed to Load Config: {str(e)}", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"Failed to Load Config: {str(e)}")
            return False
        host_ip = config.get('Host_IP')
        if not host_ip:
            logger.error(f"[MATRIX] Host_IP not found in config file.", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", "Host_IP not found in config file.")
            return False

        sw_version = config.get('SW_Version', '')
        if not sw_version:
            logger.error(f"[MATRIX] SW_Version Not Found", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", "SW_Version Not Found")
            return False

        try:
            credentials = get_credentials(feature, button_text, host_ip, sw_version)
            if not credentials:
                logger.error(f"[MATRIX] No Credentials Found for {feature} {button_text} with SW_Version: {sw_version}", extra={"tag": tag})
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"No Credentials Found for SW_Version: {sw_version}")
                return False

            credential_set = parse_sw_version(sw_version)
            logger.info(f"[MATRIX] Parsed Software Version: {sw_version} -> {credential_set}", extra={"tag": tag})

            def check_network(host, port, timeout=5):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, int(port)))
                    sock.close()
                    if result == 0:
                        logger.info(f"[MATRIX] Network check passed for {host}:{port}", extra={"tag": tag})
                        return True
                    else:
                        logger.error(f"[MATRIX] Network check failed for {host}:{port}: Connection refused", extra={"tag": tag})
                        return False
                except Exception as e:
                    logger.error(f"[MATRIX] Network Check Failed for {host}:{port}: {str(e)}", extra={"tag": tag})
                    return False

            for creds in credentials:
                creds['host'] = host_ip
                if credential_set == "MR_MP6+":
                    protocol = "ssh"
                    port = "22"
                    if not putty_path or not os.path.exists(putty_path):
                        logger.error(f"[MATRIX] PuTTY Not Found at {putty_path} for SSH ({credential_set})", extra={"tag": tag})
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"PuTTY Not Found at {putty_path} for SSH")
                        continue
                else:
                    protocol = "telnet"
                    port = "23"

                if not check_network(creds['host'], port):
                    logger.error(f"[MATRIX] Network Unreachable: {creds['host']}:{port}", extra={"tag": tag})
                    if parent:
                        msg_box = CustomMessageBox()
                        msg_box.critical(parent, "Error", f"Network Unreachable: {creds['host']}:{port}")
                    continue

                if protocol == "ssh":
                    cmd = [
                        putty_path,
                        "-ssh",
                        "-l", creds['username'],
                        "-pw", creds['password'],
                        "-P", port,
                        creds['host']
                    ]
                    logger.info(f"[MATRIX] Launching PuTTY with SSH for {creds['host']}:{port} as {creds['username']} ({credential_set})", extra={"tag": tag})
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(2.0)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] PuTTY SSH Failed: stdout={stdout}, stderr={stderr}, Command: {' '.join(cmd)}", extra={"tag": tag})
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"PuTTY SSH Failed: {stderr}")
                            continue
                        logger.info(f"[MATRIX] PuTTY SSH Launched Successfully for {creds['host']}:{port} ({credential_set})", extra={"tag": tag})
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] PuTTY Not Found: {str(e)}", extra={"tag": tag})
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"PuTTY Not Found: {str(e)}")
                        return False
                    except subprocess.TimeoutExpired:
                        logger.error(f"[MATRIX] PuTTY SSH Communication Timeout for {creds['host']}:{port}", extra={"tag": tag})
                        continue
                    except Exception as e:
                        logger.error(f"[MATRIX] PuTTY SSH Failed: {str(e)}, Command: {' '.join(cmd)}", extra={"tag": tag})
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"PuTTY SSH Failed: {str(e)}")
                        continue
                else:
                    telnet_cmd = ["cmd.exe", "/c", "telnet", creds['host'], port]
                    logger.info(f"[MATRIX] Launching Windows telnet for {creds['host']}:{port} ({credential_set})", extra={"tag": tag})
                    try:
                        process = subprocess.Popen(
                            telnet_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(2.0)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] Windows Telnet Failed: stdout={stdout}, stderr={stderr}, Command: {' '.join(telnet_cmd)}", extra={"tag": tag})
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"Windows Telnet Failed: {stderr}")
                            continue
                        logger.warning(f"[MATRIX] Manual Credential Entry May be Required {creds['username']} on {creds['host']}:{port}", extra={"tag": tag})
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] Windows Telnet Not Found: {str(e)}", extra={"tag": tag})
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Windows Telnet Not Found: {str(e)}")
                        return False
                    except subprocess.TimeoutExpired:
                        logger.error(f"[MATRIX] Windows Telnet Communication Timeout for {creds['host']}:{port}", extra={"tag": tag})
                        continue
                    except Exception as e:
                        logger.error(f"[MATRIX] Windows Telnet Failed: {str(e)}, Command: {' '.join(telnet_cmd)}", extra={"tag": tag})
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Windows Telnet Failed: {str(e)}")
                        continue

            logger.error(f"[MATRIX] All Connection Attempts Failed for {host_ip} ({credential_set})", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"All Connection Attempts Failed for {host_ip}")
            return False
        except Exception as e:
            logger.error(f"[MATRIX] Credential or Execution Error: {str(e)}", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"Credential or Execution Error: {str(e)}")
            return False
# ------------------------------------------------------------------------
# SM FILEZILLA - COMPLETED
    elif feature == "SM:" and button_text.upper() == "SFTP":
        filezilla_path = paths.get("filezilla", "")
        if not filezilla_path or not os.path.exists(filezilla_path):
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"FileZilla Not Found {filezilla_path}")
            logger.error(f"[MATRIX] FileZilla Not Found {filezilla_path}")
            return False
        try:
            credentials = get_credentials(feature, button_text, host_ip, sw_version)
            if not credentials:
                logger.error(f"[MATRIX] No Credentials Found For {feature} {button_text} with sw_version: {sw_version}")
                return False
            for creds in credentials:
                credential_set = creds['os_type']
                def check_network(host, port, timeout=10):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(timeout)
                        result = sock.connect_ex((host, int(port)))
                        sock.close()
                        return result == 0
                    except Exception as e:
                        logger.error(f"[MATRIX] Network Check Failed {host}:{port}: {str(e)}")
                        return False
# MR_GP (FTP, port 21)
                if credential_set == "MR_GP":
                    protocol = "ftp"
                    port = "21"
                    if not check_network(creds['host'], port):
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Network Unreachable: {creds['host']}:{port}")
                        logger.error(f"[MATRIX] Network Unreachable: {creds['host']}:{port}")
                        continue
                    encoded_password = urllib.parse.quote(creds['password'], safe='')
                    url = f"{protocol}://{creds['username']}:{encoded_password}@{creds['host']}:{port}"
                    cmd = [filezilla_path, url]
                    logger.info(f"[MATRIX] Launching FileZilla for MR_GP: {' '.join(cmd)}")
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(5)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] FileZilla Failed for MR_GP: stdout={stdout}, stderr={stderr}")
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"FileZilla failed for MR_GP: {stderr}")
                            continue
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] FileZilla Not Found: {str(e)}")
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"FileZilla Not Found: {str(e)}")
                        return False
                    except Exception as e:
                        logger.error(f"[MATRIX] FileZilla Error for MR_GP: {str(e)}")
                        continue
# MR_MP2 (FTP, port 21)
                elif credential_set == "MR_MP2":
                    protocol = "ftp"
                    port = "21"
                    if not check_network(creds['host'], port):
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Network Unreachable: {creds['host']}:{port}")
                        logger.error(f"[MATRIX] Network Unreachable: {creds['host']}:{port}")
                        continue
                    encoded_password = urllib.parse.quote(creds['password'], safe='')
                    url = f"{protocol}://{creds['username']}:{encoded_password}@{creds['host']}:{port}"
                    cmd = [filezilla_path, url]
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(5)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] FileZilla Failed for MR_MP2: stdout={stdout}, stderr={stderr}")
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"FileZilla failed for MR_MP2: {stderr}")
                            continue
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] FileZilla Not Found: {str(e)}")
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"FileZilla Not Found: {str(e)}")
                        return False
                    except Exception as e:
                        logger.error(f"[MATRIX] FileZilla error for MR_MP2: {str(e)}")
                        continue

# MR_MP3-5 (FTP, port 21)
                elif credential_set == "MR_MP3-5":
                    protocol = "ftp"
                    port = "21"
                    if not check_network(creds['host'], port):
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Network Unreachable: {creds['host']}:{port}")
                        continue
                    encoded_password = creds['password']  
                    url = f"{protocol}://{creds['username']}:{encoded_password}@{creds['host']}:{port}"
                    cmd = [filezilla_path, url]
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(5)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] FileZilla Failed for MR_MP3-5: stdout={stdout}, stderr={stderr}")
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"FileZilla failed for MR_MP3-5: {stderr}")
                            continue
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] FileZilla Not Found: {str(e)}")
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"FileZilla Not Found: {str(e)}")
                        return False
                    except subprocess.TimeoutExpired:
                        logger.error(f"[MATRIX] FileZilla communication timeout for {creds['host']}:{port}")
                        continue
                    except Exception as e:
                        logger.error(f"[MATRIX] FileZilla URL method error for MR_MP3-5: {str(e)}")
                        config_path = None
                        try:
                            config_path = create_filezilla_site_config(creds['username'], creds['password'], creds['host'], port, protocol)
                            cmd_fallback = [filezilla_path, f"file://{config_path}"]
                            logger.info(f"[MATRIX] Launching FileZilla with XML config for MR_MP3-5: {' '.join(cmd_fallback)}")
                            process = subprocess.Popen(
                                cmd_fallback,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                shell=False,
                                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                            )
                            time.sleep(5)
                            if process.poll() is not None:
                                stdout, stderr = process.communicate(timeout=10)
                                logger.error(f"[MATRIX] FileZilla XML config failed for MR_MP3-5: stdout={stdout}, stderr={stderr}")
                                if parent:
                                    msg_box = CustomMessageBox()
                                    msg_box.critical(parent, "Error", f"FileZilla XML config failed for MR_MP3-5: {stderr}")
                                continue
                            return True
                        except Exception as e_fallback:
                            logger.error(f"[MATRIX] FileZilla XML config error for MR_MP3-5: {str(e_fallback)}")
                            continue
                        finally:
                            if config_path and os.path.exists(config_path):
                                try:
                                    time.sleep(2)
                                    os.remove(config_path)
                                except OSError as e:
                                    logger.warning(f"[MATRIX] Failed to clean up temp file {config_path}: {str(e)}")
# MR_MP6+ (SFTP, port 22)
                elif credential_set == "MR_MP6+":
                    protocol = "sftp"
                    port = "22"
                    if not check_network(creds['host'], port):
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"Network Unreachable: {creds['host']}:{port}")
                        logger.error(f"[MATRIX] Network Unreachable: {creds['host']}:{port}")
                        continue
                    encoded_password = creds['password']  
                    url = f"{protocol}://{creds['username']}:{encoded_password}@{creds['host']}:{port}"
                    cmd = [filezilla_path, url]
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            shell=False,
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                        time.sleep(5)
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(timeout=10)
                            logger.error(f"[MATRIX] FileZilla Failed for MR_MP6+: stdout={stdout}, stderr={stderr}")
                            if parent:
                                msg_box = CustomMessageBox()
                                msg_box.critical(parent, "Error", f"FileZilla failed for MR_MP6+: {stderr}")
                            continue
                        return True
                    except FileNotFoundError as e:
                        logger.error(f"[MATRIX] FileZilla Not Found: {str(e)}")
                        if parent:
                            msg_box = CustomMessageBox()
                            msg_box.critical(parent, "Error", f"FileZilla Not Found: {str(e)}")
                        return False
                    except subprocess.TimeoutExpired:
                        logger.error(f"[MATRIX] FileZilla communication timeout for {creds['host']}:{port}")
                        continue
                    except Exception as e:
                        logger.error(f"[MATRIX] FileZilla URL method error for MR_MP6+: {str(e)}")
                        config_path = None
                        try:
                            config_path = create_filezilla_site_config(creds['username'], creds['password'], creds['host'], port, protocol)
                            cmd_fallback = [filezilla_path, f"file://{config_path}"]
                            process = subprocess.Popen(
                                cmd_fallback,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                shell=False,
                                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                            )
                            time.sleep(5)
                            if process.poll() is not None:
                                stdout, stderr = process.communicate(timeout=10)
                                logger.error(f"[MATRIX] FileZilla XML config failed for MR_MP6+: stdout={stdout}, stderr={stderr}")
                                if parent:
                                    msg_box = CustomMessageBox()
                                    msg_box.critical(parent, "Error", f"FileZilla XML config failed for MR_MP6+: {stderr}")
                                continue
                            return True
                        except Exception as e_fallback:
                            logger.error(f"[MATRIX] FileZilla XML config error for MR_MP6+: {str(e_fallback)}")
                            continue
                        finally:
                            if config_path and os.path.exists(config_path):
                                try:
                                    time.sleep(2)
                                    os.remove(config_path)
                                except OSError as e:
                                    logger.warning(f"[MATRIX] Failed to clean up temp file {config_path}: {str(e)}")

            logger.error(f"[MATRIX] All {protocol.upper()} attempts failed for {creds['host']}")
        except Exception as e:
            logger.error(f"[MATRIX] Credential or execution error: {str(e)}")
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"Credential or Execution Error: {str(e)}")
            return False
# ------------------------------------------------------------------------
# SP TERM - COMPLETED
    elif feature == "SP:" and button_text.upper() == "TERM":
        tag = "SP_TERM"
        putty_path = paths.get("putty", "")
        current_file_path = os.path.join("..", "config", "current.dat")
        port = "10" 
        try:
            with open(current_file_path, 'r', encoding='utf-8') as f:
                config_data = f.read()
                for line in config_data.splitlines():
                    if line.startswith('Port='):
                        port = line.split('=', 1)[1].strip()
                        break
        except Exception as e:
            logger.warning(f"[MATRIX] Failed to read Port from {current_file_path}: {e}, using default Port={port}", extra={"tag": tag})
        if port == "10":
            if not putty_path or not os.path.exists(putty_path):
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"PuTTY Not Found")
                logger.error(f"[MATRIX] PuTTY Not Found at {putty_path}", extra={"tag": tag})
                return False
            username = "IV_Service_User"
            password = "SU_InnerVision2020"
            protocol = "ssh"
            port_value = "22"
        elif port == "7":
            username = "COM_SP"
            password = "IV_TAC_SP"
            protocol = "telnet"
            port_value = "23"
        else:
            logger.warning(f"[MATRIX] Unknown Port value: {port}, defaulting to SP_WIN10 credentials with PuTTY", extra={"tag": tag})
            if not putty_path or not os.path.exists(putty_path):
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"PuTTY Not Found")
                logger.error(f"[MATRIX] PuTTY Not Found at {putty_path}", extra={"tag": tag})
                return False
            username = "IV_Service_User"
            password = "SU_InnerVision2020"
            protocol = "ssh"
            port_value = "22"
# ------------------------------------------------------------------------
        def check_network(host, port, timeout=5):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, int(port)))
                sock.close()
                return result == 0
            except Exception as e:
                logger.error(f"[MATRIX] Network Check Failed {host}:{port}: {str(e)}", extra={"tag": tag})
                return False

        if not check_network(host_ip, port_value):
            logger.error(f"[MATRIX] Network Unreachable: {host_ip}:{port_value}", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"Network Unreachable: {host_ip}:{port_value}")
            return False
        try:
            if protocol == "ssh":
                cmd = [
                    putty_path,
                    "-ssh",
                    "-l", username,
                    "-pw", password,
                    "-P", port_value,
                    host_ip
                ]
                logger.info(f"[MATRIX] Launching PuTTY with SSH for {host_ip}:{port_value} as {username}", extra={"tag": tag})
            else:
                cmd = ["cmd.exe", "/c", "start", "telnet", host_ip, port_value]
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=(protocol == "telnet"), 
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            time.sleep(2.0)
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=10)
                logger.error(f"[MATRIX] {protocol.upper()} Failed: stdout={stdout}, stderr={stderr}, Command: {cmd}", extra={"tag": tag})
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"{protocol.upper()} Failed: {stderr}")
                return False
            logger.info(f"[MATRIX] {protocol.upper()} Launched Successfully for {host_ip}:{port_value}", extra={"tag": tag})
            return True
        except FileNotFoundError as e:
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"PuTTY Not Found: {str(e)}")
            logger.error(f"[MATRIX] PuTTY Not Found: {str(e)}", extra={"tag": tag})
            return False
# ------------------------------------------------------------------------
# SP FILEZILLA - COMPLETED
    elif feature == "SP:" and button_text.upper() in ["SFTP", "FTP"]:
        tag = "SP_FILEZILLA"
        filezilla_path = paths.get("filezilla", "")
        if not filezilla_path or not os.path.exists(filezilla_path):
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"FileZilla Not Found {filezilla_path}")
            logger.error(f"[MATRIX] FileZilla Not Found {filezilla_path}", extra={"tag": tag})
            return False
        try:
            current_file_path = os.path.join("..", "config", "current.dat")
            port = "10"
            try:
                with open(current_file_path, 'r', encoding='utf-8') as f:
                    config_data = f.read()
                    for line in config_data.splitlines():
                        if line.startswith('Port='):
                            port = line.split('=', 1)[1].strip()
                            break
            except Exception as e:
                logger.warning(f"[MATRIX] Failed to read Port from {current_file_path}: {e}, using default Port={port}", extra={"tag": tag})

            if port == "10":
                username = "IV_Service_User"
                password = "SU_InnerVision2020"
                protocol = "sftp"
                port_value = "22"
            elif port == "7":
                username = "COM_SP"
                password = "IV_TAC_SP"
                protocol = "ftp"
                port_value = "21"
            else:
                logger.warning(f"[MATRIX] Unknown Port value: {port}, defaulting to SP_WIN10 credentials", extra={"tag": tag})
                username = "IV_Service_User"
                password = "SU_InnerVision2020"
                protocol = "sftp"
                port_value = "22"
                
            def check_network(host, port, timeout=5):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, int(port)))
                    sock.close()
                    return result == 0
                except Exception as e:
                    logger.error(f"[MATRIX] Network Check Failed {host}:{port}: {str(e)}", extra={"tag": tag})
                    return False

            if not check_network(host_ip, port_value):
                logger.error(f"[MATRIX] Network Unreachable: {host_ip}:{port_value}", extra={"tag": tag})
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"Network Unreachable: {host_ip}:{port_value}")
                return False

            encoded_password = urllib.parse.quote(password, safe='')
            cmd = [filezilla_path, f"{protocol}://{username}:{encoded_password}@{host_ip}:{port_value}"]
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                time.sleep(5)  
                if process.poll() is not None:
                    stdout, stderr = process.communicate(timeout=10)
                    logger.error(f"[MATRIX] FileZilla Failed: stdout={stdout}, stderr={stderr}, Command: {cmd}", extra={"tag": tag})
                    if parent:
                        msg_box = CustomMessageBox()
                        msg_box.critical(parent, "Error", f"FileZilla Failed: {stderr}")
                    return False
                logger.info(f"[MATRIX] FileZilla Launched Successfully for {protocol} on {host_ip}:{port_value}", extra={"tag": tag})
                return True
            except FileNotFoundError as e:
                logger.error(f"[MATRIX] FileZilla Not Found: {str(e)}", extra={"tag": tag})
                if parent:
                    msg_box = CustomMessageBox()
                    msg_box.critical(parent, "Error", f"FileZilla Not Found: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"[MATRIX] Credential or Execution Error: {str(e)}", extra={"tag": tag})
            if parent:
                msg_box = CustomMessageBox()
                msg_box.critical(parent, "Error", f"Credential or Execution Error: {str(e)}")
            return False
# ------------------------------------------------------------------------
def get_stored_credentials():
    return STORED_CREDENTIALS
# ------------------------------------------------------------------------