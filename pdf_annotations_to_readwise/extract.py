import datetime
import logging
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


def annotations(pdf_path: str) -> Annotations:
    anns = Annotations()
    for page in fitz.open(pdf_path):
        for a in page.annots(types=[fitz.PDF_ANNOT_FREE_TEXT]):
            anns.free_texts.append(Annotation(
                "FreeText",
                a.info["content"],
                page.number,
                author=a.info["title"],  # Strange but true.
                dt=_parse_date(a.info)
            ))

        for a in page.annots(types=[fitz.PDF_ANNOT_UNDERLINE]):
            # Experimentally determined offset to get text above underline.
            # TODO: expand the rect in increments until text is non-empty.
            rect = fitz.Rect(
                a.rect.x0 - 1,
                a.rect.y0 - 7,
                a.rect.x1 + 1,
                a.rect.y1 + 3
            )
            anns.underlines.append(Annotation(
                "Underline",
                page.get_textbox(rect),
                page.number,
                author=a.info["title"],
                dt=_parse_date(a.info)
            ))

    return anns


def has_annotations(pdf_path: str) -> bool:
    anns = annotations(pdf_path)
    return bool(anns.free_texts or anns.underlines)
