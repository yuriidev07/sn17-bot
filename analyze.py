import subprocess
import json
import sys
import os
import shutil
import threading
from collections import defaultdict
from typing import Optional

import requests
import yaml

# Resolve 404-cli: prefer the venv next to this repo, then fall back to PATH
_VENV_CLI = os.path.join(os.path.dirname(__file__), "..", "404-cli", ".venv", "bin", "404-cli")
CLI = os.path.normpath(_VENV_CLI) if os.path.isfile(os.path.normpath(_VENV_CLI)) else shutil.which("404-cli") or "404-cli"

GITHUB_RAW = "https://raw.githubusercontent.com/{repo}/{branch}/configuration.yaml"
BRANCHES = ["main", "master"]


def run_list_all(round_number: int) -> list[dict]:
    result = subprocess.run(
        [CLI, "list-all"],
        input=str(round_number),
        capture_output=True,
        text=True,
    )
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def fetch_config_yaml(repo: str) -> Optional[str]:
    for branch in BRANCHES:
        url = GITHUB_RAW.format(repo=repo, branch=branch)
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except requests.RequestException:
            pass
    return None


def extract_models(data) -> list[str]:
    """Recursively collect all values of 'model' keys in a YAML structure."""
    models = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "model" and isinstance(value, str) and value.strip():
                models.append(value.strip())
            else:
                models.extend(extract_models(value))
    elif isinstance(data, list):
        for item in data:
            models.extend(extract_models(item))
    return models


def get_repo_models(repo: str) -> list[str]:
    raw = fetch_config_yaml(repo)
    if raw is None:
        return []
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return []
    seen = set()
    unique = []
    for m in extract_models(data):
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def analyze_commits(round_number: int) -> None:
    entries = run_list_all(round_number)

    # --- Section 1: commit counts per username (lock_sufficient=true) ---
    username_counts: dict[str, int] = defaultdict(int)
    repos_seen: set[str] = set()

    for entry in entries:
        if not entry.get("lock_sufficient", False):
            continue
        repo = entry.get("repo", "")
        if "/" not in repo:
            continue
        username = repo.split("/")[0]
        username_counts[username] += 1
        repos_seen.add(repo)

    print(f"Round {round_number} — commits per username (lock_sufficient=true):\n")
    for username, count in sorted(username_counts.items(), key=lambda x: -x[1]):
        print(f"  {username}: {count}")
    print(f"\nTotal: {sum(username_counts.values())} commits across {len(username_counts)} username(s)")

    # --- Section 2: model names from each repo's configuration.yaml ---
    print(f"\n{'─' * 60}")
    print(f"Models in configuration.yaml ({len(repos_seen)} unique repos):\n")

    repo_models: dict[str, list[str]] = {}
    lock = threading.Lock()

    def fetch_and_store(repo: str) -> None:
        models = get_repo_models(repo)
        with lock:
            repo_models[repo] = models

    threads = [threading.Thread(target=fetch_and_store, args=(r,), daemon=True) for r in sorted(repos_seen)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for repo in sorted(repo_models):
        models = repo_models[repo]
        if models:
            print(f"  {repo}:")
            for m in models:
                print(f"    {m}")
        else:
            print(f"  {repo}: (no configuration.yaml found)")

    # --- Section 3: write JSON output ---
    output = {
        "round": round_number,
        "username_commit_counts": dict(
            sorted(username_counts.items(), key=lambda x: -x[1])
        ),
        "repos": {
            repo: repo_models[repo]
            for repo in sorted(repo_models)
        },
    }

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, f"{round_number}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'─' * 60}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        round_number = int(input("Enter round number: "))
    else:
        round_number = int(sys.argv[1])

    analyze_commits(round_number)
