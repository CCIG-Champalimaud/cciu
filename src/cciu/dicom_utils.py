import numpy as np
from pydicom import dcmread

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

    orientation = dicom_file.get("ImageOrientationPatient", None)
    orientation = [round(x) for x in orientation]
    plane = np.cross(IOP_round[0:3], IOP_round[3:6])
    plane = [abs(x) for x in plane]
    if plane[0] == 1:
        return "Sagittal"
    elif plane[1] == 1:
        return "Coronal"
    elif plane[2] == 1:
        return "Axial"
