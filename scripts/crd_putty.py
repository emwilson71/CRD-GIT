"""
crd_putty.py (ew)
Version 1.01 Updated 04/16/25
"""
# ----------------------------------------------------------------------
import json
import subprocess
import re
from cryptography.fernet import Fernet
import os
# ----------------------------------------------------------------------
def load_key(key_file="../config/user.key"):
    with open(key_file, "rb") as f:
        return f.read()
# ----------------------------------------------------------------------
def decrypt_credentials(enc_file="../config/user.enc", key_file="../config/user.key"):
    key = load_key(key_file)
    fernet = Fernet(key)
    with open(enc_file, "rb") as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    return json.loads(decrypted_data)
# ----------------------------------------------------------------------
def map_version_to_credentials(version, credentials_data):
    if "SP" in version:
        cleaned_version = re.sub(r"^(SM V)?", "", version)  
        major_version = re.match(r"(\d+)", cleaned_version)
        if major_version:
            major_version = int(major_version.group(1))
            if major_version == 2:
                return credentials_data.get("MR_MP2", {}).get("credentials")
            elif major_version in [3, 4, 5]:
                return credentials_data.get("MR_MP3-5", {}).get("credentials")
            elif major_version >= 6:
                return credentials_data.get("MR_MP6+", {}).get("credentials")
    return credentials_data.get("MR_GP", {}).get("credentials")
# ----------------------------------------------------------------------
def launch_connection(version, host, use_putty=True):
    if not version or not host:
        print("Software version and host IP are required")
        return
    try:
        credentials_data = decrypt_credentials()
    except Exception as e:
        return
    credentials = map_version_to_credentials(version, credentials_data)
    if not credentials:
        return

    user = credentials["host_user"]
    password = credentials["host_pass"]
    port = credentials["host_port"]
    alt_port = credentials["alt_port"]

    port = str(port).strip('"')
    alt_port = str(alt_port).strip('"')

    protocol = "ssh" if port == "22" else "telnet"
    if port not in ["22", "21"]:
        protocol = "telnet" if alt_port == "21" else "ssh"

    if use_putty:
        cmd = [
            "plink",
            f"-{protocol}",
            "-l", user,
            "-pw", password,
            "-P", port,
            f"{user}@{host}"
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            pass
    else:
        if protocol == "ssh":
            cmd = ["sshpass", "-p", password, "ssh", "-p", port, f"{user}@{host}"]
        else:
            cmd = ["telnet", host, port]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            pass
# ----------------------------------------------------------------------