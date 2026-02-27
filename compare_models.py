#!/usr/bin/env python3
"""モデル精度比較スクリプト — 同一記事で複数モデルの脚本を比較する

使い方:
  # 1回目: 記事取得 + 現在のモデルで生成
  python compare_models.py

  # LM Studio でモデル切り替え後、2回目: 同じ記事で別モデルの生成を追加
  python compare_models.py --dir output/compare_YYYYMMDD_HHMM
"""

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.fetcher import fetch_rss, fetch_content, _load_config, Article
from src.script import generate_script


def fetch_articles(config_path: str, max_articles: int) -> list[Article]:
    """seen_urls.txt を更新せずに記事を取得する"""
    config = _load_config(config_path)
    feeds = config.get("feeds", [])
    max_per_feed = config.get("max_articles_per_feed", 3)
    articles = []
    for feed_info in feeds:
        if len(articles) >= max_articles:
            break
        try:
            fetched = fetch_rss(feed_info["url"], feed_info["name"], max_per_feed)
            for article in fetched:
                if len(articles) >= max_articles:
                    break
                article.content = fetch_content(article.url)
                articles.append(article)
                print(f"  取得: {article.title[:60]}...")
        except Exception as e:
            print(f"  [警告] {feed_info['name']} の取得に失敗: {e}")
    return articles


def save_articles(articles: list[Article], out_dir: Path) -> None:
    data = [asdict(a) for a in articles]
    (out_dir / "articles.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sources = "\n\n".join(
        f"【{i}】{a.title}\n出典: {a.source}\nURL: {a.url}"
        for i, a in enumerate(articles, 1)
    )
    (out_dir / "sources.md").write_text(sources, encoding="utf-8")


def load_articles(out_dir: Path) -> list[Article]:
    data = json.loads((out_dir / "articles.json").read_text(encoding="utf-8"))
    return [Article(**d) for d in data]


def run_generation(articles: list[Article], config_path: str, out_dir: Path) -> None:
    model = os.getenv("LM_STUDIO_MODEL", "unknown-model")
    label = model.replace("/", "_")
    out_path = out_dir / f"{label}.txt"

    if out_path.exists():
        print(f"既存のファイルがあります: {out_path}")
        print("スキップします（別のモデルに切り替えてから実行してください）")
        return

    print(f"モデル: {model}")
    script = generate_script(articles, config_path=config_path)
    out_path.write_text(script, encoding="utf-8")
    print(f"保存: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", help="既存の比較フォルダを指定（2回目以降）")
    args = parser.parse_args()

    config_path = "config/settings.yaml"
    config = _load_config(config_path)
    max_articles = config.get("max_articles_per_episode", 5)

    if args.dir:
        out_dir = Path(args.dir)
        if not out_dir.exists():
            print(f"フォルダが見つかりません: {out_dir}")
            return
        print(f"既存フォルダから記事を読み込み中: {out_dir}")
        articles = load_articles(out_dir)
        print(f"記事数: {len(articles)} 件\n")
    else:
        out_dir = Path("output") / f"compare_{datetime.now().strftime('%Y%m%d_%H%M')}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"記事を取得中（最大 {max_articles} 件）...")
        articles = fetch_articles(config_path, max_articles)
        print(f"取得完了: {len(articles)} 件")
        save_articles(articles, out_dir)
        print(f"記事を保存しました: {out_dir}/articles.json\n")

    run_generation(articles, config_path, out_dir)

    print(f"\n比較フォルダ: {out_dir}/")
    txts = list(out_dir.glob("*.txt"))
    for f in txts:
        print(f"  {f.name}")
    if len(txts) < 2:
        model = os.getenv("LM_STUDIO_MODEL", "")
        label = model.replace("/", "_")
        print(f"\n次のモデルに切り替えて以下を実行:")
        print(f"  python compare_models.py --dir {out_dir}")


if __name__ == "__main__":
    main()
