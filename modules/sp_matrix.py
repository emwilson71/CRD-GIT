# ---------------------------------------------------------------------------
"""
sp_matrix.py
credentials and sp version lookup
from cred_matrix import load_credentials
version, credentials = load_credentials()
Version 1.00 Updated 11/12/25  
"""
# ---------------------------------------------------------------------------
import os
import json
from cryptography.fernet import Fernet
# ---------------------------------------------------------------------------
def load_credentials(config_path="../config"):
    current_file = os.path.join(config_path, "current.dat")
    port = None
    try:
        with open(current_file, 'r') as f:
            for line in f:
                if line.startswith("Port="):
                    port = line.strip().split("=")[1]
                    break
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration File Not Found at {current_file}")
    if port not in ["7", "10"]:
        raise ValueError(f"Invalid Port {port}")

    version = "win10" if port == "10" else "win7"
    key_file = os.path.join(config_path, "user.key")
    try:
        with open(key_file, 'rb') as f:
            key = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Key Not Found {key_file}")
    fernet = Fernet(key)
    enc_file = os.path.join(config_path, "user.enc")
    try:
        with open(enc_file, 'rb') as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Encrypted Credentials Not Found {enc_file}")

    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
    except Exception as e:
        raise ValueError(f"Failed to Decrypt Credentials {str(e)}")
    cred_key = "SP_WIN10" if version == "win10" else "SP_WIN7"
    if cred_key not in credentials:
        raise KeyError(f"Credentials for {cred_key} not found in user.enc")
    return version, credentials[cred_key]["credentials"]
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        version, creds = load_credentials()
        print(f"Version: {version}")
        print(f"Credentials: {creds}")
    except Exception as e:
        pass
# ---------------------------------------------------------------------------