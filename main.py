import argparse
import logging
import os
import sys

from pdf_annotations_to_readwise.extract import has_annotations

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers()

    check = subparsers.add_parser(
        "check", help="Find stray annotations and unsummarized articles")
    check.add_argument("directory", nargs="+")
    check.set_defaults(func=check_command)

    sync = subparsers.add_parser(
        "sync", help="Sync to Readwise")
    sync.add_argument("-t", "--token", help="Readwise access token")
    sync.set_defaults(func=sync_command)

    args = parser.parse_args()
    if not args.func:
        parser.print_help()
        sys.exit(1)

    return args


def check_command(args):
    exit_code = 0

    has_annotations('/Users/emptysquare/Dropbox/Research Papers/Research 1/Consensus and Replication 1/PODC 2021 Design and Verification of a Logless Dynamic Reconfiguration Protocol in MongoDB Replication/PODC 2021 Design and Verification of a Logless Dynamic Reconfiguration Protocol in MongoDB Replication ANNOTATED.pdf')

    def gen_pdfs():
        for root in args.directory:
            for dirpath, dirnames, filenames in os.walk(root):
                for filename in filenames:
                    if filename.lower().endswith('.pdf'):
                        yield os.path.join(dirpath, filename)

    def is_annotated(filename):
        return os.path.splitext(filename)[0].endswith('ANNOTATED')

    annotated = set(p for p in gen_pdfs() if is_annotated(p))
    not_annotated = set(p for p in gen_pdfs() if not is_annotated(p))

    for pdf in not_annotated:
        if has_annotations(pdf):
            logging.warning(
                "Annotations in PDF not named like '_ANNOTATED': %s", pdf)

    # TODO: check that all ANNOTATED pdfs have non-ANNOTATED counterparts
    sys.exit(exit_code)


def sync_command(args):
    pass
    # TODO: for each ANNOTATED, refresh Readwise annotations
    # books = readwise_list_books(args.token)


def main(args):
    args.func(args)


if __name__ == "__main__":
    main(parse_args())
