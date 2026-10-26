#!/usr/bin/env python3
"""Audit the KNR Studio static site before changes are published."""

from __future__ import annotations

import json
import re
import sys
from xml.etree import ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
STRIPE_PATH = re.compile(r"^/[A-Za-z0-9]+$")


class GalleryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.card = None
        self.cards = []
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())

        if tag == "div" and "piece" in classes and self.card is None:
            self.card = {"title": "", "price": "", "image": None, "alt": "", "link": None}
            self.depth = 1
            return

        if self.card is None:
            return

        if tag == "div":
            self.depth += 1
            if "price" in classes:
                self.capture = "price"
        elif tag == "h3":
            self.capture = "title"
        elif tag == "img":
            self.card["image"] = attrs.get("src")
            self.card["alt"] = attrs.get("alt", "").strip()
        elif tag == "a":
            self.card["link"] = attrs

    def handle_data(self, data):
        if self.card is not None and self.capture:
            self.card[self.capture] += data.strip()

    def handle_endtag(self, tag):
        if self.card is None:
            return
        if tag in {"h3"} or (tag == "div" and self.capture == "price"):
            self.capture = None
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.cards.append(self.card)
                self.card = None
                self.capture = None


def audit() -> list[str]:
    errors: list[str] = []
    if not INDEX.is_file():
        return ["index.html is missing"]

    parser = GalleryParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))

    if not parser.cards:
        return ["No artwork cards were found in index.html"]

    links: defaultdict[str, list[str]] = defaultdict(list)

    for number, card in enumerate(parser.cards, start=1):
        title = card["title"] or f"Artwork card {number}"
        price = card["price"]
        image = card["image"]
        alt = card["alt"]
        anchor = card["link"]

        if not card["title"]:
            errors.append(f"{title}: missing artwork title")
        if not price.startswith("$"):
            errors.append(f"{title}: missing or invalid displayed price")
        if not image:
            errors.append(f"{title}: missing image source")
        elif not (ROOT / image).is_file():
            errors.append(f"{title}: image file does not exist: {image}")
        if len(alt) < 12:
            errors.append(f"{title}: image needs meaningful alt text")

        if not anchor:
            errors.append(f"{title}: missing Buy Print link")
            continue

        href = anchor.get("href", "")
        parsed = urlparse(href)
        if parsed.scheme != "https" or parsed.netloc != "buy.stripe.com" or not STRIPE_PATH.fullmatch(parsed.path):
            errors.append(f"{title}: invalid Stripe payment link: {href or '(empty)'}")
        else:
            links[href].append(title)

        if anchor.get("target") != "_blank":
            errors.append(f"{title}: Stripe checkout must open in a new tab")

        rel = set(anchor.get("rel", "").split())
        missing_rel = {"noopener", "noreferrer"} - rel
        if missing_rel:
            errors.append(f"{title}: payment link is missing safety setting(s): {', '.join(sorted(missing_rel))}")

    for href, titles in links.items():
        if len(titles) > 1:
            errors.append(f"Duplicate Stripe link shared by {', '.join(titles)}: {href}")

    # Verify SEO essentials without changing pricing, payment or tracking code.
    pages = {
        "index.html": "https://kimberlyreising.com/",
        "queen-on-the-board.html": "https://kimberlyreising.com/queen-on-the-board.html",
        "tenfold-ascension.html": "https://kimberlyreising.com/tenfold-ascension.html",
    }
    for filename, canonical in pages.items():
        page_path = ROOT / filename
        if not page_path.is_file():
            errors.append(f"SEO page missing: {filename}")
            continue
        html = page_path.read_text(encoding="utf-8")
        if not re.search(r'<meta name="description" content="[^"]{50,}">', html):
            errors.append(f"{filename}: missing meaningful meta description")
        if f'<link rel="canonical" href="{canonical}">' not in html:
            errors.append(f"{filename}: canonical URL mismatch")
        if 'name="twitter:card"' not in html or 'property="og:image"' not in html:
            errors.append(f"{filename}: missing social preview metadata")
        jsonld = re.findall(r'<script type="application/ld\\+json">(.*?)</script>', html, flags=re.S)
        if not jsonld:
            errors.append(f"{filename}: missing structured data")
        for block in jsonld:
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{filename}: invalid JSON-LD: {exc}")
        for image in re.findall(r'<img\\b[^>]*?src="([^"]+)"', html):
            if not image.startswith(("http://", "https://")) and not (ROOT / image).is_file():
                errors.append(f"{filename}: missing artwork image {image}")
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.is_file():
        errors.append("Missing sitemap.xml")
    else:
        try:
            root = ET.parse(sitemap).getroot()
            urls = {el.text for el in root.iter() if el.tag.endswith("}loc")}
            if set(pages.values()) != urls:
                errors.append("Sitemap URLs do not match canonical pages")
        except ET.ParseError as exc:
            errors.append(f"Invalid sitemap XML: {exc}")
    robots = ROOT / "robots.txt"
    if not robots.is_file() or "Sitemap: https://kimberlyreising.com/sitemap.xml" not in robots.read_text(encoding="utf-8"):
        errors.append("robots.txt must advertise the sitemap")
    return errors


def main() -> int:
    errors = audit()
    if errors:
        print("KNR SITE AUDIT FAILED")
        for error in errors:
            print(f"  ✗ {error}")
        return 1

    print("KNR SITE AUDIT PASSED")
    print("  ✓ Artwork titles and prices are present")
    print("  ✓ Every artwork image exists and has descriptive text")
    print("  ✓ Stripe payment links are valid and unique")
    print("  ✓ Stripe checkout links open safely in new tabs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
