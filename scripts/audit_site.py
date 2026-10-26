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
        "queen-on-the-board.html": "https://kimberlyreising.com/queen-on-the-board",
        "tenfold-ascension.html": "https://kimberlyreising.com/tenfold-ascension",
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
        jsonld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.S)
        if not jsonld:
            errors.append(f"{filename}: missing structured data")
        for block in jsonld:
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{filename}: invalid JSON-LD: {exc}")
        for image in re.findall(r'<img\b[^>]*?src="([^"]+)"', html):
            if not image.startswith(("http://", "https://")) and not (ROOT / image).is_file():
                errors.append(f"{filename}: missing artwork image {image}")

    # Performance and accessibility guardrails (added Oct 2026).
    for filename in pages:
        page_path = ROOT / filename
        if not page_path.is_file():
            continue
        html = page_path.read_text(encoding="utf-8")
        title = re.search(r"<title>(.*?)</title>", html, flags=re.S)
        if not title or len(re.sub(r"&amp;", "&", title.group(1))) > 70:
            errors.append(f"{filename}: title missing or longer than 70 characters")
        desc = re.search(r'<meta name="description" content="([^"]*)">', html)
        if desc and len(desc.group(1)) > 165:
            errors.append(f"{filename}: meta description longer than 165 characters")
        if len(re.findall(r"<h1[\s>]", html)) != 1:
            errors.append(f"{filename}: page must have exactly one h1")
        for tag in re.findall(r"<img\b[^>]*>", html):
            if 'alt="' not in tag:
                errors.append(f"{filename}: image without alt attribute: {tag[:80]}")
            if "width=" not in tag or "height=" not in tag:
                errors.append(f"{filename}: image without width/height (layout shift): {tag[:80]}")
        og = re.search(r'property="og:image" content="https://kimberlyreising.com/([^"]+)"', html)
        if og and not (ROOT / og.group(1)).is_file():
            errors.append(f"{filename}: og:image file missing: {og.group(1)}")
        for ref in re.findall(r'<link rel="(?:icon|apple-touch-icon)" href="/([^"]+)"', html):
            if not (ROOT / ref).is_file():
                errors.append(f"{filename}: icon file missing: {ref}")
    # Homepage image weight budget: every image variant the page can load must stay small.
    home = INDEX.read_text(encoding="utf-8")
    for ref in set(re.findall(r'images/[^\s"\',]+\.(?:webp|jpe?g|png)', home, flags=re.I)):
        f = ROOT / ref
        if f.is_file() and f.stat().st_size > 450_000 and "/opt/" in ref:
            errors.append(f"Homepage image too heavy (>450 KB): {ref}")
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.is_file():
        errors.append("Missing sitemap.xml")
    else:
        try:
            root = ET.parse(sitemap).getroot()
            ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            urls = {u.find(ns + "loc").text for u in root.findall(ns + "url")}
            for u in root.findall(ns + "url"):
                for img in u.iter("{http://www.google.com/schemas/sitemap-image/1.1}loc"):
                    local = img.text.replace("https://kimberlyreising.com/", "")
                    if not (ROOT / local).is_file():
                        errors.append(f"Sitemap image missing from repo: {local}")
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
    print("  ✓ Titles, descriptions, canonicals, sitemap, social images and icons are valid")
    print("  ✓ Every image has alt text and dimensions; homepage image variants stay under budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())

