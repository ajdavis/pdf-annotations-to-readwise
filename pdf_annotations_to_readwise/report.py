import collections
import os.path
import typing
from typing import Optional
from itertools import zip_longest

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pdf_annotations_to_readwise import PDFPair

env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape())

env.filters['basename'] = os.path.basename
env.filters['dirname'] = os.path.dirname


def common_prefix(sorted_strings: list[str]):
    if not sorted_strings:
        return ''

    if len(sorted_strings) == 1:
        return sorted_strings[0]

    first = sorted_strings[0]
    last = sorted_strings[-1]
    prefix = ''
    for i, c in enumerate(first):
        if last[i] == c:
            prefix += c
        else:
            break

    return prefix


def report(out: typing.TextIO,
           counter: collections.Counter,
           sorted_todos: list[PDFPair],
           errors: list[str]):
    prefix = common_prefix([pair.original for pair in sorted_todos])

    def gen_todos() -> typing.Generator[
            tuple[int, str, Optional[str]], None, None]:
        stack = []

        def yield_value(pair: PDFPair, is_penultimate: bool):
            return (
                len(stack),
                prefix + '/'.join(stack),
                pair.reason_not_done if is_penultimate else None)

        for t in sorted_todos:
            parts = t.original[len(prefix):].split("/")
            for i, (part, frame) in enumerate(zip_longest(parts, stack)):
                is_penultimate = i == len(parts) - 2
                if part == frame:
                    continue
                elif frame is None:
                    stack.append(part)
                    yield yield_value(t, is_penultimate)
                else:
                    # part != frame
                    stack = stack[:i]
                    if part is not None:
                        stack.append(part)
                        yield yield_value(t, is_penultimate)

    env.get_template("report.html").stream(**locals()).dump(out)
