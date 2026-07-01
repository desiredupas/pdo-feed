#!/usr/bin/env python3
"""
Générateur de flux RSS pour le catalogue PDO de SHAPE (version 2).
Tourne sur les serveurs de GitHub (Actions) — rien à installer en local.

Nouveautés v2 :
  - récupère de façon fiable les DEUX pages du catalogue (retris + fusion) ;
  - ajoute l'IMAGE de chaque objet dans le flux (visible dans Feedly) ;
  - nettoie les titres (retire les mentions « - Ref 123 »).

Produit : feed.xml, index.html, seen.json
"""

import json
import re
import sys
import time
import datetime
import urllib.request

CATALOGUE_URLS = [
    "https://shape2day.com/our-community/recycling-centre/property-disposal-pdo-sale/catalogue",
    "https://shape2day.com/our-community/recycling-centre/property-disposal-pdo-sale/catalogue/page/2.aspx",
]

UA = "Mozilla/5.0 (compatible; PDO-Feed-Bot/2.0; +https://github.com/)"
EURO = "\u20ac"

# ── Récupération ────────────────────────────────────────────────────────────

def http_get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_markdown(url):
    """Passe par le relais Jina, qui renvoie un markdown propre (avec images)."""
    try:
        return http_get("https://r.jina.ai/" + url)
    except Exception as e:
        print(f"  jina KO ({url}) : {e}", file=sys.stderr)
        return None


def fetch_html(url):
    try:
        return http_get(url)
    except Exception as e:
        print(f"  html KO ({url}) : {e}", file=sys.stderr)
        return None

# ── Analyse ─────────────────────────────────────────────────────────────────

IMG_MAP_RE = re.compile(
    r"\[!\[[^\]]*\]\(([^)]+?\.(?:png|jpe?g|webp|gif))\)\]"
    r"\((https?://[^\s)]+/catalogue/[^\s)]+\.aspx)\)",
    re.I,
)

ITEM_RE = re.compile(
    r"###\s+\[([^\]]+)\]\((https?://[^\s)]+/catalogue/[^\s)]+\.aspx)\)(.*?)"
    r"(?=###\s+\[|\n##\s|\Z)",
    re.S,
)


def clean_title(t):
    t = re.sub(r"\s*[-\u2013\u2014]\s*Ref\.?\s*\d+\s*$", "", t, flags=re.I)
    return t.strip()


def parse_items_md(md):
    # carte image -> objet (le pouce cliquable pointe vers la même page)
    imgs = {}
    for m in IMG_MAP_RE.finditer(md):
        img = m.group(1).strip().replace(" ", "%20")
        imgs.setdefault(m.group(2).strip(), img)
    items = []
    for m in ITEM_RE.finditer(md):
        title = clean_title(m.group(1))
        url = m.group(2).strip()
        if "/page/" in url:
            continue
        block = m.group(3)
        am = re.search(r"Available:\**\s*(\d+)", block, re.I)
        pm = re.search(r"\n\s*([^\n]*" + EURO + r"[^\n]*)\n", block)
        price = ""
        if pm:
            price = re.sub(r"^\s*\d+\s+", "", pm.group(1).strip()).strip()
        items.append({
            "title": title, "url": url,
            "available": am.group(1) if am else "",
            "price": price, "image": imgs.get(url, ""),
        })
    return items


def parse_items_html(html):
    """Secours si le markdown manque. Nécessite beautifulsoup4."""
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for h in soup.find_all("h3"):
        a = h.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if "/catalogue/" not in href or not href.endswith(".aspx") or "/page/" in href:
            continue
        title = clean_title(a.get_text(strip=True))
        if not title:
            continue
        url = href if href.startswith("http") else \
            "https://shape2day.com" + ("" if href.startswith("/") else "/") + href
        ctx, img = "", ""
        node = h
        for _ in range(6):
            node = node.find_next_sibling()
            if node is None or getattr(node, "name", None) == "h3":
                break
            ctx += " " + node.get_text(" ", strip=True)
        prev = h
        for _ in range(4):
            prev = prev.find_previous_sibling()
            if prev is None:
                break
            im = prev.find("img") if hasattr(prev, "find") else None
            if im and im.get("src"):
                img = im["src"].replace(" ", "%20")
                break
        am = re.search(r"Available:?\s*(\d+)", ctx, re.I)
        pm = re.search(r"(\d+L\s*for\s*\d+" + EURO + r"|\d+" + EURO + r")", ctx)
        out.append({
            "title": title, "url": url,
            "available": am.group(1) if am else "",
            "price": pm.group(1) if pm else "", "image": img,
        })
    return out


def gather(url):
    """Récupère une page en combinant Jina (avec retris) et l'accès direct."""
    found = {}
    for attempt in range(3):
        md = fetch_markdown(url)
        if md:
            for it in parse_items_md(md):
                found.setdefault(it["url"], it)
        if len(found) >= 5:
            break
        time.sleep(2)
    html = fetch_html(url)
    if html:
        for it in parse_items_html(html):
            cur = found.get(it["url"])
            if cur is None:
                found[it["url"]] = it
            elif not cur.get("image") and it.get("image"):
                cur["image"] = it["image"]
    return found


def collect():
    all_items = {}
    for url in CATALOGUE_URLS:
        for u, it in gather(url).items():
            cur = all_items.get(u)
            if cur is None:
                all_items[u] = it
            elif not cur.get("image") and it.get("image"):
                cur["image"] = it["image"]
        time.sleep(2)  # évite de se faire limiter entre les deux pages
    return list(all_items.values())

# ── Écriture ────────────────────────────────────────────────────────────────

def load_seen():
    try:
        with open("seen.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "webp": "image/webp", "gif": "image/gif"}


def item_xml(it, pub):
    title = it["title"] + (f" \u2014 {it['price']}" if it["price"] else "")
    bits = []
    if it["price"]:
        bits.append("Prix : " + it["price"])
    if it["available"]:
        bits.append("Disponibles : " + it["available"])
    info = ". ".join(bits)
    parts = [
        "<item>",
        f"<title>{esc(title)}</title>",
        f"<link>{esc(it['url'])}</link>",
        f'<guid isPermaLink="true">{esc(it["url"])}</guid>',
    ]
    if it["image"]:
        ext = it["image"].rsplit(".", 1)[-1].lower()
        mime = MIME.get(ext, "image/png")
        parts.append(
            f"<description><![CDATA[<img src=\"{it['image']}\" "
            f"alt=\"{it['title']}\" /><p>{info}</p>]]></description>")
        parts.append(f'<enclosure url="{esc(it["image"])}" type="{mime}" length="0" />')
        parts.append(f'<media:content url="{esc(it["image"])}" medium="image" />')
        parts.append(f'<media:thumbnail url="{esc(it["image"])}" />')
    else:
        parts.append(f"<description>{esc(info)}</description>")
    parts.append(f"<pubDate>{pub}</pubDate>")
    parts.append("</item>")
    return "\n".join(parts)


def build_rss(items, seen):
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    for it in items:
        first = seen.get(it["url"])
        if not first:
            first = now.isoformat()
            seen[it["url"]] = first
        it["_pub"] = first
    items.sort(key=lambda x: x["_pub"], reverse=True)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>',
        "<title>SHAPE PDO \u2014 Catalogue</title>",
        f"<link>{esc(CATALOGUE_URLS[0])}</link>",
        "<description>Objets en vente au Property Disposal Office de SHAPE. "
        "Un nouvel article = une nouvelle entrée.</description>",
        "<language>en</language>",
        f"<lastBuildDate>{now_str}</lastBuildDate>",
    ]
    for it in items:
        try:
            pub = datetime.datetime.fromisoformat(it["_pub"]).strftime(
                "%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub = now_str
        out.append(item_xml(it, pub))
    out.append("</channel></rss>")
    return "\n".join(out)


def build_index(items):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    cards = "\n".join(
        f'<li><a href="{esc(it["url"])}">'
        f'{("<img src=" + chr(34) + it["image"] + chr(34) + ">") if it["image"] else ""}'
        f'<span class="t">{esc(it["title"])}</span></a>'
        f'<span class="p">{esc(it["price"])}'
        f'{" · dispo " + esc(it["available"]) if it["available"] else ""}</span></li>'
        for it in items
    )
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHAPE PDO — Catalogue</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;color:#16243f}}
h1{{font-size:1.4rem}} .sub{{color:#667;font-size:.85rem;margin-bottom:1.2rem}}
.feed{{display:inline-block;background:#16243f;color:#fff;text-decoration:none;padding:.5rem .9rem;border-radius:8px;font-size:.9rem;margin-bottom:1.5rem}}
ul{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:1rem}}
li{{border:1px solid #eee;border-radius:10px;padding:.6rem;display:flex;flex-direction:column;gap:.35rem}}
li a{{display:flex;flex-direction:column;gap:.4rem;text-decoration:none;color:#16243f}}
li img{{width:100%;height:110px;object-fit:contain;background:#fafafa;border-radius:6px}}
.t{{font-weight:600;font-size:.9rem}} .p{{color:#889;font-size:.8rem;font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>SHAPE PDO — Catalogue</h1>
<div class="sub">{len(items)} articles · mis à jour le {now}</div>
<a class="feed" href="feed.xml">📡 feed.xml — colle cette URL dans Feedly</a>
<ul>{cards}</ul>
</body></html>"""


def main():
    items = collect()
    print(f"Articles récupérés : {len(items)} "
          f"(dont {sum(1 for i in items if i['image'])} avec image)")
    if len(items) < 5:
        print("ÉCHEC : trop peu d'articles, on ne remplace pas le flux existant.",
              file=sys.stderr)
        sys.exit(1)
    seen = load_seen()
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(build_rss(items, seen))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_index(items))
    with open("seen.json", "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)
    print("OK : feed.xml, index.html et seen.json écrits.")


if __name__ == "__main__":
    main()
