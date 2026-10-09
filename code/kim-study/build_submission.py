"""Build a whitelisted Team 5 draft review ZIP using only the standard library.

This does not finalize author identity, validate the report's scientific claims,
or declare the archive ready for course submission. Rebuild after the final PDF
has been copied into report/.
"""

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile


BUNDLE_ROOT = Path(__file__).resolve().parent
CODE_PREFIX = PurePosixPath("code/kim-study")
DEFAULT_NAME = "Lab1_5_draft.zip"
TOP_SUFFIXES = {".py", ".patch", ".md"}
TOP_NAMES = {
    "pyproject.toml", "uv.lock", "matrix_execution.json",
    "phase2_execution.json", "phase2_results.json", "phase2_results.csv",
    "reproduction_v4.json",
}
CASE_NAMES = {"case.json", "summary.json", "config_ns3.properties", "schedule.csv"}
FIGURE_DIRECTORIES = ("v4", "tail-v5", "phase2")
FIGURE_SUFFIXES = {".png", ".pdf", ".json"}
FORBIDDEN_PARTS = {
    ".venv", "__pycache__", "logs_ns3", "rawlogs", "raw_logs", "state",
    "build", "ns-3.48", "ns3tree", "node_modules", "evidence-replayed",
    "evidence-export", "runs",
}
FORBIDDEN_SUFFIXES = {
    ".zip", ".pyc", ".pyo", ".aux", ".log", ".bbl", ".blg", ".out",
    ".toc", ".fls", ".fdb_latexmk", ".synctex.gz",
}
EXCLUDED_EXCERPTS = {"event26_evidence.csv", "event26_replayed.csv"}

ROOT_README = """# Team 5 — DRAFT review package

This is a draft package for team review. The three members' verified English
names and the agreed final team scope are incomplete. It is not ready for KLMS
submission. `report.pdf` is copied from the included independent study draft;
the correct final name will be `Lab1_5.zip` only after final checks and identity
completion.

The archive has the required top-level layout: `report.pdf`, `README.md`, and
`code/`. Extract it into a new directory and follow
[code/kim-study/README.md](code/kim-study/README.md) for the exact pinned Docker
image, clean-volume patch/build commands, all 75 recorded-case replay commands,
analysis and hash comparisons, tables, figures, and optional report compilation.
Run those PowerShell commands from this extracted archive's root directory.

The recorded cases include overlapping deterministic regression conditions;
they are not 75 independent statistical samples. Published reproduction checks
cover the recorded inputs and analyses, not all possible TCP loss paths or other
network scenarios. Consult the included experiment and phase-two notes for the
measured benefits, costs and remaining failures.

The package uses a file whitelist. It contains the patch, generators, configs,
compact summaries, dependency lock, source provenance and publication figures.
Constellation state, raw simulation logs, raw evidence excerpts, ns-3 source,
build outputs and virtual environments are excluded. The official example state
comes from the pinned course image. Regenerate the review excerpt with the
included `extract_event26.py`; no external teammate results are required.

The report uses the unchanged IEEE conference class. Keep Sections 1–6 within
six pages, complete the names and final report checks, and package the finalized
team materials before actual submission. Each member's Contribution Survey and
the team presentation remain separate requirements.
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_member(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts,
            f"Unsafe archive path: {name}")
    folded = {part.casefold() for part in path.parts}
    require(not folded & FORBIDDEN_PARTS, f"Forbidden directory in archive: {name}")
    require(path.name not in EXCLUDED_EXCERPTS, f"Raw excerpt selected: {name}")
    require(not any(name.casefold().endswith(suffix) for suffix in FORBIDDEN_SUFFIXES),
            f"Forbidden file type in archive: {name}")


def select_files(root):
    """Return archive-name -> regular source file; never traverse raw run trees."""
    selected = {}

    def add(path):
        require(path.is_file(), f"Missing required source: {path}")
        require(not path.is_symlink(), f"Symlink source is not permitted: {path}")
        relative = path.relative_to(root)
        name = str(CODE_PREFIX / PurePosixPath(relative.as_posix()))
        validate_member(name)
        require(name not in selected, f"Duplicate selected name: {name}")
        selected[name] = path

    for path in sorted(root.iterdir()):
        if path.is_file() and (path.suffix in TOP_SUFFIXES or path.name in TOP_NAMES
                               or (path.name.startswith("path_truth") and path.suffix == ".csv")):
            add(path)

    evidence = root / "evidence"
    require(evidence.is_dir() and not evidence.is_symlink(), "Missing regular evidence directory")
    for path in sorted(evidence.iterdir()):
        if path.is_file() and (path.suffix == ".json"
                               or (path.name.startswith("results") and path.suffix == ".csv")):
            add(path)

    cases = evidence / "cases"
    require(cases.is_dir() and not cases.is_symlink(), "Missing regular evidence/cases directory")
    for folder in sorted(cases.iterdir()):
        require(folder.is_dir() and not folder.is_symlink(), f"Unexpected case entry: {folder}")
        for filename in sorted(CASE_NAMES):
            path = folder / filename
            if path.is_file():
                add(path)
        require((folder / "case.json").is_file() and (folder / "summary.json").is_file(),
                f"Case lacks manifest or compact summary: {folder.name}")

    for directory in FIGURE_DIRECTORIES:
        figures = root / "figures" / directory
        require(figures.is_dir() and not figures.is_symlink(), f"Missing figure directory: {directory}")
        for path in sorted(figures.iterdir()):
            if path.is_file() and path.suffix in FIGURE_SUFFIXES:
                add(path)

    for filename in ("kim-study-draft.tex", "kim-study-draft.pdf"):
        add(root / "report" / filename)

    return selected


def packaged_markdown(path):
    """Remove links to excluded review excerpts from packaged copies only."""
    content = path.read_bytes().decode("utf-8")
    for target in ("evidence/event26_evidence.csv", "event26_replayed.csv"):
        pattern = r"\[([^\]]+)\]\(" + re.escape(target) + r"\)"
        content = re.sub(pattern,
                         lambda match: match.group(1) + " (regenerate with `extract_event26.py`)",
                         content)
    if path.name == "README.md":
        content += ("\n\nDraft-package note: raw event excerpts are excluded from this ZIP. "
                    "The documented `extract_event26.py` command regenerates them after replay. "
                    "This package still requires the three verified author names and final team review.\n")
    require(not any("](" + target + ")" in content for target in
                    ("evidence/event26_evidence.csv", "event26_replayed.csv")),
            "Excluded excerpt remains linked in packaged Markdown")
    return content.encode("utf-8")


def build(root, output):
    require(output.suffix.casefold() == ".zip", "--out must name a .zip file")
    selected = select_files(root)
    required = {
        "code/kim-study/README.md", "code/kim-study/ns3.patch",
        "code/kim-study/replay_cases.py", "code/kim-study/analyze_replay.py",
        "code/kim-study/analyze_study.py", "code/kim-study/run_phase2.py",
        "code/kim-study/analyze_phase2.py", "code/kim-study/plot_phase2.py",
        "code/kim-study/pyproject.toml", "code/kim-study/uv.lock",
        "code/kim-study/evidence/reproduction_v6.json",
        "code/kim-study/report/kim-study-draft.tex",
        "code/kim-study/report/kim-study-draft.pdf",
    }
    require(required <= set(selected), "Missing required reproducible code, proof or report files")
    proof = json.loads((root / "evidence" / "reproduction_v6.json").read_text(encoding="utf-8"))
    require(proof.get("all_identical") is True, "Published v6 comparison has not passed")
    expected_names = set(selected) | {"report.pdf", "README.md"}
    for name in expected_names:
        validate_member(name)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="." + output.stem + "-", suffix=".tmp",
                                         dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            archive.writestr("README.md", ROOT_README.encode("utf-8"))
            archive.write(root / "report" / "kim-study-draft.pdf", "report.pdf")
            for name, path in sorted(selected.items()):
                if path.suffix == ".md":
                    archive.writestr(name, packaged_markdown(path))
                else:
                    archive.write(path, name)

        with zipfile.ZipFile(temporary) as archive:
            names = archive.namelist()
            require(len(names) == len(expected_names) and set(names) == expected_names,
                    "Archive file count or selected membership changed")
            require(not any(count > 1 for count in Counter(names).values()),
                    "Duplicate archive members")
            for name in names:
                validate_member(name)
            require(archive.testzip() is None, "ZIP integrity test failed")
            require(archive.read("report.pdf") == (root / "report" / "kim-study-draft.pdf").read_bytes(),
                    "Top-level report differs from the selected draft PDF")
            for name in names:
                if name.endswith(".md"):
                    require(not any(target in archive.read(name) for target in
                                    (b"](evidence/event26_evidence.csv)",
                                     b"](event26_replayed.csv)")),
                            "Packaged Markdown has an excluded raw-excerpt link")
        temporary.replace(output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {
        "output": str(output), "file_count": len(expected_names),
        "bytes": output.stat().st_size, "zip_integrity_passed": True,
        "forbidden_paths_excluded": True, "draft": True,
        "author_names_complete": False, "ready_for_course_submission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=BUNDLE_ROOT / DEFAULT_NAME)
    args = parser.parse_args()
    try:
        result = build(BUNDLE_ROOT, args.out.resolve())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
