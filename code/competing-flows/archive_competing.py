"""Archive completed competition traces outside Git, with per-file SHA-256."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile


CASES = ("same-start-dd", "same-start-gd", "same-start-dg", "same-start-gg",
         "join10-dd", "join10-gd", "join10-dg", "join10-gg",
         "same-start-gd-first", "same-start-gd-later", "join10-gd-first", "join10-gd-later")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-competing"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=CASES,
                        help="Explicit case names; default is the original twelve-case archive")
    args = parser.parse_args()
    if args.out.exists() or args.manifest.exists() or args.out == args.manifest:
        raise SystemExit("Archive and manifest must use distinct, new output paths")
    if len(args.cases) != len(set(args.cases)) or any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", name) for name in args.cases):
        raise SystemExit("Case names must be unique simple directory names")
    entries = []
    for name in args.cases:
        run = args.root / name
        if run.is_symlink() or run.resolve().parent != args.root.resolve():
            raise ValueError(f"Case is not directly under the declared root: {name}")
        case = json.loads((run / "case.json").read_text())
        if case["status"] != "complete" or case["exit_code"] != 0:
            raise ValueError(f"Incomplete case: {name}")
        files = [run / filename for filename in ("case.json", "config_ns3.properties", "schedule.csv", "study_analysis.json")]
        files += sorted((run / "logs_ns3").glob("*.csv"))
        if not files or len(list((run / "logs_ns3").glob("*.csv"))) != 16:
            raise ValueError(f"Unexpected trace inventory: {name}")
        for path in files:
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(run.resolve()):
                raise ValueError(f"Not a regular input under the case: {path}")
            entries.append({"path": str(path.relative_to(args.root)), "bytes": path.stat().st_size,
                            "sha256": digest(path)})
    manifest = {"schema_version": 1, "script_sha256": digest(Path(__file__)),
                "cases": list(args.cases), "files": entries,
                "uncompressed_bytes": sum(e["bytes"] for e in entries),
                "qualification": "Original case/settings, all measurement and timing CSVs, and full analysis. No ns-3 tree/build, generated constellation state, or local authentication files."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.out, "x:gz", compresslevel=6) as archive:
        raw_manifest = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        header = tarfile.TarInfo("archive_manifest.json")
        header.size = len(raw_manifest)
        archive.addfile(header, io.BytesIO(raw_manifest))
        for entry in entries:
            archive.add(args.root / entry["path"], arcname=entry["path"], recursive=False)
    receipt = dict(manifest, archive={"filename": args.out.name, "bytes": args.out.stat().st_size,
                                     "sha256": digest(args.out)})
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"archive": receipt["archive"], "files": len(entries),
                      "uncompressed_bytes": manifest["uncompressed_bytes"]}))


if __name__ == "__main__":
    main()
