"""Input format detection and generic loading of medical images."""

from enum import Enum
from pathlib import Path
from typing import Any

import SimpleITK as sitk
from pydicom import dcmread

from cciu.exceptions import UnsupportedFormatError
from cciu.sitk_utils import read_dicom_as_sitk, read_dicom_seg_as_volume

SEG_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.66.4"


class ImageKind(Enum):
    """Input kinds recognised by :func:`classify_path`."""

    DICOM_SERIES = "dicom_series"
    DICOM_SINGLE_FILE = "dicom_single_file"
    DICOM_SEG = "dicom_seg"
    SITK_IMAGE = "sitk_image"
    UNKNOWN = "unknown"


def _is_dicom_file(path: Path) -> bool:
    """Return whether *path* is a DICOM file.

    Args:
        path (Path): path to inspect.

    Returns:
        bool: True if the file can be read as a DICOM dataset.
    """
    try:
        dcmread(str(path), stop_before_pixels=True)
        return True
    except Exception:
        return False


def _is_seg(path: Path) -> bool:
    """Return whether *path* is a DICOM SEG file.

    Args:
        path (Path): path to inspect.

    Returns:
        bool: True if the file has the SEG SOP Class UID.
    """
    try:
        ds = dcmread(str(path), stop_before_pixels=True)
        return str(ds.SOPClassUID) == SEG_SOP_CLASS_UID
    except Exception:
        return False


def is_dicom(path: str | Path) -> bool:
    """Return whether *path* points to a DICOM file.

    Args:
        path (str | Path): path to inspect.

    Returns:
        bool: True if the path is a DICOM file.
    """
    path = Path(path)
    if path.is_dir():
        return any(f.is_file() and _is_dicom_file(f) for f in path.iterdir())
    return path.is_file() and _is_dicom_file(path)


def is_dicom_series(path: str | Path) -> bool:
    """Return whether *path* points to a directory holding a DICOM series.

    Args:
        path (str | Path): path to inspect.

    Returns:
        bool: True if the path is a directory containing DICOM files.
    """
    path = Path(path)
    if not path.is_dir():
        return False
    return is_dicom(path)


def is_dicom_seg(path: str | Path) -> bool:
    """Return whether *path* points to a DICOM SEG file.

    Args:
        path (str | Path): path to inspect.

    Returns:
        bool: True if the path is a DICOM SEG file.
    """
    path = Path(path)
    if path.is_dir():
        dicom_files = [
            f for f in path.iterdir() if f.is_file() and _is_dicom_file(f)
        ]
        return len(dicom_files) == 1 and _is_seg(dicom_files[0])
    return path.is_file() and _is_seg(path)


def is_sitk_readable(path: str | Path) -> bool:
    """Return whether *path* can be read by SimpleITK.

    Args:
        path (str | Path): path to inspect.

    Returns:
        bool: True if the path can be read as a SimpleITK image.
    """
    path = Path(path)
    if not path.is_file():
        return False
    try:
        sitk.ReadImage(str(path))
        return True
    except Exception:
        return False


def classify_path(path: str | Path) -> ImageKind:
    """Classify an input path into a supported :class:`ImageKind`.

    A directory containing DICOM files is reported as a DICOM series (or as a
    DICOM SEG when it holds exactly one SEG file). A file is classified by
    trying DICOM detection first and falling back to SimpleITK readability.

    Args:
        path (str | Path): path to classify.

    Returns:
        ImageKind: The detected input kind.
    """
    path = Path(path)

    if path.is_dir():
        dicom_files = [
            f for f in path.iterdir() if f.is_file() and _is_dicom_file(f)
        ]
        if not dicom_files:
            return ImageKind.UNKNOWN
        if len(dicom_files) == 1 and _is_seg(dicom_files[0]):
            return ImageKind.DICOM_SEG
        return ImageKind.DICOM_SERIES

    if not path.is_file():
        return ImageKind.UNKNOWN

    if _is_dicom_file(path):
        if _is_seg(path):
            return ImageKind.DICOM_SEG
        return ImageKind.DICOM_SINGLE_FILE

    if is_sitk_readable(path):
        return ImageKind.SITK_IMAGE

    return ImageKind.UNKNOWN


def read_image_any(path: str | Path) -> sitk.Image:
    """Load *path* as a :class:`SimpleITK.Image` regardless of input kind.

    Dispatches to the appropriate reader based on :func:`classify_path`.

    Args:
        path (str | Path): path to load.

    Returns:
        sitk.Image: The loaded image.

    Raises:
        UnsupportedFormatError: If the input kind is not recognised.
    """
    path = Path(path)
    kind = classify_path(path)

    if kind in (ImageKind.DICOM_SERIES, ImageKind.DICOM_SINGLE_FILE):
        image, _ = read_dicom_as_sitk(str(path))
        return image
    if kind == ImageKind.DICOM_SEG:
        return read_dicom_seg_as_volume(path)
    if kind == ImageKind.SITK_IMAGE:
        return sitk.ReadImage(str(path))

    raise UnsupportedFormatError(
        f"Could not determine a supported format for input: {path}"
    )


def provenance(path: str | Path) -> dict[str, Any]:
    """Return a descriptive summary of *path* and how it would be read.

    Args:
        path (str | Path): path to inspect.

    Returns:
        dict[str, Any]: A dictionary with ``path``, ``kind``, and (where
            applicable) ``reader``, ``sop_class_uid``, ``modality``, and
            ``series_uid``.
    """
    path = Path(path)
    kind = classify_path(path)
    info: dict[str, Any] = {"path": str(path), "kind": kind.value}

    if kind is ImageKind.UNKNOWN:
        return info

    if kind is ImageKind.SITK_IMAGE:
        info["reader"] = "SimpleITK"
        return info

    try:
        ds = dcmread(str(path), stop_before_pixels=True)
        info["reader"] = "pydicom"
        info["sop_class_uid"] = str(getattr(ds, "SOPClassUID", ""))
        info["modality"] = str(getattr(ds, "Modality", ""))
        info["series_uid"] = str(getattr(ds, "SeriesInstanceUID", ""))
    except Exception:
        info["reader"] = "pydicom"

    return info
