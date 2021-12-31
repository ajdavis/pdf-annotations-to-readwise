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

from pdf_annotations_to_readwise import extract, readwise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers()

    check = subparsers.add_parser(
        "check", help="Find stray annotations and unsummarized articles")
    check.set_defaults(func=check_command)

    sync = subparsers.add_parser(
        "sync", help="Sync to Readwise")
    sync.add_argument("-t", "--token", help="Readwise access token",
                      required=True)
    sync.set_defaults(func=sync_command)

    for command in check, sync:
        command.add_argument("-i", "--ignore", action="append",
                             help="File(s) to ignore, glob patterns allowed")
        command.add_argument("directory", nargs="+")

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


def find_pdfs(args: argparse.Namespace) -> (set[PDFPair], set[PDFPair]):
    """Return to-read and done PDFs."""
    all_filenames = set()

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

                assert filename not in all_filenames, f"Duplicate: {filename}"
                all_filenames.add(filename)

                # If there's an original and annotated we'll generate this pair
                # twice, but the set will contain only one copy.
                pair = PDFPair.from_filename(full_path)
                if is_done:
                    done.add(pair)
                else:
                    todo.add(pair)

    return todo, done


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

    todo, done = find_pdfs(args)
    all_pairs = todo | done

    counter = Counter({
        "Original PDFs": len([p for p in all_pairs if p.original]),
        "Annotated PDFs": len([p for p in all_pairs if p.annotated]),
        "Done": len(done),
        "TODO": len(todo)})

    for pair in all_pairs:
        if pair.original:
            logger.debug("Checking %s", pair.original)
            if extract.has_annotations(pair.original):
                error("Annotated PDF not named like 'ANNOTATED' or 'DONE': %s",
                      pair.original)
                counter["original PDFs with stray annotations"] += 1

        if pair.annotated:
            logger.debug("Checking %s", pair.annotated)
            if not pair.original:
                error("Annotated pdf '%s' without original version",
                      pair.annotated)
                counter["annotated PDFs without originals"] += 1
            if not extract.has_annotations(pair.annotated):
                error("No annotations in PDF: %s", pair.annotated)
                counter["PDFs that should have annotations but don't"] += 1

    for name, n in counter.items():
        logging.info("%4d %s", n, name)

    logging.info("TODO:")
    for pdf in sorted([pair.original for pair in todo]):
        logging.info(pdf)

    return exit_code


def sync_command(args: argparse.Namespace) -> int:
    exit_code = 0
    todo, done = find_pdfs(args)
    all_pairs = todo | done
    # Map: book title -> book info dict.
    books = readwise.list_books(args.token)
    for pair in sorted(all_pairs, key=lambda p: p.original):
        if not pair.annotated:
            continue

        title = os.path.basename(pair.annotated)
        anns = extract.annotations(pair.annotated)

        if title in books:
            book_id = books[title]["id"]
            highlights = readwise.list_highlights(args.token, book_id)
            old_annotation_ids = set(highlights) - anns.annotation_ids
            if old_annotation_ids:
                logging.info("Delete %d old annotations for '%s' from Readwise",
                             len(old_annotation_ids), title)
                for annotation_id in old_annotation_ids:
                    readwise.delete_highlight(
                        args.token, highlights[annotation_id]["id"])

        readwise.post_highlights(token=args.token, anns=anns)

    return exit_code


def main(args: argparse.Namespace) -> None:
    start = time.time()
    exit_code = args.func(args)
    end = time.time()
    logger.info("Finished in %s", datetime.timedelta(seconds=int(end - start)))
    sys.exit(exit_code)


if __name__ == "__main__":
    main(parse_args())
