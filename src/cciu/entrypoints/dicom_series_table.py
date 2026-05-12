import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydicom import dcmread

from cciu.logging_utils import get_logger

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
        choices=["csv", "json", "jsonl"],
        default="csv",
        help="Output format (default: csv)",
    )
    return parser


def _iter_series(root: Path):
    """Yield (series_key, representative_ds, num_instances) for each series.

    series_key = (patient_id, study_uid, series_uid)
    """
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

    for key, paths in series_files.items():
        if not paths:
            continue
        try:
            rep_ds = dcmread(str(paths[0]), stop_before_pixels=True)
        except Exception:
            continue
        yield key, rep_ds, len(paths)


def main(args: argparse.Namespace) -> None:
    root = Path(args.input)
    if not root.is_dir():
        raise SystemExit(
            f"Input directory does not exist or is not a directory: {root}"
        )

    rows: list[dict[str, Any]] = []

    for (patient_id, study_uid, series_uid), ds, num_instances in _iter_series(
        root
    ):
        row: dict[str, Any] = {
            "patient_id": patient_id,
            "study_uid": study_uid,
            "series_uid": series_uid,
            "modality": getattr(ds, "Modality", ""),
            "series_description": getattr(ds, "SeriesDescription", ""),
            "study_description": getattr(ds, "StudyDescription", ""),
            "body_part_examined": getattr(ds, "BodyPartExamined", ""),
            "protocol_name": getattr(ds, "ProtocolName", ""),
            "manufacturer": getattr(ds, "Manufacturer", ""),
            "manufacturer_model_name": getattr(ds, "ManufacturerModelName", ""),
            "rows": getattr(ds, "Rows", None),
            "columns": getattr(ds, "Columns", None),
            "num_instances": num_instances,
        }
        rows.append(row)

    if args.output:
        out_fh = open(args.output, "w", newline="", encoding="utf-8")
        close_out = True
    else:
        out_fh = None
        close_out = False

    fieldnames = [
        "patient_id",
        "study_uid",
        "series_uid",
        "modality",
        "series_description",
        "study_description",
        "body_part_examined",
        "protocol_name",
        "manufacturer",
        "manufacturer_model_name",
        "rows",
        "columns",
        "num_instances",
    ]

    try:
        if args.format == "csv":
            writer = csv.DictWriter(out_fh or sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        elif args.format == "json":
            text = json.dumps(rows, indent=2, default=str)
            if out_fh is None:
                print(text)
            else:
                out_fh.write(text + "\n")
        else:  # jsonl
            for row in rows:
                line = json.dumps(row, default=str)
                if out_fh is None:
                    print(line)
                else:
                    out_fh.write(line + "\n")
    finally:
        if close_out and out_fh is not None:
            out_fh.close()
