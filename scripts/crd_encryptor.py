# ----------------------------------------------------------------------
"""X
crd_encryptor.py (ew)
Stores the user.enc with the json values
Version 1.0 Updated 04/08/25

"""
# ----------------------------------------------------------------------
import json
import os
from cryptography.fernet import Fernet, InvalidToken
from pathlib import Path
# ----------------------------------------------------------------------
def generate_key(key_path):
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "wb") as key_file:
        key_file.write(key)
    return key
# ----------------------------------------------------------------------
def load_key(key_path):
    if not Path(key_path).exists():
        raise FileNotFoundError(f"Key File Not Found: {key_path}")
    with open(key_path, "rb") as key_file:
        return key_file.read()
# ----------------------------------------------------------------------
def encrypt_json(data, key, enc_path):
    fernet = Fernet(key)
    try:
        json_str = json.dumps(data)
    except TypeError as e:
        raise ValueError(f"Data Is Not JSON: {e}")
    encrypted_data = fernet.encrypt(json_str.encode())
    os.makedirs(os.path.dirname(enc_path), exist_ok=True)
    with open(enc_path, "wb") as enc_file:
        enc_file.write(encrypted_data)
# ----------------------------------------------------------------------
def decrypt_json(enc_path, key):
    if not Path(enc_path).exists():
        raise FileNotFoundError(f"File Not Found: {enc_path}")
    fernet = Fernet(key)  
    with open(enc_path, "rb") as enc_file:
        encrypted_data = enc_file.read()
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
    except InvalidToken:
        raise ValueError("Decryption failed: Invalid key or corrupted encrypted file.")
# ----------------------------------------------------------------------
def update_config(updates, key_path=None, enc_path=None):
    if key_path is None or enc_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        key_path = key_path or os.path.join(parent_dir, "config", "user.key")
        enc_path = enc_path or os.path.join(parent_dir, "config", "user.enc")

    if not Path(enc_path).exists() or not Path(key_path).exists():
        print("No encrypted file or key found. Initializing new config.")
        default_data = {
            "USER": {"vpn_user": "", "vpn_pass": ""},
            "SP_WIN10": {"host_user": "", "host_pass": "", "host_port": ""},
            "SP_WIN7": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "MR_MP6+": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "MR_MP3-5": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "MR_MP2": {"credentials": {"host_user": "", "host_pass": "", "host_port": "",}},
            "MR_GP": {"credentials": {"host_user": "", "host_pass": "", "host_port": "",}},
            "CT_SCAN": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "UL": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "VL": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "XR": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}},
            "CT_DISPLAY": {"credentials": {"host_user": "", "host_pass": "", "host_port": ""}}
        }
        key = generate_key(key_path)
        encrypt_json(default_data, key, enc_path)
        return default_data

    key = load_key(key_path)
    config = decrypt_json(enc_path, key)
    section_map = {
        "user": "USER",
        "SP_WIN10": "SP_WIN10",
        "SP_WIN7": "SP_WIN7",
        "MR_MP6+": "MR_MP6+",
        "MR_MP3-5": "MR_MP3-5",
        "MR_MP2": "MR_MP2",
        "MR_GP": "MR_GP",
        "CT_SCAN": "CT_SCAN",
        "UL": "UL",
        "VL": "VL",
        "XR": "XR",
        "CT_DISPLAY": "CT_DISPLAY"
    }
    normalized_updates = {}
    for section, data in updates.items():
        norm_section = section_map.get(section.lower(), section)
        normalized_updates[norm_section] = data

    for section, data in normalized_updates.items():
        if section in config:
            if section in ["USER", "SP_WIN10"]:
                config[section].update(data)
            else:
                config[section]["credentials"].update(data.get("credentials", {}))
        else:
            config[section] = data

    encrypt_json(config, key, enc_path)
    return config
# ----------------------------------------------------------------------