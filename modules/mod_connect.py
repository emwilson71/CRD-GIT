# ------------------------------------------------------------------------
"""
mod_connect.py (ew)
Establish Connection to SP for SM Scripts and Checks SM Status
Version 1.00 Updated 02/04/26
"""
# ------------------------------------------------------------------------
"""
Note: 'conn as a ref variable for open and close connection'

import mod_connect

call connect_sp()
conn, successful_creds, current_data = crd_connect.connect_sp()

if conn is None:
    break
# TEST CONNECTION FOR [Status] LOOKING AT SM ROOT OR SM /TEMP
else:
    if isinstance(conn, paramiko.SFTPClient):
        files = conn.listdir('/')
    elif isinstance(conn, paramiko.SSHClient):
        stdin, stdout, stderr = conn.exec_command("dir C:\\")
        output = stdout.read().decode()
    elif isinstance(conn, ftplib.FTP):
        files = conn.nlst()
    if isinstance(conn, paramiko.SFTPClient):
        conn.close()
    elif isinstance(conn, paramiko.SSHClient):
        conn.close()
    elif isinstance(conn, ftplib.FTP):
        conn.quit()
"""  
# ------------------------------------------------------------------------
import os,json,sys,paramiko,logging
import socket, ftplib, re
from cryptography.fernet import Fernet
from mod_logging import CRDLogger
# ------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
crd_logger = CRDLogger("MOD")
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
        logger.error(f"[MOD_CONNECT] Failed to Decrypt {enc_file_path}: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def swversion_group(version: str) -> str:
    cleaned_version = re.sub(r"^(SM\s*)?V?", "", version.upper())
    if re.search(r"SP", cleaned_version):
        major_version_match = re.match(r"(\d+)", cleaned_version)
        if major_version_match:
            major_version = int(major_version_match.group(1))
            if major_version == 2:
                return "MR_MP2"
            elif major_version in [3, 4, 5]:
                return "MR_MP3-5"
            elif major_version >= 6:
                return "MR_MP6+"
    return "MR_GP"
# ------------------------------------------------------------------------
def group_credentials(group: str) -> dict:
    tag = "CREDENTIALS"
    enc_file_path = os.path.join(script_dir, '..', 'config', 'user.enc')
    key_file_path = os.path.join(script_dir, '..', 'config', 'user.key')
 
    if os.path.exists(enc_file_path) and os.path.exists(key_file_path):
        credentials_data = decrypt_file(enc_file_path, key_file_path, is_json=True)
        if credentials_data:
            return credentials_data.get(group, {}).get("credentials", {})
    logger.warning(f"[MOD_CONNECT] Failed to Load Credentials for {group}", extra={"tag": tag})
    return {}
# ------------------------------------------------------------------------
def get_protocols(group: str) -> tuple[str, str, str]:
    if group in ["MR_MP6+", "SP_WIN10"]:
        return "sftp", "ssh", "22"
    else:
        return "ftp", "telnet", "21"
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
        logger.info(f"[MOD_CONNECT] Loaded current.dat: {data}", extra={"tag": tag})
        return data
    except Exception as e:
        logger.error(f"[MOD_CONNECT] Failed to Read {current_file_path}: {e}", extra={"tag": tag})
        return None
# ------------------------------------------------------------------------
def write_current_dat(data):
    tag = "CURRENT_DAT"
    current_file_path = os.path.join(script_dir, '..', 'config', 'current.dat')
    try:
        with open(current_file_path, 'w') as f:
            for key, value in data.items():
                f.write(f"{key}={value}\n")
    except Exception as e:
        logger.error(f"[MOD_CONNECT] Failed to Write {current_file_path}: {e}", extra={"tag": tag})
# ------------------------------------------------------------------------
def connection_sm(host_ip, credentials, file_protocol, term_protocol, port, group="unknown", test_path=r"C:\InnerVision.dir\Comm.dir\ini.dir"):
    tag = "CONNECTION"
    conn = None
    successful_creds = None
    username = credentials.get("host_user", credentials.get("sp_user", "default_user"))
    password = credentials.get("host_pass", credentials.get("sp_pass", "default_pass"))
    protocol = file_protocol.upper()
    source = credentials.get("source", group)
    port = int(port)
    test_dirs = [
        "/temp",
        "/",
    ]
 
    if protocol == "SFTP":
        transport = None
        sftp = None
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            socket.setdefaulttimeout(10)
            transport = paramiko.Transport((host_ip, port))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            logger.info(f"[MOD_CONNECT] SFTP Connection Established to {host_ip}:{port}", extra={"tag": tag})
 
            success = False
            for dir_path in test_dirs:
                try:
                    sftp.listdir(dir_path)
                    success = True
                    break
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"[MOD_CONNECT] SFTP listdir Failed For {dir_path}: {e}", extra={"tag": tag})
 
            if success:
                conn = sftp
                successful_creds = {"spuser": username, "sppass": password, "port": str(port), "protocol": "SFTP", "source": source}
                return conn, successful_creds
 
        except (paramiko.SSHException, socket.timeout, paramiko.AuthenticationException, OSError) as sftp_error:
            logger.warning(f"[MOD_CONNECT] SFTP Failed on Port {port}: {sftp_error}")
            try:
                client.connect(host_ip, username=username, password=password, port=port, timeout=10)
                success = False
                for dir_path in test_dirs:
                    try:
                        check_command = f"ls \"{dir_path}\""  
                        stdin, stdout, stderr = client.exec_command(check_command, timeout=10)
                        check_error = stderr.read().decode('utf-8').strip()
                        if check_error:
                            check_command = f"dir \"{dir_path}\""
                            stdin, stdout, stderr = client.exec_command(check_command, timeout=10)
                            check_error = stderr.read().decode('utf-8').strip()
                            if check_error:
                                logger.debug(f"[MOD_CONNECT] Directory Check Failed")
                                continue
                        check_output = stdout.read().decode('utf-8').strip()
                        logger.info(f"[MOD_CONNECT] Directory Check Successful")
                        success = True
                        break
                    except Exception as e:
                        logger.debug(f"[MOD_CONNECT] SSH Check Failed for {dir_path}: {e}")
 
                if success:
                    logger.info(f"[MOD_CONNECT] SSH Connection Successful")
                    conn = client
                    successful_creds = {"spuser": username, "sppass": password, "port": str(port), "protocol": "SSH", "source": source}
                    return conn, successful_creds
 
            except (paramiko.SSHException, socket.timeout, paramiko.AuthenticationException, OSError) as ssh_error:
                logger.warning(f"[MOD_CONNECT] SSH Failed on Port {port}: {ssh_error}", extra={"tag": tag})
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
            ftp.connect(host_ip, port=port, timeout=10)
            ftp.login(user=username, passwd=password)
            logger.info(f"[MOD_CONNECT] FTP Connection Established to {host_ip}:{port}", extra={"tag": tag})
            current_pwd = ftp.pwd()
            success = False
            for ftp_dir in test_dirs:
                try:
                    ftp.cwd(ftp_dir)
                    ftp.nlst()
                    success = True
                    break
                except ftplib.error_perm as e:
                    logger.debug(f"[MOD_CONNECT] FTP cwd Failed for {ftp_dir}: {e}")
 
            if success:
                conn = ftp
                successful_creds = {"spuser": username, "sppass": password, "port": str(port), "protocol": "FTP", "source": source}
                return conn, successful_creds
 
        except ftplib.all_errors as ftp_error:
            logger.warning(f"[MOD_CONNECT] FTP Failed on Port {port}: {ftp_error}")
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
    if conn is None:
        logger.error(f"[MOD_CONNECT] Connection Attempt Failed for {host_ip}")
    return conn, successful_creds
# ------------------------------------------------------------------------
def connect_sp(test_path=r"C:\InnerVision.dir\Comm.dir\ini.dir"):
    tag = "CONNECT_SP"
    current_data = read_current_dat()
    if not current_data:
        logger.error("[MOD_CONNECT] No current.dat Data Available")
        return None, None, None
 
    host_ip = current_data.get('Host_IP')
    if not host_ip:
        logger.error("[MOD_CONNECT] No Host_IP Found in current.dat")
        return None, None, None
 
    group = current_data.get('SW_Group')
    version = current_data.get('SW_Version')
 
    if group:
        credentials = group_credentials(group)
        if not credentials:
            logger.error(f"[MOD_CONNECT] No Credentials for Group {group}")
            current_data['Status'] = '0'
            write_current_dat(current_data)
            return None, None, current_data
        file_protocol, term_protocol, default_port = get_protocols(group)
        host_port = default_port  
        if 'Conn1' not in current_data:
            current_data['Conn1'] = term_protocol
        if 'Conn2' not in current_data:
            current_data['Conn2'] = file_protocol
        write_current_dat(current_data)
        conn, successful_creds = connection_sm(host_ip, credentials, file_protocol, term_protocol, host_port, group=group, test_path=test_path)
        current_data['Status'] = '1' if conn else '0'
        write_current_dat(current_data)
        return conn, successful_creds, current_data
 
    if version:
        group = swversion_group(version)
        credentials = group_credentials(group)
        if not credentials:
            logger.error(f"[MOD_CONNECT] No Credentials for Mapped Group {group}")
            current_data['Status'] = '0'
            write_current_dat(current_data)
            return None, None, current_data
        file_protocol, term_protocol, default_port = get_protocols(group)
        host_port = default_port  
        current_data['SW_Group'] = group
        current_data['Conn1'] = term_protocol
        current_data['Conn2'] = file_protocol
        write_current_dat(current_data)
        conn, successful_creds = connection_sm(host_ip, credentials, file_protocol, term_protocol, host_port, group=group, test_path=test_path)
        current_data['Status'] = '1' if conn else '0'
        write_current_dat(current_data)
        return conn, successful_creds, current_data
    
    logger.warning("[MOD_CONNECT] No SW_Group or SW_Version in current.dat", extra={"tag": tag})
    possible_groups = ["MR_MP6+", "MR_MP3-5", "MR_MP2", "MR_GP"]
    conn = None
    successful_creds = None
    selected_group = None
    for trial_group in possible_groups:
        credentials = group_credentials(trial_group)
        if not credentials:
            continue
        file_protocol, term_protocol, default_port = get_protocols(trial_group)
        host_port = default_port 
        temp_conn, temp_creds = connection_sm(host_ip, credentials, file_protocol, term_protocol, host_port, group=trial_group, test_path=test_path)
        if temp_conn:
            conn = temp_conn
            successful_creds = temp_creds
            selected_group = trial_group
            break
    if conn:
        file_protocol, term_protocol, _ = get_protocols(selected_group)
        current_data['SW_Group'] = selected_group
        current_data['Conn1'] = term_protocol
        current_data['Conn2'] = file_protocol
        current_data['Status'] = '1'
    else:
        current_data['Status'] = '0'
    write_current_dat(current_data)
    return conn, successful_creds, current_data
# ------------------------------------------------------------------------
def main():
    tag = "MAIN"
    try:
        conn, creds, current_data = connect_sp()
        if conn:
            logger.info(f"[MOD_CONNECT] Connected Successfully With {creds['protocol']} from {creds['source']}")
            if isinstance(conn, paramiko.SFTPClient):
                conn.close()
            elif isinstance(conn, paramiko.SSHClient):
                stdin, stdout, stderr = conn.exec_command("dir C:\\")
                conn.close()
            elif isinstance(conn, ftplib.FTP):
                conn.quit()
        else:
            logger.error("[MOD_CONNECT] Connection Failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"[MOD_CONNECT] Main Function Failed: {e}", extra={"tag": tag})
        sys.exit(1)
if __name__ == '__main__':
    main()
# ------------------------------------------------------------------------