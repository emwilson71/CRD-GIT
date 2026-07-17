# ------------------------------------------------------------------------
"""X
sm_matrix.py
Call for sw version compatibility for scripts
Version 1.02 Updated 08/14/25   
"""
# ------------------------------------------------------------------------
import os
import json
import re
from cryptography.fernet import Fernet
from pathlib import Path
from mod_logging import CRDLogger, Paths
# ------------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
def map_version_to_credentials(version: str, credentials_data: dict) -> tuple[str, dict, str, str, str]:
    if "SP" in version.upper():
        cleaned_version = re.sub(r"^(SM\s*)?V?", "", version)
        major_version_match = re.match(r"(\d+)", cleaned_version)
        if major_version_match:
            major_version = int(major_version_match.group(1))
            if major_version == 2:
                creds = credentials_data.get("MR_MP2", {}).get("credentials", {})
                logger.info(f"[MOD SMMTX] Mapped version {version} to MR_MP2")
                return "MR_MP2", creds, "ftp", "telnet", creds.get("host_port", "23")
            elif major_version in [3, 4, 5]:
                creds = credentials_data.get("MR_MP3-5", {}).get("credentials", {})
                logger.info(f"[MOD SMMTX] Mapped version {version} to MR_MP3-5")
                return "MR_MP3-5", creds, "ftp", "telnet", creds.get("host_port", "23")
            elif major_version >= 6:
                creds = credentials_data.get("MR_MP6+", {}).get("credentials", {})
                logger.info(f"[MOD SMMTX] Mapped version {version} to MR_MP6+")
                return "MR_MP6+", creds, "sftp", "ssh", creds.get("host_port", "22")
    creds = credentials_data.get("MR_GP", {}).get("credentials", {})
    logger.info(f"[MOD SMMTX] Mapped version {version} to MR_GP")
    return "MR_GP", creds, "ftp", "telnet", creds.get("host_port", "23")
# ------------------------------------------------------------------------
def load_credentials(config_path: str = "../config") -> tuple[str, str, dict, str, str, str]:
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
            logger.error(f"[MOD SMMTX] No SW_Version Found in {current_file}")
            raise ValueError("No SW_Version Found")
    except FileNotFoundError:
        logger.error(f"[MOD SMMTX] Configuration File Missing {current_file}")
        raise
    logger.info(f"[MOD SMMTX] Detected Version: {version}")
    key_file = config_path / "user.key"
    try:
        with key_file.open('rb') as f:
            key = f.read()
    except FileNotFoundError:
        logger.error(f"[MOD SMMTX] Key Not Found {key_file}")
        raise
    try:
        fernet = Fernet(key)
    except Exception as e:
        logger.error(f"[MOD SMMTX] Invalid Key {str(e)}")
        raise
    enc_file = config_path / "user.enc"
    try:
        with enc_file.open('rb') as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        logger.error(f"[MOD SMMTX] Encrypted Credentials Missing {enc_file}")
        raise
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials_data = json.loads(decrypted_data.decode())
    except Exception as e:
        logger.error(f"[MOD SMMTX] Decrypt Credentials {str(e)}")
        raise
    version_key, credentials, file_protocol, term_protocol, host_port = map_version_to_credentials(version, credentials_data)
   
    if not credentials:
        logger.error(f"[MOD SMMTX] Missing Credentials {version}")
        raise ValueError(f"Missing Credentials {version}")
    logger.info(f"[MOD SMMTX] Successfully Loaded {version_key}")
    return version, version_key, credentials, file_protocol, term_protocol, host_port
# ------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        version, version_key, creds, file_proto, term_proto, port = load_credentials()
        logger.info(f"[MOD SMMTX] Version: {version}")
        logger.info(f"[MOD SMMTX] Version Key: {version_key}")
        logger.info(f"[MOD SMMTX] Credentials: {creds}")
        logger.info(f"[MOD SMMTX] File Protocol: {file_proto}")
        logger.info(f"[MOD SMMTX] Terminal Protocol: {term_proto}")
        logger.info(f"[MOD SMMTX] Host Port: {port}")
    except Exception as e:
        logger.error(f"[MOD SMMTX] Script failed: {str(e)}")
        raise
# ------------------------------------------------------------------------