import logging

import slugify
import requests

logger = logging.getLogger("readwise")


def _readwise_api(token: str, endpoint: str, query: dict) -> dict:
    reply = requests.get(
        url=f"https://readwise.io/api/v2/{endpoint}/",
        headers={"Authorization": f"Token {token}"},
        params=query).json()
    assert reply["next"] is None, "TODO: pagination"
    return reply["results"]


# TODO: use or remove
def _book_title_slug(title: str) -> str:
    return slugify.slugify(title, separator="_")


def readwise_list_books(token: str) -> dict:
    return _readwise_api(token, "books", {"category": "books", "source": "pdf"})
