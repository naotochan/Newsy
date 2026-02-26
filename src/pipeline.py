"""パイプライン — ニュース取得から音声生成までを一括実行する"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .fetcher import fetch_all_news, Article
from .script import generate_script, parse_script
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
    batches: list[list[Article]],
    run_dir: str,
    date_str: str,
    summaries: dict[int, str] | None = None,
    part_timestamps: list[float] | None = None,
) -> None:
    dt = datetime.strptime(date_str, "%Y%m%d_%H%M")
    total_articles = sum(len(b) for b in batches)
    lines = [
        f"# Newsy — {dt.strftime('%Y年%m月%d日 %H:%M')}",
        f"\n{total_articles} 記事 · `newsy.mp3`\n",
    ]
    for part, batch in enumerate(batches, 1):
        ts = ""
        if part_timestamps and part - 1 < len(part_timestamps):
            ts = f" [{_fmt_timestamp(part_timestamps[part - 1])}]"
        lines.append(f"## パート{part}{ts}")
        if summaries and part in summaries:
            lines.append(f"\n> {summaries[part]}\n")
        for a in batch:
            lines.append(f"- [{a.title}]({a.url})  _{a.source}_")
        lines.append("")
    with open(os.path.join(run_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _generate_script_batch(
    articles: list[Article],
    part: int,
    total_parts: int,
    date_str: str,
    output_dir: str,
    config_path: str,
) -> tuple[list[dict], str]:
    """バッチの脚本を生成し (parsed_lines, summary) を返す"""
    print(f"\n--- パート{part}/{total_parts} ({len(articles)} 記事) ---")

    # 脚本生成
    script_text = generate_script(articles, config_path, ep=part, total_eps=total_parts)
    lines = parse_script(script_text, config_path)
    summary = _extract_summary(script_text)

    script_path = os.path.join(output_dir, f"script_part{part}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_text)

    sources_path = os.path.join(output_dir, f"sources_part{part}.md")
    _save_sources(articles, sources_path, date_str, part)

    print(f"  脚本 {len(lines)} 行 → {script_path}")
    print(f"  ソース → {sources_path}")

    if not lines:
        print("  [警告] 脚本のパースに失敗しました。スキップします。")

    return lines, summary


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
    articles_per_ep = cfg.get("max_articles_per_episode", 5)

    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = os.path.join(output_dir, date_str)
    Path(run_dir).mkdir(parents=True, exist_ok=True)

    # 1. ニュース取得
    print("\n[1/3] ニュース取得中...")
    articles = fetch_all_news(config_path)
    if not articles:
        print("  [エラー] 記事を取得できませんでした。")
        return []
    print(f"  {len(articles)} 件の記事を取得しました。")

    # 2 & 3. エピソードごとに脚本生成 → 音声生成
    min_articles_per_ep = cfg.get("min_articles_per_episode", 3)
    batches = [articles[i:i + articles_per_ep] for i in range(0, len(articles), articles_per_ep)]
    # 最後のバッチが少なすぎる場合、前のバッチにまとめる
    if len(batches) >= 2 and len(batches[-1]) < min_articles_per_ep:
        batches[-2].extend(batches[-1])
        batches.pop()
    total_parts = len(batches)
    print(f"\n[2/3] 脚本生成中（{total_parts} パート × 最大 {articles_per_ep} 記事）...")

    all_lines: list[dict] = []
    part_line_counts: list[int] = []
    summaries: dict[int, str] = {}
    for part, batch in enumerate(batches, 1):
        lines, summary = _generate_script_batch(
            batch, part, total_parts, date_str, run_dir, config_path
        )
        all_lines.extend(lines)
        part_line_counts.append(len(lines))
        if summary:
            summaries[part] = summary

    if not all_lines:
        print("  [エラー] 脚本の生成に失敗しました。")
        return []

    # 全パートをまとめて 1 つの MP3 に
    print(f"\n[3/3] 音声生成中（{len(all_lines)} 行）...")
    mp3_path = os.path.join(run_dir, "newsy.mp3")
    mp3_path, part_timestamps = create_audio(
        all_lines, config_path, output_path=mp3_path, part_line_counts=part_line_counts
    )
    print(f"  音声 → {mp3_path}")

    _save_readme(batches, run_dir, date_str, summaries, part_timestamps)

    print(f"\n{'=' * 50}")
    print(f"  完了！ {mp3_path}")
    print("=" * 50)

    return [mp3_path]
