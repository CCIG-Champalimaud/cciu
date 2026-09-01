"""Local DICOM utilities for sorting, filtering, and tag extraction.

Includes helpers for sorting slices by instance number, selecting DICOM
volumes by diffusion b-value, best-effort extraction of vendor-specific
b-value tags, and grouping DICOM files into series within a dataset tree.
"""

import os
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
from pydicom import dcmread
from pydicom.dataset import Dataset
from tqdm import tqdm

from cciu.logging_utils import get_logger

logger = get_logger(__name__)


def filter_by_bvalue_from_dict(
    dicom_files: dict,
    target_bvalue: int,
    exact: bool = False,
) -> list:
    """
    Selects the DICOM values with a b-value which is exactly or closest to
    target_bvalue (depending on whether exact is True or False).

    Args:
        dicom_files (list): list of pydicom file objects.
        target_bvalue (int): the expected b-value.
        exact (bool, optional): whether the b-value matching is to be exact
            (raises error if exact target_bvalue is not available) or
            approximate returns the b-value which is closest to target_bvalue.

    Returns:
        list: list of b-value-filtered pydicom file objects.
    """
    BVALUE_TAG = ("0018", "9087")
    SIEMENS_BVALUE_TAG = ("0019", "100c")
    GE_BVALUE_TAG = ("0043", "1039")
    bvalues = []
    logger.info(f"Filtering by b-value using {target_bvalue}")
    for k, d in dicom_files.items():
        curr_bvalue = None
        bvalue = d.get(BVALUE_TAG, None)
        siemens_bvalue = d.get(SIEMENS_BVALUE_TAG, None)
        ge_bvalue = d.get(GE_BVALUE_TAG, None)
        if bvalue is not None:
            logger.debug("Using bvalue.value")
            curr_bvalue = bvalue.value
        elif siemens_bvalue is not None:
            logger.debug("Using siemens_bvalue.value")
            curr_bvalue = siemens_bvalue.value
        elif ge_bvalue is not None:
            logger.debug("Using ge_value.value")
            curr_bvalue = ge_bvalue.value
            if isinstance(curr_bvalue, bytes):
                curr_bvalue = curr_bvalue.decode()
            curr_bvalue = str(curr_bvalue)
            if "[" in curr_bvalue and "]" in curr_bvalue:
                curr_bvalue = (
                    curr_bvalue.strip().strip("[").strip("]").split(",")
                )
                curr_bvalue = [int(x) for x in curr_bvalue]
            if isinstance(curr_bvalue, list) is False:
                curr_bvalue = curr_bvalue.split("\\")
                curr_bvalue = str(curr_bvalue[0])
            else:
                curr_bvalue = str(curr_bvalue[0])
            if len(curr_bvalue) > 5:
                curr_bvalue = curr_bvalue[-4:]
        if curr_bvalue is None:
            curr_bvalue = 0
        bvalues.append(int(curr_bvalue))
    unique_bvalues = set(bvalues)
    if len(unique_bvalues) in [0, 1]:
        return dicom_files
    logger.info(f"Detected {len(unique_bvalues)} unique b-values")
    if (target_bvalue not in unique_bvalues) and (exact is True):
        raise RuntimeError("Requested b-value not available")
    best_bvalue = sorted(unique_bvalues, key=lambda b: abs(b - target_bvalue))[
        0
    ]
    logger.info(f"Keeping instances with b-value={best_bvalue}")
    dicom_files = {
        k: d
        for (k, d), b in zip(dicom_files.items(), bvalues)
        if b == best_bvalue
    }
    return dicom_files


def sort_dicom_datasets(datasets: list[Dataset]) -> list[int]:
    """
    Sorts DICOM slices by spatial position along the slice normal.

    Uses ImageOrientationPatient to compute the slice normal and projects
    each slice's ImagePositionPatient onto it, sorting by the resulting
    scalar. This ensures correct spatial ordering regardless of
    InstanceNumber conventions.

    Falls back to SliceLocation, then InstanceNumber, when ImagePositionPatient
    is not available.

    Args:
        datasets (list[Dataset]): list of pydicom Dataset objects.

    Returns:
        list[int] | None: indices of the datasets in spatial order, or None
        if no spatial or fallback ordering keys are available.

    """
    if all("ImagePositionPatient" in ds for ds in datasets):
        positions = np.array([list(ds.ImagePositionPatient) for ds in datasets])

        ref_ds = datasets[0]
        if "ImageOrientationPatient" in ref_ds:
            iop = np.array(ref_ds.ImageOrientationPatient).reshape(2, 3)
            normal = np.cross(iop[0], iop[1])
            normal = normal / np.linalg.norm(normal)
        else:
            normal = np.array([0, 0, 1])

        projections = positions @ normal
        order = np.argsort(projections)
        return [i for i in order]

    logger.warning(
        "ImagePositionPatient not available for all slices, trying SliceLocation..."
    )

    if all("SliceLocation" in ds for ds in datasets):
        sort_keys = [float(ds.SliceLocation) for ds in datasets]
        order = np.argsort(sort_keys)
        return [i for i in order]

    logger.warning(
        "SliceLocation not available for all slices, trying InstanceNumber..."
    )

    if all("InstanceNumber" in ds for ds in datasets):
        sort_keys = [int(ds.InstanceNumber) for ds in datasets]
        order = np.argsort(sort_keys)
        return [i for i in order]

    return None


def sort_dicom_files(
    file_paths: list[str] | None = None,
) -> list[str] | list[Dataset]:
    """
    Wrapper around ``sort_dicom_datasets`` for files.

    Falls back to SliceLocation, then InstanceNumber, then filename order
    when ImagePositionPatient is not available.

    Args:
        file_paths (list[str], optional): list of DICOM file paths. Defaults to
            None (``files`` should be specified).

    Returns:
        list[str] | list[Dataset]: sorted list of DICOM files.
    """

    if len(file_paths) <= 1:
        return file_paths

    datasets = [dcmread(p, stop_before_pixels=True) for p in file_paths]

    order = sort_dicom_datasets(datasets)
    if order is None:
        return sorted(file_paths)
    return [file_paths[i] for i in order]


def get_orientation_string(dicom_file: Dataset) -> str:
    """
    Gets the orientation string from a DICOM dataset.

    Args:
        dicom_file (Dataset): DICOM dataset.

    Returns:
        str: orientation string.
    """

    ORIENTATION_KEY = [0x0020, 0x0037]
    if ORIENTATION_KEY not in dicom_file:
        return "Not available"
    orientation = dicom_file[ORIENTATION_KEY]
    if not orientation:
        return "Not available"
    orientation = [round(x) for x in orientation]
    plane = np.cross(orientation[0:3], orientation[3:6])
    plane = [abs(x) for x in plane]
    if plane[0] == 1:
        return "Sagittal"
    elif plane[1] == 1:
        return "Coronal"
    elif plane[2] == 1:
        return "Axial"
    return "Oblique"


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


def _extract_bvalue(ds: Any) -> tuple[int | None, str | None]:
    """Best-effort extraction of diffusion b-value from a DICOM dataset.

    Tries standard and common vendor-specific tags. Returns a tuple of
    (b_value, source) where b_value is an integer when possible and
    source is a string indicating which tag was used ("global",
    "siemens", "ge", or None).
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
            return int(bvalue_elem.value), "global"
        except Exception:
            pass

    siemens_elem = ds.get(SIEMENS_BVALUE_TAG, None)
    if siemens_elem is not None:
        b = _normalize_siemens_bvalue(
            getattr(siemens_elem, "value", siemens_elem)
        )
        if b is not None:
            return b, "siemens"

    ge_elem = ds.get(GE_BVALUE_TAG, None)
    if ge_elem is not None:
        b = _normalize_ge_bvalue(getattr(ge_elem, "value", ge_elem))
        if b is not None:
            return b, "ge"

    return None, None


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


extract_bvalue = _extract_bvalue


def iter_dicom_paths(root: str | Path) -> list[str]:
    """List the file paths under *root*.

    Args:
        root (str | Path): Root directory to walk.

    Returns:
        list[str]: The paths of all files found under *root*.
    """
    root = Path(root)
    return [
        str(Path(dirpath) / name)
        for dirpath, _, filenames in os.walk(root)
        for name in filenames
    ]


def read_basic_tags(path: str | Path) -> dict[str, str]:
    """Read the tags needed to group a DICOM file into a series.

    Args:
        path (str | Path): Path to the DICOM instance.

    Returns:
        dict[str, str]: A dictionary with ``PatientID``, ``StudyInstanceUID``,
            and ``SeriesInstanceUID``, or an empty dict if the file cannot be
            read.
    """
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
        return {}
    return {
        "PatientID": getattr(ds, "PatientID", ""),
        "StudyInstanceUID": getattr(ds, "StudyInstanceUID", ""),
        "SeriesInstanceUID": getattr(ds, "SeriesInstanceUID", ""),
    }


def _read_basic_tags_with_path(path: str) -> tuple[str, dict[str, str]]:
    """Read basic tags for one path, returning the path alongside them.

    Args:
        path (str): Path to the DICOM instance.

    Returns:
        tuple[str, dict[str, str]]: The path and its basic tags.
    """
    return path, read_basic_tags(path)


def group_into_series(
    paths: list[str | Path],
    n_workers: int = 0,
    show_progress: bool = False,
) -> dict[tuple[str, str, str], list[str]]:
    """Group DICOM file paths into series.

    Series are keyed by ``(PatientID, StudyInstanceUID, SeriesInstanceUID)``.
    Files that cannot be read are skipped. When ``n_workers`` is 2 or more the
    basic tags are read in parallel.

    Args:
        paths (list[str | Path]): DICOM file paths to group.
        n_workers (int, optional): Number of parallel processes to use when
            reading basic tags. Values below 2 use the main thread.
            Defaults to 0.
        show_progress (bool, optional): Whether to show a progress bar.
            Defaults to False.

    Returns:
        dict[tuple[str, str, str], list[str]]: Series key to file paths.
    """
    paths = [str(p) for p in paths]
    series_files: dict[tuple[str, str, str], list[str]] = defaultdict(list)

    if n_workers < 2:
        iterator = tqdm(paths) if show_progress else paths
        for path in iterator:
            tags = read_basic_tags(path)
            if not tags:
                continue
            key = (
                tags["PatientID"],
                tags["StudyInstanceUID"],
                tags["SeriesInstanceUID"],
            )
            series_files[key].append(path)
        return series_files

    with Pool(n_workers) as pool:
        results = pool.imap_unordered(_read_basic_tags_with_path, paths)
        iterator = tqdm(results, total=len(paths)) if show_progress else results
        for path, tags in iterator:
            if not tags:
                continue
            key = (
                tags["PatientID"],
                tags["StudyInstanceUID"],
                tags["SeriesInstanceUID"],
            )
            series_files[key].append(path)
    return series_files
