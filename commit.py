import subprocess
import time
import threading
import json
import re
import requests
from datetime import datetime, timezone
from typing import Any, Optional

COMMITS = [
    # {
    #     "wallet_name": "one",
    #     "hotkey": "one-new-h1",
    #     "hash": "c5f270df34b33e26cf082e0eafba86f72014e863",
    #     "repo": "SR1279/DoYourBest",
    #     "cdn_url": "https://pub-5bc6e24296a44fa3b3d88205e860be74.r2.dev/h1/"
    # },
    # {
    #     "wallet_name": "one",
    #     "hotkey": "one-new-h2",
    #     "hash": "f14523f2a1bc55b4da535d02eb71043329fe82a5",
    #     "repo": "SR1279/RLStepone",
    #     "cdn_url": "https://pub-5bc6e24296a44fa3b3d88205e860be74.r2.dev/h2/"
    # },
    # {
    #     "wallet_name": "one",
    #     "hotkey": "one-new-h3",
    #     "hash": "f185db53c3c8a818a59a66d89f2269845c8d47af",
    #     "repo": "SR1279/Cucumber",
    #     "cdn_url": "https://pub-5bc6e24296a44fa3b3d88205e860be74.r2.dev/h3/"
    # },
    # {
    #     "wallet_name": "one",
    #     "hotkey": "one-new-h4",
    #     "hash": "bc264e54f1cf1e5ece4d8d1f111ad5ead5c9632e",
    #     "repo": "SR1279/Pumpkin",
    #     "cdn_url": "https://pub-5bc6e24296a44fa3b3d88205e860be74.r2.dev/h4/"
    # },
    # {
    #     "wallet_name": "one",
    #     "hotkey": "one-new-h5",
    #     "hash": "e547c7360ad6afe301d76c8bd5db2c34c8fc11e9",
    #     "repo": "SR1279/GoldLion",
    #     "cdn_url": "https://pub-5bc6e24296a44fa3b3d88205e860be74.r2.dev/h5/"
    # },
    # {
    #     "wallet_name": "apr2-w",
    #     "hotkey": "h1",
    #     "hash": "4f62b3eb1123718a7550574133ec39a1249024b9",
    #     "repo": "Gael1125/Boeing747",
    #     "cdn_url": "https://pub-84fb5c3e34fb448d9c04d2f27aff0391.r2.dev/h1/"
    # },
    # {
    #     "wallet_name": "apr2-w",
    #     "hotkey": "h2",
    #     "hash": "3ab6c465733a4c047d422a37763cca010520b8f1",
    #     "repo": "Gael1125/MiraclePairs",
    #     "cdn_url": "https://pub-84fb5c3e34fb448d9c04d2f27aff0391.r2.dev/h2/"
    # },
    # {
    #     "wallet_name": "apr2-w",
    #     "hotkey": "h3",
    #     "hash": "9a3cf688c21f4290ab61edbd4a85de9813c270e4",
    #     "repo": "Gael1125/Rampage",
    #     "cdn_url": "https://pub-84fb5c3e34fb448d9c04d2f27aff0391.r2.dev/h3/"
    # },
    # {
    #     "wallet_name": "apr2-w",
    #     "hotkey": "h4",
    #     "hash": "badbae00d26ff8d8dbc58e170aec5e17d1829c17",
    #     "repo": "Gael1125/TripleOops",
    #     "cdn_url": "https://pub-84fb5c3e34fb448d9c04d2f27aff0391.r2.dev/h4/"
    # },
    # {
    #     "wallet_name": "apr2-w",
    #     "hotkey": "h5",
    #     "hash": "0a799e29e9188d9b29cb24f3723e9c0200b417ae",
    #     "repo": "Gael1125/DarkShadow",
    #     "cdn_url": "https://pub-84fb5c3e34fb448d9c04d2f27aff0391.r2.dev/h5/"
    # },
    # {
    #     "wallet_name": "apr3-w",
    #     "hotkey": "h1",
    #     "hash": "19c5898e04f7269f07b17dbb2f40aec3f09d4b54",
    #     "repo": "TSH483/Captain",
    #     "cdn_url": "https://pub-a2cebfd53ca14d1d84f6d610f40f233c.r2.dev/h1/"
    # },
    # {
    #     "wallet_name": "apr3-w",
    #     "hotkey": "h2",
    #     "hash": "9a42fe92352587187ffdd8db21ba835e3044dcf4",
    #     "repo": "TSH483/DoubleRabbits",
    #     "cdn_url": "https://pub-a2cebfd53ca14d1d84f6d610f40f233c.r2.dev/h2/"
    # },
    # {
    #     "wallet_name": "apr3-w",
    #     "hotkey": "h3",
    #     "hash": "78eb600344961449998441c3954653810f853436",
    #     "repo": "TSH483/Golden-Palace",
    #     "cdn_url": "https://pub-a2cebfd53ca14d1d84f6d610f40f233c.r2.dev/h3/"
    # },
    # {
    #     "wallet_name": "apr3-w",
    #     "hotkey": "h4",
    #     "hash": "2694ba07347b33509f961bf920a11230a5949d38",
    #     "repo": "TSH483/Sharp-Sword",
    #     "cdn_url": "https://pub-a2cebfd53ca14d1d84f6d610f40f233c.r2.dev/h4/"
    # },
    # {
    #     "wallet_name": "apr3-w",
    #     "hotkey": "h5",
    #     "hash": "41c4541886f8a476cb5924dbd2ab86b320bcb144",
    #     "repo": "TSH483/Innerpeace",
    #     "cdn_url": "https://pub-a2cebfd53ca14d1d84f6d610f40f233c.r2.dev/h5/"
    # },
    # {
    #     "wallet_name": "apr6-w",
    #     "hotkey": "h1",
    #     "hash": "d31417fb6867a378a274fd50b0b1fc7440484cbe",
    #     "repo": "lucky319193/Crown",
    #     "cdn_url": "https://pub-cd945be8bc8544d98fbfbfd2021315f0.r2.dev/h1/"
    # },
    # {
    #     "wallet_name": "apr6-w",
    #     "hotkey": "h2",
    #     "hash": "274d8c532a00db3e9c521f428a5030ebe28c6cf7",
    #     "repo": "lucky319193/HeartBeat",
    #     "cdn_url": "https://pub-cd945be8bc8544d98fbfbfd2021315f0.r2.dev/h2/"
    # },
    # {
    #     "wallet_name": "apr6-w",
    #     "hotkey": "h3",
    #     "hash": "16f686231458b5ab734cbc24a65af415c9909ce7",
    #     "repo": "lucky319193/CornerStone",
    #     "cdn_url": "https://pub-cd945be8bc8544d98fbfbfd2021315f0.r2.dev/h3/"
    # },
    # {
    #     "wallet_name": "apr6-w",
    #     "hotkey": "h4",
    #     "hash": "e397c652c7a58cf8817cd6e31eb1be2c9661d795",
    #     "repo": "lucky319193/RedFlag",
    #     "cdn_url": "https://pub-cd945be8bc8544d98fbfbfd2021315f0.r2.dev/h4/"
    # },
    # {
    #     "wallet_name": "apr6-w",
    #     "hotkey": "h5",
    #     "hash": "25285cbf6948f89b75c4615cbf0f5a5a1109e642",
    #     "repo": "lucky319193/Uranus",
    #     "cdn_url": "https://pub-cd945be8bc8544d98fbfbfd2021315f0.r2.dev/h5/"
    # },
    # {
    #     "wallet_name": "why",
    #     "hotkey": "why-h1",
    #     "hash": "ade94e734c45e3c1bcabb550306b249a3e6ce74b",
    #     "repo": "yuriidev07/Amazon",
    #     "cdn_url": "https://pub-ce47ef6ebd0f4a5e84363d6b84e0704c.r2.dev/h1/"
    # },
    # {
    #     "wallet_name": "why",
    #     "hotkey": "why-h2",
    #     "hash": "01c4e8cdc0734fd502265076009a1f2ccb47a3d1",
    #     "repo": "yuriidev07/FILA",
    #     "cdn_url": "https://pub-ce47ef6ebd0f4a5e84363d6b84e0704c.r2.dev/h2/"
    # },
    # {
    #     "wallet_name": "why",
    #     "hotkey": "why-h3",
    #     "hash": "849ab8902c57db7decfd8dacd94efa0a9b187f12",
    #     "repo": "yuriidev07/Huawei",
    #     "cdn_url": "https://pub-ce47ef6ebd0f4a5e84363d6b84e0704c.r2.dev/h3/"
    # },
    # {
    #     "wallet_name": "why",
    #     "hotkey": "why-h4",
    #     "hash": "c83afda5e57b6b01c8fc6a1f6d3252b73da55c65",
    #     "repo": "yuriidev07/Microsoft",
    #     "cdn_url": "https://pub-ce47ef6ebd0f4a5e84363d6b84e0704c.r2.dev/h4/"
    # },
    # {
    #     "wallet_name": "why",
    #     "hotkey": "why-h5",
    #     "hash": "1641cb7f8cfac70fa19f17111ab9c8c2221faca0",
    #     "repo": "yuriidev07/NVIDIA",
    #     "cdn_url": "https://pub-ce47ef6ebd0f4a5e84363d6b84e0704c.r2.dev/h5/"
    # }
]

target_block = 8432555  # e.g. 7_000_000 when trigger_mode == "block"

# Command used to query current chain block when trigger_mode == "block".
# If your setup exposes another command that prints block info, replace this.
block_query_command = [
    "btcli", "subnets", "show",
    "--network", "finney",
    "--netuid", "17",
    "--json-output",
    "--no-prompt",
]
block_poll_interval_seconds = 1.0
block_network = "finney"
block_network_endpoints = {
    "finney": "wss://entrypoint-finney.opentensor.ai:443",
    "test": "wss://test.finney.opentensor.ai:443",
    "archive": "wss://archive.chain.opentensor.ai:443",
    "rao": "wss://rao.chain.opentensor.ai:443",
    "dev": "wss://dev.chain.opentensor.ai:443",
    "local": "ws://127.0.0.1:9944",
}
prompt_url = "https://github.com/404-Repo/404-active-competition/blob/main/rounds/14/prompts.txt"
seed_url = "https://github.com/404-Repo/404-active-competition/blob/main/rounds/14/seed.json"
url_poll_interval_seconds = 5.0

# Indices into COMMITS to commit this run. Set to None to commit all slots.
indices = None

print_lock = threading.Lock()


def log(msg: str) -> None:
    with print_lock:
        print(msg)


def _find_block_in_json(payload: Any) -> Optional[int]:
    if isinstance(payload, dict):
        for key in ("current_block", "block_number", "block", "best_block", "height"):
            value = payload.get(key)
            if isinstance(value, int):
                return value
        for value in payload.values():
            found = _find_block_in_json(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_block_in_json(item)
            if found is not None:
                return found
    return None


def parse_block_number(raw_output: str) -> Optional[int]:
    text = raw_output.strip()
    if not text:
        return None

    # Plain integer output (e.g. "7485021")
    if text.isdigit():
        return int(text)

    # JSON output with explicit block-like keys
    try:
        payload = json.loads(text)
        found = _find_block_in_json(payload)
        if found is not None:
            return found
    except json.JSONDecodeError:
        pass

    # Text output patterns (avoid matching keys like block_since_last_step)
    patterns = [
        r"\bcurrent[_\s-]?block\b\D+(\d+)",
        r"\bblock[_\s-]?number\b\D+(\d+)",
        r"\bbest[_\s-]?block\b\D+(\d+)",
        r"\bheight\b\D+(\d+)",
        r"\bblock\b\D+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def get_current_block() -> int:
    endpoint = block_network_endpoints.get(block_network, block_network)
    try:
        from async_substrate_interface.sync_substrate import SubstrateInterface

        substrate = SubstrateInterface(url=endpoint)
        try:
            head = substrate.get_chain_head()
            return substrate.get_block_number(head)
        finally:
            substrate.close()
    except Exception:
        # Fallback to user-configured command if direct RPC is unavailable.
        result = subprocess.run(
            block_query_command,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"block query failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
            )

        block = parse_block_number(result.stdout)
        if block is None:
            raise RuntimeError(
                "could not parse block number from both direct RPC and block_query_command output. "
                "Update block_query_command to a command that prints current block information."
            )
        return block

def commit(c: dict) -> None:
    tag = f"[{c['repo']}]"

    result = subprocess.run(
        [
            "404-cli", "commit-hash",
            "--hash", c["hash"],
            "--wallet.name", c["wallet_name"],
            "--wallet.hotkey", c["hotkey"],
        ],
        capture_output=True,
        text=True,
    )
    log(f"{tag} commit-hash\n{result.stdout}{result.stderr}".strip())

    if result.returncode != 0:
        log(f"{tag} ❌ commit-hash failed (exit {result.returncode}), skipping commit-repo-cdn")
        return

    time.sleep(60)

    result = subprocess.run(
        [
            "404-cli", "commit-repo-cdn",
            "--repo", c["repo"],
            "--cdn-url", c["cdn_url"],
            "--wallet.name", c["wallet_name"],
            "--wallet.hotkey", c["hotkey"],
        ],
        capture_output=True,
        text=True,
    )
    log(f"{tag} commit-repo-cdn\n{result.stdout}{result.stderr}".strip())

    if result.returncode != 0:
        log(f"{tag} ❌ commit-repo-cdn failed (exit {result.returncode})")
    else:
        log(f"{tag} ✅ done")

if indices is None:
    selected = COMMITS
else:
    selected = [COMMITS[i] for i in indices]

if target_block is None:
    raise ValueError("target_block must be set when trigger_mode == 'block'")

print(f"\nWaiting for chain block >= {target_block}...")
while True:
    try:
        current_block = get_current_block()
    except Exception as e:
        print(f"Block query error: {e} (retrying in {block_poll_interval_seconds}s)", end="\r")
        time.sleep(block_poll_interval_seconds)
        continue

    if current_block >= target_block:
        print(f"\nBlock {current_block} reached. Committing {len(selected)} slot(s) in parallel...")
        break

    remaining = target_block - current_block
    print(f"Current block: {current_block} — {remaining} block(s) remaining", end="\r")
    time.sleep(block_poll_interval_seconds)

threads = [threading.Thread(target=commit, args=(c,), daemon=True) for c in selected]
for t in threads:
    t.start()
for t in threads:
    t.join()

print("\nAll threads finished.")
