import asyncio

import pytest

from app.client import KibegiAPI
from app.config import Settings


def test_api_client_rejects_paths_outside_kibegi_namespace():
    client = KibegiAPI(Settings(go_api_base_url="http://localhost:8080"))
    with pytest.raises(ValueError):
        client._url("/admin/")


def test_api_client_requires_confirmation_for_mutations():
    client = KibegiAPI(Settings(go_api_base_url="http://localhost:8080"))
    with pytest.raises(ValueError):
        asyncio.run(client.request("POST", "/api/v1/search/", body={}))
