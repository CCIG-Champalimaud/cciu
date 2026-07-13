import numpy as np
from typing import Any
from pydicom import dcmread
from pydicom.dataset import Dataset

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
            curr_bvalue = bvalue.value
        elif siemens_bvalue is not None:
            curr_bvalue = siemens_bvalue.value
        elif ge_bvalue is not None:
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


def sort_dicom_slices(file_paths: list[str]) -> list[str]:
    """
    Sorts DICOM slices by instance number.

    Args:
        file_paths (list[str]): list of DICOM files.

    Returns:
        list[str]: sorted list of DICOM files.
    """

    if len(file_paths) <= 1:
        return file_paths

    instance_numbers = []
    for p in file_paths:
        ds = dcmread(p, stop_before_pixels=True)
        instance_numbers.append(int(getattr(ds, "InstanceNumber")))
    order = np.argsort(np.array(instance_numbers))
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
