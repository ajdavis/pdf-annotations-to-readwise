import argparse
import datetime
import fnmatch
import logging
import os
import stat
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Optional

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


ANNOTATED = " ANNOTATED"


def is_annotated(filename: str) -> bool:
    base_name = os.path.splitext(filename)[0]
    return base_name.endswith(ANNOTATED)


def original_name(filename: str) -> str:
    base_name = os.path.splitext(filename)[0]
    if base_name.endswith(ANNOTATED):
        return f"{base_name[:-len(ANNOTATED)].strip()}.pdf"

    assert False, f"Bad original_name() input: {filename}"


def annotated_name(filename: str) -> str:
    assert not is_annotated(filename)
    base_name = os.path.splitext(filename)[0]
    return f"{base_name}{ANNOTATED}.pdf"


@dataclass(unsafe_hash=True)
class PDFPair:
    """Pair of (original, annotated) PDF files for a paper."""
    original: Optional[str] = None
    annotated: Optional[str] = None

    @classmethod
    def from_filename(cls, filename: str):
        pair = PDFPair()

        if is_annotated(filename):
            a = filename
            o = original_name(filename)
        else:
            a = annotated_name(filename)
            o = filename

        if os.path.exists(o):
            pair.original = o

        if os.path.exists(a):
            pair.annotated = a

        return pair


def check_command(args: argparse.Namespace) -> int:
    logging.info("""Check that PDFs obey rules about naming and annotations.

    1. Only "Foo ANNOTATED.pdf" files may have annotations.
    2. Every "Foo ANNOTATED.pdf" must have annotations.
    2. Every annotated PDF needs a corresponding original in the same directory.
    
    PDFs are "done" if the containing directory is named "Bar DONE" and contains
    a non-empty "Bar.md" file.""")
    exit_code = 0

    def error(msg, *args):
        nonlocal exit_code
        logger.error(msg, *args)
        exit_code = 1

    def should_ignore(full_path: str) -> bool:
        for ignore in args.ignore:
            if fnmatch.fnmatch(full_path, ignore):
                return True

        return False

    def directory_is_done(dir_path: str) -> bool:
        if not os.path.split(dir_path)[-1].endswith(" DONE"):
            return False

        md_path = os.path.join(
            dir_path, os.path.basename(dir_path)[:-len(" DONE")]
        ) + ".md"

        return (os.path.exists(md_path)
                and os.stat(md_path)[stat.ST_SIZE] > 0)

    todo: set[PDFPair] = set()
    done: set[PDFPair] = set()

    # args.directory is a list of directory names.
    for root in args.directory:
        for dirpath, dirnames, filenames in os.walk(root):
            is_done = directory_is_done(dirpath)

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if should_ignore(full_path) or should_ignore(filename):
                    continue

                base, ext = os.path.splitext(filename)
                if ext.lower() != ".pdf":
                    continue

                # If there's an original and annotated we'll generate this pair
                # twice, but the set will contain only one copy.
                pair = PDFPair.from_filename(full_path)
                if is_done:
                    done.add(pair)
                else:
                    todo.add(pair)

    all_pairs = todo | done

    counter = Counter({
        "Original PDFs": len([p for p in all_pairs if p.original]),
        "Annotated PDFs": len([p for p in all_pairs if p.annotated]),
        "Done": len(done),
        "TODO": len(todo)})

    for pair in all_pairs:
        if pair.original:
            logger.debug("Checking %s", pair.original)
            if has_annotations(pair.original):
                error("Annotated PDF not named like 'ANNOTATED' or 'DONE': %s",
                      pair.original)
                counter["original PDFs with stray annotations"] += 1

        if pair.annotated:
            logger.debug("Checking %s", pair.annotated)
            if not pair.original:
                error("Annotated pdf '%s' without original version",
                      pair.annotated)
                counter["annotated PDFs without originals"] += 1
            if not has_annotations(pair.annotated):
                error("No annotations in PDF: %s", pair.annotated)
                counter["PDFs that should have annotations but don't"] += 1

    for name, n in counter.items():
        logging.info("%4d %s", n, name)

    logging.info("TODO:")
    for pdf in sorted([pair.original for pair in all_pairs]):
        logging.info(pdf)

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
