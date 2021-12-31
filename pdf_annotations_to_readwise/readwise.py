import logging

import requests

from pdf_annotations_to_readwise import extract

_APP_NAME = "pdf-annotations-to-readwise"
_logger = logging.getLogger("readwise")


def _readwise_get(token: str, endpoint: str, query: dict) -> dict:
    response = requests.get(
        url=f"https://readwise.io/api/v2/{endpoint}/",
        headers={"Authorization": f"Token {token}"},
        params=query)
    response.raise_for_status()
    rv = response.json()
    assert rv["next"] is None, "TODO: pagination"
    return rv["results"]


def _readwise_post(token: str, endpoint: str, data: dict) -> dict:
    response = requests.post(
        url=f"https://readwise.io/api/v2/{endpoint}/",
        headers={"Authorization": f"Token {token}"},
        json=data)
    response.raise_for_status()
    return response.json()


def _readwise_delete(token: str, endpoint: str) -> None:
    response = requests.delete(
        url=f"https://readwise.io/api/v2/{endpoint}/",
        headers={"Authorization": f"Token {token}"})
    response.raise_for_status()


def list_books(token: str) -> dict[str, dict]:
    """Get dict: book title -> book info."""
    return {b["title"]: b
            for b in _readwise_get(token,
                                   "books",
                                   {"category": "books", "source": _APP_NAME})}


def list_highlights(token: str, book_id: int) -> dict[str, dict]:
    """Get dict: highlight_url -> highlight info."""
    return {h["url"]: h
            for h in _readwise_get(token, "highlights", {"book_id": book_id})}


def delete_highlight(token: str, highlight_url: str) -> None:
    _readwise_delete(token, f"highlights/{highlight_url}")


def post_highlights(token: str, anns: extract.Annotations) -> dict:
    return _readwise_post(token, "highlights", {"highlights": [{
        "text": a.text,
        "title": anns.source_title,
        "location": a.page_number + 1,
        "highlighted_at": a.dt.isoformat(),
        # id isn't a URL, but it's unique!
        "highlight_url": a.id,
        "category": "books",
        "location_type": "page",
        "source_type": _APP_NAME
    } for a in anns.underlines + anns.free_texts]})
