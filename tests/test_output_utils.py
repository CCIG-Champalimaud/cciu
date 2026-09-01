"""Unit tests for shared entrypoint output helpers."""

from cciu.entrypoints._output_utils import (
    label_rows_to_long_format,
    overall_to_long_format,
)


def test_label_rows_to_long_format_expands_label_keys():
    rows = [
        {
            "file": "a.nii",
            "spacing": [1.0, 1.0, 1.0],
            "pixel_sizes": [10, 20],
        }
    ]
    long_rows, fieldnames = label_rows_to_long_format(
        rows, label_keys=("pixel_sizes",)
    )
    assert fieldnames == ["file", "attribute", "label_index", "value"]
    pixel_rows = [r for r in long_rows if r["attribute"] == "pixel_sizes"]
    assert pixel_rows[0]["label_index"] == 1
    assert pixel_rows[0]["value"] == 10
    assert pixel_rows[1]["label_index"] == 2
    assert pixel_rows[1]["value"] == 20


def test_overall_to_long_format_flattens_nested_stat_groups():
    overall = {
        "n_files": 2,
        "spacing": {"x": {"mean": 1.5}, "y": {"mean": 2.5}},
        "labels": {"1": {"pixel_sizes": {"mean": 10}}},
    }
    rows = overall_to_long_format(overall)
    attrs = {r["attribute"]: r["value"] for r in rows}
    assert attrs["n_files"] == 2
    assert attrs["spacing_x_mean"] == 1.5
    assert attrs["spacing_y_mean"] == 2.5
    assert attrs["label_1_pixel_sizes_mean"] == 10


def test_overall_to_long_format_scalar_passthrough():
    overall = {"n_files": 1, "n_labels_total": 0}
    rows = overall_to_long_format(overall)
    assert len(rows) == 2
    for row in rows:
        assert row["file"] == "__overall__"
        assert row["label_index"] is None
