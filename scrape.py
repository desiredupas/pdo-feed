#!/usr/bin/env python3
"""
Générateur de flux RSS pour le catalogue PDO de SHAPE.
Tourne sur les serveurs de GitHub (Actions) — rien à installer en local.

Il récupère les deux pages du catalogue, en extrait les articles, et produit :
  - feed.xml   -> le flux RSS à coller dans Feedly
  - index.html -> une petite page lisible (bonus)
  - seen.json  -> mémoire des dates de première apparition (dates stables)
"""

import json
import re
import sys
import datetime
import urllib.parse
import urllib.request

CATALOGUE_URLS = [
    "https://shape2day.com/our-community/recycling-centre/property-disposal-pdo-sale/catalogue",
    "https://shape2day.com/our-community/recycling-centre/property-disposal-pdo-sale/catalogue/page/2.aspx",
]

UA = "Mozilla/5.0 (compatible; PDO-Feed-Bot/1.0; +https://github.com/)"


def http_get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_page(url):
    """Récupère une page. Essaie le relais Jina (markdown propre) d'abord,
    puis un accès direct en secours."""
    try:
        md = http_get("https://r.jina.ai/" + url)
        if "/catalogue/" in md:
            return md, "markdown"
    except Exception as e:
        print(f"  (jina KO pour {url}: {e})", file=sys.stderr)
    # secours : HTML direct
    html = http_get(url)
    return html, "html"


def parse_markdown(text):
    items = []
    pat = re.compile(
        r"###\s+\[([^\]]+)\]\((https?://[^\s)]+/catalogue/[^\s)]+\.aspx)\)(.*?)"
        r"(?=###\s+\[|\n##\s|\Z)",
        re.S,
    )
    for m in pat.finditer(text):
        title = m.group(1).strip()
        url = m.group(2).strip()
        if "/page/" in url:
            continue
        block = m.group(3)
        am = re.search(r"Available:\**\s*(\d+)", block, re.I)
        pm = re.search(r"\n\s*([^\n]*\u20ac[^\n]*)\n", block)
        price = ""
        if pm:
            price = re.sub(r"^\s*\d+\s+", "", pm.group(1).strip()).strip()
        items.append({
            "title": title,
            "url": url,
            "available": am.group(1) if am else "",
            "price": price,
        })
    return items


def parse_html(html):
    """Secours si le markdown n'est pas dispo. Nécessite beautifulsoup4."""
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for h in soup.find_all("h3"):
        a = h.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if "/catalogue/" not in href or not href.endswith(".aspx"):
            continue
        if "/page/" in href:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        url = href if href.startswith("http") else "https://shape2day.com" + \
            ("" if href.startswith("/") else "/") + href
        ctx = ""
        node = h
        for _ in range(6):
            node = node.find_next_sibling()
            if node is None or node.name == "h3":
                break
            ctx += " " + node.get_text(" ", strip=True)
        am = re.search(r"Available:?\s*(\d+)", ctx, re.I)
        pm = re.search(r"(\d+L\s*for\s*\d+\u20ac|\d+\u20ac)", ctx)
        items.append({
            "title": title,
            "url": url,
            "available": am.group(1) if am else "",
            "price": pm.group(1) if pm else "",
        })
    return items


def collect():
    all_items, seen_urls = [], set()
    for url in CATALOGUE_URLS:
        text, kind = fetch_page(url)
        parsed = parse_markdown(text) if kind == "markdown" else parse_html(text)
        if not parsed:  # dernier recours : tenter l'autre parseur
            parsed = parse_html(text) or parse_markdown(text)
        for it in parsed:
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                all_items.append(it)
    return all_items


def load_seen():
    try:
        with open("seen.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def build_rss(items, seen):
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>SHAPE PDO — Catalogue</title>",
        f"<link>{esc(CATALOGUE_URLS[0])}</link>",
        "<description>Objets en vente au Property Disposal Office de SHAPE. "
        "Un nouvel article = une nouvelle entrée.</description>",
        "<language>en</language>",
        f"<lastBuildDate>{now_str}</lastBuildDate>",
    ]
    # date de première apparition stable
    for it in items:
        first = seen.get(it["url"])
        if not first:
            first = now.isoformat()
            seen[it["url"]] = first
        it["_pub"] = first
    # les plus récents d'abord
    items.sort(key=lambda x: x["_pub"], reverse=True)
    for it in items:
        try:
            pub = datetime.datetime.fromisoformat(it["_pub"]).strftime(
                "%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub = now_str
        bits = []
        if it["price"]:
            bits.append("Prix : " + it["price"])
        if it["available"]:
            bits.append("Disponibles : " + it["available"])
        desc = ". ".join(bits)
        title = it["title"] + (f" — {it['price']}" if it["price"] else "")
        parts += [
            "<item>",
            f"<title>{esc(title)}</title>",
            f"<link>{esc(it['url'])}</link>",
            f'<guid isPermaLink="true">{esc(it["url"])}</guid>',
            f"<description>{esc(desc)}</description>",
            f"<pubDate>{pub}</pubDate>",
            "</item>",
        ]
    parts.append("</channel></rss>")
    return "\n".join(parts)


def build_index(items):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    rows = "\n".join(
        f'<li><a href="{esc(it["url"])}">{esc(it["title"])}</a>'
        f'<span>{esc(it["price"])}{" · dispo " + esc(it["available"]) if it["available"] else ""}</span></li>'
        for it in items
    )
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHAPE PDO — Catalogue</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#16243f}}
h1{{font-size:1.4rem}} .sub{{color:#667;font-size:.85rem;margin-bottom:1.5rem}}
.feed{{display:inline-block;background:#16243f;color:#fff;text-decoration:none;padding:.5rem .9rem;border-radius:8px;font-size:.9rem;margin-bottom:1.5rem}}
ul{{list-style:none;padding:0}} li{{display:flex;justify-content:space-between;gap:1rem;padding:.6rem 0;border-bottom:1px solid #eee}}
a{{color:#16243f}} span{{color:#889;font-size:.82rem;white-space:nowrap;font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>SHAPE PDO — Catalogue</h1>
<div class="sub">{len(items)} articles · mis à jour le {now}</div>
<a class="feed" href="feed.xml">📡 feed.xml — colle cette URL dans Feedly</a>
<ul>{rows}</ul>
</body></html>"""


def main():
    items = collect()
    if len(items) < 3:
        print(f"ÉCHEC : seulement {len(items)} article(s) extrait(s). "
              "Le site a peut-être changé de structure.", file=sys.stderr)
        # on n'écrase pas un bon flux existant avec du vide
        sys.exit(1)
    seen = load_seen()
    rss = build_rss(items, seen)
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_index(items))
    with open("seen.json", "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)
    print(f"OK : {len(items)} articles écrits dans feed.xml")


if __name__ == "__main__":
    main()
