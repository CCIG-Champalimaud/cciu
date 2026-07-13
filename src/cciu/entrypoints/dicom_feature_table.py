import argparse
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydicom import dcmread

from cciu.entrypoints._output_utils import open_output, write_output
from cciu.dicom_utils import (
    _extract_bvalue,
    _extract_bvalue_ge,
    _extract_bvalue_siemens,
)
from cciu.logging_utils import get_logger

logger = get_logger(__name__)


dicom_header_dict: dict[str, tuple[str, str]] = dict(
    study_uid=("0020", "000D"),
    series_uid=("0020", "000E"),
    diffusion_bvalue=("0018", "9087"),
    diffusion_directionality=("0018", "9075"),
    echo_time=("0018", "0081"),
    echo_train_length=("0018", "0091"),
    repetition_time=("0018", "0080"),
    flip_angle=("0018", "1314"),
    in_plane_phase_encoding_direction=("0018", "1312"),
    mr_acquisition_type=("0018", "0023"),
    acquisition_matrix=("0018", "1310"),
    patient_position=("0018", "5100"),
    reconstruction_matrix=("0018", "1100"),
    magnetic_field_strength=("0018", "0087"),
    manufacturer=("0008", "0070"),
    manufacturer_model_name=("0008", "1090"),
    body_part_examined=("0018", "0015"),
    number_of_phase_encoding_steps=("0018", "0089"),
    percent_phase_field_of_view=("0018", "0094"),
    pixel_bandwidth=("0018", "0095"),
    receive_coil_name=("0018", "1250"),
    transmit_coil_name=("0018", "1251"),
    sar=("0018", "1316"),
    scanning_sequence=("0018", "0020"),
    sequence_variant=("0018", "0021"),
    slice_thickness=("0018", "0050"),
    software_versions=("0018", "1020"),
    temporal_resolution=("0020", "0110"),
    image_orientation_patient=("0020", "0037"),
    image_type=("0008", "0008"),
    scan_options=("0018", "0022"),
    photometric_interpretation=("0028", "0004"),
    spectrally_selected_suppression=("0018", "9025"),
    inversion_time=("0018", "0082"),
    pixel_spacing=("0028", "0030"),
    number_of_echos=("0018", "0086"),
    number_of_temporal_positions=("0020", "0105"),
    modality=("0008", "0060"),
    series_description=("0008", "103E"),
    diffusion_bvalue_ge=("0043", "1039"),
    diffusion_bvalue_siemens=("0019", "100c"),
)

inverted_dicom_header_dict: dict[tuple[str, str], str] = {
    v: k for k, v in dicom_header_dict.items()
}


DEFAULT_TAGS = list(dicom_header_dict.keys())


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
    parser.add_argument(
        "--tags",
        nargs="*",
        default=DEFAULT_TAGS,
        help="DICOM keywords to extract as features (default: a small curated set)",
    )
    return parser


def main(args: argparse.Namespace) -> None:
    root = Path(args.input)
    if not root.is_dir():
        raise SystemExit(
            f"Input directory does not exist or is not a directory: {root}"
        )

    feature_rows: list[dict[str, Any]] = []

    # Names of fields to extract. These are logical names (keys of dicom_header_dict)
    # and/or raw DICOM attribute keywords for getattr(ds, ...).
    field_names: list[str] = args.tags or DEFAULT_TAGS

    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                ds = dcmread(str(path), stop_before_pixels=True)
            except Exception:
                continue

            row: dict[str, Any] = {}
            for field in field_names:
                # Normalised b-value using shared helpers
                if field == "diffusion_bvalue":
                    b = _extract_bvalue(ds)
                    row[field] = None if b is None else int(b)
                    continue
                if field == "diffusion_bvalue_ge":
                    b_ge = _extract_bvalue_ge(ds)
                    row[field] = None if b_ge is None else int(b_ge)
                    continue
                if field == "diffusion_bvalue_siemens":
                    b_siemens = _extract_bvalue_siemens(ds)
                    row[field] = None if b_siemens is None else int(b_siemens)
                    continue

                if field in dicom_header_dict:
                    tag = dicom_header_dict[field]
                    elem = ds.get(tag, None)
                    if elem is None:
                        row[field] = None
                    else:
                        # pydicom DataElement exposes .value
                        value = getattr(elem, "value", elem)
                        row[field] = str(value)
                else:
                    # Fallback: interpret as DICOM keyword / attribute name
                    value = getattr(ds, field, None)
                    row[field] = None if value is None else str(value)

            feature_rows.append(row)

    fh, close_out = open_output(args.output)
    try:
        write_output(feature_rows, args.format, fh, fieldnames=field_names)
    finally:
        if close_out and fh is not None:
            fh.close()
