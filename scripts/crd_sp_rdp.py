# ------------------------------------------------------------------------
"""
crd_sp_rdp.py (ew)
SP RDP for WIN10
- Needs to use enc credentials and variable for screen size
Version 1.0 Updated 07/08/26
"""
# ------------------------------------------------------------------------
# LIBRARIES
import subprocess
import os
import time
import threading
import logging
# MODULES
from crd_embedded import CustomMessageBox, Paths, CRDLogger
# ------------------------------------------------------------------------
crd_logger = CRDLogger("CRD")
logger = crd_logger.get_logger()
# ------------------------------------------------------------------------
# DEFINE RDP FILE
def create_rdp_file(ip, username, password, filepath="temp.rdp"):
    rdp_content = f"""screen mode id:i:1
                    use multimon:i:0
                    desktopwidth:i:1920
                    desktopheight:i:1080
                    session bpp:i:32
                    winposstr:s:0,3,0,0,800,600
                    compression:i:1
                    keyboardhook:i:2
                    audiocapturemode:i:0
                    videoplaybackmode:i:1
                    connection type:i:7
                    networkautodetect:i:1
                    bandwidthautodetect:i:1
                    displayconnectionbar:i:1
                    enableworkspacereconnect:i:0
                    disable wallpaper:i:0
                    allow font smoothing:i:0
                    allow desktop composition:i:0
                    disable full window drag:i:1
                    disable menu anims:i:1
                    disable themes:i:0
                    disable cursor setting:i:0
                    bitmapcachepersistenable:i:1
                    full address:s:{ip}
                    audiomode:i:0
                    redirectprinters:i:1
                    redirectcomports:i:0
                    redirectsmartcards:i:1
                    redirectclipboard:i:1
                    redirectposdevices:i:0
                    autoreconnection enabled:i:1
                    authentication level:i:2
                    prompt for credentials:i:0
                    negotiate security layer:i:1
                    remoteapplicationmode:i:0
                    alternate shell:s:
                    shell working directory:s:
                    gatewayhostname:s:
                    gatewayusagemethod:i:4
                    gatewaycredentialssource:i:4
                    gatewayprofileusagemethod:i:0
                    promptcredentialonce:i:0
                    gatewaybrokeringtype:i:0
                    use redirection server name:i:0
                    rdgiskdcproxy:i:0
                    kdcproxyname:s:
                    username:s:{username}
                    password 51:s:{password}
                    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(rdp_content)
        return filepath
    except OSError as e:
        logger.error(f"[SP_RDP] Failed To Create RDP File {filepath}: {str(e)}")
        raise
# ------------------------------------------------------------------------
def launch_rdp(ip, username, password):
    try:
        if not ip:
            raise ValueError("IP Address Missing")
        rdp_file = create_rdp_file(ip, username, password)
        cmdkey_cmd = f'cmdkey /generic:TERMSRV/{ip} /user:{username} /pass:{password}'
        result = os.system(cmdkey_cmd)
        if result != 0:
            raise RuntimeError(f"cmdkey Failed With Exit Code {result}")
        process = subprocess.Popen(["mstsc", rdp_file])
        logger.info(f"[SP_RDP] MSTSC Started {process.pid}")
        
        time.sleep(2)
        if process.poll() is not None:
            raise RuntimeError(f"MSTSC Failed {process.returncode}")

        def cleanup_cmdkey(host):
            time.sleep(60)
            os.system(f'cmdkey /delete:TERMSRV/{host}')
            logger.info(f"[SP_RDP] Deleted TERMSRV/{host}")
        threading.Thread(target=cleanup_cmdkey, args=(ip,), daemon=True).start()
# REMOVE TEMP FILE
        try:
            os.remove(rdp_file)
        except OSError as e:
            logger.info(f"[SP_RDP] Failed to delete RDP file {rdp_file}: {str(e)}")
        return True
    except Exception as e:
        logger.error(f"[SP_RDP] Failed To Launch RDP: {str(e)}")
        raise
# ------------------------------------------------------------------------
if __name__ == "__main__":
    ip_address = ""
    username = "IV_Service_User"
    password = "SU_InnerVision2020"    
    launch_rdp(ip_address, username, password)
# ------------------------------------------------------------------------