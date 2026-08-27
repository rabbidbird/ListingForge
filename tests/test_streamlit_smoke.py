from __future__ import annotations

from streamlit.testing.v1 import AppTest

import core.auth
import core.ui


def test_public_home_renders_without_exception():
    app = AppTest.from_file("app.py").run(timeout=15)
    assert not app.exception
    assert any("Etsy listing drafts" in title.value for title in app.title)


def test_product_pages_render_without_exception(monkeypatch, user_factory):
    user = user_factory()
    monkeypatch.setattr(core.auth, "require_streamlit_user", lambda: user)
    monkeypatch.setattr(core.auth, "streamlit_current_user", lambda: user)
    monkeypatch.setattr(core.ui, "render_sidebar", lambda _user=None: None)
    files = [
        "pages/1_Optimizer.py",
        "pages/2_Bulk_Processor.py",
        "pages/3_SEO_Analyzer.py",
        "pages/4_History.py",
        "pages/5_About_Pricing.py",
        "pages/6_Legal.py",
    ]
    for file in files:
        app = AppTest.from_file(file).run(timeout=15)
        assert not app.exception, file
