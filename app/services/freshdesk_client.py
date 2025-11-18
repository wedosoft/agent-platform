from __future__ import annotations

from typing import Any, List, Optional

import httpx


class FreshdeskClientError(RuntimeError):
    pass


class FreshdeskClient:
    def __init__(self, domain: str, api_key: str, *, timeout: float = 10.0) -> None:
        if not domain or not api_key:
            raise FreshdeskClientError("Freshdesk domain/API key required")
        normalized = domain.replace("https://", "").replace("http://", "").rstrip("/")
        if not normalized.endswith(".freshdesk.com"):
            normalized = f"{normalized}.freshdesk.com"
        self.base_url = f"https://{normalized}/api/v2"
        self.api_key = api_key
        self.timeout = timeout

    async def get_groups(self) -> List[dict[str, Any]]:
        return await self._request("GET", "/groups")

    async def get_categories(self) -> List[dict[str, Any]]:
        return await self._request("GET", "/solutions/categories")

    async def get_folders(self, category_id: int) -> List[dict[str, Any]]:
        return await self._request("GET", f"/solutions/categories/{category_id}/folders")

    async def get_ticket_fields(self) -> List[dict[str, Any]]:
        return await self._request("GET", "/ticket_fields")

    async def search_tickets(self, query: str) -> dict[str, Any]:
        return await self._request("GET", "/search/tickets", params={"query": query})

    async def search_contacts(self, query: str) -> dict[str, Any]:
        return await self._request("GET", "/search/contacts", params={"query": query})

    async def search_agents(self, query: str) -> dict[str, Any]:
        return await self._request("GET", "/search/agents", params={"query": query})

    async def _request(self, method: str, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        auth = (self.api_key, "X")
        async with httpx.AsyncClient(timeout=self.timeout, auth=auth) as client:
            response = await client.request(method, url, params=params)
        if response.status_code >= 400:
            raise FreshdeskClientError(
                f"Freshdesk API {method} {path} failed: {response.status_code} {response.text}"
            )
        return response.json()
