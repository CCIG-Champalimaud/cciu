from cciu.entrypoints import describe_sitk
from cciu.entrypoints import characterise_label_sizes
from cciu.entrypoints import dicom_bvalue_table
from cciu.entrypoints import dicom_series_table
from cciu.entrypoints import dicom_feature_table

def main_cli():    
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    describe_sitk_subparser = subparsers.add_parser(
        "describe_sitk",
        help="Describes a SITK-readable image",
    )
    describe_sitk.add_arguments(describe_sitk_subparser)
    characterise_label_sizes_subparser = subparsers.add_parser(
        "characterise-label-sizes",
        help="Characterises the label sizes in a folder with SITK-readable files",
    )
    characterise_label_sizes.add_arguments(characterise_label_sizes_subparser)

    dicom_bvalue_table_subparser = subparsers.add_parser(
        "dicom-bvalue-table",
        help="Summarises b-values for each DICOM series in a dataset",
    )
    dicom_bvalue_table.add_arguments(dicom_bvalue_table_subparser)

    dicom_series_table_subparser = subparsers.add_parser(
        "dicom-series-table",
        help="Exports a per-series metadata table from a DICOM dataset",
    )
    dicom_series_table.add_arguments(dicom_series_table_subparser)

    dicom_feature_table_subparser = subparsers.add_parser(
        "dicom-feature-table",
        help="Extracts a configurable feature table from DICOM instances",
    )
    dicom_feature_table.add_arguments(dicom_feature_table_subparser)

    args = parser.parse_args()
    if args.command == "describe_sitk":
        describe_sitk.main(args)
    elif args.command == "characterise-label-sizes":
        characterise_label_sizes.main(args)
    elif args.command == "dicom-bvalue-table":
        dicom_bvalue_table.main(args)
    elif args.command == "dicom-series-table":
        dicom_series_table.main(args)
    elif args.command == "dicom-feature-table":
        dicom_feature_table.main(args)
    elif args.command == "help" or args.command == "h":
        parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main_cli()
