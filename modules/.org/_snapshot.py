# ------------------------------------------------------------------------
"""X
savelog.py
Maps to current sw version for snapshot
ewilson@us.medical.canon 08/14/25
"""
# ------------------------------------------------------------------------
import os
import sys
import subprocess
from mod_logging import CRDLogger
import mod_sm_matrix
# ------------------------------------------------------------------------
def run_snapshot_script(version_key, logger):
    script_map = {
        'MR_GP': 'snapshotGP.py',
        'MR_MP2': 'snapshot2.py',
        'MR_MP3-5': 'snapshot35.py',
        'MR_MP6+': 'snapshotMP6.py'
    }
   
    script_name = script_map.get(version_key)
    if not script_name:
        logger.error(f"Invalid Key: {version_key}")
        sys.exit(1)
   
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    if not os.path.isfile(script_path):
        logger.error(f"Script {script_name} Not Found at {script_path}")
        sys.exit(1)
   
    try:
        process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logger.info(f"Started {script_name} For {version_key}")
        stdout, stderr = process.communicate(timeout=3600) 
        if stderr:
            logger.error(f"Error From {script_name}: {stderr}")
        if process.returncode != 0:
            logger.error(f"{script_name} Exited With Code {process.returncode}")
            sys.exit(process.returncode)
        logger.info(f"{script_name} Completed Successfully")
        sys.exit(0)
    except subprocess.TimeoutExpired:
        logger.warning(f"{script_name} Timed Out")
        process.terminate()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error Running {script_name}: {e}")
        sys.exit(1)
# ------------------------------------------------------------------------
def main():
    crd_logger = CRDLogger("CRD")
    logger = crd_logger.get_logger()
    
    try:
        version, version_key, creds, file_proto, term_proto, port = sm_matrix.load_credentials()
        logger.info(f"Loaded Version: {version}, {version_key}, {term_proto}")
        run_snapshot_script(version_key, logger)
    except Exception as e:
        logger.error(f"Failed to Run Script: {str(e)}")
        sys.exit(1)
if __name__ == "__main__":
    main()
# ------------------------------------------------------------------------