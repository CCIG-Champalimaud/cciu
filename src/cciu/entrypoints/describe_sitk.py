import argparse

import SimpleITK as sitk

from cciu.entrypoints._output_utils import open_output, write_output

def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--input",
        help="Input files",
        nargs="+",
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
    return parser


def get_unique_labels(
    image: sitk.Image, max_labels: int = 128
) -> tuple[int, list[int], list[float]]:
    """
    Extracts the unique labels from an image if fewer than `max_labels` are
    found in an image. If the number of labels is smaller than `max_labels`,
    returns the number of labels and the number of pixels and physical size per
    label. Otherwise, returns the total number of labels and [] for the other
    values.

    Args:
        image (sitk.Image): input image.
        max_labels (int, optional): maximum number of labels to return.

    Returns:
        tuple[int, list[int] | None, list[float] | None]: number of labels,
            number of pixels per label, physical size per label.
    """
    lssi = sitk.LabelShapeStatisticsImageFilter()
    lssi.Execute(sitk.Cast(image, sitk.sitkInt32))
    n = lssi.GetNumberOfLabels()
    np, ps = [], []
    if n < max_labels:
        for i in range(1, n + 1):
            try:
                curr_np = lssi.GetNumberOfPixels(i)
                curr_ps = lssi.GetPhysicalSize(i)
            except Exception:
                curr_np = 0
                curr_ps = 0
            np.append(curr_np)
            ps.append(curr_ps)
    return (n, np, ps)


def basic_image_information(image: sitk.Image) -> dict[str, any]:
    """
    Returns basic image information including spacing, size, and origin.

    Args:
        image (sitk.Image): input image.

    Returns:
        dict[str, any]: dictionary containing spacing, size, and origin.

    """
    return {
        "spacing": image.GetSpacing(),
        "size": image.GetSize(),
        "origin": image.GetOrigin(),
    }


def print_unique_values(image: sitk.Image):
    """ """
    n, np, ps = get_unique_labels(image, 10)
    print(f"  n_labels: {n}")
    if np:
        print("  labels:")
        for i in range(n):
            print(f"  - label: {i + 1}")
            print(f"    size_pixels: {np[i]}")
            print(f"    size_mm3: {ps[i]:.3f}")


def main(args):
    rows = []
    for inp in args.input:
        img = sitk.ReadImage(inp)
        basic_info = basic_image_information(img)
        n_labels, pixel_sizes, physical_sizes = get_unique_labels(img)
        row = {
            "file": inp,
            "spacing": list(basic_info["spacing"]),
            "size": list(basic_info["size"]),
            "origin": list(basic_info["origin"]),
            "n_labels": n_labels,
            "pixel_sizes_per_label": pixel_sizes,
            "physical_sizes_per_label": physical_sizes,
        }
        rows.append(row)

    fh, close_out = open_output(args.output)
    try:
        write_output(rows, args.format, fh)
    finally:
        if close_out and fh is not None:
            fh.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
