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
from cciu.entrypoints.describe_sitk import get_image_information


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
        "--n_cores",
        type=int,
        default=None,
        help=(
            "Number of worker processes to use for parallel file processing "
            "(default: all available cores)"
        ),
    )
    return parser


def worker(path: str) -> dict:
    return get_image_information(path)[0]


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
    spacing_values: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    size_values: dict[str, list[int]] = {"x": [], "y": [], "z": []}

    if image_files:
        n_workers = args.n_cores or multiprocessing.cpu_count()
        with multiprocessing.Pool(processes=n_workers) as pool:
            results = list(
                tqdm(
                    pool.imap(worker, image_files),
                    total=len(image_files),
                )
            )

        for info in results:
            spacing = info["spacing"]
            size = info["size"]
            for axis, index in (("x", 0), ("y", 1), ("z", 2)):
                spacing_values[axis].append(spacing[index])
                size_values[axis].append(size[index])

            file_rows.append(info)

    overall: dict = {"n_files": len(file_rows)}

    overall["spacing"] = {
        axis: compute_stats(spacing_values[axis]) for axis in spacing_values
    }
    overall["size"] = {
        axis: compute_stats(size_values[axis]) for axis in size_values
    }

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
