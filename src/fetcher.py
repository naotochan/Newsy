"""ニュース取得モジュール — RSS フィードから記事を収集し本文を抽出する"""

import feedparser
import trafilatura
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source: str
    summary: str = ""
    content: Optional[str] = None


def _load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_rss(feed_url: str, source_name: str, max_items: int = 5) -> list[Article]:
    feed = feedparser.parse(feed_url)
    articles = []
    for entry in feed.entries[:max_items]:
        articles.append(Article(
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            source=source_name,
            summary=entry.get("summary", ""),
        ))
    return articles


def fetch_content(url: str, max_chars: int = 2000) -> Optional[str]:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text:
                return text[:max_chars]
    except Exception:
        pass
    return None


def fetch_all_news(config_path: str = "config/settings.yaml") -> list[Article]:
    config = _load_config(config_path)
    feeds = config.get("feeds", [])
    max_per_feed = config.get("max_articles_per_feed", 3)
    max_total = config.get("max_articles_total", 10)

    all_articles: list[Article] = []

    for feed_info in feeds:
        if len(all_articles) >= max_total:
            break
        try:
            articles = fetch_rss(feed_info["url"], feed_info["name"], max_per_feed)
            for article in articles:
                if len(all_articles) >= max_total:
                    break
                article.content = fetch_content(article.url)
                all_articles.append(article)
                print(f"  取得: {article.title[:60]}...")
        except Exception as e:
            print(f"  [警告] {feed_info['name']} の取得に失敗: {e}")

    return all_articles
