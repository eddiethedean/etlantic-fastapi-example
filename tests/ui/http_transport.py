from __future__ import annotations

import httpx
from fastapi.testclient import TestClient


class SyncTestClientTransport(httpx.BaseTransport):
    """Adapt FastAPI TestClient to httpx's sync transport API."""

    def __init__(self, test_client: TestClient) -> None:
        self._test_client = test_client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = httpx.URL(request.url)
        path = url.path
        if url.query:
            path = f"{path}?{url.query.decode()}"
        headers = dict(request.headers)
        headers.pop("host", None)
        response = self._test_client.request(
            request.method,
            path,
            headers=headers,
            content=request.content,
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )
