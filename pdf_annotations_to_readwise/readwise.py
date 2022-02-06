import logging

import requests

from pdf_annotations_to_readwise import extract

_APP_NAME = "pdf-annotations-to-readwise"
_logger = logging.getLogger("readwise")


def _readwise_api(token: str, method: str, endpoint: str, **kwargs) -> dict:
    response = requests.request(
        method=method,
        url=f"https://readwise.io/api/v2/{endpoint}/",
        headers={"Authorization": f"Token {token}"},
        **kwargs)
    response.raise_for_status()
    return response.json()


def _readwise_get(token: str, endpoint: str, query: dict) -> dict:
    rv = _readwise_api(token, "get", endpoint, params=query)
    assert rv["next"] is None, "TODO: pagination"
    return rv["results"]


def _readwise_post(token: str, endpoint: str, data: dict) -> dict:
    return _readwise_api(token, "post", endpoint, json=data)


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


def add_highlight_tag(token: str, highlight_url: str, tag: str) -> None:
    try:
        _readwise_post(token, f"highlights/{highlight_url}/tags", {"name": tag})
    except requests.HTTPError as exc:
        if exc.response.status_code == 400:
            error_message = exc.response.json().get("name")
            if error_message == "Tag with this name already exists":
                return

        raise


def post_highlights(token: str, anns: extract.Annotations) -> None:
    def highlights_json(annotations: list[extract.Annotation]) -> list[dict]:
        return [{
            "text": a.text,
            "title": anns.source_title,
            "location": a.page_number + 1,
            "highlighted_at": a.dt.isoformat(),
            # id isn't a URL, but it's unique!
            "highlight_url": a.id,
            "category": "books",
            "location_type": "page",
            "source_type": _APP_NAME
        } for a in annotations]

    # Readwise returns HTTP 400 if highlights is an empty list.
    if anns.underlines:
        _readwise_post(
            token,
            "highlights",
            {"highlights": highlights_json(anns.underlines)})

    if anns.free_texts:
        free_texts_reply = _readwise_post(
            token,
            "highlights",
            {"highlights": highlights_json(anns.free_texts)})

        for book_info in free_texts_reply:
            for highlight_id in book_info.get("modified_highlights", []):
                add_highlight_tag(token, highlight_id, "freetext")
