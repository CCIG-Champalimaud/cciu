from cciu.entrypoints import describe_sitk
from cciu.entrypoints import characterise_label_sizes

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
        "characterise_label_sizes",
        help="Characterises the label sizes in a folder with SITK-readable files",
    )
    characterise_label_sizes.add_arguments(characterise_label_sizes_subparser)

    args = parser.parse_args()
    if args.command == "describe_sitk":
        describe_sitk.main(args)
    elif args.command == "characterise_label_sizes":
        characterise_label_sizes.main(args)

if __name__ == "__main__":
    main_cli()