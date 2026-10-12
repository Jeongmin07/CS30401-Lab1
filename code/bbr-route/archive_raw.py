"""Archive local diagnostic runs without source/build/state or binary crash dumps."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = args.out.with_name(args.out.name + ".inventory.json")
    if args.out.exists() or receipt.exists():
        raise ValueError("Archive and inventory paths must be new")
    allowed = {".csv", ".json", ".txt", ".properties"}
    files = []
    with tarfile.open(args.out, "w:gz") as archive:
        for root in args.roots:
            if not root.is_dir():
                raise ValueError(f"No run root: {root}")
            for path in sorted(root.rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix in allowed:
                    name = root.name + "/" + str(path.relative_to(root))
                    archive.add(path, arcname=name, recursive=False)
                    files.append({"path": name, "bytes": path.stat().st_size, "sha256": sha(path)})
    record = {"archive": args.out.name, "bytes": args.out.stat().st_size,
              "sha256": sha(args.out), "uncompressed_input_bytes": sum(row["bytes"] for row in files),
              "file_count": len(files), "files": files,
              "limits": ["Failed and timed-out attempts are retained and are not completed performance results.",
                         "No ns-3 tree, runtime builds, generated state or crash dumps are included.",
                         "Archive SHA identifies this stored artifact; gzip/tar byte determinism is not asserted."]}
    receipt.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ["archive", "bytes", "sha256", "uncompressed_input_bytes", "file_count"]}))


if __name__ == "__main__":
    main()
