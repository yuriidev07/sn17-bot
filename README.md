# 404-gen-bot

Automation bot for participating in the [404 Gen subnet (SN17)](https://github.com/404-Repo) on Bittensor. It waits for a round's prompts to be published on GitHub, submits them to a local generation server in batches, and uploads the resulting JS files to Cloudflare R2.

---

## Requirements

- Python 3.10+
- A running local generation server on `http://localhost:10006`
- A Cloudflare R2 bucket per account

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

### 1. Copy the sample env file

```bash
cp .env.sample .env
```

### 2. Fill in `.env`

Each account needs its own `<ACCOUNT_NAME>_CONFIG` entry as a JSON object on a single line.

```
SR1279_CONFIG={"GIT_TOKEN": "...", "ACCESS_KEY_ID": "...", "SECRET_ACCESS_KEY": "...", "ENDPOINT_URL": "...", "BUCKET_NAME": "...", "DEVELOPMENT_URL": "...", "REPOS": [...]}
```

| Key | Description |
|---|---|
| `GIT_TOKEN` | GitHub personal access token for the account |
| `ACCESS_KEY_ID` | Cloudflare R2 access key ID |
| `SECRET_ACCESS_KEY` | Cloudflare R2 secret access key |
| `ENDPOINT_URL` | R2 endpoint URL (from Cloudflare dashboard) |
| `BUCKET_NAME` | R2 bucket name (e.g. `sn17`) |
| `DEVELOPMENT_URL` | Public R2 dev URL for the bucket |
| `REPOS` | List of GitHub repos belonging to this account |

You can add as many `<NAME>_CONFIG` entries as you have accounts. The account name you type at runtime must match the prefix (e.g. `SR1279` for `SR1279_CONFIG`).

---

## Usage

### `main.py` — Generation bot

Generates 3D assets from round prompts and uploads them to R2.

```bash
python main.py
```

You will be prompted for three inputs:

```
Enter the round number:   # e.g. 14
Enter the folder name:    # R2 folder to upload into, e.g. h1
Enter the account name:   # must match a key in .env, e.g. SR1279
```

**What it does:**

1. Clears the specified R2 folder to remove any previous round's files.
2. Polls GitHub every 5 seconds until the round's `prompts.txt` and `seed.json` are published.
3. Splits prompts into batches of 32 and submits each batch to the local generation server.
4. Waits for generation to complete, downloads the result zip, and retries any failed items automatically.
5. Uploads successful `.js` files to R2 using up to 8 parallel upload threads.

**Directory structure created at runtime:**

```
rounds/<round_id>/   — downloaded prompts.txt and seed.json
results/             — downloaded result zips
js/<account_name>/   — extracted JS files before upload
```

---

### `repo_update.py` — Bulk repository visibility toggle

Sets all GitHub repositories listed in `.env` to either public or private across all accounts in one go.

```bash
python repo_update.py
```

You will be prompted for one input:

```
Type public or private:   # e.g. private
```

**What it does:**

1. Reads every `*_CONFIG` entry from `.env` and extracts the `GIT_TOKEN` and `REPOS` list for each account.
2. Calls the GitHub API (`PATCH /repos/{owner}/{name}`) to set every repo to the chosen visibility.
3. Prints `[OK]` or `[ERR]` for each repo with the result.

**Example output:**

```
[SR1279_CONFIG] Setting 5 repo(s) to private …
  [OK]   SR1279/DoYourBest  →  private
  [OK]   SR1279/RLStepone   →  private
  ...
```

> `GIT_TOKEN` must have the `repo` scope to change repository visibility.

---

## Notes

- Never commit `.env` — it is already listed in `.gitignore`.
- The generation server must be running on `http://localhost:10006` before starting `main.py`.
- If generation partially fails, failed prompts are automatically re-queued and retried in the next batch.
