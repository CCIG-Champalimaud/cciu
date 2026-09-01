"""Unit tests for the cciu exception hierarchy."""

import pytest

from cciu.exceptions import (
    CCIUError,
    DICOMReadError,
    OrthancError,
    UnsupportedFormatError,
)


def test_subclasses_inherit_from_base():
    for exc in (DICOMReadError, OrthancError, UnsupportedFormatError):
        assert issubclass(exc, CCIUError)


def test_unsupported_format_carries_message():
    with pytest.raises(UnsupportedFormatError, match="unsupported"):
        raise UnsupportedFormatError("unsupported input")
