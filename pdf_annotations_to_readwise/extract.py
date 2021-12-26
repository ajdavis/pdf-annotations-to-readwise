import datetime
import logging
import multiprocessing
import re
from dataclasses import dataclass, field
from typing import Optional

import fitz  # aka PyMuPDF


logger = logging.getLogger("extract")

@dataclass
class Annotation:
    type: str
    text: str
    page_number: int
    author: Optional[str] = None
    dt: Optional[datetime.datetime] = None


@dataclass
class Annotations:
    free_texts: list[Annotation] = field(default_factory=list)
    underlines: list[Annotation] = field(default_factory=list)


def _parse_date(info: dict) -> Optional[datetime.datetime]:
    if not (date_str := info.get("modDate", info.get("creationDate"))):
        return None

    # Like "D:20211215162238-05'00'", see
    # verypdf.com/pdfinfoeditor/pdf-date-format.htm
    match = re.match(
        r"D:(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})"
        r"(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})"
        r"(?P<sign>[+-Z])(?P<Hoffset>\d{2})'(?P<Moffset>\d{2})'",
        date_str)

    if not match:
        logger.warning("Bad date string: '%s'", date_str)
        return None

    sign = -1 if match.group("sign") == "-" else 1
    return datetime.datetime(
        year=int(match.group("y")),
        month=int(match.group("m")),
        day=int(match.group("d")),
        hour=int(match.group("H")),
        minute=int(match.group("M")),
        second=int(match.group("S")),
        tzinfo=datetime.timezone(datetime.timedelta(
            hours=sign * int(match.group("Hoffset")),
            minutes=int(match.group("Moffset")))))


def _underlined_text(page: fitz.Page, annot: fitz.Annot) -> str:
    # Vertices is an array of underlines (long thin rects).
    rv = ""
    for i in range(0, len(annot.vertices), 4):
        vs = annot.vertices[i:i+4]
        xs = [v[0] for v in vs]
        ys = [v[1] for v in vs]
        # Bounds of the rect.
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        # Raise top of box upward from the underline to capture text.
        # (Found these offsets by experiment, there must be a better way.)
        rect = fitz.Rect(x0 - 1, y0 - 7, x1 + 1, y1 + 3)
        if text := page.get_textbox(rect):
            rv += " " + text
        else:
            logger.warning("No text for underline on page %s of '%s'",
                           page.number, page.parent.name)

    return rv.strip()


def _annotations(pdf_path: str, q: multiprocessing.Queue) -> None:
    anns = Annotations()
    for page in fitz.open(pdf_path):
        for a in page.annots(types=[fitz.PDF_ANNOT_FREE_TEXT]):
            anns.free_texts.append(Annotation(
                "FreeText",
                a.info["content"],
                page.number,
                author=a.info["title"],  # Strange but true.
                dt=_parse_date(a.info)))

        for a in page.annots(types=[fitz.PDF_ANNOT_UNDERLINE]):
            anns.underlines.append(Annotation(
                "Underline",
                _underlined_text(page, a),
                page.number,
                author=a.info["title"],
                dt=_parse_date(a.info)))

    q.put(anns)


def annotations(pdf_path: str) -> Annotations:
    # mupdf is crashy; avoid terminating the whole script.
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=_annotations, args=(pdf_path, q))
    p.start()
    p.join()
    if 0 != p.exitcode:
        logger.error("Subprocess failed with exit code: %s", p.exitcode)
        return Annotations()

    return q.get()


def has_annotations(pdf_path: str) -> bool:
    anns = annotations(pdf_path)
    return bool(anns.free_texts or anns.underlines)
