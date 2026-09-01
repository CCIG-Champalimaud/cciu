"""CLI entrypoint to describe properties of a dataset of SITK-readable images."""

import argparse
import multiprocessing
import re
import statistics
from functools import partial
from pathlib import Path

import SimpleITK as sitk
from tqdm import tqdm

from cciu.entrypoints._output_utils import (
    compute_stats,
    label_rows_to_long_format,
    open_output,
    overall_to_long_format,
    write_output,
)
from cciu.entrypoints.describe_sitk import (
    basic_image_information,
    get_unique_labels,
)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add ``describe-sitk-dataset`` arguments to an argument parser.

    Args:
        parser (argparse.ArgumentParser): The parser to populate.

    Returns:
        argparse.ArgumentParser: The populated parser.
    """
    parser.add_argument(
        "--input",
        help="Path to directory containing images",
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
        "--max_labels",
        type=int,
        default=128,
        help="Maximum labels to enumerate per image",
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


def _process_image_file(
    file: Path, max_labels: int
) -> tuple[str, dict, int, list[int], list[float]]:
    """Load an image and extract its metadata and per-label sizes.

    Args:
        file (Path): Path to the image.
        max_labels (int): Maximum number of labels to enumerate.

    Returns:
        tuple[str, dict, int, list[int], list[float]]: The file path, basic
            image information, number of labels, pixel sizes per label, and
            physical sizes per label.
    """
    img = sitk.ReadImage(str(file))
    basic_info = basic_image_information(img)
    n_labels, pixel_sizes, physical_sizes = get_unique_labels(img, max_labels)
    return str(file), basic_info, n_labels, pixel_sizes, physical_sizes


def main(args: argparse.Namespace) -> None:
    """Describe a dataset of images and write the results.

    Args:
        args (argparse.Namespace): Parsed CLI arguments, including ``input``,
            ``output``, ``format``, ``sitk_regex``, ``max_labels``, and
            ``n_cores``.
    """
    sitk_regex = re.compile(args.sitk_regex)

    path = Path(args.input)
    image_files = [f for f in path.rglob("*") if sitk_regex.search(str(f))]

    file_rows: list[dict] = []
    all_n_labels: list[int] = []
    spacing_values: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    size_values: dict[str, list[int]] = {"x": [], "y": [], "z": []}
    pixel_sizes_per_label: dict[int, list[int]] = {}
    physical_sizes_per_label: dict[int, list[float]] = {}

    if image_files:
        n_workers = args.n_cores or multiprocessing.cpu_count()
        worker = partial(_process_image_file, max_labels=args.max_labels)
        with multiprocessing.Pool(processes=n_workers) as pool:
            results = list(
                tqdm(pool.imap(worker, image_files), total=len(image_files))
            )

        for (
            file_str,
            basic_info,
            n_labels,
            pixel_sizes,
            physical_sizes,
        ) in results:
            all_n_labels.append(n_labels)

            spacing = basic_info["spacing"]
            size = basic_info["size"]
            for axis, index in (("x", 0), ("y", 1), ("z", 2)):
                spacing_values[axis].append(spacing[index])
                size_values[axis].append(size[index])

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
                    "spacing": list(spacing),
                    "size": list(size),
                    "origin": list(basic_info["origin"]),
                    "n_labels": n_labels,
                    "pixel_sizes_per_label": pixel_sizes,
                    "physical_sizes_per_label": physical_sizes,
                }
            )

    overall: dict = {"n_files": len(all_n_labels)}
    if all_n_labels:
        overall["n_labels_total"] = sum(all_n_labels)
        overall["n_labels_min"] = min(all_n_labels)
        overall["n_labels_max"] = max(all_n_labels)
        overall["n_labels_mean"] = round(statistics.mean(all_n_labels), 3)
        overall["n_labels_median"] = round(statistics.median(all_n_labels), 3)

        overall["spacing"] = {
            axis: compute_stats(spacing_values[axis]) for axis in spacing_values
        }
        overall["size"] = {
            axis: compute_stats(size_values[axis]) for axis in size_values
        }

        label_stats: dict[str, dict] = {}
        for label_idx in sorted(
            set(pixel_sizes_per_label) | set(physical_sizes_per_label)
        ):
            entry: dict = {}
            pix_vals = pixel_sizes_per_label.get(label_idx, [])
            entry["pixel_sizes"] = compute_stats(pix_vals) if pix_vals else []
            phys_vals = physical_sizes_per_label.get(label_idx, [])
            entry["physical_sizes"] = (
                compute_stats(phys_vals) if phys_vals else []
            )
            label_stats[str(label_idx)] = entry

        if label_stats:
            overall["labels"] = label_stats

    output_data = {"files": file_rows, "overall": overall}

    fh, close_out = open_output(args.output)
    try:
        if args.format == "csv":
            long_rows, fieldnames = label_rows_to_long_format(
                file_rows,
                label_keys=(
                    "pixel_sizes_per_label",
                    "physical_sizes_per_label",
                ),
            )
            long_rows += overall_to_long_format(overall)
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
