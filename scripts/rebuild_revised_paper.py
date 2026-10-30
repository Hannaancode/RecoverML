"""Audit saved evidence, regenerate every used figure, and compile the ACM PDF."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper/acm_revised"
FIGURES = PAPER / "figures"
OUTPUT = ROOT / "output/pdf"
USED = ("methodology_rebuilt.pdf", "shared_storage.pdf", "planner_timing.pdf",
        "native_recovery.pdf", "retinal_storage.pdf", "letter_storage.pdf",
        "runtime_scaling.pdf")


def command(args, *, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(map(str, args))} failed:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tectonic", type=Path, default=None)
    args = parser.parse_args()
    audit = json.loads(command([sys.executable, str(ROOT / "scripts/audit_runtime_scaling_release.py")]).stdout)
    if audit["full"]["exact"] != 32256:
        raise ValueError("Runtime evidence audit differs")
    command([sys.executable, str(FIGURES / "make_evidence_figures.py")])
    for script in ("make_methodology.py", "make_letter_storage.py", "make_runtime_scaling.py"):
        command([sys.executable, str(FIGURES / script)])
    if any(not (FIGURES / name).is_file() for name in USED):
        raise ValueError("A primary vector figure is missing")
    tectonic = str(args.tectonic.resolve()) if args.tectonic else shutil.which("tectonic")
    if not tectonic:
        raise RuntimeError("Tectonic 0.17.0 is required; pass --tectonic PATH")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command([tectonic, "RecoverML_paper_revised.tex", "--outdir", str(OUTPUT)], cwd=PAPER)
    pdf = OUTPUT / "RecoverML_paper_revised.pdf"
    if not pdf.is_file():
        raise RuntimeError("Tectonic did not write the paper PDF")
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        info = command([pdfinfo, str(pdf)]).stdout
        match = re.search(r"^Pages:\s+(\d+)$", info, re.MULTILINE)
        if match is None or not 10 <= int(match.group(1)) <= 12:
            raise ValueError("The compiled paper is outside the 10–12 page rubric range")
        pages = int(match.group(1))
    else:
        pages = "pdfinfo unavailable"
    print(json.dumps(dict(status="PASS", pages=pages, audited_requests=audit["full"]["exact"],
                          primary_vector_figures=len(USED), pdf=str(pdf)), indent=2))


if __name__ == "__main__":
    main()
