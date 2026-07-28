# ------------------------------------------------------------------------
"""
GITHUB DEPLOYMENT WRAPPER
"""
import os
import subprocess
import sys
# ------------------------------------------------------------------------
def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Error ", result.stderr)
    return result.returncode == 0
# ------------------------------------------------------------------------
def deploy():
    os.chdir(r"C:\CRD-GIT")
    print("CRD Deploy Script")
    run_command("git add .")
    
    status = subprocess.getoutput("git status --porcelain")
    if status:
        message = input("Enter Commit Message: ") or "Auto Update From Deploy"
        run_command(f'git commit -m "{message}"')
    else:
        return

    if run_command("git push"):
        print("✅ Successfully Pushed")
    else:
        print("❌ Push Failed. Run 'git pull' Manually")

if __name__ == "__main__":
    deploy()
# ------------------------------------------------------------------------