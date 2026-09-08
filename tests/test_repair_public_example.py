from __future__ import annotations

import html
import importlib

from fastapi.testclient import TestClient

from core.marketing import worked_example


def test_rendered_home_uses_every_actual_generated_output_field():
    import core.web

    web = importlib.reload(core.web)
    generated = worked_example()
    with TestClient(web.app) as client:
        response = client.get("/")
    assert response.status_code == 200
    for label, value in (
        ("Title", generated["best_title"]),
        ("Description", generated["description"]),
        ("Tags", ", ".join(generated["tags"])),
    ):
        displayed = html.escape(value).replace("\n", "<br>")
        assert f"<span>{label}</span><p>{displayed}</p>" in response.text
    assert "font-src 'self'" in response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
