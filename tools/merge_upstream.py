"""Brings the changes of a new Ownfoil release into GameDock's code.

    python3 tools/merge_upstream.py <old ownfoil source> <new ownfoil source> <gamedock repo>

Both sources are Ownfoil release trees (as on GitHub). Only what the image uses is
compared: app/, docker/run.sh (GameDock's app/run.sh) and requirements.txt. Each file
Ownfoil changed between the two releases is merged into GameDock's copy with a three-way
merge (git merge-file), so GameDock's own changes stay and Ownfoil's arrive. Where both
changed the same lines the file gets conflict markers. Prints a report and exits 1 when
something needs a person.
"""

import filecmp
import shutil
import subprocess
import sys
from pathlib import Path


def tracked_files(src):
    """GameDock path -> file in an Ownfoil release tree."""
    src = Path(src)
    files = {}
    for path in (src / "app").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            files["app/" + path.relative_to(src / "app").as_posix()] = path
    files["app/run.sh"] = src / "docker" / "run.sh"
    files["requirements.txt"] = src / "requirements.txt"
    return files


def is_text(path):
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def main():
    old, new, repo = tracked_files(sys.argv[1]), tracked_files(sys.argv[2]), Path(sys.argv[3])
    report = {"merged": [], "conflict": [], "added": [], "deleted": [], "attention": []}
    for name in sorted(set(old) | set(new)):
        before, after, ours = old.get(name), new.get(name), repo / name
        if before and after and filecmp.cmp(before, after, shallow=False):
            continue                                      # Ownfoil did not touch it
        if after and not before:                          # new in Ownfoil
            if not ours.exists():
                ours.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(after, ours)
                report["added"].append(name)
            elif not filecmp.cmp(after, ours, shallow=False):
                report["attention"].append(f"{name}: Ownfoil added a file GameDock already has")
            continue
        if before and not after:                          # removed from Ownfoil
            if ours.exists() and filecmp.cmp(before, ours, shallow=False):
                ours.unlink()
                report["deleted"].append(name)
            elif ours.exists():
                report["attention"].append(f"{name}: removed in Ownfoil, changed in GameDock (kept)")
            continue
        # changed in Ownfoil
        if not ours.exists():
            report["attention"].append(f"{name}: changed in Ownfoil, removed or moved in GameDock")
            continue
        if filecmp.cmp(before, ours, shallow=False):      # GameDock never touched it
            shutil.copy2(after, ours)
            report["merged"].append(name)
            continue
        if not (is_text(before) and is_text(after) and is_text(ours)):
            report["attention"].append(f"{name}: binary file changed on both sides (kept GameDock's)")
            continue
        result = subprocess.run(
            ["git", "merge-file", "-L", "GameDock", "-L", "Ownfoil (before)", "-L", "Ownfoil (new)",
             str(ours), str(before), str(after)])
        (report["conflict"] if result.returncode else report["merged"]).append(name)

    for title, key in (("Merged", "merged"), ("Added", "added"), ("Deleted", "deleted"),
                       ("Conflicts (markers in the file)", "conflict"), ("Needs a look", "attention")):
        if report[key]:
            print(f"## {title}")
            print("\n".join(f"- {item}" for item in report[key]))
            print()
    sys.exit(1 if report["conflict"] or report["attention"] else 0)


if __name__ == "__main__":
    main()
