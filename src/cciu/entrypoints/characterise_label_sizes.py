import argparse
import multiprocessing
import re
import statistics
import SimpleITK as sitk
from pathlib import Path
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
        "--sitk_regex",
        help="Regex to match SITK-readable files",
        default="(\.nrrd|\.mha|.*\.nii(\.gz)?)$",
    )
    parser.add_argument(
        "--label_regex",
        help="Regex used to match labels",
        default=".*",
    )


def _process_label_file(file: Path):
    img = sitk.ReadImage(str(file))
    basic_info = basic_image_information(img)
    n_labels, pixel_sizes, physical_sizes = get_unique_labels(img)
    return str(file), basic_info, n_labels, pixel_sizes, physical_sizes


def main(args):
    sitk_regex = re.compile(args.sitk_regex)
    label_regex = re.compile(args.label_regex)

    path = Path(args.input)
    all_files = path.rglob("*")
    sitk_files = [f for f in all_files if sitk_regex.search(str(f))]
    label_files = [f for f in sitk_files if label_regex.search(str(f))]

    all_n_labels = []
    # Per-label aggregates: label_index -> list of values
    pixel_sizes_per_label: dict[int, list[int]] = {}
    physical_sizes_per_label: dict[int, list[float]] = {}
    print("files:")

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

            # Aggregate pixel sizes per label index (1-based), ignoring zeros
            if pixel_sizes:
                for idx, v in enumerate(pixel_sizes, start=1):
                    if v == 0:
                        continue
                    pixel_sizes_per_label.setdefault(idx, []).append(v)

            # Aggregate physical sizes per label index (1-based), independently, ignoring zeros
            if physical_sizes:
                for idx, v in enumerate(physical_sizes, start=1):
                    if v == 0:
                        continue
                    physical_sizes_per_label.setdefault(idx, []).append(v)

            print(f'- file: "{file_str}"')
            print(f"  spacing: {basic_info['spacing']}")
            print(f"  size: {basic_info['size']}")
            print(f"  origin: {basic_info['origin']}")
            print(f"  n_labels: {n_labels}")
            print(f"  pixel_sizes: {pixel_sizes}")
            print(f"  physical_sizes: {physical_sizes}")

    print("overall:")

    if all_n_labels:
        print(f"  n_files: {len(all_n_labels)}")
        print(f"  n_labels_total: {sum(all_n_labels)}")
        print(f"  n_labels_min: {min(all_n_labels)}")
        print(f"  n_labels_max: {max(all_n_labels)}")
        print(f"  n_labels_mean: {statistics.mean(all_n_labels):.3f}")
        print(f"  n_labels_median: {statistics.median(all_n_labels):.3f}")
    else:
        print("  n_files: 0")

    # Per-label distributions
    if pixel_sizes_per_label or physical_sizes_per_label:
        print("  labels:")
        for label_idx in sorted(
            set(pixel_sizes_per_label) | set(physical_sizes_per_label)
        ):
            print(f"    {label_idx}:")

            # Pixel sizes for this label
            pix_vals = pixel_sizes_per_label.get(label_idx, [])
            if pix_vals:
                print("      pixel_sizes:")
                print(f"        count: {len(pix_vals)}")
                print(f"        min: {min(pix_vals)}")
                print(f"        max: {max(pix_vals)}")
                print(f"        mean: {statistics.mean(pix_vals):.3f}")
                print(f"        median: {statistics.median(pix_vals):.3f}")
                if len(pix_vals) > 1:
                    print(f"        stdev: {statistics.stdev(pix_vals):.3f}")
            else:
                print("      pixel_sizes: []")

            # Physical sizes for this label
            phys_vals = physical_sizes_per_label.get(label_idx, [])
            if phys_vals:
                print("      physical_sizes:")
                print(f"        count: {len(phys_vals)}")
                print(f"        min: {min(phys_vals):.6f}")
                print(f"        max: {max(phys_vals):.6f}")
                print(f"        mean: {statistics.mean(phys_vals):.6f}")
                print(f"        median: {statistics.median(phys_vals):.6f}")
                if len(phys_vals) > 1:
                    print(f"        stdev: {statistics.stdev(phys_vals):.6f}")
            else:
                print("      physical_sizes: []")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    parser.add_argument(
        "--n_cores",
        type=int,
        default=None,
        help=(
            "Number of worker processes to use for parallel file processing "
            "(default: all available cores)"
        ),
    )
    args = parser.parse_args()
    main(args)
