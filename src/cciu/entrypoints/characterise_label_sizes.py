import argparse
import multiprocessing
import re
import statistics
from pathlib import Path

import SimpleITK as sitk

from cciu.entrypoints._output_utils import (
    label_rows_to_long_format,
    open_output,
    write_output,
)
from cciu.entrypoints.describe_sitk import (
    basic_image_information,
    get_unique_labels,
)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        help="Path to directory containing label images",
        required=True,
    )
    parser.add_argument(
        "--output",
        help="Optional path to output file (default: stdout)",
        default=None,
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "jsonl", "yaml"],
        default="yaml",
        help="Output format (default: yaml)",
    )
    parser.add_argument(
        "--sitk_regex",
        help="Regex to match SITK-readable files",
        default=r"(\.nrrd|\.mha|.*\.nii(\.gz)?)$",
    )
    parser.add_argument(
        "--label_regex",
        help="Regex used to match labels",
        default=".*",
    )
    parser.add_argument(
        "--n_cores",
        type=int,
        default=None,
        help=(
            "Number of worker processes to use for parallel file processing "
            "(default: all available cores)"
        ),
    )
    return parser


def _process_label_file(file: Path):
    img = sitk.ReadImage(str(file))
    basic_info = basic_image_information(img)
    n_labels, pixel_sizes, physical_sizes = get_unique_labels(img)
    return str(file), basic_info, n_labels, pixel_sizes, physical_sizes


def _stats(values: list) -> dict:
    d: dict = {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 6),
        "median": round(statistics.median(values), 6),
    }
    if len(values) > 1:
        d["stdev"] = round(statistics.stdev(values), 6)
    return d


def main(args):
    sitk_regex = re.compile(args.sitk_regex)
    label_regex = re.compile(args.label_regex)

    path = Path(args.input)
    all_files = path.rglob("*")
    sitk_files = [f for f in all_files if sitk_regex.search(str(f))]
    label_files = [f for f in sitk_files if label_regex.search(str(f))]

    file_rows: list[dict] = []
    all_n_labels: list[int] = []
    pixel_sizes_per_label: dict[int, list[int]] = {}
    physical_sizes_per_label: dict[int, list[float]] = {}

    if label_files:
        n_workers = args.n_cores or multiprocessing.cpu_count()
        with multiprocessing.Pool(processes=n_workers) as pool:
            results = pool.map(_process_label_file, label_files)

        for (
            file_str,
            basic_info,
            n_labels,
            pixel_sizes,
            physical_sizes,
        ) in results:
            all_n_labels.append(n_labels)

            for idx, v in enumerate(pixel_sizes, start=1):
                if v == 0:
                    continue
                pixel_sizes_per_label.setdefault(idx, []).append(v)

            for idx, v in enumerate(physical_sizes, start=1):
                if v == 0:
                    continue
                physical_sizes_per_label.setdefault(idx, []).append(v)

            file_rows.append(
                {
                    "file": file_str,
                    "spacing": list(basic_info["spacing"]),
                    "size": list(basic_info["size"]),
                    "origin": list(basic_info["origin"]),
                    "n_labels": n_labels,
                    "pixel_sizes": pixel_sizes,
                    "physical_sizes": physical_sizes,
                }
            )

    overall: dict = {"n_files": len(all_n_labels)}
    if all_n_labels:
        overall["n_labels_total"] = sum(all_n_labels)
        overall["n_labels_min"] = min(all_n_labels)
        overall["n_labels_max"] = max(all_n_labels)
        overall["n_labels_mean"] = round(statistics.mean(all_n_labels), 3)
        overall["n_labels_median"] = round(statistics.median(all_n_labels), 3)

        label_stats: dict[str, dict] = {}
        for label_idx in sorted(
            set(pixel_sizes_per_label) | set(physical_sizes_per_label)
        ):
            entry: dict = {}
            pix_vals = pixel_sizes_per_label.get(label_idx, [])
            entry["pixel_sizes"] = _stats(pix_vals) if pix_vals else []
            phys_vals = physical_sizes_per_label.get(label_idx, [])
            entry["physical_sizes"] = _stats(phys_vals) if phys_vals else []
            label_stats[str(label_idx)] = entry

        if label_stats:
            overall["labels"] = label_stats

    output_data = {"files": file_rows, "overall": overall}

    fh, close_out = open_output(args.output)
    try:
        if args.format == "csv":
            long_rows, fieldnames = label_rows_to_long_format(file_rows)
            write_output(long_rows, "csv", fh, fieldnames=fieldnames)
        else:
            write_output([output_data], args.format, fh)
    finally:
        if close_out and fh is not None:
            fh.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
