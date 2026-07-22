import requests, os
token = os.environ.get("CRD_GITHUB_TOKEN") or "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"
r = requests.get(
    "https://raw.githubusercontent.com/emwilson71/CRD-GIT/main/config/versions.json",
    headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"},
    timeout=10
)
print(r.status_code)
print(r.text[:300] if r.ok else r.text)