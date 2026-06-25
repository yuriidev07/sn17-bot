import requests
import time
import json
from pathlib import Path
import zipfile
import os
import shutil
import boto3
from botocore.client import Config
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor, as_completed

config = dotenv_values(".env")

def is_github_file_downloadable(repo_url):
    """
    Check if a GitHub file is downloadable.
    
    Args:
        repo_url: GitHub file URL (blob URL)
    
    Returns:
        bool: True if file is downloadable, False otherwise
    """

    if '/blob/' in repo_url:
        raw_url = repo_url.replace('/blob/', '/raw/')
    else:
        raw_url = repo_url
    
    try:
        # Send HEAD request to check without downloading full content
        response = requests.head(raw_url, timeout=10, allow_redirects=True)
        
        # Check if request was successful
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            # Some servers don't support HEAD, try GET with stream
            response = requests.get(raw_url, timeout=10, stream=True)
            return response.status_code == 200
            
    except requests.exceptions.RequestException as e:
        print(f"Error checking file: {e}")
        return False

### download prompts and seeds for specific round from github
def download_files(prompt_url, seed_url, round_id):
    raw_prompt_url = prompt_url.replace("/blob/", "/raw/")
    raw_seed_url = seed_url.replace("/blob/", "/raw/")
    
    prompt_response = requests.get(raw_prompt_url)
    seed_response = requests.get(raw_seed_url)

    with open(f"rounds/{round_id}/prompts.txt", "w") as f:
        f.write(prompt_response.text)
    with open(f"rounds/{round_id}/seed.json", "w") as f:
        f.write(seed_response.text)

def submit_prompt(prompts, seed):
    url = "http://localhost:10006/generate"

    payload = json.dumps({
        "prompts": prompts,
        "seed": seed
    })

    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)

## real-time check the generation result
def check_generation_result():
    url = "http://localhost:10006/status"
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)

    return response.json()['status']

### download results
def download_results(filename):
    url = "http://localhost:10006/results"

    response = requests.get(url, stream=True)

    if response.status_code == 200:
        with open(f"results/{filename}.zip", "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return True
    else:
        return False

### upload a single js file from js/ to R2
def upload_js_file(js_filename, bucket_folder_name, s3_client, bucket_name, account_name):
    r2_object_key = f"{bucket_folder_name}/{js_filename}"
    local_path = f"js/{account_name}/{js_filename}"

    s3_client.upload_file(local_path, bucket_name, r2_object_key)
    print(f"✅ Uploaded '{js_filename}' to R2 '{bucket_folder_name}/'")

def clear_r2_folder(bucket_folder_name, s3_client, bucket_name, account_name):
    prefix = f"{bucket_folder_name}/"
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    deleted = 0
    for page in pages:
        objects = page.get("Contents", [])
        if not objects:
            continue
        delete_payload = {"Objects": [{"Key": obj["Key"]} for obj in objects if obj["Key"] != prefix]}
        if not delete_payload["Objects"]:
            continue
        s3_client.delete_objects(Bucket=bucket_name, Delete=delete_payload)
        deleted += len(delete_payload["Objects"])

    print(f"🗑️  Cleared {deleted} object(s) from {account_name}/{bucket_name}/{prefix}")

if __name__ == "__main__":
    round_id = input("Enter the round number: ")
    folder_name = input("Enter the folder name: ")
    account_name = input("Enter the account name: ")

    account_config = json.loads(config[f"{account_name}_CONFIG"])
    s3_client = boto3.client(
        "s3",
        endpoint_url=account_config['ENDPOINT_URL'],
        aws_access_key_id=account_config['ACCESS_KEY_ID'],
        aws_secret_access_key=account_config['SECRET_ACCESS_KEY'],
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )
    bucket_name = account_config['BUCKET_NAME']

    if not os.path.exists(f"rounds/{round_id}"):
        os.makedirs(f"rounds/{round_id}")

    if not os.path.exists(f"results"):
        os.makedirs("results")

    if not os.path.exists(f"js"):
        os.makedirs("js")

    print(f"🗑️  Clearing R2 {folder_name} folder before starting...")   
    clear_r2_folder(folder_name, s3_client, bucket_name, account_name)
    print(f"✅ R2 {folder_name} folder cleared")

    prompt_url = f"https://github.com/404-Repo/404-active-competition/blob/main/rounds/{round_id}/prompts.txt"
    seed_url = f"https://github.com/404-Repo/404-active-competition/blob/main/rounds/{round_id}/seed.json"

    while True:
        if is_github_file_downloadable(prompt_url) and is_github_file_downloadable(seed_url):
            print("✅ Both files are downloadable")
            download_files(prompt_url, seed_url, round_id)

            with open(f"rounds/{round_id}/seed.json", "r") as f:
                seed = json.load(f)

            with open(f'rounds/{round_id}/prompts.txt', 'r') as file:
                lines = [line.strip() for line in file]

            BATCH_SIZE = 32
            pending_prompts = [
                {"stem": Path(line).stem, "image_url": line}
                for line in lines if line
            ]
            upload_futures = {}
            batch_num = 0

            with ThreadPoolExecutor(max_workers=8) as upload_executor:
                while pending_prompts:
                    batch = pending_prompts[:BATCH_SIZE]
                    pending_prompts = pending_prompts[BATCH_SIZE:]
                    batch_key = f"batch_{batch_num}"
                    batch_num += 1

                    print(f"\n📦 {batch_key}: submitting {len(batch)} prompt(s): {[p['stem'] for p in batch]}")

                    while True:
                        submit_prompt(batch, seed["seed"])

                        while check_generation_result() != "complete":
                            time.sleep(1)

                        if not download_results(batch_key):
                            print(f"⚠️  {batch_key} download failed, retrying whole batch...")
                            continue

                        with zipfile.ZipFile(f'results/{batch_key}.zip', 'r') as zip_ref:
                            zip_names = zip_ref.namelist()
                            failed_stems = {
                                n[: -len("_failed.json")]
                                for n in zip_names
                                if n.endswith("_failed.json")
                            }

                            if failed_stems:
                                print(f"⚠️  {batch_key}: {len(failed_stems)} failed — re-queuing: {list(failed_stems)}")
                                # Extract only successful JS files
                                for name in zip_names:
                                    if not name.endswith("_failed.json"):
                                        zip_ref.extract(name, f"js/{account_name}")
                            else:
                                zip_ref.extractall(f"js/{account_name}")

                            # Queue uploads for every item that succeeded
                            for item in batch:
                                if item["stem"] not in failed_stems:
                                    future = upload_executor.submit(
                                        upload_js_file, f"{item['stem']}.js", folder_name, s3_client, bucket_name, account_name
                                    )
                                    upload_futures[future] = item["stem"]
                                    print(f"  ✅ {item['stem']} complete, upload queued")

                            # Prepend failed items so they lead the next batch
                            failed_items = [item for item in batch if item["stem"] in failed_stems]
                            pending_prompts = failed_items + pending_prompts

                        break  # exit the download-retry loop; failures re-enter via pending_prompts

                # Wait for all in-flight uploads and report any failures
                for future in as_completed(upload_futures):
                    fname = upload_futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        print(f"❌ Upload failed for {fname}.js: {e}")

            break
        else:
            print("❌ One or both files are not downloadable")

        time.sleep(5)
