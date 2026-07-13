import argparse
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydicom import dcmread

from cciu.entrypoints._output_utils import open_output, write_output
from cciu.logging_utils import get_logger
from cciu.dicom_utils import _extract_bvalue

logger = get_logger(__name__)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        required=True,
        help="Root directory containing DICOM files (dataset level)",
    )
    parser.add_argument(
        "--output",
        help="Optional path to output file (default: stdout)",
        default=None,
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "jsonl", "yaml"],
        default="csv",
        help="Output format (default: csv)",
    )
    return parser

def main(args: argparse.Namespace) -> None:
    root = Path(args.input)
    if not root.is_dir():
        raise SystemExit(
            f"Input directory does not exist or is not a directory: {root}"
        )

    # Group files by (PatientID, StudyInstanceUID, SeriesInstanceUID)
    series_files: dict[tuple[str, str, str], list[Path]] = defaultdict(list)

    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                ds = dcmread(
                    str(path),
                    stop_before_pixels=True,
                    specific_tags=[
                        "PatientID",
                        "StudyInstanceUID",
                        "SeriesInstanceUID",
                    ],
                )
            except Exception:
                continue
            patient_id = getattr(ds, "PatientID", "")
            study_uid = getattr(ds, "StudyInstanceUID", "")
            series_uid = getattr(ds, "SeriesInstanceUID", "")
            if not series_uid:
                continue
            series_files[(patient_id, study_uid, series_uid)].append(path)

    rows: list[dict[str, Any]] = []

    for (patient_id, study_uid, series_uid), paths in series_files.items():
        if not paths:
            continue
        # Use first instance as representative for series-level metadata
        try:
            rep_ds = dcmread(
                str(paths[0]),
                stop_before_pixels=True,
            )
        except Exception:
            continue

        series_description = getattr(rep_ds, "SeriesDescription", "")
        modality = getattr(rep_ds, "Modality", "")

        # Collect b-values across instances
        bvalues: list[int] = []
        for p in paths:
            try:
                ds = dcmread(str(p), stop_before_pixels=True)
            except Exception:
                continue
            b, _ = _extract_bvalue(ds)
            if b is not None:
                bvalues.append(b)

        bvalue_counts: dict[int, int] = defaultdict(int)
        for b in bvalues:
            bvalue_counts[b] += 1

        row: dict[str, Any] = {
            "patient_id": patient_id,
            "study_uid": study_uid,
            "series_uid": series_uid,
            "modality": modality,
            "series_description": series_description,
            "num_instances": len(paths),
            "bvalues": sorted(set(bvalues)) if bvalues else [],
            "bvalue_counts": dict(sorted(bvalue_counts.items())),
        }
        rows.append(row)

    fieldnames = [
        "patient_id",
        "study_uid",
        "series_uid",
        "modality",
        "series_description",
        "num_instances",
        "bvalues",
        "bvalue_counts",
    ]
    out_fh, close_out = open_output(args.output)
    try:
        write_output(rows, args.format, out_fh, fieldnames=fieldnames)
    finally:
        if close_out and out_fh is not None:
            out_fh.close()
