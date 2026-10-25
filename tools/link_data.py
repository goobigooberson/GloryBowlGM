# tools/link_data.py
# For a separate copy of the project (a git worktree: a second folder on its own branch, so a
# session's unfinished edits never mix with another's): links the big real-NFL data folder
# that git doesn't keep (tools/data/nflverse, 643 MB) to the main folder's copy instead of
# downloading it again. Run once in the new folder:
#     python tools/link_data.py
# In the main folder it does nothing. On Windows the link is a directory junction (no admin
# rights needed); deleting the worktree deletes only the link, never the data.

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINKED = ["tools/data/nflverse"]          # git-ignored folders the check tools read


def main_checkout():
    """The main folder of this git repository (where the shared data lives)."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    common = Path(common)
    if not common.is_absolute():
        common = (ROOT / common).resolve()
    return common.parent


def main():
    main_dir = main_checkout()
    if main_dir.resolve() == ROOT.resolve():
        print("This is the main folder: nothing to link.")
        return
    for rel in LINKED:
        here, there = ROOT / rel, main_dir / rel
        if here.exists():
            print(f"{rel}: already here")
            continue
        if not there.exists():
            print(f"{rel}: not in the main folder either ({there}); run tools/download_nflverse.py there")
            continue
        here.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(here), str(there)], check=True,
                           capture_output=True)
        else:
            here.symlink_to(there, target_is_directory=True)
        print(f"{rel}: linked to {there}")


if __name__ == "__main__":
    sys.exit(main())
