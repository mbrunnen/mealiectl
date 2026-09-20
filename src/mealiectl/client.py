"""Thin HTTP client for the Mealie v3 REST API."""

from __future__ import annotations

import requests


def _raise_for_status(resp: requests.Response) -> None:
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(f"{exc}: {resp.text[:500]}", response=resp) from exc


class MealieClient:
    """Authenticated client over the subset of the Mealie API we use."""

    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    def _url(self, path: str) -> str:
        return self.base_url + path

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(self._url(path), params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _paginate(self, path: str) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            data = self._get(path, params={"page": page, "perPage": 100})
            items.extend(data.get("items", []))
            if page >= (data.get("total_pages") or 1):
                return items
            page += 1

    def _post(self, path: str, json_body: dict) -> requests.Response:
        resp = self.session.post(self._url(path), json=json_body, timeout=self.timeout)
        _raise_for_status(resp)
        return resp

    def _put(self, path: str, json_body: dict) -> requests.Response:
        resp = self.session.put(self._url(path), json=json_body, timeout=self.timeout)
        _raise_for_status(resp)
        return resp

    def list_recipes(self) -> list[dict]:
        return self._paginate("/api/recipes")

    def get_recipe(self, slug: str) -> dict:
        return self._get(f"/api/recipes/{slug}")

    def create_recipe(self, name: str) -> str:
        return self._post("/api/recipes", {"name": name}).json()

    def update_recipe(self, slug: str, payload: dict) -> None:
        self._put(f"/api/recipes/{slug}", payload)

    def get_image(self, recipe_id: str) -> bytes | None:
        resp = self.session.get(
            self._url(f"/api/media/recipes/{recipe_id}/images/original.webp"),
            timeout=self.timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content

    def update_image(self, slug: str, data: bytes, extension: str) -> None:
        resp = self.session.put(
            self._url(f"/api/recipes/{slug}/image"),
            files={"image": (f"image.{extension}", data)},
            data={"extension": extension},
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def list_foods(self) -> list[dict]:
        return self._paginate("/api/foods")

    def create_food(self, payload: dict) -> dict:
        return self._post("/api/foods", payload).json()

    def update_food(self, item_id: str, payload: dict) -> None:
        self._put(f"/api/foods/{item_id}", payload)

    def list_units(self) -> list[dict]:
        return self._paginate("/api/units")

    def create_unit(self, payload: dict) -> dict:
        return self._post("/api/units", payload).json()

    def update_unit(self, item_id: str, payload: dict) -> None:
        self._put(f"/api/units/{item_id}", payload)

    def list_labels(self) -> list[dict]:
        return self._paginate("/api/groups/labels")

    def create_label(self, payload: dict) -> dict:
        return self._post("/api/groups/labels", payload).json()

    def list_tags(self) -> list[dict]:
        return self._paginate("/api/organizers/tags")

    def create_tag(self, name: str) -> dict:
        return self._post("/api/organizers/tags", {"name": name}).json()

    def list_categories(self) -> list[dict]:
        return self._paginate("/api/organizers/categories")

    def create_category(self, name: str) -> dict:
        return self._post("/api/organizers/categories", {"name": name}).json()

    def list_tools(self) -> list[dict]:
        return self._paginate("/api/organizers/tools")

    def create_tool(self, name: str) -> dict:
        return self._post("/api/organizers/tools", {"name": name}).json()
