"""Integration tests for the ``dicom-bvalue-table`` CLI entrypoint."""

import argparse
import os
import tempfile
from pathlib import Path

import pytest

from cciu.entrypoints import dicom_bvalue_table

PROSTATEX_STUDY_ENV = "PROSTATEX_TRAIN_STUDY_DIR"


@pytest.mark.skipif(
    not os.environ.get(PROSTATEX_STUDY_ENV),
    reason=(
        f"Environment variable {PROSTATEX_STUDY_ENV} not set; "
        "skipping integration test."
    ),
)
def test_dicom_bvalue_table_runs_and_produces_nonempty_csv():
    """``dicom-bvalue-table`` should produce a non-empty CSV for real data.

    Integration-style test over a real DICOM study directory.

    Requires the environment variable PROSTATEX_TRAIN_STUDY_DIR to point to
    a directory like ProstateX-0017 containing DICOM instances.
    """

    input_dir = Path(os.environ[PROSTATEX_STUDY_ENV])
    assert input_dir.is_dir(), f"Input dir does not exist: {input_dir}"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "bvalues.csv"

        parser = argparse.ArgumentParser()
        dicom_bvalue_table.add_arguments(parser)
        args = parser.parse_args(
            [
                "--input",
                str(input_dir),
                "--output",
                str(out_path),
                "--format",
                "csv",
            ]
        )

        dicom_bvalue_table.main(args)

        assert out_path.is_file(), "Output CSV was not created"
        content = out_path.read_text(encoding="utf-8").strip().splitlines()
        # Expect at least header + one row
        assert len(content) >= 2
        header = content[0].split(",")
        assert "series_uid" in header
        assert "bvalues" in header

        bvalues_col = header.index("bvalues")
        # At least one series must have a non-empty b-value list
        data_rows = content[1:]
        assert any(
            row.split(",")[bvalues_col].strip() not in ("", "[]")
            for row in data_rows
        ), "No series had any b-values — b-value extraction appears broken"
