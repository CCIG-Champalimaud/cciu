"""Exception hierarchy for the ``cciu`` package."""


class CCIUError(Exception):
    """Base exception for all ``cciu`` errors."""


class UnsupportedFormatError(CCIUError):
    """Raised when an input cannot be recognised as a supported format."""


class DICOMReadError(CCIUError):
    """Raised when a DICOM file or series cannot be read or parsed."""


class OrthancError(CCIUError):
    """Raised when an Orthanc operation fails or the server is unavailable."""
