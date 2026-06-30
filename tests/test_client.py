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
