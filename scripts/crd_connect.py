# ------------------------------------------------------------------------
"""
crd_connect.py (ew)
Establish connection to SP for SM Scripts
Version 1.10 Updated 02/03/26
"""
# ------------------------------------------------------------------------
import os
import paramiko
import json
import sys
import logging
import socket
import configparser
import ftplib
import io
import re
from cryptography.fernet import Fernet
# ------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger("CRD")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
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
        logger.error(f"[CONNECT] Failed to Decrypt {enc_file_path}: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def read_credentials():
    tag = "CREDENTIALS"
    default_credentials = [
        {
            "spuser": "IV_Service_User",
            "sppass": "SU_InnerVision2020",
            "port": "22",
            "source": "SP_WIN10",
            "protocol": "SFTP"
        },
        {
            "spuser": "COM_SP",
            "sppass": "IV_TAC_SP",
            "port": "21",
            "source": "SP_WIN7",
            "protocol": "FTP"
        }
    ]
    enc_file_path = os.path.join(script_dir, '..', 'config', 'user.enc')
    key_file_path = os.path.join(script_dir, '..', 'config', 'user.key')
  
    if os.path.exists(enc_file_path) and os.path.exists(key_file_path):
        logger.info(f"[CONNECT] Loading Credentials from {enc_file_path}", extra={"tag": tag})
        creds_dict = decrypt_file(enc_file_path, key_file_path, is_json=True)
        if creds_dict:
            logger.debug(f"[CONNECT] user.enc contents: {creds_dict.keys()}", extra={"tag": tag})
            credential_sets = []
            if "SP_WIN10" in creds_dict:
                credential_sets.append({
                    "spuser": creds_dict["SP_WIN10"].get("sp_user", "IV_Service_User"),
                    "sppass": creds_dict["SP_WIN10"].get("sp_pass", "SU_InnerVision2020"),
                    "port": creds_dict["SP_WIN10"].get("host_port", "22"),
                    "source": "SP_WIN10",
                    "protocol": "SFTP"
                })
            if "SP_WIN7" in creds_dict and "credentials" in creds_dict["SP_WIN7"]:
                credential_sets.append({
                    "spuser": creds_dict["SP_WIN7"]["credentials"].get("host_user", "COM_SP"),
                    "sppass": creds_dict["SP_WIN7"]["credentials"].get("host_pass", "IV_TAC_SP"),
                    "port": creds_dict["SP_WIN7"]["credentials"].get("host_port", "21"),
                    "source": "SP_WIN7",
                    "protocol": "FTP"
                })
            if credential_sets:
                return credential_sets
    return default_credentials
# ------------------------------------------------------------------------
def read_current_dat():
    tag = "CURRENT_DAT"
    current_file_path = os.path.join(script_dir, '..', 'config', 'current.dat')
    data = {}
    try:
        with open(current_file_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    data[key.strip()] = value.strip()
        logger.info(f"[CONNECT] Loaded current.dat: {data}", extra={"tag": tag})
        return data
    except Exception as e:
        logger.error(f"[CONNECT] Failed to read {current_file_path}: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def establish_connection(spip, creds_dict, test_path=r"C:\InnerVision.dir\Comm.dir\ini.dir"):
    tag = "CONNECTION"
    conn = None
    successful_creds = None
    for credentials in creds_dict:
        username = credentials["spuser"]
        password = credentials["sppass"]
        protocol = credentials["protocol"]
        try:
            port = int(credentials["port"])
        except ValueError:
            logger.error(f"[CONNECT] Invalid Port: {credentials['port']} for {credentials['source']}, using default", extra={"tag": tag})
            port = 22 if protocol == "SFTP" else 21
        source = credentials["source"]
        logger.info(f"[CONNECT] Attempting Connection With {source} Credentials: {spip} as {username} using {protocol} on port {port}", extra={"tag": tag})
      
        if protocol == "SFTP":
            transport = None
            sftp = None
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                socket.setdefaulttimeout(10)
                transport = paramiko.Transport((spip, port))
                transport.connect(username=username, password=password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                logger.info(f"[CONNECT] SFTP Connection Established with {source} to {spip}:{port}", extra={"tag": tag})
              
                dir_path = test_path.replace('\\', '/')
                sftp.listdir(dir_path)  
                logger.info(f"[CONNECT] Directory listing successful for {dir_path}", extra={"tag": tag})
                
                conn = sftp  # Return SFTP client
                successful_creds = credentials
                break
          
            except (paramiko.SSHException, socket.timeout, paramiko.AuthenticationException, OSError, FileNotFoundError) as sftp_error:
                logger.warning(f"[CONNECT] SFTP failed with {source} on port {port}: {sftp_error}", extra={"tag": tag})
                try:
                    client.connect(spip, username=username, password=password, port=port, timeout=10)
                    check_command = f"dir \"{test_path}\""
                    stdin, stdout, stderr = client.exec_command(check_command, timeout=10)
                    check_output = stdout.read().decode('utf-8').strip()
                    check_error = stderr.read().decode('utf-8').strip()
                    if check_error:
                        logger.error(f"[CONNECT] Directory check error: {check_error}", extra={"tag": tag})
                        raise RuntimeError(f"Directory check error: {check_error}")
                    logger.info(f"[CONNECT] SSH Connection Established and directory check successful", extra={"tag": tag})
                    
                    conn = client  
                    successful_creds = credentials
                    break
              
                except (paramiko.SSHException, socket.timeout, paramiko.AuthenticationException, OSError) as ssh_error:
                    logger.warning(f"[CONNECT] SSH Failed {source} on Port {port}: {ssh_error}", extra={"tag": tag})
                    continue
                finally:
                    if sftp:
                        sftp.close()
                    if transport:
                        transport.close()
            finally:
                socket.setdefaulttimeout(None)
        elif protocol == "FTP":
            ftp = None
            try:
                ftp = ftplib.FTP()
                ftp.set_pasv(True)
                ftp.connect(spip, port=port, timeout=10)
                ftp.login(user=username, passwd=password)
                logger.info(f"[CONNECT] FTP Connection Established with {source} to {spip}:{port}", extra={"tag": tag})
              
                ftp_path = test_path.replace("\\", "/")
                ftp_dir = "/".join(ftp_path.split("/")[:-1]) if '/' in ftp_path else ftp_path
                if ftp_dir:
                    ftp.cwd(ftp_dir)
                    logger.info(f"[CONNECT] Changed to directory: {ftp_dir}", extra={"tag": tag})
                ftp.nlst()  
                
                conn = ftp  
                successful_creds = credentials
                break
          
            except ftplib.all_errors as ftp_error:
                logger.warning(f"[CONNECT] FTP Failed With {source} on Port {port}: {ftp_error}", extra={"tag": tag})
                if ftp:
                    try:
                        ftp.quit()
                    except:
                        pass
                continue
    if conn is None:
        logger.error(f"[CONNECT] All Connection Attempts Failed for {spip}", extra={"tag": tag})
    else:
        logger.info(f"[CONNECT] Successful connection using {successful_creds['protocol']} from {successful_creds['source']}", extra={"tag": tag})
    return conn, successful_creds
# ------------------------------------------------------------------------
def connect_to_sp(test_path=r"C:\InnerVision.dir\Comm.dir\ini.dir"):
    tag = "CONNECT_SP"
    current_data = read_current_dat()
    if not current_data:
        logger.error("[CONNECT] No current.dat Data Available", extra={"tag": tag})
        return None, None, None
    
    sp_ip = current_data.get('SP_IP')
    if not sp_ip:
        logger.error("[CONNECT] No SP_IP Found in current.dat", extra={"tag": tag})
        return None, None, None
    
    creds_dict = read_credentials()
    creds_dict = [c for c in creds_dict if c["source"] == "SP_WIN10"] + [c for c in creds_dict if c["source"] == "SP_WIN7"]
    
    conn, successful_creds = establish_connection(spip=sp_ip, creds_dict=creds_dict, test_path=test_path)
    
    return conn, successful_creds, current_data
# ------------------------------------------------------------------------
def main():
    tag = "MAIN"
    try:
        conn, creds, current_data = connect_to_sp()
        if conn:
            logger.info(f"[CONNECT] Connected successfully using {creds['protocol']} from {creds['source']}")
            logger.info(f"[CONNECT] SID: {current_data.get('SID', 'N/A')}")
            logger.info(f"[CONNECT] SP_IP: {current_data.get('SP_IP', 'N/A')}")
            logger.info(f"[CONNECT] Host_IP: {current_data.get('Host_IP', 'N/A')}")
            if isinstance(conn, paramiko.SFTPClient):
                logger.info("[CONNECT] SFTP listing /:")
                logger.info(conn.listdir('/'))
                conn.close()
            elif isinstance(conn, paramiko.SSHClient):
                stdin, stdout, stderr = conn.exec_command("dir C:\\")
                logger.info("[CONNECT] SSH dir C:\\ Output")
                logger.info(stdout.read().decode())
                conn.close()
            elif isinstance(conn, ftplib.FTP):
                logger.info("[CONNECT] FTP Listing:")
                logger.info(conn.nlst())
                conn.quit()
        else:
            logger.error("[CONNECT] Connection Failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"[CONNECT] Main Function Failed: {e}", extra={"tag": tag})
        sys.exit(1)

if __name__ == '__main__':
    main()
# ------------------------------------------------------------------------