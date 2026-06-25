import re
import json
import requests

ENV_FILE = ".env"

def load_configs(env_path: str = ENV_FILE) -> dict:
    configs = {}
    with open(env_path, "r") as f:
        content = f.read()

    pattern = re.compile(r"(\w+_CONFIG)\s*=\s*(\{.*?\})", re.DOTALL)
    for match in pattern.finditer(content):
        key = match.group(1)
        raw = re.sub(r'(?<!["\w])REPOS(?!\s*")', '"REPOS"', match.group(2))
        try:
            configs[key] = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[WARN] Could not parse {key}: {e}")
    return configs


def set_repo_visibility(token: str, repo: str, private: bool) -> None:
    owner, name = repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{name}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.patch(url, headers=headers, json={"private": private})
    status = "private" if private else "public"
    if resp.status_code == 200:
        print(f"  [OK]   {repo}  →  {status}")
    else:
        print(f"  [ERR]  {repo}  →  {resp.status_code} {resp.json().get('message', '')}")


while True:
    visibility = input("Type public or private: ").strip().lower()
    if visibility in ("public", "private"):
        break
    print("Invalid input. Please type 'public' or 'private'.")

private = visibility == "private"
configs = load_configs()

for key, config in configs.items():
    token = config.get("GIT_TOKEN", "")
    repos = config.get("REPOS", [])
    print(f"\n[{key}] Setting {len(repos)} repo(s) to {visibility} …")
    for repo in repos:
        set_repo_visibility(token, repo, private)
