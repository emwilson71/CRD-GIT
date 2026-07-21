"""/
mr_matrix.py
Maps the sw version to connectivity
WIP
"""
import json
import os
import re
import telnetlib
import paramiko

def parse_current_dat(file_path):
    config = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
        return config
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return None
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def determine_system_type(sw_version):
    if sw_version.startswith('9.'):
        return 'SM3'
    elif 'SP' in sw_version:
        if sw_version.startswith(('V2', 'V3', 'V4', 'V5')):
            return 'SM2'
        elif sw_version.startswith('V6') or sw_version.startswith('V7') or sw_version.startswith('V8') or sw_version.startswith('V9'):
            return 'SM1'
    return None

def load_matrix_config(json_path):
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {json_path} not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing {json_path}: {e}")
        return None

def connect_telnet(host, port, username, password):
    try:
        tn = telnetlib.Telnet(host, port, timeout=10)
        tn.read_until(b"login: ", timeout=5)
        tn.write(username.encode('ascii') + b"\n")
        tn.read_until(b"Password: ", timeout=5)
        tn.write(password.encode('ascii') + b"\n")
        output = tn.read_some().decode('ascii')
        print("Telnet connection established.")
        return tn
    except Exception as e:
        print(f"Telnet connection failed: {e}")
        return None

def connect_ssh(host, port, username, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        print("SSH connection established.")
        return ssh
    except Exception as e:
        print(f"SSH connection failed: {e}")
        return None

def main():
    current_dat_path = '../config/current.dat'
    matrix_json_path = '../config/mr_matrix.json'

    # Read current.dat
    config = parse_current_dat(current_dat_path)
    if not config:
        return

    # Determine system type
    sw_version = config.get('SW_Version', '')
    system_type = determine_system_type(sw_version)
    if not system_type:
        print(f"Error: Could not determine system type from SW_Version: {sw_version}")
        return


    matrix_config = load_matrix_config(matrix_json_path)
    if not matrix_config:
        return

    settings = matrix_config.get(system_type)
    if not settings:
        print(f"Error: No settings found for system type {system_type}")
        return

    host = config.get('Host_IP', '')
    port = int(settings.get('port', 0))
    username = settings.get('user', '')
    password = settings.get('pass', '')
    mode = settings.get('mode', '')

    if not host or not port:
        print("Error: Host_IP or port not specified.")
        return

    if mode == 'ssh':
        connection = connect_ssh(host, port, username, password)
    elif mode == 'telnet':
        connection = connect_telnet(host, port, username, password)
    else:
        print(f"Error: Unsupported connection mode: {mode}")
        return

    if connection:
        print(f"Connected to {host} via {mode} as {system_type}")
        connection.close()

if __name__ == "__main__":
    main()