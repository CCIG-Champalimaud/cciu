"""Unit tests for input format detection and generic loading (io_utils)."""

import numpy as np
import SimpleITK as sitk
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from cciu.exceptions import UnsupportedFormatError
from cciu.io_utils import (
    ImageKind,
    classify_path,
    is_dicom,
    is_dicom_seg,
    is_dicom_series,
    is_sitk_readable,
    provenance,
    read_image_any,
)

SEG_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.66.4"


def _make_sitk(path, size=(4, 4, 4)):
    arr = np.zeros(size, dtype=np.uint8)
    img = sitk.GetImageFromArray(arr)
    sitk.WriteImage(img, str(path))
    return path


def _make_dicom(path, sop_class_uid="1.2.840.10008.5.1.4.1.1.2"):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class_uid
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = meta
    ds.preamble = b"\x00" * 128
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = generate_uid()
    ds.Modality = "CT"
    ds.PatientID = "123"
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Rows = 4
    ds.Columns = 4
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = np.zeros((4, 4), dtype=np.uint16).tobytes()
    ds.save_as(str(path))
    return path


def test_classify_sitk_file(tmp_path):
    path = _make_sitk(tmp_path / "img.nii.gz")
    assert classify_path(path) is ImageKind.SITK_IMAGE
    assert is_sitk_readable(path) is True


def test_classify_single_dicom_file(tmp_path):
    path = _make_dicom(tmp_path / "slice.dcm")
    assert classify_path(path) is ImageKind.DICOM_SINGLE_FILE
    assert is_dicom(path) is True


def test_classify_dicom_series(tmp_path):
    d = tmp_path / "series"
    d.mkdir()
    _make_dicom(d / "1.dcm")
    _make_dicom(d / "2.dcm")
    assert classify_path(d) is ImageKind.DICOM_SERIES
    assert is_dicom_series(d) is True


def test_classify_dicom_seg(tmp_path):
    path = _make_dicom(tmp_path / "seg.dcm", SEG_SOP_CLASS_UID)
    assert classify_path(path) is ImageKind.DICOM_SEG
    assert is_dicom_seg(path) is True

    d = tmp_path / "seg_dir"
    d.mkdir()
    _make_dicom(d / "seg.dcm", SEG_SOP_CLASS_UID)
    assert classify_path(d) is ImageKind.DICOM_SEG


def test_classify_unknown(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    assert classify_path(path) is ImageKind.UNKNOWN
    assert is_sitk_readable(path) is False
    assert is_dicom(path) is False


def test_read_image_any_sitk(tmp_path):
    path = _make_sitk(tmp_path / "img.mha")
    img = read_image_any(path)
    assert isinstance(img, sitk.Image)
    assert img.GetSize() == (4, 4, 4)


def test_read_image_any_unknown_raises(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        read_image_any(path)


def test_provenance_unknown(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    info = provenance(path)
    assert info["path"] == str(path)
    assert info["kind"] == "unknown"
