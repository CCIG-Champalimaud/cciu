# cciu

Computational Clinical Imaging Utilities from the Computational Clinical Imaging Group.

Small, reusable building blocks for clinical imaging workflows:

- SimpleITK-based utilities for 3D images (resampling, cropping, padding, orientation).
- DICOM + Orthanc helpers for querying, downloading, uploading, and sorting DICOM data.
- Minimal logging utilities with consistent formatting and optional file logging.

The code is organized as a Python package under `src/cciu`.

## Installation

Requirements (see `pyproject.toml` for details):

- Python `>=3.10`
- `requests>=2.33.1`
- `simpleitk>=2.5.4`
- `numpy>=2.2.6`
- `pydicom>=3.0.2`
- `pydicom-seg` (installed from the Git source defined in `pyproject.toml`)

Install in editable mode during development:

```bash
uv pip install .
```

You will need a running Orthanc instance if you use the Orthanc/DICOM server helpers.

After installation, a `cciu` command-line entrypoint is available (see below).

## Package structure

```text
src/
  cciu/
    __init__.py
    logging_utils.py     # Logging helpers
    dicom_utils.py       # Local DICOM utilities (sorting, b-value filtering)
    orthanc_utils.py     # Orthanc DICOM server utilities
    sitk_utils.py        # SimpleITK-based image utilities
```

## Command-line usage

Installing the package exposes a `cciu` console script (configured in `pyproject.toml` as `cciu.__main__:main_cli`).

Available subcommands:

- `cciu describe_sitk`  
  Describe basic properties (spacing, size, origin, labels) of one or more SITK-readable images.

  Example:

  ```bash
  uv run cciu describe_sitk --input /path/to/image1.nii.gz /path/to/image2.nrrd
  ```

- `cciu characterise_label_sizes`  
  Characterise label distributions (per-file and overall statistics) in a directory of SITK-readable label images.

  Example:

  ```bash
  uv run cciu characterise_label_sizes \
      --input /path/to/labels_dir \
      --sitk_regex '(\.nrrd|\.mha|.*\.nii(\.gz)?)$' \
      --label_regex '.*'
  ```

## Modules

- **`cciu.logging_utils`**  
  Create/get loggers with a consistent format and optional file handlers.

  Environment:
  - `LOGS_DIR` (default `./logs`)
  - `NNUNET_SERVE_LOGGING_LEVEL` (e.g. `DEBUG`, `INFO`, `WARNING`)

- **`cciu.dicom_utils`**  
  Local DICOM helpers, e.g.:
  - `sort_dicom_slices(file_paths)` – sort DICOM slices by spatial position (ImagePositionPatient → SliceLocation → InstanceNumber → filename fallback).
  - `filter_by_bvalue_from_dict(dicom_files, target_bvalue, exact=False)` – keep slices for a given/closest diffusion b‑value.

- **`cciu.orthanc_utils`**  
  Thin wrapper around an Orthanc DICOM server, including:
  - Listing patients, studies, and series.
  - Downloading series archives to disk.
  - Uploading instances/series.
  - Querying by patient ID, StudyInstanceUID, SeriesInstanceUID, etc.

  Environment:
  - `ORTHANC_URL` (default `http://localhost:8042`)
  - `ORTHANC_USER`, `ORTHANC_PASSWORD` (optional auth)
  - `TMP_STUDY_DIR` (default `/tmp/nnunet_serve/orthanc`)

- **`cciu.sitk_utils`**  
  SimpleITK-based image utilities used for 3D preprocessing/postprocessing:
  - Resampling images (including anisotropic handling and resampling to a target geometry).
  - Converting images to/from a “closest canonical” orientation.
  - Cropping around a label with padding and minimum size.
  - Padding images, including vector images.
  - `is_same_image_geometry(img_a, img_b)` – compare image geometries using `IsSameImageGeometryAs`.
  - `label_erode(image, radius)` / `label_dilate(image, radius)` – label-preserving morphology via `LabelErodeDilateImageFilter`.
  - `pathlib.Path` support for all file-path arguments.

These modules are designed to be used independently; import only what you need in your pipelines.
