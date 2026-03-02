#!/usr/bin/env python3
"""output/ から docs/ に静的サイトを生成する（GitHub Pages 用）"""

import html as html_mod
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"

HTML = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Newsy</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #0f0f0f; color: #e0e0e0; line-height: 1.6;
          padding: 20px 16px; max-width: 640px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 24px; color: #fff; font-weight: 700;
        letter-spacing: 0.02em; }}
  h2 {{ font-size: 1.15rem; color: #fff; margin-bottom: 6px; font-weight: 600; }}
  .latest {{ margin-bottom: 32px; }}
  .latest .date {{ font-size: 1.1rem; font-weight: 700; color: #4a9eff; margin-bottom: 10px; }}
  .latest audio {{ width: 100%; border-radius: 8px; margin-bottom: 12px; }}
  .latest .summary {{ font-size: 0.9rem; color: #b0b0b0; line-height: 1.7; margin-bottom: 14px; }}
  .ep {{ background: #1c1c1e; border-radius: 14px; padding: 18px;
         margin-bottom: 12px; border: 1px solid #2a2a2a; }}
  .ep[data-time] {{ cursor: pointer; }}
  .ep[data-time]:hover {{ background: #242426; border-color: #3a3a3c; }}
  .ep-title {{ font-size: 0.92rem; font-weight: 700; color: #4a9eff; margin-bottom: 8px; }}
  .ep-summary {{ font-size: 0.85rem; color: #b0b0b0; line-height: 1.6; margin-bottom: 12px; }}
  .ep-time {{ font-size: 0.78rem; color: #4a9eff; font-weight: 600;
              margin-left: 8px; font-variant-numeric: tabular-nums; }}
  audio {{ width: 100%; border-radius: 8px; }}
  details {{ margin-top: 12px; }}
  summary {{ font-size: 0.82rem; color: #a0a0a0; cursor: pointer; padding: 6px 0;
             transition: color 0.2s; }}
  summary:hover {{ color: #d0d0d0; }}
  summary:focus-visible {{ outline: 2px solid #4a9eff; outline-offset: 2px; border-radius: 4px; }}
  .sources {{ list-style: none; padding: 0; margin-top: 8px; }}
  .sources li {{ font-size: 0.82rem; line-height: 1.6; padding: 8px 0;
                 border-bottom: 1px solid #333; }}
  .sources li:last-child {{ border-bottom: none; }}
  .sources a {{ color: #6ab0ff; text-decoration: none; transition: color 0.2s; }}
  .sources a:hover {{ color: #8ec5ff; text-decoration: underline; }}
  .sources a:focus-visible {{ outline: 2px solid #4a9eff; outline-offset: 2px; border-radius: 2px; }}
  .sources .src-site {{ color: #777; font-size: 0.75rem; margin-top: 2px; }}
  .archive {{ margin-top: 32px; }}
  .archive h2 {{ margin-bottom: 14px; }}
  .archive-item {{ background: #1c1c1e; border-radius: 14px; border: 1px solid #2a2a2a;
                   margin-bottom: 8px; }}
  .archive-item summary {{ display: flex; align-items: center; gap: 10px;
                           padding: 14px 18px; font-size: 0.9rem; color: #e0e0e0; }}
  .archive-item summary::-webkit-details-marker {{ display: none; }}
  .archive-item summary::before {{ content: "▸"; color: #4a9eff; font-size: 0.8rem;
                                   transition: transform 0.2s; }}
  .archive-item[open] summary::before {{ transform: rotate(90deg); }}
  .archive-item .archive-date {{ font-weight: 600; color: #4a9eff; }}
  .archive-item .archive-meta {{ font-size: 0.78rem; color: #777; }}
  .archive-item .archive-body {{ padding: 0 18px 18px; }}
  .archive-item audio {{ width: 100%; border-radius: 8px; margin-bottom: 10px; }}
  @media (max-width: 480px) {{
    body {{ padding: 14px 12px; }}
    h1 {{ font-size: 1.35rem; }}
    .ep {{ padding: 14px; border-radius: 10px; }}
    .archive-item summary {{ padding: 12px 14px; }}
    .archive-item .archive-body {{ padding: 0 14px 14px; }}
  }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def parse_readme(readme_path: Path):
    """README.md から情報を抽出する（新旧フォーマット両対応）"""
    text = readme_path.read_text(encoding="utf-8")

    # 新形式: "20 記事 · `newsy.mp3`"
    m_new = re.search(r"(\d+) 記事 · `(newsy\.mp3)`", text)
    # 旧形式: "全 N エピソード / M 記事"
    m_old = re.search(r"全 (\d+) エピソード / (\d+) 記事", text)

    if m_new:
        total_articles = int(m_new.group(1))
        mp3_file = m_new.group(2)
    elif m_old:
        total_articles = int(m_old.group(2))
        mp3_file = None
    else:
        total_articles = 0
        mp3_file = None

    # 概要（> で始まる行）
    summary_m = re.search(r"^> (.+)$", text, re.MULTILINE)
    summary = summary_m.group(1) if summary_m else ""

    # 記事一覧（フラット形式 / パート形式共通）
    articles = []
    for am in re.finditer(r"- \[(.+?)\]\((.+?)\)\s+_(.+?)_", text):
        articles.append({"title": am.group(1), "url": am.group(2), "site": am.group(3)})

    parts = []
    # 新形式（パートあり）: "## パートN" or "## パートN [MM:SS]"
    for block in re.split(r"(?=## パート\d+)", text):
        pm = re.match(r"## パート(\d+)(?:\s+\[(\d{2}:\d{2})\])?", block)
        if not pm:
            continue
        part_summary_m = re.search(r"^> (.+)$", block, re.MULTILINE)
        part_articles = []
        for am in re.finditer(r"- \[(.+?)\]\((.+?)\)\s+_(.+?)_", block):
            part_articles.append({"title": am.group(1), "url": am.group(2), "site": am.group(3)})
        parts.append({
            "num": pm.group(1),
            "time": pm.group(2),
            "summary": part_summary_m.group(1) if part_summary_m else "",
            "articles": part_articles,
        })

    # 旧形式: "## EPN — `newsy_epN.mp3`"
    if not parts:
        for block in re.split(r"(?=## EP\d+)", text):
            em = re.match(r"## EP(\d+) — `(newsy_ep\d+\.mp3)`", block)
            if not em:
                continue
            ep_summary_m = re.search(r"^> (.+)$", block, re.MULTILINE)
            ep_articles = []
            for am in re.finditer(r"- \[(.+?)\]\((.+?)\)\s+_(.+?)_", block):
                ep_articles.append({"title": am.group(1), "url": am.group(2), "site": am.group(3)})
            parts.append({
                "num": em.group(1),
                "mp3": em.group(2),
                "summary": ep_summary_m.group(1) if ep_summary_m else "",
                "articles": ep_articles,
            })

    return total_articles, mp3_file, parts, summary, articles


def fmt_date(folder_name: str) -> str:
    d = folder_name
    return f"{d[0:4]}年{d[4:6]}月{d[6:8]}日 {d[9:11]}:{d[11:13]}"


def _render_articles(articles: list[dict], esc) -> str:
    """記事一覧の HTML を生成"""
    if not articles:
        return ""
    items = "".join(
        f'<li><a href="{esc(a["url"])}" target="_blank">{esc(a["title"])}</a>'
        f' <span class="src-site">{esc(a["site"])}</span></li>'
        for a in articles
    )
    return f'<ul class="sources">{items}</ul>'


def _render_parts(parts: list[dict], mp3_file: str | None, esc) -> str:
    """パート一覧の HTML を生成"""
    html_parts = []
    for part in parts:
        articles_html = ""
        if part["articles"]:
            items = "".join(
                f'<li><a href="{esc(a["url"])}" target="_blank">{esc(a["title"])}</a>'
                f' <span class="src-site">{esc(a["site"])}</span></li>'
                for a in part["articles"]
            )
            articles_html = (
                f'<details>'
                f'<summary>引用記事 ({len(part["articles"])})</summary>'
                f'<ul class="sources">{items}</ul>'
                f'</details>'
            )
        part_audio = ""
        if not mp3_file and "mp3" in part:
            part_audio = f'<audio controls preload="none" src="./{part["mp3"]}"></audio>'
        time_attr = f' data-time="{part["time"]}"' if part.get("time") else ""
        time_badge = f'<span class="ep-time">{part["time"]}</span>' if part.get("time") else ""
        html_parts.append(
            f'<div class="ep"{time_attr}>'
            f'<div class="ep-title">パート{part["num"]}{time_badge}</div>'
            f'<div class="ep-summary">{esc(part["summary"])}</div>'
            f'{part_audio}'
            f'{articles_html}'
            f'</div>'
        )
    return "\n".join(html_parts)


def _render_episode_body(mp3_file: str | None, mp3_prefix: str,
                         parts: list[dict], summary: str,
                         flat_articles: list[dict], esc) -> str:
    """音声プレーヤー + パート/記事一覧の HTML を生成"""
    chunks = []

    if mp3_file:
        chunks.append(f'<audio controls preload="none" src="{mp3_prefix}{mp3_file}"></audio>')

    if parts:
        chunks.append(_render_parts(parts, mp3_file, esc))
    elif flat_articles:
        summary_html = f'<div class="ep-summary">{esc(summary)}</div>' if summary else ""
        chunks.append(f'<div class="ep">{summary_html}{_render_articles(flat_articles, esc)}</div>')

    return "\n".join(chunks)


def build_single_page(folders: list[Path]) -> str:
    """1ページ構成の HTML を生成"""
    esc = html_mod.escape

    # --- 最新エピソード ---
    latest = folders[0]
    readme = latest / "README.md"
    latest_content = ""
    summary_html = ""
    latest_mp3 = None
    latest_parts: list[dict] = []
    if readme.exists():
        total_articles, latest_mp3, latest_parts, summary, flat_articles = parse_readme(readme)
        latest_content = _render_episode_body(
            latest_mp3, f"./{latest.name}/", latest_parts, summary, flat_articles, esc)
        if summary:
            summary_html = f'<div class="summary">{esc(summary)}</div>'

    # パートクリックでシークする JS（最新エピソード用）
    seek_js = ""
    has_timestamps = any(p.get("time") for p in latest_parts)
    if latest_mp3 and has_timestamps:
        seek_js = """
<script>
document.querySelectorAll('.latest .ep[data-time]').forEach(el => {
  el.addEventListener('click', e => {
    if (e.target.closest('details, a')) return;
    const p = document.querySelector('.latest audio');
    if (!p) return;
    const [m, s] = el.dataset.time.split(':').map(Number);
    p.currentTime = m * 60 + s;
    p.play();
  });
});
</script>"""

    latest_html = (
        f'<div class="latest">\n'
        f'  <div class="date">{fmt_date(latest.name)}</div>\n'
        f'  {summary_html}\n'
        f'  {latest_content}\n'
        f'</div>'
    )

    # --- 過去エピソード ---
    archive_items = []
    for folder in folders[1:]:
        readme = folder / "README.md"
        if not readme.exists():
            continue
        total_articles, mp3_file, parts, summary, flat_articles = parse_readme(readme)
        meta = f"{total_articles} 記事" if total_articles else ""

        body_html = _render_episode_body(
            mp3_file, f"./{folder.name}/", parts, summary, flat_articles, esc)

        archive_items.append(
            f'<details class="archive-item">\n'
            f'  <summary><span class="archive-date">{fmt_date(folder.name)}</span>'
            f' <span class="archive-meta">{meta}</span></summary>\n'
            f'  <div class="archive-body">{body_html}</div>\n'
            f'</details>'
        )

    archive_html = ""
    if archive_items:
        archive_html = (
            f'\n<div class="archive">\n'
            f'  <h2>過去のエピソード</h2>\n'
            + "\n".join(archive_items)
            + "\n</div>"
        )

    body = f"<h1>Newsy</h1>\n{latest_html}{archive_html}{seek_js}"
    return HTML.format(body=body)


def build_site():
    """output/ → docs/ に静的サイトを生成する"""
    folders = sorted(
        [d for d in OUTPUT_DIR.iterdir()
         if d.is_dir() and re.match(r"\d{8}_\d{4}", d.name)],
        key=lambda d: d.name,
        reverse=True,
    )

    if not folders:
        print("  [警告] output/ にフォルダがありません。")
        return

    DOCS_DIR.mkdir(exist_ok=True)

    # 1ページ構成の index.html を生成
    page_html = build_single_page(folders)
    (DOCS_DIR / "index.html").write_text(page_html, encoding="utf-8")

    # MP3 をフォルダごとにコピー
    for folder in folders:
        dest = DOCS_DIR / folder.name
        dest.mkdir(exist_ok=True)
        for mp3 in folder.glob("*.mp3"):
            dest_mp3 = dest / mp3.name
            if not dest_mp3.exists() or mp3.stat().st_mtime > dest_mp3.stat().st_mtime:
                shutil.copy2(mp3, dest_mp3)

    print(f"  静的サイト生成完了 → {DOCS_DIR}/")
    print(f"  {len(folders)} フォルダ（1ページ構成）")


if __name__ == "__main__":
    print("Newsy 静的サイト生成")
    build_site()
