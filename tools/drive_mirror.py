#!/usr/bin/env python3
"""Mirror a local directory tree into a Google Drive folder mounted through GVFS.

The Google Drive GVFS backend addresses entries by Drive file ID, while new
entries can be created by title. This helper resolves children by their Drive
display name so repeated runs update files in place instead of creating
duplicates.

Usage:
    python3 tools/drive_mirror.py SOURCE_DIR DEST_SUBPATH

DEST_SUBPATH is a "/"-separated list of folder titles below the agent folder,
e.g. "CORROSAO/03_dft_baseline". The agent-folder GVFS path is read from the
environment variable DRIVE_AGENT_DIR (never hard-coded in this public repo).

A file is re-uploaded when its size differs from the Drive copy or when
--force is given. A JSON manifest (path, bytes, sha256) of everything mirrored
is written to SOURCE_DIR/DRIVE_MANIFEST.json and uploaded with the tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIP_NAMES = {".git", ".venv-step02", "__pycache__", ".pytest_cache"}


def gio_children(gvfs_dir: str) -> dict[str, tuple[str, int, bool]]:
    """Return {display_name: (gvfs_path, size, is_dir)} for a GVFS directory."""
    out = subprocess.run(
        ["gio", "list", "-a", "standard::display-name,standard::size,standard::type", gvfs_dir],
        check=True, capture_output=True, text=True,
    ).stdout
    children: dict[str, tuple[str, int, bool]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        entry_id, size, kind = parts[0], int(parts[1]), parts[2]
        name = parts[3].split("standard::display-name=", 1)[1].split(" standard::")[0]
        children[name] = (f"{gvfs_dir}/{entry_id}", size, kind == "(directory)")
    return children


def ensure_folder(parent: str, title: str) -> str:
    for attempt in range(8):
        children = gio_children(parent)
        if title in children:
            path, _, is_dir = children[title]
            if not is_dir:
                raise RuntimeError(f"Drive entry '{title}' under {parent} is not a folder")
            return path
        if attempt == 0:
            subprocess.run(["gio", "mkdir", f"{parent}/{title}"], check=True)
        import time
        time.sleep(1.5)
    children = gio_children(parent)
    if title in children:
        return children[title][0]
    raise RuntimeError(f"Drive entry '{title}' under {parent} was not found after mkdir retries")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mirror(src: Path, dst: str, force: bool, stats: dict) -> None:
    children = gio_children(dst)
    for item in sorted(src.iterdir()):
        if item.name in SKIP_NAMES or item.is_symlink():
            continue
        if item.is_dir():
            mirror(item, ensure_folder(dst, item.name), force, stats)
            children = gio_children(dst)
            continue
        size = item.stat().st_size
        if item.name in children:
            remote, rsize, is_dir = children[item.name]
            if is_dir:
                raise RuntimeError(f"Drive folder collides with file name {item}")
            if rsize == size and not force:
                stats["skipped"] += 1
                continue
            subprocess.run(["gio", "copy", str(item), remote], check=True)
            stats["updated"] += 1
        else:
            subprocess.run(["gio", "copy", str(item), f"{dst}/{item.name}"], check=True)
            stats["created"] += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("dest_subpath")
    ap.add_argument("--force", action="store_true", help="re-upload files even when sizes match")
    args = ap.parse_args()

    root = os.environ.get("DRIVE_AGENT_DIR")
    if not root or not Path(root).is_dir():
        print("ERROR: set DRIVE_AGENT_DIR to the GVFS path of the agent folder (e.g. CLAUDE).", file=sys.stderr)
        return 2
    src = Path(args.source).resolve()
    if not src.is_dir():
        print(f"ERROR: source directory not found: {src}", file=sys.stderr)
        return 3

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": src.name,
        "dest_subpath": args.dest_subpath,
        "files": [
            {"path": str(p.relative_to(src)), "bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted(src.rglob("*"))
            if p.is_file() and not p.is_symlink() and p.name != "DRIVE_MANIFEST.json"
            and not any(part in SKIP_NAMES for part in p.relative_to(src).parts)
        ],
    }
    (src / "DRIVE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    dst = root
    for title in [t for t in args.dest_subpath.split("/") if t]:
        dst = ensure_folder(dst, title)

    stats = {"created": 0, "updated": 0, "skipped": 0}
    mirror(src, dst, args.force, stats)
    print(f"[drive_mirror] {src} -> {args.dest_subpath}: "
          f"{len(manifest['files'])} files in manifest; "
          f"created={stats['created']} updated={stats['updated']} unchanged={stats['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
