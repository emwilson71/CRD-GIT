import os
import re
import csv
import datetime
import logging
import sys


# Get directory where the script/.exe is located
if getattr(sys, 'frozen', False):
    # Running as compiled .exe (PyInstaller)
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # Running as .py/.pyw script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------
# Logging setup – logs to same folder as the .exe/script
# Deletes old log on every start, creates fresh one
# ----------------------------------------------------------------------

LOG_FILE = os.path.join(SCRIPT_DIR, "Avg_Pwr_Updater.log")

# Delete old log if it exists
if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
    except Exception as e:
        print(f"Warning: Could not delete old log: {e}")

# Set up fresh logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    filename=LOG_FILE,
    filemode='w',  # 'w' = overwrite (fresh log)
    encoding='utf-8'
)

# Optional: Also print to console *if* there is one
if sys.stdin and sys.stdin.isatty():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
    logging.getLogger().addHandler(console_handler)


def log_info(msg):
    logging.info(msg)

def log_error(msg):
    logging.error(msg)

# ----------------------------------------------------------------------
# Load directory from INI to point to _tui.dir
# ----------------------------------------------------------------------
BASE_DIR = r"C:\InnerVision.dir"
INI_FILE = os.path.join(BASE_DIR, "Comm.dir", "Ini.dir", "SpSite.ini")

def load_output_dir():
    try:
        with open(INI_FILE, 'r') as file:
            lines = file.readlines()
        
        site_id = None
        modality_dir = None
        
        for line in reversed(lines):
            line = line.strip()
            if not site_id and re.match(r'^\[.*\]$', line):
                site_id = line.strip('[]')
            elif not modality_dir and line.startswith('ModalityDir='):
                modality_dir = line.split('=')[1].strip()
            if site_id and modality_dir:
                break
        
        if not site_id or not modality_dir:
            raise ValueError("Could not find SiteId or ModalityDir in SpSite.ini")
        
        tui_dir = os.path.join(BASE_DIR, modality_dir, site_id, "_tui.dir")
        log_info(f"Loaded TUI directory: {tui_dir}")
        return tui_dir

    except Exception as e:
        log_error(f"Error determining output directory from {INI_FILE}: {e}")
        return None

# ----------------------------------------------------------------------
# Main update logic
# ----------------------------------------------------------------------
def update_pwr(tui_dir):
    try:
        now = datetime.datetime.now()
        year_dir = os.path.join(tui_dir, str(now.year))
        log_info(f"Looking in year directory: {year_dir}")

        if not os.path.exists(year_dir):
            log_error(f"Year directory not found: {year_dir}")
            return
        
        # Find all SVU log files (format: *_SVU_FULL_LOG.csv)
        files = [f for f in os.listdir(year_dir) 
                if f.endswith('_SVU_FULL_LOG.csv') and len(f.split('_')[0]) == 17]
        
        if not files:
            log_error(f"No SVU log files found in {year_dir}")
            return
        
        # Get newest SVU Log File
        newest = max(files)
        svu_path = os.path.join(year_dir, newest)
        log_info(f"Processing newest SVU log: {svu_path}")

        # Read and parse SVU log
        with open(svu_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if len(rows) < 3:
            log_error(f"SVU log has insufficient rows: {svu_path}")
            return
        
        data_rows = rows[1:-1]  # Skip header and last blank row
        max_powers = {}

        for row in data_rows:
            if len(row) < 7:
                continue
            dt_str = row[1]
            try:
                date_part = dt_str.split(' ')[0].replace('/', '-')  # e.g., 2025-06-11
                power = float(row[6])  # Column 7: HeaterPower(W)
                if date_part not in max_powers or power > max_powers[date_part]:
                    max_powers[date_part] = power
            except (ValueError, IndexError):
                continue
        
        if not max_powers:
            log_info("No valid power data found in SVU log")
            return
        
        log_info(f"Found max power for {len(max_powers)} dates")

        # Load VisartConditionHistory2.csv
        history_path = os.path.join(tui_dir, 'VisartConditionHistory2.csv')
        if not os.path.exists(history_path):
            log_error(f"History file not found: {history_path}")
            return
        
        log_info(f"Loading history file: {history_path}")
        with open(history_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if len(rows) < 2:
            log_error(f"History file has insufficient rows: {history_path}")
            return
        
        headers = rows[0]
        data_rows = rows[1:]
        updated_count = 0

        for row in data_rows:
            if len(row) < 21:
                continue
            file_dt = row[0]
            try:
                date_part = file_dt.split(' ')[0].replace('/', '-')  # Match format
                if date_part in max_powers and not row[20].strip():
                    row[20] = f"{max_powers[date_part]:.2f}"
                    updated_count += 1
            except:
                continue
        
        if updated_count > 0:
            # Write back updated file
            with open(history_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data_rows)
            log_info(f"Updated {updated_count} Pwr values in {history_path}")
        else:
            log_info("No updates needed (all Pwr values already filled or no match)")

    except Exception as e:
        log_error(f"Unexpected error in update_pwr: {e}")

# ----------------------------------------------------------------------
# Main entry point – runs immediately on double-click
# ----------------------------------------------------------------------
if __name__ == "__main__":
    log_info("=== Avg_Pwr_Updater STARTED ===")
    
    tui_dir = load_output_dir()
    if not tui_dir:
        log_error("Cannot proceed: failed to load TUI directory")
        sys.exit(1)
    
    update_pwr(tui_dir)
    
    log_info("=== Avg_Pwr_Updater FINISHED ===")