"""CLI entrypoint to export a per-series metadata table from DICOM files."""

import argparse
from pathlib import Path
from typing import Any

from pydicom import dcmread

from cciu.dicom_utils import (
    _extract_bvalue,
    group_into_series,
    iter_dicom_paths,
)
from cciu.entrypoints._output_utils import open_output, write_output
from cciu.logging_utils import get_logger

logger = get_logger(__name__)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add ``dicom-series-table`` arguments to an argument parser.

    Args:
        parser (argparse.ArgumentParser): The parser to populate.

    Returns:
        argparse.ArgumentParser: The populated parser.
    """
    parser.add_argument(
        "--input",
        required=True,
        help="Root directory containing DICOM files (dataset level)",
    )
    parser.add_argument(
        "--n_workers",
        required=False,
        default=0,
        type=int,
        help="Number of parallel processes. (default: 0 (no parallel processes)).",
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


def _iter_series(root: Path, n_workers: int = 0):
    """Yield grouped series information from a DICOM directory.

    Args:
        root (Path): Root directory containing DICOM files.
        n_workers (int, optional): Number of parallel processes to use when
            reading basic tags. Values below 2 use the main thread.

    Yields:
        tuple[tuple[str, str, str], Dataset, int]: The series key
        ``(patient_id, study_uid, series_uid)``, a representative pydicom
        dataset, and the number of instances in the series.
    """
    paths = iter_dicom_paths(root)
    series_files = group_into_series(
        paths, n_workers=n_workers, show_progress=True
    )

    for (
        patient_id,
        study_uid,
        series_uid,
    ), series_paths in series_files.items():
        if not series_paths:
            continue
        try:
            rep_ds = dcmread(str(series_paths[0]), stop_before_pixels=True)
        except Exception:
            continue
        yield (patient_id, study_uid, series_uid), rep_ds, len(series_paths)


def main(args: argparse.Namespace) -> None:
    """Export a per-series metadata table and write the results.

    Args:
        args (argparse.Namespace): Parsed CLI arguments, including ``input``,
            ``n_workers``, ``output``, and ``format``.
    """
    root = Path(args.input)
    if not root.is_dir():
        raise SystemExit(
            f"Input directory does not exist or is not a directory: {root}"
        )

    rows: list[dict[str, Any]] = []

    for (patient_id, study_uid, series_uid), ds, num_instances in _iter_series(
        root, args.n_workers
    ):
        bvalue, provenance = _extract_bvalue(ds)
        row: dict[str, Any] = {
            "patient_id": patient_id,
            "study_uid": str(study_uid),
            "series_uid": str(series_uid),
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
            "bvalue": bvalue,
            "bvalue_provenance": provenance,
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
        "bvalue",
        "bvalue_provenance",
    ]
    out_fh, close_out = open_output(args.output)
    try:
        write_output(rows, args.format, out_fh, fieldnames=fieldnames)
    finally:
        if close_out and out_fh is not None:
            out_fh.close()
