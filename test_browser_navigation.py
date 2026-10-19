"""Tests for browser back/forward navigation and SPA fallback routing."""
import re
from pathlib import Path
from fastapi.testclient import TestClient
from main import app, SPA_PATHS

ROOT = Path(__file__).resolve().parent


def test_all_spa_routes_serve_index_html():
    client = TestClient(app)
    expected_spa_paths = [
        "/",
        "/home",
        "/horoscope",
        "/horoscopes",
        "/kundli",
        "/kundali",
        "/dashboard",
        "/pooja",
        "/poojas",
        "/homam",
        "/homams",
        "/consult",
        "/consultation",
        "/consult-astrologer",
        "/booking",
        "/booking-form",
        "/payment",
        "/confirmation",
    ]

    for path in expected_spa_paths:
        res = client.get(path)
        assert res.status_code == 200, f"Route {path} failed with {res.status_code}"
        assert b'class="navbar"' in res.content, f"Route {path} did not serve index.html"
        assert b'id="page-home"' in res.content, f"Route {path} missing page-home"
        assert b'id="page-poojas"' in res.content, f"Route {path} missing page-poojas"
        assert b'id="page-homams"' in res.content, f"Route {path} missing page-homams"
        assert b'id="page-dashboard"' in res.content, f"Route {path} missing page-dashboard"

        # Trailing slash test
        if path != "/":
            res_slash = client.get(f"{path}/")
            assert res_slash.status_code == 200, f"Route {path}/ failed with {res_slash.status_code}"
            assert b'class="navbar"' in res_slash.content


def test_homam_detail_pages_and_assets_intact():
    client = TestClient(app)
    # Check detail page serves React app with id="root"
    res = client.get("/homam/prathyangira-homam")
    assert res.status_code == 200
    assert b'id="root"' in res.content

    res_chandi = client.get("/homam/chandi-mula-mantra-homam")
    assert res_chandi.status_code == 200
    assert b'id="root"' in res_chandi.content

    # Check homam index.html direct access
    res_idx = client.get("/homam/index.html")
    assert res_idx.status_code == 200
    assert b'id="root"' in res_idx.content

    # Check /homam root serves the main website SPA (so back/forward works without redirect loop)
    res_homam_root = client.get("/homam")
    assert res_homam_root.status_code == 200
    assert b'id="page-homams"' in res_homam_root.content


def test_navbar_links_have_semantic_urls_and_navigateto():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")

    # Logo link
    assert 'href="/" class="nav-logo" onclick="navigateTo(\'home\', event)"' in index_html

    # Nav links
    assert 'href="/" class="nav-link" data-page="home" onclick="navigateTo(\'home\', event)"' in index_html
    assert 'href="/horoscope" class="nav-link" data-page="horoscope" onclick="navigateTo(\'horoscope\', event)"' in index_html
    assert 'href="/kundli" class="nav-link" data-page="kundli" onclick="navigateTo(\'kundli\', event)"' in index_html
    assert 'href="/dashboard" class="nav-link" data-page="dashboard" onclick="navigateTo(\'dashboard\', event)"' in index_html
    assert 'href="/pooja" class="nav-link" data-page="poojas" onclick="navigateTo(\'poojas\', event)"' in index_html
    assert 'href="/homam" class="nav-link" data-page="homams" onclick="navigateTo(\'homams\', event)"' in index_html
    assert 'href="/consult" class="nav-link" data-page="consult" onclick="navigateTo(\'consult\', event)"' in index_html

    # No leftover href="#" in navbar
    nav_links_match = re.search(r'<nav class="nav-links".*?</nav>', index_html, re.DOTALL)
    assert nav_links_match, "Navbar links container not found"
    assert 'href="#"' not in nav_links_match.group(0), "Found leftover href='#' in navbar links"


def test_app_js_history_and_routing_logic():
    app_js = (ROOT / "app.js").read_text(encoding="utf-8")

    # Check key functions and variables exist
    assert "PAGE_ROUTES" in app_js
    assert "ROUTE_ALIASES" in app_js
    assert "HASH_ALIASES" in app_js
    assert "function normalizePageId" in app_js
    assert "function getPageIdFromLocation" in app_js
    assert "function navigateTo" in app_js
    assert "window.addEventListener('popstate'" in app_js
    assert "window.history.pushState" in app_js
    assert "window.history.replaceState" in app_js

    # Check window exports
    assert "window.showPage = showPage;" in app_js
    assert "window.navigateTo = navigateTo;" in app_js
    assert "window.getPageIdFromLocation = getPageIdFromLocation;" in app_js


def test_web_config_has_spa_fallback_rules():
    web_config = (ROOT / "web.config").read_text(encoding="utf-8")
    assert "Homam SPA fallback" in web_config
    assert "Main SPA fallback" in web_config
    assert '<action type="Rewrite" url="/index.html" />' in web_config
