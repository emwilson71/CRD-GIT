# ------------------------------------------------------------------------
"""
Extracts Script/Module Versions
02/17/26 (ew)
Version 1.1 Updated 07/10/26
"""
# ------------------------------------------------------------------------
import re
import os
import json
# ------------------------------------------------------------------------
def extract_version(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                match = re.match(r'Version\s*([\d.]+)\s*(Updated\s*(\d{2}/\d{2}/\d{2}))?', line)
                if match:
                    version = match.group(1)
                    date = match.group(3)
                    if date:
                        return f"{version} ({date})"
                    return version
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        return None
# ------------------------------------------------------------------------
versions = {}
current_dir = os.path.dirname(os.path.abspath(__file__))
this_script = os.path.basename(__file__)
script_files_current = [f for f in os.listdir(current_dir) if (f.endswith('.py') or f.endswith('.pyw')) and f != this_script]
for filename in script_files_current:
    file_path = os.path.join(current_dir, filename)
    version = extract_version(file_path)
    if version:
        versions[filename] = version
    else:
        pass
    
modules_dir = os.path.join(current_dir, '..', 'modules')
if os.path.exists(modules_dir):
    script_files_modules = [f for f in os.listdir(modules_dir) if f.endswith('.py') or f.endswith('.pyw')]
    for filename in script_files_modules:
        file_path = os.path.join(modules_dir, filename)
        version = extract_version(file_path)
        if version:
            key = os.path.join('modules', filename)
            versions[key] = version
else:
    pass
   
json_dir = os.path.join(current_dir, '..', 'config')
os.makedirs(json_dir, exist_ok=True)
json_path = os.path.join(json_dir, 'versions.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(versions, f, indent=4)
# ------------------------------------------------------------------------