# cciu

Computational Clinical Imaging Utilities from the Computational Clinical Imaging Group.

This package provides small, reusable building blocks for clinical imaging workflows, focusing on:

- SimpleITK-based image utilities for 3D medical images (resampling, cropping, padding, orientation).
- Orthanc DICOM utilities for interacting with an Orthanc server (query, download, upload DICOM data).
- Lightweight logging utilities with consistent formatting and optional file logging.

The code is organized as a pure Python package under `src/cciu`.

## Installation

The project is defined via `pyproject.toml`.

- Python: `>=3.10`
- Core dependencies:
  - `requests>=2.33.1`
  - `simpleitk>=2.5.4`

Install with your preferred PEP 621–compatible tool, for example:

```bash
pip install .
# or, if using uv
uv pip install .
```

You will also need an Orthanc instance running if you plan to use the DICOM utilities.

## Package structure

```text
src/
  cciu/
    __init__.py
    logging_utils.py     # Minimal logging helpers
    orthanc_utils.py     # Utilities for interacting with an Orthanc DICOM server
    sitk_utils.py        # SimpleITK-based image utilities
```

## Logging utilities (`cciu.logging_utils`)

`logging_utils` provides a shared logger factory and helpers for adding file handlers.

Environment variables:

- `LOGS_DIR` (default: `./logs`)
- `NNUNET_SERVE_LOGGING_LEVEL` (e.g. `DEBUG`, `INFO`, `WARNING`, …)

Example:

```python
from cciu.logging_utils import get_logger, add_file_handler_to_manager

logger = get_logger(__name__)
logger.info("Starting pipeline")

# Optionally log to a file for all loggers
add_file_handler_to_manager(log_name="cciu_run")
```

## Orthanc utilities (`cciu.orthanc_utils`)

`orthanc_utils` wraps common HTTP operations against an Orthanc DICOM server, providing functions to:

- List patients, studies, and series.
- Retrieve metadata for patients/studies/series.
- Download series archives and extract them to disk.
- Upload instances or entire series to Orthanc.
- Query series/studies by UIDs or patient ID and return structured DICOM tag dictionaries.

Environment variables:

- `ORTHANC_URL` (default: `http://localhost:8042`)
- `ORTHANC_USER` (optional)
- `ORTHANC_PASSWORD` (optional)
- `TMP_STUDY_DIR` (default: `/tmp/nnunet_serve/orthanc`), used as a default download directory.

Basic usage:

```python
from cciu.orthanc_utils import (
    get_all_patients,
    get_all_studies_for_patient_id,
    download_series,
    upload_series,
)

patients = get_all_patients()

studies = get_all_studies_for_patient_id(patient_id="12345")

series_paths = download_series(series_id="SERIES_ID_HERE")

responses = upload_series("/path/to/dicom/series")
```

All public functions that hit Orthanc are guarded by a decorator that raises an exception if Orthanc is not reachable at import time.

## SimpleITK utilities (`cciu.sitk_utils`)

`sitk_utils` provides reusable components built on top of SimpleITK for typical 3D image preprocessing/postprocessing:

- Resampling:
  - `_resample_image_standard` – low-level resampling helper.
  - `resample_image_separate_z` – resample with decoupled XY and Z spacing.
  - `resample_image` – higher-level entry point that can optionally decouple Z based on anisotropy.
  - `resample_image_to_target` – resample a moving image into the geometry of a target image.

- Anisotropy and spacing:
  - `get_do_separate_z` – decide whether Z should be handled separately, based on spacing anisotropy.

- Orientation helpers:
  - `to_closest_canonical_sitk` – flip axes as needed so an image is as close as possible to a canonical orientation.
  - `from_closest_canonical_sitk` – restore from canonical orientation back to the original orientation and metadata.

- Cropping and padding:
  - `get_crop` – compute a bounding box around label 1 in a label image, with optional padding and minimum size, and return both bounding box and padding information.
  - `pad_sitk` – pad an image (including vector images) with constant values.

Examples:

```python
import SimpleITK as sitk
from cciu.sitk_utils import (
    resample_image,
    resample_image_to_target,
    get_crop,
    pad_sitk,
)

img = sitk.ReadImage("image.nii.gz")

# Resample to isotropic 1mm spacing
img_resampled = resample_image(img, out_spacing=[1.0, 1.0, 1.0])

# Resample to match a target image
target = sitk.ReadImage("target.nii.gz")
img_to_target = resample_image_to_target(img, target=target)

# Compute crop around label 1 in a mask, with padding
mask = sitk.ReadImage("mask.nii.gz")
(bbox, padding) = get_crop(mask)

# Pad an image
padded = pad_sitk(
    img,
    pad_lower=(10, 10, 10),
    pad_upper=(10, 10, 10),
)
```

Internally, these utilities log useful information about image sizes, paddings, and bounding boxes via `cciu.logging_utils`.

## Contributing

If you extend the utilities or introduce new modules, consider updating this document accordingly:

- Add a short description of new modules under `src/cciu/`.
- Document new environment variables or important configuration options.
- Provide small, self-contained usage examples.
