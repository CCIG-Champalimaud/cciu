"""CLI entrypoint to inspect and classify medical image inputs."""

import argparse

from cciu.entrypoints._output_utils import open_output, write_output
from cciu.io_utils import provenance


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add ``inspect`` arguments to an argument parser.

    Args:
        parser (argparse.ArgumentParser): The parser to populate.

    Returns:
        argparse.ArgumentParser: The populated parser.
    """
    parser.add_argument(
        "--input",
        help="Input files or directories",
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


def main(args: argparse.Namespace) -> None:
    """Classify each input and write a provenance summary.

    Args:
        args (argparse.Namespace): Parsed CLI arguments, including ``input``,
            ``output``, and ``format``.
    """
    rows = [provenance(inp) for inp in args.input]

    fieldnames = [
        "path",
        "kind",
        "reader",
        "sop_class_uid",
        "modality",
        "series_uid",
    ]
    fh, close_out = open_output(args.output)
    try:
        write_output(rows, args.format, fh, fieldnames=fieldnames)
    finally:
        if close_out and fh is not None:
            fh.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
