import json
import os
import subprocess
import threading
import requests
import boto3
from botocore.client import Config
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import dotenv_values
import re

config = dotenv_values(".env")

def parse_config(raw: str) -> dict:
    fixed = re.sub(r'(?<!["\w])REPOS(?!\s*")', '"REPOS"', raw)
    return json.loads(fixed)

SR1279 = parse_config(config['SR1279_CONFIG'])
TSH483 = parse_config(config['TSH483_CONFIG'])
lucky319193 = parse_config(config['lucky319193_CONFIG'])
yuriidev07 = parse_config(config['yuriidev07_CONFIG'])

yuriidev07_s3_client = boto3.client(
    "s3",
    endpoint_url=yuriidev07['ENDPOINT_URL'],
    aws_access_key_id=yuriidev07['ACCESS_KEY_ID'],
    aws_secret_access_key=yuriidev07['SECRET_ACCESS_KEY'],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

SR1279_s3_client = boto3.client(
    "s3",
    endpoint_url=SR1279['ENDPOINT_URL'],
    aws_access_key_id=SR1279['ACCESS_KEY_ID'],
    aws_secret_access_key=SR1279['SECRET_ACCESS_KEY'],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

lucky319193_s3_client = boto3.client(
    "s3",
    endpoint_url=lucky319193['ENDPOINT_URL'],
    aws_access_key_id=lucky319193['ACCESS_KEY_ID'],
    aws_secret_access_key=lucky319193['SECRET_ACCESS_KEY'],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

client_targets = [
    (SR1279_s3_client,       "SR1279"),
    (yuriidev07_s3_client,   "yuriidev07"),
    (lucky319193_s3_client,  "lucky319193"),
]

# Accounts owned by the operator — used to distinguish own commits from competitors
OWN_ACCOUNTS = {"yuriidev07", "SR1279", "lucky319193", "TSH483", "Gael1125"}


def upload_to_r2_single(client, js_filename, local_path, bucket_folder_name):
    r2_object_key = f"{bucket_folder_name}/{js_filename}"
    client.upload_file(local_path, "sn17", r2_object_key)
    print(f"Uploaded '{js_filename}' → sn17/{r2_object_key}")


def clear_r2_folder(client, account_name, bucket_folder_name):
    prefix = f"{bucket_folder_name}/"
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket="sn17", Prefix=prefix)

    deleted = 0
    for page in pages:
        objects = page.get("Contents", [])
        if not objects:
            continue
        delete_payload = {"Objects": [{"Key": obj["Key"]} for obj in objects if obj["Key"] != prefix]}
        if not delete_payload["Objects"]:
            continue
        client.delete_objects(Bucket="sn17", Delete=delete_payload)
        deleted += len(objects)

    print(f"🗑️  Cleared {deleted} object(s) from {account_name}/sn17/{prefix}")


def is_github_file_downloadable(repo_url):
    raw_url = repo_url.replace('/blob/', '/raw/') if '/blob/' in repo_url else repo_url
    try:
        response = requests.head(raw_url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            response = requests.get(raw_url, timeout=10, stream=True)
            return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error checking file: {e}")
        return False


def download_github_file(url, round_number):
    raw_url = url.replace("/blob/", "/raw/")
    response = requests.get(raw_url)
    with open(f"rounds/{round_number}/prompts.txt", "w") as f:
        f.write(response.text)


def list_all(round_number: int) -> tuple[list[dict], list[dict]]:
    """
    Calls 404-cli list-all and splits results into:
      - own_commits:        entries belonging to OWN_ACCOUNTS (includes commit_block)
      - competitor_commits: all other valid entries with a cdn_url
    """
    result = subprocess.run(
        ["404-cli", "list-all"],
        input=str(round_number),
        capture_output=True,
        text=True,
    )
    own_commits = []
    competitor_commits = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
            if not entry.get("repo"):
                continue
            owner = entry["repo"].split("/")[0]
            if owner in OWN_ACCOUNTS:
                own_commits.append(entry)
            elif entry.get("cdn_url"):
                competitor_commits.append(entry)
        except (json.JSONDecodeError, KeyError):
            continue
    return own_commits, competitor_commits


def build_assignment(
    own_commits: list[dict],
    competitor_commits: list[dict],
) -> dict[tuple[str, str], dict]:
    """
    Builds a per-slot source descriptor:
      (account_name, folder) -> {cdn_url, source_repo, source_hotkey, source_commit_block}

    Rules:
      - Source commit_block must be STRICTLY GREATER than the slot's own commit_block
        (so the operator's commit appears first on-chain, avoiding copier detection).
      - Each slot is assigned a UNIQUE competitor (no two slots share the same primary
        source, preventing cross-detection between own hotkeys).
    """
    client_accounts = {name for _, name in client_targets}

    # Parse own commit_block per (account, folder) slot
    own_by_slot: dict[tuple[str, str], int] = {}
    for entry in own_commits:
        account = entry["repo"].split("/")[0]
        if account not in client_accounts:
            continue
        m = re.search(r'/(h\d)/', entry.get("cdn_url", ""))
        if not m:
            continue
        folder = m.group(1)
        key = (account, folder)
        # Keep the highest commit_block seen for this slot (robustness)
        own_by_slot[key] = max(own_by_slot.get(key, 0), entry.get("commit_block", 0))

    if not own_by_slot:
        print("⚠️  No own commits found on-chain yet. Cannot determine commit_block ordering.")

    # Sort competitors by commit_block ascending so we pick the "just-later" commits first
    sorted_comps = sorted(competitor_commits, key=lambda x: x.get("commit_block", 0))

    assignment: dict[tuple[str, str], dict] = {}
    used_primary: set[str] = set()  # competitor hotkeys already chosen as a primary

    # Process slots with the tightest constraint first (lowest own commit_block)
    for (account, folder), own_cb in sorted(own_by_slot.items(), key=lambda x: x[1]):
        eligible = [
            c for c in sorted_comps
            if c.get("commit_block", 0) > own_cb and c.get("cdn_url")
        ]
        if not eligible:
            print(f"⚠️  No eligible competitor (later commit_block) for ({account}, {folder}) [own_block={own_cb}]")
            continue

        # Pick the first unused eligible competitor as the unique primary
        primary = None
        for comp in eligible:
            if comp["hotkey"] not in used_primary:
                primary = comp
                used_primary.add(comp["hotkey"])
                break
        if primary is None:
            # All eligible competitors already used as primaries elsewhere — reuse the best one
            primary = eligible[0]
            print(f"⚠️  Exhausted unique competitors for ({account}, {folder}); reusing {primary['cdn_url']}")

        assignment[(account, folder)] = {
            "cdn_url": primary["cdn_url"],
            "source_repo": primary.get("repo", ""),
            "source_hotkey": primary.get("hotkey", ""),
            "source_commit_block": primary.get("commit_block", 0),
        }
        print(
            f"  ({account}, {folder}) [own_block={own_cb}]"
            f" → {primary.get('repo', '?')} @ block {primary.get('commit_block')} ({primary['cdn_url']})"
        )

    return assignment


if __name__ == "__main__":
    round_number = input("Enter the round number: ")

    os.makedirs(f"rounds/{round_number}", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    # Fetch on-chain commit data first so we know exactly which slots are active
    own_commits, competitor_commits = list_all(round_number)
    print(f"Found {len(own_commits)} own commit(s) and {len(competitor_commits)} competitor commit(s)")

    # Derive the active (account, folder) slots from own commits only
    client_accounts = {name for _, name in client_targets}
    active_slots: list[tuple[str, str]] = []
    for entry in own_commits:
        account = entry["repo"].split("/")[0]
        if account not in client_accounts:
            continue
        m = re.search(r'/(h\d)/', entry.get("cdn_url", ""))
        if m:
            slot = (account, m.group(1))
            if slot not in active_slots:
                active_slots.append(slot)

    print(f"Active slots from own commits: {sorted(active_slots)}")

    # Clear only the R2 folders that correspond to active slots
    print("\n🗑️  Clearing active R2 folders...")
    client_by_account = {name: client for client, name in client_targets}
    clear_tasks = [
        (client_by_account[account], account, folder)
        for account, folder in active_slots
    ]
    with ThreadPoolExecutor(max_workers=max(len(clear_tasks), 1)) as executor:
        futures = [
            executor.submit(clear_r2_folder, client, account_name, folder)
            for client, account_name, folder in clear_tasks
        ]
        for future in as_completed(futures):
            future.result()
    print("✅ Active R2 folders cleared")

    # Build the per-slot source assignment (unique primary per slot, later commit_block only)
    print("\nBuilding per-slot assignment...")
    assignment = build_assignment(own_commits, competitor_commits)
    print(f"\n✅ Assignment built for {len(assignment)} / {len(active_slots)} slot(s)\n")

    # Save the assignment for debugging
    with open(f"rounds/{round_number}/assignment.json", "w") as f:
        json.dump({f"{acc}/{fld}": info for (acc, fld), info in assignment.items()}, f, indent=2)

    # Build own-commit info lookup keyed by (account, folder)
    own_info_by_slot: dict[tuple[str, str], dict] = {}
    for entry in own_commits:
        account = entry["repo"].split("/")[0]
        if account not in client_accounts:
            continue
        m = re.search(r'/(h\d)/', entry.get("cdn_url", ""))
        if not m:
            continue
        folder = m.group(1)
        key = (account, folder)
        if key not in own_info_by_slot or entry.get("commit_block", 0) > own_info_by_slot[key]["own_commit_block"]:
            own_info_by_slot[key] = {
                "own_repo": entry["repo"],
                "own_hotkey": entry.get("hotkey", ""),
                "own_commit_block": entry.get("commit_block", 0),
            }

    # Initialise copy_log — one entry per slot, updated as files are uploaded
    copy_log_lock = threading.Lock()
    copy_log: dict[str, dict] = {}
    for (account, folder), slot_info in assignment.items():
        key = f"{account}/{folder}"
        own_info = own_info_by_slot.get((account, folder), {})
        copy_log[key] = {
            "own_repo": own_info.get("own_repo", account),
            "own_hotkey": own_info.get("own_hotkey", ""),
            "own_commit_block": own_info.get("own_commit_block", 0),
            "source_repo": slot_info["source_repo"],
            "source_hotkey": slot_info["source_hotkey"],
            "source_commit_block": slot_info["source_commit_block"],
            "source_cdn_url": slot_info["cdn_url"],
            "files_copied": [],
        }
    print("\n📋 Copy log initialised:")
    for key, entry in copy_log.items():
        print(f"  {entry['own_repo']} ← {entry['source_repo']} (block {entry['source_commit_block']})")

    # Wait until the round's prompt and seed files are published on GitHub
    prompt_url = f"https://github.com/404-Repo/404-active-competition/blob/main/rounds/{round_number}/prompts.txt"
    seed_url   = f"https://github.com/404-Repo/404-active-competition/blob/main/rounds/{round_number}/seed.json"

    while True:
        if is_github_file_downloadable(prompt_url) and is_github_file_downloadable(seed_url):
            print("✅ Both files are downloadable")
            download_github_file(prompt_url, round_number)
            break
        print("Prompts and seeds file are not downloadable yet — retrying in 1s")
        time.sleep(1)

    with open(f"rounds/{round_number}/prompts.txt", "r") as f:
        prompt_urls = f.readlines()

    prompt_status: dict[str, bool] = {}
    for line in prompt_urls:
        filename = line.strip().split("/")[-1]
        if filename:
            prompt_status[filename] = False

    def process_prompt(png_filename: str) -> tuple[str, bool]:
        """
        For each assigned (account, folder) slot, independently fetch the JS file
        from that slot's assigned competitor CDN and upload it to that folder only.
        Returns (png_filename, all_slots_succeeded).
        """
        js_filename = png_filename.rsplit('.png', 1)[0] + '.js'

        def fetch_and_upload(account: str, folder: str, slot_info: dict) -> bool:
            cdn_url = slot_info["cdn_url"]
            cdn_file_url = cdn_url.rstrip("/") + "/" + js_filename
            try:
                r = requests.get(cdn_file_url, timeout=15)
            except requests.exceptions.RequestException as e:
                print(f"  ✗ [{account}/{folder}] request error: {e}")
                return False
            if r.status_code == 200:
                local_path = f"downloads/{account}_{folder}_{js_filename}"
                with open(local_path, "wb") as f:
                    f.write(r.content)
                upload_to_r2_single(client_by_account[account], js_filename, local_path, folder)
                with copy_log_lock:
                    copy_log[f"{account}/{folder}"]["files_copied"].append(js_filename)
                return True
            return False

        slot_tasks = [
            (account, folder, slot_info)
            for (account, folder), slot_info in assignment.items()
            if account in client_by_account
        ]

        all_slots_succeeded = True
        with ThreadPoolExecutor(max_workers=min(len(slot_tasks), 20)) as executor:
            futures = {
                executor.submit(fetch_and_upload, account, folder, slot_info): (account, folder)
                for account, folder, slot_info in slot_tasks
            }
            for future in as_completed(futures):
                if not future.result():
                    all_slots_succeeded = False

        if not all_slots_succeeded:
            print(f"  ✗ {js_filename}: one or more slots not yet available — will retry")

        return png_filename, all_slots_succeeded

    attempt = 0
    total = len(prompt_status)
    while True:
        done_count = sum(prompt_status.values())

        if done_count == total:
            print("✅ All 128 files completed across all slots")
            break

        pending = [fname for fname, done in prompt_status.items() if not done]
        attempt += 1
        print(f"\n🔄 Attempt {attempt} — {done_count}/{total} done, {len(pending)} pending")

        with ThreadPoolExecutor(max_workers=min(len(pending), 8)) as executor:
            futures = {executor.submit(process_prompt, fname): fname for fname in pending}
            for future in as_completed(futures):
                fname, result = future.result()
                prompt_status[fname] = result

        done_count = sum(prompt_status.values())
        print(f"📊 Progress: {done_count}/{total} files completed")

        if done_count < total:
            time.sleep(2)

    copy_log_path = f"rounds/{round_number}/copy_log.json"
    with open(copy_log_path, "w") as f:
        json.dump(copy_log, f, indent=2)
    print(f"\n📋 Copy log saved → {copy_log_path}")
    for key, entry in copy_log.items():
        print(f"  {entry['own_repo']} ← {entry['source_repo']}: {len(entry['files_copied'])} file(s) copied")
