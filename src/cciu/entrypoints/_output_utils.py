"""Shared output helpers for cciu entrypoints."""

import csv
import json
import sys
from typing import Any, IO

import yaml


def write_output(
    rows: list[dict[str, Any]],
    fmt: str,
    fh: IO[str] | None,
    fieldnames: list[str] | None = None,
) -> None:
    """Write *rows* to *fh* (or stdout when None) in the requested *fmt*.

    Args:
        rows: List of dicts to serialise.
        fmt: One of ``"csv"``, ``"json"``, ``"jsonl"``, ``"yaml"``.
        fh: Open writable text file-handle, or None for stdout.
        fieldnames: Column order for CSV.  When None the keys of the first row
            are used (or an empty list when *rows* is empty).
    """
    out = fh if fh is not None else sys.stdout

    if fmt == "csv":
        cols = (
            fieldnames
            if fieldnames is not None
            else (list(rows[0].keys()) if rows else [])
        )
        writer = csv.DictWriter(out, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    elif fmt == "json":
        out.write(json.dumps(rows, indent=2, default=str) + "\n")

    elif fmt == "jsonl":
        for row in rows:
            out.write(json.dumps(row, default=str) + "\n")

    elif fmt == "yaml":
        out.write(
            yaml.dump(_rows_for_yaml(rows), allow_unicode=True, sort_keys=False)
        )

    else:
        raise ValueError(f"Unknown format: {fmt!r}")


def _rows_for_yaml(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursively convert values to yaml-safe primitives."""
    result = []
    for row in rows:
        clean: dict[str, Any] = {}
        for k, v in row.items():
            clean[k] = _to_yaml_safe(v)
        result.append(clean)
    return result


def _to_yaml_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(kk): _to_yaml_safe(vv) for kk, vv in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_yaml_safe(x) for x in v]
    if isinstance(v, (int, float, bool, str)) or v is None:
        return v
    return str(v)


def label_rows_to_long_format(
    file_rows: list[dict[str, Any]],
    file_key: str = "file",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Expand per-file label rows into true long format.

    Produces one row per (file, attribute, label_index) with columns:
    ``file``, ``attribute``, ``label_index``, ``value``.

    Scalar attributes (non-list values other than *file_key*) are emitted
    with ``label_index`` of ``None``.  List-valued attributes are emitted
    once per element with 1-based ``label_index``.

    Returns:
        (long_rows, fieldnames)
    """
    fieldnames = ["file", "attribute", "label_index", "value"]
    long_rows: list[dict[str, Any]] = []

    for row in file_rows:
        file_val = row.get(file_key, "")
        for k, v in row.items():
            if k == file_key:
                continue
            if isinstance(v, (list, tuple)):
                for idx, elem in enumerate(v, start=1):
                    long_rows.append(
                        {
                            "file": file_val,
                            "attribute": k,
                            "label_index": idx,
                            "value": elem,
                        }
                    )
            else:
                long_rows.append(
                    {
                        "file": file_val,
                        "attribute": k,
                        "label_index": None,
                        "value": v,
                    }
                )

    return long_rows, fieldnames


def open_output(path: str | None) -> tuple[IO[str] | None, bool]:
    """Open *path* for writing and return ``(fh, should_close)``.

    When *path* is None returns ``(None, False)`` — callers use stdout.
    """
    if path:
        return open(path, "w", newline="", encoding="utf-8"), True
    return None, False
