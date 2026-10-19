"""Homam SPA routes: listing hrefs, FastAPI fallback, built slug pages, assets, and booking."""
import re
import itertools
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from service_catalogue import get_service, validate_and_price

ROOT = Path(__file__).resolve().parent
HOMAM_DIST = ROOT / "homam"
HOMAMS_JS = ROOT / "homam-app" / "src" / "data" / "homams.js"


def _slugs():
    source = HOMAMS_JS.read_text(encoding="utf-8")
    return re.findall(r"slug:\s*'([^']+)'", source)


def test_all_22_homam_slugs_match_listing_and_data():
    slugs = _slugs()
    assert len(slugs) == 22, f"Expected 22 homams, got {len(slugs)}"
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    hrefs = set(re.findall(r'class="homam-name homam-name-link" href="/homam/([^"]+)"', index_html))
    assert hrefs == set(slugs), f"Mismatch in index.html: {hrefs ^ set(slugs)}"
    project_html = (ROOT / "project" / "homam.html").read_text(encoding="utf-8")
    project_hrefs = set(
        re.findall(r'class="homam-name homam-name-link" href="/homam/([^"]+)"', project_html)
    )
    assert project_hrefs == set(slugs), f"Mismatch in project/homam.html: {project_hrefs ^ set(slugs)}"


def test_built_assets_and_slug_pages_exist():
    spa = HOMAM_DIST / "index.html"
    assert spa.is_file(), "homam/index.html is missing"
    html = spa.read_text(encoding="utf-8")
    assert 'src="/homam/assets/' in html
    assert 'href="/homam/assets/' in html
    assert (HOMAM_DIST / "web.config").is_file()
    for slug in _slugs():
        nested = HOMAM_DIST / slug / "index.html"
        assert nested.is_file(), f"missing {nested}"
        assert nested.read_text(encoding="utf-8") == html


def test_fastapi_serves_all_22_homam_detail_pages_and_assets():
    client = TestClient(app)
    listing = client.get("/index.html")
    assert listing.status_code == 200

    index = client.get("/homam/index.html")
    assert index.status_code == 200

    js_refs = re.findall(r'src="(/homam/assets/[^"]+\.js)"', index.text)
    css_refs = re.findall(r'href="(/homam/assets/[^"]+\.css)"', index.text)
    assert js_refs and css_refs
    for url in js_refs + css_refs:
        asset = client.get(url)
        assert asset.status_code == 200, f"Asset failed: {url}"

    # Test all 22 slug URLs with and without trailing slashes
    for slug in _slugs():
        # Direct access
        res = client.get(f"/homam/{slug}")
        assert res.status_code == 200, f"Direct access failed for /homam/{slug}"
        assert b'id="root"' in res.content

        # Direct access with trailing slash (refresh scenario)
        res_slash = client.get(f"/homam/{slug}/")
        assert res_slash.status_code == 200, f"Refresh/trailing slash failed for /homam/{slug}/"
        assert b'id="root"' in res_slash.content

        # Direct access to nested index.html
        res_idx = client.get(f"/homam/{slug}/index.html")
        assert res_idx.status_code == 200, f"Direct index failed for /homam/{slug}/index.html"
        assert b'id="root"' in res_idx.content

    # Fallback to SPA shell for arbitrary subpath
    missing = client.get("/homam/not-a-real-homam")
    assert missing.status_code == 200
    assert b'id="root"' in missing.content


from service_catalogue import get_service, validate_and_price, is_homam_enabled, ENABLED_HOMAMS


def test_every_homam_in_service_catalogue_for_booking():
    """Verify that only the 4 approved homams are active, while the other 18 are Coming Soon."""
    source = HOMAMS_JS.read_text(encoding="utf-8")
    titles = re.findall(r"title:\s*'([^']+)'", source)
    assert len(titles) == 22
    for title in titles:
        if is_homam_enabled(title):
            svc, total = validate_and_price(title, "homam", 2)
            assert svc is not None
            assert svc.type == "homam"
            assert total == 4000.0  # 2000 * 2 persons
        else:
            # Availability check blocks disabled homams
            import pytest
            with pytest.raises(ValueError, match="Coming Soon"):
                validate_and_price(title, "homam", 2, check_availability=True)
            # Without availability check, pricing still exists
            svc, total = validate_and_price(title, "homam", 2, check_availability=False)
            assert total == 4000.0


def test_homam_order_creation_for_all_homams():
    """Verify that Razorpay order creation accepts only 4 approved homams and blocks disabled homams."""
    client = TestClient(app)
    source = HOMAMS_JS.read_text(encoding="utf-8")
    titles = re.findall(r"title:\s*'([^']+)'", source)
    mock_rzp = MagicMock()
    order_ids = itertools.count(1)
    mock_rzp.order.create.side_effect = lambda data: {
        "id": f"order_H_{next(order_ids)}",
        "amount": data["amount"],
        "currency": data["currency"],
    }
    with patch("main._rzp_client", return_value=mock_rzp):
        for title in titles:
            r = client.post("/api/payment/order", json={
                "name": title,
                "serviceType": "homam",
                "persons": 1,
            })
            if is_homam_enabled(title):
                assert r.status_code == 200, f"Order creation failed for approved homam {title}: {r.text}"
                body = r.json()
                assert body["order_id"].startswith("order_H_")
                assert body["unit_price"] == 2000.0
            else:
                assert r.status_code == 400, f"Disabled homam {title} should be blocked: {r.text}"
                assert "Coming Soon" in r.json()["detail"]


def test_homam_buttons_ui_states():
    """Verify that exactly 4 buttons are enabled and 18 are disabled 'Coming Soon'."""
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    project_html = (ROOT / "project" / "homam.html").read_text(encoding="utf-8")

    for html_doc, name in [(index_html, "index.html"), (project_html, "project/homam.html")]:
        coming_soon_matches = re.findall(r'<button[^>]*class="[^"]*btn-disabled[^"]*"[^>]*disabled[^>]*>\s*Coming Soon\s*</button>', html_doc)
        assert len(coming_soon_matches) == 18, f"Expected 18 Coming Soon buttons in {name}, found {len(coming_soon_matches)}"

    # In index.html, exactly 4 startHomamBooking calls
    active_in_index = re.findall(r'onclick="startHomamBooking\(this,\'([^\']*)\'', index_html)
    assert len(active_in_index) == 4
    for homam in active_in_index:
        assert is_homam_enabled(homam)

    # In project/homam.html, exactly 4 data-book-homam buttons
    active_in_project = re.findall(r'data-book-homam data-name="([^"]+)"', project_html)
    assert len(active_in_project) == 4
    for homam in active_in_project:
        assert is_homam_enabled(homam)
