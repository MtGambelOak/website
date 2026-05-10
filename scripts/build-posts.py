#!/usr/bin/env python3
"""
Scan app/blog/posts/*.md and write app/blog/posts.json.
Run this whenever you add or update a post.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "app" / "blog" / "posts"
OUTPUT = ROOT / "app" / "blog" / "posts.json"
WORDS_PER_MINUTE = 200


def git_dates(path: Path):
    try:
        log = subprocess.check_output(
            ["git", "log", "--follow", "--format=%aI", "--", str(path)],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip().splitlines()
        if not log:
            return None, None
        return log[-1], log[0]
    except subprocess.CalledProcessError:
        return None, None


def fs_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def extract_metadata(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    body = text[title_match.end():].strip() if title_match else text

    excerpt = ""
    for para in re.split(r'\n\n+', body):
        para = para.strip()
        if not para or para.startswith('#') or para.startswith('!') or para.startswith('$$'):
            continue
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', para)
        clean = re.sub(r'[*_`]{1,3}([^*_`]+)[*_`]{1,3}', r'\1', clean)
        clean = re.sub(r'\$[^$\n]+\$', '', clean)
        clean = ' '.join(clean.split())
        if clean:
            excerpt = clean[:220] + ('…' if len(clean) > 220 else '')
            break

    word_count = len(re.sub(r'\$\$[\s\S]+?\$\$|\$[^$\n]+\$|[#*_`\[\]()!]', ' ', text).split())
    reading_time = max(1, round(word_count / WORDS_PER_MINUTE))

    created_git, updated_git = git_dates(path)
    created = created_git or fs_date(path)
    updated = updated_git or fs_date(path)

    return {
        "slug": path.stem,
        "title": title,
        "excerpt": excerpt,
        "reading_time": reading_time,
        "created": created,
        "updated": updated,
    }


def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    posts = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta = extract_metadata(md_file)
        posts.append(meta)
        print(f"  {meta['slug']}: {meta['title']}")

    posts.sort(key=lambda p: p["created"], reverse=True)
    OUTPUT.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(posts)} post(s) to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
