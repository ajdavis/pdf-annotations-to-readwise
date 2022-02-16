import os
from dataclasses import dataclass
from typing import Optional

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
    reason_not_done: Optional[str] = None

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
