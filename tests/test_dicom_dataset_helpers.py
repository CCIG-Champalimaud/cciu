"""Unit tests for DICOM dataset-walking and series-grouping helpers."""

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from cciu.dicom_utils import (
    group_into_series,
    iter_dicom_paths,
    read_basic_tags,
)


def _make_dicom(path, series_uid=None, study_uid=None):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = meta
    ds.preamble = b"\x00" * 128
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = generate_uid()
    ds.PatientID = "123"
    ds.SeriesInstanceUID = series_uid or generate_uid()
    ds.StudyInstanceUID = study_uid or generate_uid()
    ds.Rows = 4
    ds.Columns = 4
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = np.zeros((4, 4), dtype=np.uint16).tobytes()
    ds.save_as(str(path))
    return ds


def test_iter_dicom_paths_lists_files(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    _make_dicom(d / "a.dcm")
    (d / "notes.txt").write_text("hello", encoding="utf-8")
    paths = iter_dicom_paths(d)
    assert len(paths) == 2


def test_read_basic_tags(tmp_path):
    path = tmp_path / "a.dcm"
    ds = _make_dicom(path)
    tags = read_basic_tags(path)
    assert tags["PatientID"] == "123"
    assert tags["SeriesInstanceUID"] == ds.SeriesInstanceUID


def test_group_into_series_separates_series(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    series_a = generate_uid()
    series_b = generate_uid()
    study_a = generate_uid()
    study_b = generate_uid()
    _make_dicom(d / "a1.dcm", series_uid=series_a, study_uid=study_a)
    _make_dicom(d / "a2.dcm", series_uid=series_a, study_uid=study_a)
    _make_dicom(d / "b1.dcm", series_uid=series_b, study_uid=study_b)

    paths = iter_dicom_paths(d)
    grouped = group_into_series(paths)

    assert len(grouped) == 2
    counts = sorted(len(v) for v in grouped.values())
    assert counts == [1, 2]


def test_group_into_series_skips_non_dicom(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    _make_dicom(d / "a.dcm")
    (d / "notes.txt").write_text("hello", encoding="utf-8")
    paths = iter_dicom_paths(d)
    grouped = group_into_series(paths)
    assert sum(len(v) for v in grouped.values()) == 1
