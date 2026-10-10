"""Archive exactly the exported cases; keep this large file outside Git."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("Refusing to overwrite archive")
    with (a.evidence / "results.csv").open(newline="") as f:
        names = sorted(r["case"] for r in csv.DictReader(f))
    if len(names) != 31 or len(set(names)) != 31:
        raise ValueError("Expected 31 distinct cases")
    expected = json.loads((a.evidence / "raw_hashes.json").read_text())
    for name in names:
        for record in expected[name]:
            file = a.runs_root / name / "logs_ns3" / record["file"]
            with file.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if file.stat().st_size != record["bytes"] or digest != record["sha256"]:
                raise ValueError(f"Raw input differs: {name}/{file.name}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(a.out, "w:gz", compresslevel=1) as archive:
        for name in names:
            archive.add(a.runs_root / name, arcname=name)
    with a.out.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    print(json.dumps(dict(file=a.out.name, bytes=a.out.stat().st_size, sha256=digest, cases=names), indent=2))


if __name__ == "__main__":
    main()
