import argparse
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


def main(args):
    sitk_regex = re.compile(args.sitk_regex)
    label_regex = re.compile(args.label_regex)

    path = Path(args.input)
    all_files = path.rglob("*")
    sitk_files = [f for f in all_files if sitk_regex.search(str(f))]
    label_files = [f for f in sitk_files if label_regex.search(str(f))]

    all_n_labels = []
    all_pixel_sizes = []
    all_physical_sizes = []
    print("files:")
    for file in label_files:
        img = sitk.ReadImage(file)
        basic_info = basic_image_information(img)
        n_labels, pixel_sizes, physical_sizes = get_unique_labels(img)
        all_n_labels.append(n_labels)
        if pixel_sizes:
            all_pixel_sizes.extend(pixel_sizes)
        if physical_sizes:
            all_physical_sizes.extend(physical_sizes)
        print(f'- file: "{str(file)}"')
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

    if all_pixel_sizes:
        print("  pixel_sizes:")
        print(f"    count: {len(all_pixel_sizes)}")
        print(f"    min: {min(all_pixel_sizes)}")
        print(f"    max: {max(all_pixel_sizes)}")
        print(f"    mean: {statistics.mean(all_pixel_sizes):.3f}")
        print(f"    median: {statistics.median(all_pixel_sizes):.3f}")
        if len(all_pixel_sizes) > 1:
            print(f"    stdev: {statistics.stdev(all_pixel_sizes):.3f}")
    else:
        print("  pixel_sizes: []")

    if all_physical_sizes:
        print("  physical_sizes:")
        print(f"    count: {len(all_physical_sizes)}")
        print(f"    min: {min(all_physical_sizes):.6f}")
        print(f"    max: {max(all_physical_sizes):.6f}")
        print(f"    mean: {statistics.mean(all_physical_sizes):.6f}")
        print(f"    median: {statistics.median(all_physical_sizes):.6f}")
        if len(all_physical_sizes) > 1:
            print(f"    stdev: {statistics.stdev(all_physical_sizes):.6f}")
    else:
        print("  physical_sizes: []")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
