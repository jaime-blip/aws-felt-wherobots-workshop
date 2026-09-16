"""
Workshop bootstrap runner — one command, everything else handled.

Reads the sibling bootstrap.py from the cloned workshop repo, uploads
it into your Wherobots managed storage, submits a Wherobots job run,
and streams logs until completion. Exits 0 on success.

Why this wrapper exists:
    The Wherobots Runs REST API requires the script's S3 URI to be
    readable by your org's compute role via SIGNED requests. Public S3
    buckets allow anonymous reads but not signed cross-account reads
    from arbitrary Wherobots orgs, so we shuttle bootstrap.py through
    your own managed storage as a transit point.

Usage (from the cloned workshop repo, with WHEROBOTS_API_KEY set in .env):

    python3 scripts/run_bootstrap.py              # run the bootstrap
    python3 scripts/run_bootstrap.py --check-key  # only verify the key works

Requires Python 3.8+ and curl on PATH. Pure stdlib otherwise.
Idempotent — re-runs replace the uploaded script and create a fresh
Wherobots job run.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


# ── Config ────────────────────────────────────────────────────────────────────

WHEROBOTS_API = "https://api.cloud.wherobots.com"
REGION = "aws-us-west-2"

# bootstrap.py is expected to live next to this wrapper in the cloned repo
LOCAL_BOOTSTRAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bootstrap.py")
UPLOAD_SUBPATH = "scripts/bootstrap.py"  # relative to the managed storage default dir

RUN_NAME = "workshop-bootstrap"
RUNTIME = "tiny"
TIMEOUT_SEC = 1800

POLL_INTERVAL_SEC = 4
TERMINAL_STATES = ("COMPLETED", "FAILED", "CANCELLED")


# ── Auth ──────────────────────────────────────────────────────────────────────
# Prefer the repo's .env over the shell environment. Participants put the key
# in .env (Lab 01), but many machines also export a stale WHEROBOTS_API_KEY in
# ~/.zshrc, and Kiro's command tool runs an interactive shell that sources it,
# so the shell value silently wins and every API call returns 401.

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key_from_dotenv():
    path = os.path.join(REPO_ROOT, ".env")
    if not os.path.isfile(path):
        return None, None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("WHEROBOTS_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value and not value.startswith("your-"):
                    return value, path
    return None, None


API_KEY, KEY_SOURCE = _key_from_dotenv()
if not API_KEY:
    API_KEY, KEY_SOURCE = os.environ.get("WHEROBOTS_API_KEY"), "the shell environment"
if not API_KEY:
    sys.exit(
        "Missing WHEROBOTS_API_KEY. Generate one at https://cloud.wherobots.com/ "
        "and put it in the repo's .env (see .env.example)."
    )


# ── Tiny HTTP helper around the Wherobots REST API ────────────────────────────

def api(method, path, body=None, query=None):
    url = f"{WHEROBOTS_API}{path}"
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", API_KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        hint = ""
        if e.code == 401:
            hint = (
                f"\nThe API key came from {KEY_SOURCE}. If your shell also exports "
                "WHEROBOTS_API_KEY (check ~/.zshrc), that value may be stale; the key in "
                "the repo's .env is the one the workshop uses."
            )
        sys.exit(f"Wherobots API error {e.code} on {method} {path}:\n{body}{hint}")


def step(msg):
    print(f"━━ {msg}", flush=True)


# ── Workflow ──────────────────────────────────────────────────────────────────

def main():
    print(f"   using WHEROBOTS_API_KEY from {KEY_SOURCE} (ends …{API_KEY[-4:]})")
    if "--check-key" in sys.argv:
        step("checking the API key against Wherobots")
        api("GET", "/storage")
        print("   OK: key accepted")
        return 0

    # 1. Find this org's managed storage integration
    step("looking up your managed storage integration")
    integrations = api("GET", "/storage")
    if not isinstance(integrations, list):
        # Some endpoints wrap the list in a payload; try common shapes.
        integrations = integrations.get("items") or integrations.get("integrations") or []
    managed = next((i for i in integrations if i.get("type") == "MANAGED"), None)
    if not managed:
        sys.exit("No MANAGED storage integration found for this Wherobots org.")
    integration_id = managed["id"]
    default_dir = (managed.get("defaultDirectory") or "").strip("/")
    upload_path = f"/{default_dir}/{UPLOAD_SUBPATH}" if default_dir else f"/{UPLOAD_SUBPATH}"
    print(f"   integration: {integration_id}")
    print(f"   target path: {upload_path}")

    # 2. Read the local bootstrap.py from the cloned repo
    step(f"reading {LOCAL_BOOTSTRAP_PATH}")
    if not os.path.isfile(LOCAL_BOOTSTRAP_PATH):
        sys.exit(
            f"bootstrap.py not found at {LOCAL_BOOTSTRAP_PATH}. "
            "Run this script from the cloned workshop repo so bootstrap.py is alongside."
        )
    with open(LOCAL_BOOTSTRAP_PATH, "rb") as f:
        bootstrap_bytes = f.read()
    print(f"   {len(bootstrap_bytes):,} bytes")

    # 3. Ask Wherobots for a presigned PUT URL into managed storage.
    # The {path} segment must be URL-encoded so its leading "/" survives.
    step("requesting presigned upload URL")
    encoded_path = urllib.parse.quote(upload_path, safe="")
    upload_resp = api(
        "POST",
        f"/storage/{integration_id}/file-upload-url/{encoded_path}",
    )
    presigned_url = upload_resp["uploadUrl"]
    s3_uri = upload_resp["destination"]
    print(f"   destination: {s3_uri}")

    # 4. PUT the file directly to S3 via the presigned URL.
    # We shell out to curl because S3 presigned URLs are very picky about
    # request headers — urllib's defaults (Connection, etc.) trip the
    # signature check. curl with -T sends a clean PUT that S3 accepts.
    step("uploading bootstrap.py to your managed storage")
    if not shutil.which("curl"):
        sys.exit("`curl` is required for the upload step. Install it and re-run.")
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(bootstrap_bytes)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["curl", "-sS", "-X", "PUT", "-T", tmp_path, "-w", "%{http_code}", presigned_url],
            capture_output=True, text=True, timeout=180,
        )
        http_code = result.stdout.strip().split("\n")[-1]
        if http_code != "200":
            sys.exit(f"Upload failed (HTTP {http_code}). Body: {result.stdout}\nstderr: {result.stderr}")
        print(f"   HTTP {http_code}")
    finally:
        os.unlink(tmp_path)

    # 5. Submit the Wherobots job run pointing at the uploaded script
    step(f"submitting Wherobots job run on {RUNTIME} runtime")
    run_resp = api(
        "POST",
        "/runs",
        body={
            "runtime": RUNTIME,
            "name": RUN_NAME,
            "runPython": {"uri": s3_uri},
            "timeoutSeconds": TIMEOUT_SEC,
        },
        query={"region": REGION},
    )
    run_id = run_resp["id"]
    print(f"   run_id: {run_id}")
    print(f"   monitor at: https://cloud.wherobots.com/jobs/{run_id}")

    # 6. Stream logs + status until terminal.
    # The /logs endpoint's pagination semantics are fuzzy enough that
    # tracking a cursor is unreliable; the safest pattern is to fetch
    # the recent window each poll and dedupe locally by (timestamp, raw).
    step("streaming logs (poll every 4s)")
    seen = set()
    last_status = None
    while True:
        logs = api("GET", f"/runs/{run_id}/logs", query={"cursor": 0, "size": 1000})
        items = logs.get("items") if isinstance(logs, dict) else None
        if items:
            for item in items:
                key = (item.get("timestamp"), item.get("raw"))
                if key in seen:
                    continue
                seen.add(key)
                line = (item.get("raw") or "").rstrip()
                if line:
                    print(line, flush=True)

        status_resp = api("GET", f"/runs/{run_id}")
        status = status_resp.get("status")
        if status != last_status:
            print(f"   ── status: {status}", flush=True)
            last_status = status
        if status in TERMINAL_STATES:
            break

        time.sleep(POLL_INTERVAL_SEC)

    if last_status == "COMPLETED":
        print("\n✅ Bootstrap complete. Bronze tables are ready in your org_catalog.")
        print("   Next: open bronze-to-silver.ipynb in your Wherobots notebook.")
        return 0
    else:
        print(f"\n❌ Bootstrap finished with status: {last_status}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
