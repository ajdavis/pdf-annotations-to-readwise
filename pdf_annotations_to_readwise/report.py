import collections
import os.path
import typing
from itertools import zip_longest

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
           sorted_todos: list[str]):
    prefix = common_prefix(sorted_todos)

    def gen_todos() -> typing.Generator[tuple[int, str], None, None]:
        stack = []

        def yield_value():
            return len(stack), prefix + '/'.join(stack)

        for t in sorted_todos:
            parts = t[len(prefix):].split("/")
            for i, (part, frame) in enumerate(zip_longest(parts, stack)):
                if part == frame:
                    continue
                elif frame is None:
                    stack.append(part)
                    yield yield_value()
                else:
                    # part != frame
                    stack = stack[:i]
                    if part is not None:
                        stack.append(part)
                        yield yield_value()

    env.get_template("report.html").stream(**locals()).dump(out)
