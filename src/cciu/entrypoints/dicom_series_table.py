import argparse
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydicom import dcmread

from cciu.entrypoints._output_utils import open_output, write_output
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
        choices=["csv", "json", "jsonl", "yaml"],
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
    out_fh, close_out = open_output(args.output)
    try:
        write_output(rows, args.format, out_fh, fieldnames=fieldnames)
    finally:
        if close_out and out_fh is not None:
            out_fh.close()
