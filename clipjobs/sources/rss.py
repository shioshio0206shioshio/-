"""RSS / Atom フィード（求人サイトが公式に提供しているもの）から募集を取り込む。"""

from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET

from ..models import Job

USER_AGENT = "clipjobs/0.1 (personal job alert reader)"
_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return html.unescape(_TAG.sub(" ", text or "")).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(el: ET.Element, *names: str) -> str:
    for child in el:
        if _local(child.tag) in names:
            if _local(child.tag) == "link" and child.get("href"):
                return child.get("href", "")
            return (child.text or "").strip()
    return ""


def parse_feed(xml_text: str, source: str) -> list[Job]:
    root = ET.fromstring(xml_text)
    items = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    jobs = []
    for item in items:
        title = strip_html(_child_text(item, "title"))
        if not title:
            continue
        jobs.append(
            Job(
                source=source,
                title=title,
                url=_child_text(item, "link", "guid", "id"),
                body=strip_html(_child_text(item, "description", "summary", "content")),
                posted_at=_child_text(item, "pubDate", "published", "updated"),
            )
        )
    return jobs


def fetch(feeds: list[dict], timeout: float = 20) -> list[Job]:
    jobs: list[Job] = []
    for feed in feeds:
        req = urllib.request.Request(feed["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                xml_text = resp.read().decode("utf-8", errors="replace")
            jobs.extend(parse_feed(xml_text, feed.get("name", "rss")))
        except Exception as e:  # 1つのフィードが落ちても他は続行
            print(f"[rss] {feed.get('name', feed['url'])}: 取得失敗 ({e})")
    return jobs
