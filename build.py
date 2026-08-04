#!/usr/bin/env python3
"""
Build the site: render Jinja2 templates → dist/
Run: python build.py
Then serve: python3 -m http.server 8080 --directory dist
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "app"
TEMPLATES_DIR = SRC / "templates"
STATIC_DIR = SRC / "static"
POSTS_DIR = SRC / "blog" / "posts"
POSTS_JSON = SRC / "blog" / "posts.json"
DIST = ROOT / "dist"
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://lpearce.dev").rstrip("/")
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

BUILD_TIME = datetime.now(timezone.utc)
BUILD_VERSION = BUILD_TIME.strftime("%Y%m%d%H%M%S")
CURRENT_YEAR = BUILD_TIME.year


# ── Helpers ──────────────────────────────────────────────────────────────────

def git_lastmod(*paths) -> str | None:
    normalized = [str(Path(p).relative_to(ROOT)) for p in paths if Path(p).exists()]
    if not normalized:
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", *normalized],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def to_date(iso: str | None) -> str:
    if not iso:
        return BUILD_TIME.date().isoformat()
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return iso[:10]


def format_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return iso[:10]


def add_sitemap_entry(entries, url_path: str, lastmod: str | None = None):
    entries.append({"loc": f"{SITE_BASE_URL}{url_path}", "lastmod": lastmod})


def write_sitemap(entries):
    urlset = Element("urlset", attrib={"xmlns": SITEMAP_NS})
    for e in entries:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = e["loc"]
        if e.get("lastmod"):
            SubElement(url_el, "lastmod").text = e["lastmod"]
    ElementTree(urlset).write(DIST / "sitemap.xml", encoding="utf-8", xml_declaration=True)


def write_robots():
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n"
    )


# ── Load posts ────────────────────────────────────────────────────────────────

posts = []
if POSTS_JSON.exists():
    posts = json.loads(POSTS_JSON.read_text(encoding="utf-8"))


# ── Setup ─────────────────────────────────────────────────────────────────────

if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir()

shutil.copytree(STATIC_DIR, DIST / "static")

# Copy markdown source files so post.html can fetch them client-side
dest_posts = DIST / "blog" / "posts"
dest_posts.mkdir(parents=True, exist_ok=True)
for md in POSTS_DIR.glob("*.md"):
    shutil.copy(md, dest_posts / md.name)

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
env.filters["format_date"] = format_date
env.globals.update(
    site_base_url=SITE_BASE_URL,
    build_version=BUILD_VERSION,
    current_year=CURRENT_YEAR,
)

sitemap_entries = []


def render(template_name: str, output: Path, context: dict, sitemap_url: str | None = None, lastmod_sources=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    tpl = env.get_template(template_name)
    output.write_text(tpl.render(**context), encoding="utf-8")
    if sitemap_url:
        lastmod = to_date(git_lastmod(*(lastmod_sources or [])) or None)
        add_sitemap_entry(sitemap_entries, sitemap_url, lastmod)


# ── Pages ─────────────────────────────────────────────────────────────────────

render("index.html", DIST / "index.html",
       {"active_page": "home", "canonical_url": f"{SITE_BASE_URL}/"},
       sitemap_url="/", lastmod_sources=[TEMPLATES_DIR / "index.html"])

render("blog.html", DIST / "blog" / "index.html",
       {"active_page": "blog", "posts": posts, "canonical_url": f"{SITE_BASE_URL}/blog/"},
       sitemap_url="/blog/", lastmod_sources=[TEMPLATES_DIR / "blog.html", POSTS_JSON])

render("projects.html", DIST / "projects" / "index.html",
       {"active_page": "projects", "canonical_url": f"{SITE_BASE_URL}/projects/"},
       sitemap_url="/projects/", lastmod_sources=[TEMPLATES_DIR / "projects.html"])

render("resume.html", DIST / "resume" / "index.html",
       {"active_page": "resume", "canonical_url": f"{SITE_BASE_URL}/resume/"},
       sitemap_url="/resume/", lastmod_sources=[TEMPLATES_DIR / "resume.html"])

render("404.html", DIST / "404.html",
       {"active_page": "", "canonical_url": f"{SITE_BASE_URL}/404.html"})

for post in posts:
    slug = post["slug"]
    render("post.html", DIST / "blog" / slug / "index.html",
           {"active_page": "blog", "post": post, "canonical_url": f"{SITE_BASE_URL}/blog/{slug}/"},
           sitemap_url=f"/blog/{slug}/", lastmod_sources=[POSTS_DIR / f"{slug}.md"])

# ── Sitemap + robots ──────────────────────────────────────────────────────────

write_sitemap(sitemap_entries)
write_robots()

print(f"Built {len(posts)} post(s) → dist/  [{BUILD_VERSION}]")
