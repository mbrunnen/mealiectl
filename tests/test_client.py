import pytest
import requests

from mealiectl.client import MealieClient


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _StubSession:
    def __init__(self, pages):
        self._pages = pages
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        page = (params or {}).get("page", 1)
        return _StubResponse(self._pages[page - 1])


def test_client_sets_bearer_header():
    client = MealieClient("https://x/", "tok")
    assert client.session.headers["Authorization"] == "Bearer tok"
    assert client.base_url == "https://x"


def test_client_list_recipes_paginates():
    pages = [
        {"items": [{"slug": "a"}], "page": 1, "total_pages": 2},
        {"items": [{"slug": "b"}], "page": 2, "total_pages": 2},
    ]
    client = MealieClient("https://x", "tok")
    client.session = _StubSession(pages)
    assert [r["slug"] for r in client.list_recipes()] == ["a", "b"]


def test_http_error_includes_response_body():
    resp = requests.Response()
    resp.status_code = 400
    resp._content = b'{"detail":{"message":"Recipe already exists"}}'
    resp.url = "https://x/api/recipes/soup"
    client = MealieClient("https://x", "tok")
    client.session = type("S", (), {"put": lambda self, *a, **k: resp})()
    with pytest.raises(requests.HTTPError, match="Recipe already exists"):
        client.update_recipe("soup", {})
