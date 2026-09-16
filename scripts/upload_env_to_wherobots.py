#!/usr/bin/env python3
"""
Upload the AURORA_DSN line of the workshop .env to your org's Wherobots managed
storage, where a remote notebook kernel can read it, and point
silver-to-gold.ipynb at it (MANAGED_ENV_URI in the config cell).

The silver-to-gold notebook's config cell resolves the Aurora connection from,
in order: the AURORA_DSN environment variable, a .env in the kernel's working
directory tree, and finally a .env in managed storage at the path this script
uploads to. Remote kernels started from Kiro or VS Code see neither the laptop's
environment nor its .env, so this is the path that works for them.

Usage (from the repo root, after filling in .env):
    set -a; source .env; set +a
    python3 scripts/upload_env_to_wherobots.py [path/to/.env] [--dry-run]

Only the AURORA_DSN line is uploaded. --dry-run resolves the destination and
patches the notebook without uploading anything.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

API = "https://api.cloud.wherobots.com"
SUBPATH = "aws-felt-wherobots-workshop/workshop.env"  # no leading dot: Spark ignores hidden files
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO, "part1_data_engineering", "silver-to-gold.ipynb")
DRY_RUN = "--dry-run" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--dry-run"]

def _key_from_dotenv(path):
    if not os.path.isfile(path):
        return None
    for line in open(path):
        line = line.strip()
        if line.startswith("WHEROBOTS_API_KEY="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if v and not v.startswith("your-"):
                return v
    return None


# Prefer .env over the shell: a stale export in ~/.zshrc otherwise wins inside Kiro's command tool.
key = _key_from_dotenv(os.path.join(REPO, ".env")) or os.environ.get("WHEROBOTS_API_KEY")
if not key:
    sys.exit("WHEROBOTS_API_KEY not found in .env or the environment")

env_path = ARGS[0] if ARGS else os.path.join(REPO, ".env")
lines = [l for l in open(env_path) if l.startswith("AURORA_DSN=")]
if not lines or "<" in lines[0]:
    sys.exit(f"no usable AURORA_DSN line in {env_path}")


def api(method, path, body=None):
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode() if body else None, method=method
    )
    req.add_header("X-API-Key", key)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


storage = api("GET", "/storage")
storage = storage if isinstance(storage, list) else storage.get("items") or []
managed = next(i for i in storage if i.get("type") == "MANAGED")
default_dir = (managed.get("defaultDirectory") or "").strip("/")
upload_path = f"/{default_dir}/{SUBPATH}" if default_dir else f"/{SUBPATH}"
base = (managed.get("path") or "").rstrip("/")
destination = f"{base}{upload_path}"

if DRY_RUN:
    print(f"dry run: would upload AURORA_DSN line to {destination}")
else:
    resp = api("POST", f"/storage/{managed['id']}/file-upload-url/{urllib.parse.quote(upload_path, safe='')}")
    destination = resp["destination"]
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as tmp:
        tmp.write(lines[0])
        tmp_path = tmp.name
    try:
        r = subprocess.run(
            ["curl", "-sS", "-X", "PUT", "-T", tmp_path, "-w", "%{http_code}", resp["uploadUrl"]],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        os.unlink(tmp_path)
    code = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "?"
    if code != "200":
        sys.exit(f"upload failed: HTTP {code} {r.stderr.strip()}")
    print(f"uploaded AURORA_DSN line to {destination}")

# Point the Gold notebook at the uploaded file (config cell: MANAGED_ENV_URI = ...)
import json, re
nb = json.load(open(NOTEBOOK, encoding="utf-8"))
patched = False
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    for i, line in enumerate(cell["source"]):
        if line.startswith("MANAGED_ENV_URI = "):
            cell["source"][i] = re.sub(r"^MANAGED_ENV_URI = .*?(  #.*)?$", lambda m: f'MANAGED_ENV_URI = "{destination}"{m.group(1) or ""}', line.rstrip("\n")) + "\n"
            patched = True
assert patched, "MANAGED_ENV_URI line not found in silver-to-gold.ipynb"
with open(NOTEBOOK, "w", encoding="utf-8") as f:
    f.write(json.dumps(nb, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
print(f"silver-to-gold.ipynb: MANAGED_ENV_URI set to {destination}")
