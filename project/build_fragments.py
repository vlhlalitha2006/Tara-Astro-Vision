#!/usr/bin/env python3
"""Extract pooja/homam bodies from root index.html and strip inline handlers."""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
idx = (root / "index.html").read_text(encoding="utf-8")

def sub_pooja_buttons(html: str) -> str:
    html = re.sub(
        r'<button([^>]*?)onclick="addToCart\(\'([^\']*)\',(\d+)\)"([^>]*)>',
        r'<button type="button"\1data-add-cart data-name="\2" data-price="\3"\4>',
        html,
    )
    html = re.sub(
        r'<button([^>]*?)onclick="startPoojaBooking\(\'([^\']*)\',(\d+)\)"([^>]*)>',
        r'<button type="button"\1data-book-pooja data-name="\2" data-price="\3"\4>',
        html,
    )
    return html

def sub_homam_buttons(html: str) -> str:
    html = re.sub(
        r'<button([^>]*?)onclick="startHomamBooking\(this,\'([^\']*)\',(\d+)\)"([^>]*)>',
        r'<button type="button"\1data-book-homam data-name="\2" data-price="\3"\4>',
        html,
    )
    return html

# Poojas: inner content lines 480-786 (1-based) = inside page-poojas, excluding outer wrapper
lines = idx.splitlines()
pooja_body = "\n".join(lines[479:786])  # 480-786 in 1-based file lines
pooja_body = sub_pooja_buttons(pooja_body)
Path(__file__).parent.joinpath("_pooja_body.html").write_text(pooja_body, encoding="utf-8")

homam_body = "\n".join(lines[794:1223])  # lines 795–1223 (1-based): page-hero through homam-note
homam_body = sub_homam_buttons(homam_body)
# Fix homam detail links for pages served from /project/
homam_body = homam_body.replace('href="homam/', 'href="../homam/')
Path(__file__).parent.joinpath("_homam_body.html").write_text(homam_body, encoding="utf-8")

print("Wrote _pooja_body.html and _homam_body.html")
