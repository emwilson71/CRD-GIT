import os
import subprocess
import sys

def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Error:", result.stderr)
    return result.returncode == 0

def deploy():
    os.chdir(r"C:\CRD-GIT")
    
    print("=== CRD Deploy Script ===")
    run_command("git add .")
    
    status = subprocess.getoutput("git status --porcelain")
    if status:
        message = input("Enter commit message: ") or "Auto update from deploy"
        run_command(f'git commit -m "{message}"')
    else:
        print("No changes to commit.")
        return
    
    # Push
    if run_command("git push"):
        print("✅ Successfully pushed to GitHub!")
    else:
        print("❌ Push failed. Run 'git pull' manually if needed.")

if __name__ == "__main__":
    deploy()