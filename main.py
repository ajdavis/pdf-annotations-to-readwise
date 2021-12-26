import argparse
import datetime
import fnmatch
import logging
import os
import stat
import sys
import time
from collections import Counter

from pdf_annotations_to_readwise.extract import has_annotations

logging.basicConfig(level=logging.INFO)
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


def check_command(args: argparse.Namespace) -> int:
    logging.info("""Check that PDFs obey rules about naming and annotations.

    1. Only "Foo ANNOTATED.pdf" or "Foo DONE.pdf" files may have annotations.
    2. Every "Foo ANNOTATED.pdf" must have annotations.
    2. Every annotated PDF needs a corresponding original in the same directory.
    
    PDFs are "done" if the containing directory is named "Bar DONE" and contains
    a non-empty "Bar.md" file.""")
    exit_code = 0

    annotated_suffixes = " ANNOTATED", " DONE"

    def original_name(filename: str) -> str:
        base_name = os.path.splitext(filename)[0]
        for s in annotated_suffixes:
            if base_name.endswith(s):
                return f"{base_name[:-len(s)].strip()}.pdf"

        assert False, f"Bad original_name() input: {filename}"

    def error(msg, *args):
        nonlocal exit_code
        logger.error(msg, *args)
        exit_code = 1

    def should_ignore(full_path: str) -> bool:
        for ignore in args.ignore:
            if fnmatch.fnmatch(full_path, ignore):
                return True

        return False

    def has_nonempty_file(full_path: str) -> bool:
        return (os.path.exists(full_path)
                and os.stat(full_path)[stat.ST_SIZE] > 0)

    original, annotated, done = set(), set(), set()

    # args.directory is a list of directory names.
    for root in args.directory:
        for dirpath, dirnames, filenames in os.walk(root):
            dirpath_is_done = (
                os.path.split(dirpath)[-1].endswith(" DONE")
                and has_nonempty_file(os.path.join(
                    dirpath,
                    os.path.basename(dirpath)[:-len(' DONE')]) + ".md"))

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if should_ignore(full_path) or should_ignore(filename):
                    continue

                base, ext = os.path.splitext(filename)
                if ext.lower() != ".pdf":
                    continue

                if dirpath_is_done:
                    done.add(full_path)
                elif base.endswith(annotated_suffixes):
                    annotated.add(full_path)
                else:
                    original.add(full_path)

    counter = Counter({"Original PDFs": len(original),
                       "Annotated PDFs": len(annotated),
                       "Done PDFs": len(done)})

    # TODO: list unfinished PDFs (not named "DONE" or in a dir named "DONE").
    for pdf in original:
        logger.debug("Checking %s", pdf)
        if has_annotations(pdf):
            error("Annotated PDF not named like 'ANNOTATED' or 'DONE': %s", pdf)
            counter["original PDFs with stray annotations"] += 1

    for pdf in annotated:
        logger.debug("Checking %s", pdf)
        if original_name(pdf) not in original:
            error("Annotated pdf '%s' without original version", pdf)
            counter["annotated PDFs without originals"] += 1
        if not has_annotations(pdf):
            error("No annotations in PDF: %s", pdf)
            counter["PDFs that should have annotations but don't"] += 1

    for name, n in counter.items():
        logging.info("%4d %s", n, name)

    return exit_code


def sync_command(args: argparse.Namespace) -> int:
    return 0
    # TODO: for each ANNOTATED, refresh Readwise annotations
    # books = readwise_list_books(args.token)


def main(args: argparse.Namespace) -> None:
    start = time.time()
    exit_code = args.func(args)
    end = time.time()
    logger.info("Finished in %s", datetime.timedelta(seconds=int(end - start)))
    sys.exit(exit_code)


if __name__ == "__main__":
    main(parse_args())
