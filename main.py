import argparse
import datetime
import fnmatch
import logging
import os
import sys
import time
from collections import Counter
from typing import Generator

from pdf_annotations_to_readwise.extract import has_annotations

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers()

    check = subparsers.add_parser(
        "check", help="Find stray annotations and unsummarized articles")
    check.add_argument("-i", "--ignore", action="append",
                       help="File(s) to ignore, glob patterns allowed")
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


def check_command(args: argparse.Namespace) -> None:
    exit_code = 0

    def fnmatch_any(full_path: str) -> bool:
        for ignore in args.ignore:
            if fnmatch.fnmatch(full_path, ignore):
                return True

        return False

    def gen_pdfs() -> Generator[str, None, None]:
        for root in args.directory:
            for dirpath, dirnames, filenames in os.walk(root):
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    if fnmatch_any(full_path) or fnmatch_any(filename):
                        continue
                    if filename.lower().endswith(".pdf"):
                        yield full_path

    annotated_suffixes = "ANNOTATED", "DONE"

    def should_be_annotated(filename: str) -> bool:
        base = os.path.splitext(filename)[0]
        return base.endswith(annotated_suffixes)

    def original_name(filename: str) -> str:
        base = os.path.splitext(filename)[0]
        for s in annotated_suffixes:
            if base.endswith(s):
                return f"{base[:len(s)].strip()}.pdf"

        assert False, f"Bad unannotated_name() input: {filename}"

    def error(msg, *args):
        nonlocal exit_code
        logger.error(msg, *args)
        exit_code = 1

    original_pdfs = set(p for p in gen_pdfs() if not should_be_annotated(p))
    annotated_pdfs = set(p for p in gen_pdfs() if should_be_annotated(p))
    counter = Counter({"Annotated PDFs": len(annotated_pdfs),
                       "Original PDFs": len(original_pdfs)})

    for pdf in original_pdfs:
        logger.debug("Checking %s", pdf)
        if has_annotations(pdf):
            error("Annotated PDF not named like 'ANNOTATED' or 'DONE': %s", pdf)
            counter["Original PDFs with stray annotations"] += 1

    for pdf in annotated_pdfs:
        logger.debug("Checking %s", pdf)
        if original_name(pdf) not in original_pdfs:
            error("Annotated pdf '%s' without unannotated version", pdf)
            counter["Annotated PDFs without originals"] += 1
        if not has_annotations(pdf):
            error("No annotations in PDF: %s", pdf)
            counter["PDFs that should have annotations but don't"] += 1

    for name, n in counter.items():
        logging.info("%s: %s", name, n)

    sys.exit(exit_code)


def sync_command(args: argparse.Namespace) -> None:
    pass
    # TODO: for each ANNOTATED, refresh Readwise annotations
    # books = readwise_list_books(args.token)


def main(args: argparse.Namespace) -> None:
    start = time.time()
    args.func(args)
    end = time.time()
    logger.info("Finished in %s", datetime.timedelta(seconds=int(end - start)))


if __name__ == "__main__":
    main(parse_args())
