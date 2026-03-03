"""パイプライン — ニュース取得から音声生成までを一括実行する"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from .fetcher import fetch_all_news, Article
from .script import generate_script, parse_script, select_articles
from .tts import check_tts, create_audio


def _save_sources(articles: list[Article], path: str, date_str: str, ep: int) -> None:
    lines = [f"# Newsy ソース記事メモ — EP{ep} ({date_str})\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"## {i}. {a.title}")
        lines.append(f"- **出典**: {a.source}")
        lines.append(f"- **URL**: {a.url}")
        body = a.content or a.summary or ""
        if body:
            snippet = body[:300].replace("\n", " ")
            lines.append(f"- **概要**: {snippet}…")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _extract_summary(script_text: str) -> str:
    """台本先頭の「概要: ...」行を抽出する"""
    for raw in script_text.splitlines():
        raw = raw.strip()
        if raw.startswith("概要:"):
            return raw[len("概要:"):].strip()
    return ""


def _fmt_timestamp(seconds: float) -> str:
    """秒数を MM:SS 形式に変換する"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _save_readme(
    articles: list[Article],
    run_dir: str,
    date_str: str,
    summary: str = "",
) -> None:
    dt = datetime.strptime(date_str, "%Y%m%d_%H%M")
    lines = [
        f"# Newsy — {dt.strftime('%Y年%m月%d日 %H:%M')}",
        f"\n{len(articles)} 記事 · `newsy.mp3`\n",
    ]
    if summary:
        lines.append(f"> {summary}\n")
    for a in articles:
        lines.append(f"- [{a.title}]({a.url})  _{a.source}_")
    lines.append("")
    with open(os.path.join(run_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _parse_stock_file(stock_path: str) -> list[dict]:
    """ストックファイルをパースして記事情報のリストを返す"""
    entries: list[dict] = []
    if not os.path.exists(stock_path):
        return entries

    current: dict = {}
    with open(stock_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("## "):
                if current:
                    entries.append(current)
                current = {"title": line[3:], "source": "", "url": "", "date": "", "summary": ""}
            elif line.startswith("- 出典: "):
                current["source"] = line[len("- 出典: "):]
            elif line.startswith("- URL: "):
                current["url"] = line[len("- URL: "):]
            elif line.startswith("- 取得日: "):
                current["date"] = line[len("- 取得日: "):]
            elif line.startswith("- 概要: "):
                current["summary"] = line[len("- 概要: "):]
        if current and current.get("url"):
            entries.append(current)

    return entries


def _load_stock_articles(output_dir: str) -> tuple[list[Article], list[dict]]:
    """ストック記事を読み込み、有効な Article リストと期限切れエントリを返す"""
    stock_path = os.path.join(output_dir, "stock_articles.md")
    entries = _parse_stock_file(stock_path)
    if not entries:
        return [], []

    today = datetime.now().date()
    cutoff = today - timedelta(days=14)

    valid: list[Article] = []
    expired: list[dict] = []
    for e in entries:
        try:
            entry_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            entry_date = today  # 日付なしは新しいとみなす

        if entry_date < cutoff:
            expired.append(e)
        else:
            valid.append(Article(
                title=e["title"],
                url=e["url"],
                source=e["source"],
                summary=e.get("summary", ""),
            ))

    return valid, expired


def _save_stock_articles(
    all_articles: list[Article],
    selected: list[Article],
    output_dir: str,
    expired: list[dict] | None = None,
) -> None:
    """選定されなかった記事をストックファイルに書き直す（期限切れは廃棄へ）"""
    selected_urls = {a.url for a in selected}
    stock = [a for a in all_articles if a.url not in selected_urls]

    stock_path = os.path.join(output_dir, "stock_articles.md")

    # 廃棄記事を保存
    if expired:
        expired_path = os.path.join(output_dir, "expired_articles.md")
        existing_expired_urls: set[str] = set()
        if os.path.exists(expired_path):
            with open(expired_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("- URL: "):
                        existing_expired_urls.add(line.strip()[len("- URL: "):])
        new_expired = [e for e in expired if e["url"] not in existing_expired_urls]
        if new_expired:
            with open(expired_path, "a", encoding="utf-8") as f:
                if not existing_expired_urls:
                    f.write("# 廃棄記事（2週間経過）\n\n")
                for e in new_expired:
                    f.write(f"## {e['title']}\n")
                    f.write(f"- 出典: {e['source']}\n")
                    f.write(f"- URL: {e['url']}\n")
                    f.write(f"- 取得日: {e['date']}\n")
                    f.write(f"- 廃棄日: {datetime.now().strftime('%Y-%m-%d')}\n")
                    f.write("\n")
            print(f"  廃棄記事 {len(new_expired)} 件 → {expired_path}")

    if not stock:
        # ストックが空ならファイルを空にする
        if os.path.exists(stock_path):
            os.remove(stock_path)
        return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # 既存ストックから残留分を保持（選定されたものは除外）
    existing = _parse_stock_file(stock_path)
    existing_urls = {e["url"] for e in existing}
    # 既存のうち選定されなかったものを保持
    kept = [e for e in existing if e["url"] not in selected_urls]
    kept_urls = {e["url"] for e in kept}

    # 新規ストック（今回取得分で選定されなかったもの）
    new_stock = [a for a in stock if a.url not in kept_urls and a.url not in existing_urls]

    # ファイルを書き直す
    with open(stock_path, "w", encoding="utf-8") as f:
        f.write("# ストック記事\n\n")
        for e in kept:
            f.write(f"## {e['title']}\n")
            f.write(f"- 出典: {e['source']}\n")
            f.write(f"- URL: {e['url']}\n")
            f.write(f"- 取得日: {e['date']}\n")
            if e.get("summary"):
                f.write(f"- 概要: {e['summary']}\n")
            f.write("\n")
        for a in new_stock:
            snippet = (a.content or a.summary or "")[:150].replace("\n", " ")
            f.write(f"## {a.title}\n")
            f.write(f"- 出典: {a.source}\n")
            f.write(f"- URL: {a.url}\n")
            f.write(f"- 取得日: {date_str}\n")
            if snippet:
                f.write(f"- 概要: {snippet}\n")
            f.write("\n")

    total = len(kept) + len(new_stock)
    print(f"  ストック記事 {total} 件（新規 {len(new_stock)}）→ {stock_path}")


def _load_articles_from_sources(sources_path: str) -> list[Article]:
    """sources.md から記事情報を復元する"""
    import re
    articles = []
    with open(sources_path, encoding="utf-8") as f:
        text = f.read()
    for block in re.split(r"(?=## \d+\.)", text):
        m_title = re.match(r"## \d+\.\s+(.+)", block)
        if not m_title:
            continue
        title = m_title.group(1)
        m_source = re.search(r"\*\*出典\*\*:\s*(.+)", block)
        m_url = re.search(r"\*\*URL\*\*:\s*(.+)", block)
        source = m_source.group(1).strip() if m_source else ""
        url = m_url.group(1).strip() if m_url else ""
        articles.append(Article(title=title, url=url, source=source, summary=""))
    return articles


def resume(
    folder_name: str,
    config_path: str = "config/settings.yaml",
    output_dir: str = "output",
) -> list[str]:
    """既存の script.txt から音声生成を再実行する"""
    run_dir = os.path.join(output_dir, folder_name)
    if not os.path.isdir(run_dir):
        print(f"  [エラー] フォルダが見つかりません: {run_dir}")
        return []

    print("=" * 50)
    print("  Newsy - 途中再開（音声生成のみ）")
    print("=" * 50)

    if not check_tts(config_path):
        print("\n[エラー] TTS が利用できません。")
        return []

    # script.txt を探す（新形式 / 旧形式）
    script_path = os.path.join(run_dir, "script.txt")
    if not os.path.exists(script_path):
        # 旧形式: script_part1.txt, script_part2.txt, ...
        part_scripts = sorted(Path(run_dir).glob("script_part*.txt"))
        if not part_scripts:
            print(f"  [エラー] 脚本が見つかりません: {run_dir}")
            return []
        script_text = "\n".join(p.read_text(encoding="utf-8") for p in part_scripts)
        print(f"  脚本読み込み: {len(part_scripts)} パートファイル")
    else:
        script_text = Path(script_path).read_text(encoding="utf-8")
        print(f"  脚本読み込み: {script_path}")

    lines = parse_script(script_text, config_path)
    summary = _extract_summary(script_text)

    if not lines:
        print("  [エラー] 脚本のパースに失敗しました。")
        return []
    print(f"  脚本 {len(lines)} 行")

    # 音声生成
    print(f"\n音声生成中（{len(lines)} 行）...")
    mp3_path = os.path.join(run_dir, "newsy.mp3")
    mp3_path, _ = create_audio(lines, config_path, output_path=mp3_path)
    print(f"  音声 → {mp3_path}")

    # sources から記事情報を復元して README 生成
    sources_path = os.path.join(run_dir, "sources.md")
    if not os.path.exists(sources_path):
        part_sources = sorted(Path(run_dir).glob("sources_part*.md"))
        if part_sources:
            sources_path = str(part_sources[0])

    articles = _load_articles_from_sources(sources_path) if os.path.exists(sources_path) else []
    _save_readme(articles, run_dir, folder_name, summary)

    print(f"\n{'=' * 50}")
    print(f"  完了！ {mp3_path}")
    print("=" * 50)

    return [mp3_path]


def run(config_path: str = "config/settings.yaml", output_dir: str = "output") -> list[str]:
    print("=" * 50)
    print("  Newsy - AI ラジオ番組生成")
    print("=" * 50)

    if not check_tts(config_path):
        print("\n[エラー] TTS が利用できません。")
        print("  ElevenLabs: ELEVEN_API_KEY を設定してください。")
        print("  VOICEVOX: サーバーを起動してください。")
        return []

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    max_select = cfg.get("selected_articles", 3)

    # 1. ニュース取得 + ストック記事読み込み
    print("\n[1/4] ニュース取得中...")
    fresh_articles = fetch_all_news(config_path)
    stock_articles, expired = _load_stock_articles(output_dir)
    if expired:
        print(f"  期限切れストック {len(expired)} 件 → 廃棄")
    if stock_articles:
        print(f"  ストック記事 {len(stock_articles)} 件を候補に追加")

    # 新規取得 + ストックを合わせて候補にする（新規を優先表示）
    all_articles = (fresh_articles or []) + stock_articles
    if not all_articles:
        print("  新着記事がありませんでした。スキップします。")
        return ["skip"]
    print(f"  候補記事 {len(all_articles)} 件（新規 {len(fresh_articles or [])} + ストック {len(stock_articles)}）")

    # 2. 記事選定（LLM で重要度判定）
    print(f"\n[2/4] 記事選定中（上限 {max_select} 本）...")
    selected = select_articles(all_articles, max_select=max_select, config_path=config_path)
    print(f"  選定記事:")
    for a in selected:
        print(f"    - [{a.source}] {a.title}")

    # ストック記事を更新（選定されなかった記事を保存、期限切れは廃棄）
    _save_stock_articles(all_articles, selected, output_dir, expired=expired)

    # 出力フォルダ作成（記事選定後）
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = os.path.join(output_dir, date_str)
    Path(run_dir).mkdir(parents=True, exist_ok=True)

    # 3. 脚本生成（1パート）
    print(f"\n[3/4] 脚本生成中（{len(selected)} 記事）...")
    script_text = generate_script(selected, config_path, ep=1, total_eps=1)
    lines = parse_script(script_text, config_path)
    summary = _extract_summary(script_text)

    script_path = os.path.join(run_dir, "script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_text)

    sources_path = os.path.join(run_dir, "sources.md")
    _save_sources(selected, sources_path, date_str, ep=1)

    print(f"  脚本 {len(lines)} 行 → {script_path}")
    print(f"  ソース → {sources_path}")

    if not lines:
        print("  [エラー] 脚本の生成に失敗しました。")
        return []

    # 4. 音声生成
    print(f"\n[4/4] 音声生成中（{len(lines)} 行）...")
    mp3_path = os.path.join(run_dir, "newsy.mp3")
    mp3_path, _ = create_audio(lines, config_path, output_path=mp3_path)
    print(f"  音声 → {mp3_path}")

    _save_readme(selected, run_dir, date_str, summary)

    print(f"\n{'=' * 50}")
    print(f"  完了！ {mp3_path}")
    print("=" * 50)

    return [mp3_path]
