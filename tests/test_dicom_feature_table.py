import argparse
import os
import tempfile
from pathlib import Path

import pytest

from cciu.entrypoints import dicom_feature_table

PROSTATEX_STUDY_ENV = "PROSTATEX_TRAIN_STUDY_DIR"


@pytest.mark.skipif(
    not os.environ.get(PROSTATEX_STUDY_ENV),
    reason=(
        f"Environment variable {PROSTATEX_STUDY_ENV} not set; "
        "skipping integration test."
    ),
)
def test_dicom_feature_table_runs_and_produces_nonempty_csv():
    input_dir = Path(os.environ[PROSTATEX_STUDY_ENV])
    assert input_dir.is_dir(), f"Input dir does not exist: {input_dir}"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "features.csv"

        parser = argparse.ArgumentParser()
        dicom_feature_table.add_arguments(parser)
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

        dicom_feature_table.main(args)

        assert out_path.is_file(), "Output CSV was not created"
        content = out_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(content) >= 2
