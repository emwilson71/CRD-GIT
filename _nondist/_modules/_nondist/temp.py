import os
import json
import logging
import re
from cryptography.fernet import Fernet
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

def map_version_to_credentials(version: str, credentials_data: dict) -> tuple[dict, str, str, str, dict]:
    if "SP" in version:
        cleaned_version = re.sub(r"^(SM V)?", "", version)
        major_version = re.match(r"(\d+)", cleaned_version)
        if major_version:
            major_version = int(major_version.group(1))
            if major_version == 2:
                creds = credentials_data.get("MR_MP2", {}).get("credentials", {})
                return creds, "ftp", "telnet", creds.get("host_port", "23"), credentials_data.get("SP_WIN10", {}).get("credentials", {})
            elif major_version in [3, 4, 5]:
                creds = credentials_data.get("MR_MP3-5", {}).get("credentials", {})
                return creds, "ftp", "telnet", creds.get("host_port", "23"), credentials_data.get("SP_WIN10", {}).get("credentials", {})
            elif major_version >= 6:
                creds = credentials_data.get("MR_MP6+", {}).get("credentials", {})
                return creds, "sftp", "ssh", creds.get("host_port", "22"), credentials_data.get("SP_WIN10", {}).get("credentials", {})
    creds = credentials_data.get("MR_GP", {}).get("credentials", {})
    return creds, "ftp", "telnet", creds.get("host_port", "23"), credentials_data.get("SP_WIN10", {}).get("credentials", {})

def load_credentials(config_path: str = "../config") -> tuple[str, dict, str, str, str, dict]:
    config_path = Path(config_path).resolve()
    current_file = config_path / "current.dat"
    version = None
    try:
        with current_file.open('r') as f:
            for line in f:
                if line.strip().startswith("SW_Version="):
                    version = line.strip().split("=")[1]
                    break
        if not version:
            raise ValueError("No SW_Version specified in current.dat")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {current_file}")
        raise
    except Exception as e:
        logger.error(f"Error reading current.dat: {str(e)}")
        raise ValueError(f"Failed to read current.dat: {str(e)}")
    
    logger.info(f"Detected version: {version}")
    key_file = config_path / "user.key"
    try:
        with key_file.open('rb') as f:
            key = f.read()
    except FileNotFoundError:
        logger.error(f"Key file not found: {key_file}")
        raise FileNotFoundError(f"Key file not found: {key_file}")
    
    try:
        fernet = Fernet(key)
    except Exception as e:
        logger.error(f"Invalid encryption key: {str(e)}")
        raise ValueError(f"Invalid encryption key: {str(e)}")
    
    enc_file = config_path / "user.enc"
    try:
        with enc_file.open('rb') as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        logger.error(f"Encrypted credentials file not found: {enc_file}")
        raise FileNotFoundError(f"Encrypted credentials file not found: {enc_file}")
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials_data = json.loads(decrypted_data.decode())
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {str(e)}")
        raise ValueError(f"Failed to decrypt credentials: {str(e)}")
    
    sm_credentials, file_protocol, term_protocol, host_port, sp_credentials = map_version_to_credentials(version, credentials_data)
    
    if not sm_credentials:
        logger.error(f"No SM credentials found for version: {version}")
        raise KeyError(f"No SM credentials found for version: {version}")
    if not sp_credentials:
        logger.warning(f"No SP credentials found for version: {version}")
    
    logger.info(f"Successfully loaded credentials for version {version}")
    return version, sm_credentials, file_protocol, term_protocol, host_port, sp_credentials