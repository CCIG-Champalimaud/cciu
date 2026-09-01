"""CLI entrypoint to describe basic properties of SITK-readable images."""

import argparse

import SimpleITK as sitk

from cciu.entrypoints._output_utils import (
    label_rows_to_long_format,
    open_output,
    write_output,
)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add ``describe_sitk`` arguments to an argument parser.

    Args:
        parser (argparse.ArgumentParser): The parser to populate.

    Returns:
        argparse.ArgumentParser: The populated parser.
    """
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


def get_image_information(
    path: str,
    private_tags: bool = False,
    include_unique_values: bool = False,
) -> tuple[dict[str, any], sitk.ImageFileReader]:
    """
    Returns basic image information including spacing, size, and origin.

    Args:
        path (str): path to input image.
        private_tags (bool, optional): returns private tags. Defaults to False.
        include_unique_values (bool, optional): returns the number of unique
            values. Defaults to False.

    Returns:
        dict[str, any]: dictionary containing spacing, size, and origin,
            as well as metadata keys.
            Private tags are included if `private_tags` is True.
        sitk.ImageFileReader: the image file reader in case other operations
            are necessary.
    """
    reader = sitk.ImageFileReader()
    reader.SetFileName(path)
    if private_tags:
        reader.LoadPrivateTagsOn()
    reader.ReadImageInformation()
    output = {
        "file": path,
        "spacing": reader.GetSpacing(),
        "size": reader.GetSize(),
        "origin": reader.GetOrigin(),
        "metadata": {},
    }
    for key in reader.GetMetaDataKeys():
        output["metadata"][key] = reader.GetMetaData(key)
    if include_unique_values:
        img = reader.Execute()
        unique_values, pixel_sizes, physical_sizes = get_unique_labels(img)
        output["n_unique_values"] = unique_values
        output["label_pixel_sizes"] = pixel_sizes
        output["label_physical_sizes"] = physical_sizes
    return output, reader


def main(args: argparse.Namespace) -> None:
    """Describe the requested images and write the results.

    Args:
        args (argparse.Namespace): Parsed CLI arguments, including ``input``,
            ``output``, and ``format``.
    """
    rows = []
    for inp in args.input:
        info, _ = get_image_information(inp, include_unique_values=True)
        rows.append(info)

    fh, close_out = open_output(args.output)
    try:
        if args.format == "csv":
            long_rows, fieldnames = label_rows_to_long_format(
                rows,
                label_keys=(
                    "pixel_sizes_per_label",
                    "physical_sizes_per_label",
                ),
            )
            write_output(long_rows, "csv", fh, fieldnames=fieldnames)
        else:
            write_output(rows, args.format, fh)
    finally:
        if close_out and fh is not None:
            fh.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
