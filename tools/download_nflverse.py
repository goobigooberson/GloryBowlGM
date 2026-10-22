# tools/download_nflverse.py
# Downloads every nflverse dataset (free, public NFL data: github.com/nflverse/
# nflverse-data) as CSV into tools/data/nflverse/<dataset>/, gzipped.
# Blake (Oct 21): "download as much data as you can that will help in making
# this game realistic, for literally any category of this game."
#
# Skips files already downloaded, and the duplicate formats nflverse also
# publishes (parquet, rds, qs). Safe to re-run (e.g. after a new season).
#
# Run from the project folder:  python tools/download_nflverse.py

import gzip
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "nflverse"
API = "https://api.github.com/repos/nflverse/nflverse-data"
SKIP_TAGS = {"test"}


def get_json(url):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "fof-project-data"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # rate limit or network: wait and retry
            print(f"  retry {url}: {e}", flush=True)
            time.sleep(30 * (attempt + 1))
    raise RuntimeError(url)


def assets_of(release):
    out, page = [], 1
    while True:
        batch = get_json(f"{API}/releases/{release['id']}/assets?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def pick(assets):
    """CSV versions only: prefer .csv.gz, else .csv."""
    names = {a["name"]: a for a in assets}
    chosen = []
    for name, a in names.items():
        if name.endswith(".csv.gz"):
            chosen.append(a)
        elif name.endswith(".csv") and name + ".gz" not in names:
            chosen.append(a)
    return chosen


def download(a, folder):
    name = a["name"]
    target = folder / (name if name.endswith(".gz") else name + ".gz")
    if target.exists() and target.stat().st_size > 0:
        return 0
    tmp = folder / (name + ".part")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(a["browser_download_url"], timeout=300) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            break
        except Exception as e:
            print(f"  retry {name}: {e}", flush=True)
            time.sleep(10 * (attempt + 1))
    else:
        print(f"  FAILED {name}", flush=True)
        return 0
    if name.endswith(".gz"):
        tmp.replace(target)
    else:
        with open(tmp, "rb") as src, gzip.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        tmp.unlink()
    return target.stat().st_size


def main():
    only = set(sys.argv[1:])
    releases = []
    page = 1
    while True:
        batch = get_json(f"{API}/releases?per_page=100&page={page}")
        releases += batch
        if len(batch) < 100:
            break
        page += 1
    total = 0
    for rel in sorted(releases, key=lambda r: r["tag_name"]):
        tag = rel["tag_name"]
        if tag in SKIP_TAGS or (only and tag not in only):
            continue
        folder = OUT / tag
        folder.mkdir(parents=True, exist_ok=True)
        files = pick(assets_of(rel))
        got = 0
        for a in files:
            got += download(a, folder)
        total += got
        print(f"{tag}: {len(files)} CSV files, {got / 1e6:.1f} MB new", flush=True)
    print(f"done: {total / 1e6:.0f} MB new in {OUT}", flush=True)


if __name__ == "__main__":
    main()
