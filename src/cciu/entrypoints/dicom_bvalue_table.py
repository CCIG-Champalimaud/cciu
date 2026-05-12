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


def _normalize_ge_bvalue(raw: Any) -> int | None:
    """Normalise GE b-value representations to a single integer.

    Handles bytes, lists, and backslash- or comma-separated strings.
    """
    if raw is None:
        return None

    curr_bvalue = raw
    if isinstance(curr_bvalue, bytes):
        curr_bvalue = curr_bvalue.decode()

    curr_bvalue = str(curr_bvalue)
    # GE might encode as "[0, 800, ...]"
    if "[" in curr_bvalue and "]" in curr_bvalue:
        parts = curr_bvalue.strip().strip("[").strip("]").split(",")
        try:
            vals = [int(x) for x in parts]
        except Exception:
            vals = []
        curr_bvalue = vals[0] if vals else None
    else:
        # Or as "0\\800\\..."
        parts = curr_bvalue.split("\\")
        try:
            curr_bvalue = int(parts[0])
        except Exception:
            curr_bvalue = None

    if isinstance(curr_bvalue, int):
        return curr_bvalue
    return None


def _normalize_siemens_bvalue(raw: Any) -> int | None:
    """Normalise Siemens b-value representations to a single integer."""
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _extract_bvalue(ds: Any) -> int | None:
    """Best-effort extraction of diffusion b-value from a DICOM dataset.

    Tries standard and common vendor-specific tags. Returns an integer b-value
    when possible, otherwise None.
    """
    # Standard tag (0018,9087) - Diffusion b-value
    BVALUE_TAG = ("0018", "9087")
    # Siemens private tag
    SIEMENS_BVALUE_TAG = ("0019", "100c")
    # GE private tag
    GE_BVALUE_TAG = ("0043", "1039")

    bvalue_elem = ds.get(BVALUE_TAG, None)
    if bvalue_elem is not None:
        try:
            return int(bvalue_elem.value)
        except Exception:
            pass

    siemens_elem = ds.get(SIEMENS_BVALUE_TAG, None)
    if siemens_elem is not None:
        b = _normalize_siemens_bvalue(
            getattr(siemens_elem, "value", siemens_elem)
        )
        if b is not None:
            return b

    ge_elem = ds.get(GE_BVALUE_TAG, None)
    if ge_elem is not None:
        b = _normalize_ge_bvalue(getattr(ge_elem, "value", ge_elem))
        if b is not None:
            return b

    return None


def _extract_bvalue_ge(ds: Any) -> int | None:
    """Extract GE-specific b-value using the shared normalisation."""
    GE_BVALUE_TAG = ("0043", "1039")
    ge_elem = ds.get(GE_BVALUE_TAG, None)
    return _normalize_ge_bvalue(
        getattr(ge_elem, "value", ge_elem) if ge_elem is not None else None
    )


def _extract_bvalue_siemens(ds: Any) -> int | None:
    """Extract Siemens-specific b-value using the shared normalisation."""
    SIEMENS_BVALUE_TAG = ("0019", "100c")
    siemens_elem = ds.get(SIEMENS_BVALUE_TAG, None)
    return _normalize_siemens_bvalue(
        getattr(siemens_elem, "value", siemens_elem)
        if siemens_elem is not None
        else None
    )


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
            b = _extract_bvalue(ds)
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
