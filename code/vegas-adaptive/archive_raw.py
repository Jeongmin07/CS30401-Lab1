"""Archive completed runs outside Git and verify each archived file's SHA256."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import time


def digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--pattern", default="v1-*")
    p.add_argument("--extra", nargs="*", default=[])
    p.add_argument("--attach-tree", action="append", default=[], metavar="LABEL=PATH",
                   help="Include a separate post-hoc output tree under LABEL in the same archive")
    p.add_argument("--compresslevel", type=int, choices=range(1,10), default=1)
    a = p.parse_args()
    root, out = a.root.resolve(), a.out.resolve()
    inventory_path = out.with_suffix(out.suffix + ".inventory.json")
    receipt_path = out.with_suffix(out.suffix + ".receipt.json")
    if any(path.exists() for path in (out, inventory_path, receipt_path)):
        raise SystemExit("Refusing existing archive/manifest/receipt")
    if out.is_relative_to(root):
        raise SystemExit("Archive destination must be outside selected run root")
    directories = sorted(path for path in root.glob(a.pattern) if path.is_dir())
    if not directories:
        raise SystemExit("No run directories selected")
    files = []
    for run in directories:
        manifest = json.loads((run / "case.json").read_text())
        if manifest.get("status") != "complete" or manifest.get("exit_code") != 0:
            raise SystemExit(f"Unfinished/failed run: {run}")
        files.extend(path for path in run.rglob("*") if path.is_file())
    for name in a.extra:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise SystemExit(f"Missing/unsafe extra input: {name}")
        files.append(path)
    selected = {path.relative_to(root).as_posix(): path for path in files}
    attached = {}
    for declaration in a.attach_tree:
        label, separator, value = declaration.partition("=")
        tree = Path(value).resolve()
        if (not separator or not re.fullmatch(r"[A-Za-z0-9_-]+", label)
                or label in attached or not tree.is_dir() or out.is_relative_to(tree)):
            raise SystemExit(f"Invalid attached tree: {declaration}")
        attached[label] = str(tree)
        for path in tree.rglob("*"):
            if path.is_file():
                if path.is_symlink() or not path.resolve().is_relative_to(tree):
                    raise SystemExit(f"Symlink/outside attached tree: {path}")
                name = label + "/" + path.relative_to(tree).as_posix()
                if name in selected:
                    raise SystemExit(f"Conflicting archive path: {name}")
                selected[name] = path
    started = time.monotonic()
    records, stamps = [], {}
    for name, path in sorted(selected.items()):
        if path.is_symlink():
            raise SystemExit(f"Symlink/outside-root input: {path}")
        stat = path.stat()
        with path.open("rb") as stream:
            sha = digest(stream)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise SystemExit(f"Input changed while hashing: {path}")
        stamps[name] = (stat.st_size, stat.st_mtime_ns)
        records.append({"path": name, "bytes": stat.st_size, "sha256": sha})
    inventory = {"schema_version": 1, "root_at_creation": str(root),
                 "pattern": a.pattern, "extra": a.extra, "files": records,
                 "attached_posthoc_trees": attached,
                 "file_count": len(records), "total_uncompressed_bytes": sum(r["bytes"] for r in records),
                 "scope": "Original completed run trees, including analysis outputs where present; no source tree, state directory or build. Filenames/bytes and each file hash are independently checked after compression."}
    raw_inventory = encoded(inventory)
    out.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_bytes(raw_inventory)
    with out.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", compresslevel=a.compresslevel, mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                info = tarfile.TarInfo("RAW_INVENTORY.json")
                info.size, info.mtime = len(raw_inventory), 0
                archive.addfile(info, io.BytesIO(raw_inventory))
                for record in records:
                    path = selected[record["path"]]
                    stat = path.stat()
                    if (stat.st_size, stat.st_mtime_ns) != stamps[record["path"]]:
                        raise SystemExit(f"Input changed before archiving: {path}")
                    archive.add(path, arcname=record["path"], recursive=False)
    expected = {r["path"]: r for r in records}
    observed = set()
    with tarfile.open(out, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile():
                raise SystemExit(f"Unexpected archive member: {member.name}")
            stream = archive.extractfile(member)
            if member.name == "RAW_INVENTORY.json":
                if stream.read() != raw_inventory:
                    raise SystemExit("Embedded inventory changed")
                continue
            record = expected.get(member.name)
            if record is None or member.name in observed:
                raise SystemExit(f"Unexpected/duplicate member: {member.name}")
            if member.size != record["bytes"] or digest(stream) != record["sha256"]:
                raise SystemExit(f"Archived bytes differ: {member.name}")
            observed.add(member.name)
    if observed != set(expected):
        raise SystemExit("Archive missing selected files")
    with out.open("rb") as stream:
        archive_sha = digest(stream)
    receipt = {"schema_version": 1, "archive": str(out), "archive_bytes": out.stat().st_size,
               "archive_sha256": archive_sha, "compresslevel": a.compresslevel, "verified_file_count": len(observed),
               "inventory_sha256": hashlib.sha256(raw_inventory).hexdigest(),
               "verification": "Every archived file independently streamed and matched to pre-archive size/SHA256; no raw logs were edited.",
               "wall_time_s": round(time.monotonic() - started, 3)}
    receipt_path.write_bytes(encoded(receipt))
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
