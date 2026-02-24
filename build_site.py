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
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          background: #0f0f0f; color: #e0e0e0; padding: 16px; max-width: 640px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 20px; color: #fff; }}
  h2 {{ font-size: 1.1rem; color: #fff; margin-bottom: 4px; }}
  .card {{ background: #1c1c1e; border-radius: 12px; padding: 16px; margin-bottom: 12px; }}
  .card-link {{ text-decoration: none; color: inherit; display: block; }}
  .card-link .card {{ transition: background 0.15s; }}
  .card-link:hover .card {{ background: #2c2c2e; }}
  .card-date {{ font-size: 1rem; font-weight: 600; color: #4a9eff; }}
  .card-meta {{ font-size: 0.8rem; color: #888; margin-top: 4px; }}
  .ep {{ background: #1c1c1e; border-radius: 12px; padding: 16px; margin-bottom: 12px; }}
  .ep-title {{ font-size: 0.9rem; font-weight: 700; color: #4a9eff; margin-bottom: 6px; }}
  .ep-summary {{ font-size: 0.85rem; color: #aaa; line-height: 1.55; margin-bottom: 12px; }}
  audio {{ width: 100%; }}
  .back {{ display: inline-block; margin-bottom: 16px; color: #4a9eff;
           text-decoration: none; font-size: 0.9rem; }}
  .page-meta {{ color: #888; font-size: 0.82rem; margin-bottom: 20px; }}
  details {{ margin-top: 10px; }}
  summary {{ font-size: 0.82rem; color: #888; cursor: pointer; padding: 4px 0; }}
  summary:hover {{ color: #aaa; }}
  .sources {{ list-style: none; padding: 0; margin-top: 8px; }}
  .sources li {{ font-size: 0.8rem; line-height: 1.6; padding: 4px 0;
                 border-bottom: 1px solid #2a2a2a; }}
  .sources li:last-child {{ border-bottom: none; }}
  .sources a {{ color: #6ab0ff; text-decoration: none; }}
  .sources a:hover {{ text-decoration: underline; }}
  .sources .src-site {{ color: #666; font-size: 0.75rem; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def parse_readme(readme_path: Path):
    """README.md から EP 情報を抽出する"""
    text = readme_path.read_text(encoding="utf-8")

    m = re.search(r"全 (\d+) エピソード / (\d+) 記事", text)
    total_eps = int(m.group(1)) if m else 0
    total_articles = int(m.group(2)) if m else 0

    episodes = []
    for block in re.split(r"(?=## EP\d+)", text):
        em = re.match(r"## EP(\d+) — `(newsy_ep\d+\.mp3)`", block)
        if not em:
            continue
        summary_m = re.search(r"^> (.+)$", block, re.MULTILINE)
        articles = []
        for am in re.finditer(r"- \[(.+?)\]\((.+?)\)\s+_(.+?)_", block):
            articles.append({"title": am.group(1), "url": am.group(2), "site": am.group(3)})
        episodes.append({
            "num": em.group(1),
            "mp3": em.group(2),
            "summary": summary_m.group(1) if summary_m else "",
            "articles": articles,
        })

    return total_eps, total_articles, episodes


def fmt_date(folder_name: str) -> str:
    d = folder_name
    return f"{d[0:4]}年{d[4:6]}月{d[6:8]}日 {d[9:11]}:{d[11:13]}"


def build_index(folders: list[Path]) -> str:
    """トップページ（フォルダ一覧）の HTML を生成"""
    cards = []
    for folder in folders:
        meta = ""
        readme = folder / "README.md"
        if readme.exists():
            total_eps, total_articles, _ = parse_readme(readme)
            meta = f"{total_eps} エピソード · {total_articles} 記事"

        cards.append(
            f'<a class="card-link" href="./{folder.name}/">'
            f'<div class="card">'
            f'<div class="card-date">{fmt_date(folder.name)}</div>'
            f'<div class="card-meta">{meta}</div>'
            f'</div></a>'
        )

    content = "\n".join(cards) if cards else "<p>エピソードがありません</p>"
    body = f"<h1>Newsy</h1>\n{content}"
    return HTML.format(title="Newsy", body=body)


def build_folder_page(folder: Path) -> str:
    """EP 詳細ページの HTML を生成"""
    readme = folder / "README.md"
    if not readme.exists():
        return ""

    total_eps, total_articles, episodes = parse_readme(readme)

    eps_html = []
    for ep in episodes:
        articles_html = ""
        if ep["articles"]:
            esc = html_mod.escape
            items = "".join(
                f'<li><a href="{esc(a["url"])}" target="_blank">{esc(a["title"])}</a>'
                f' <span class="src-site">{esc(a["site"])}</span></li>'
                for a in ep["articles"]
            )
            articles_html = (
                f'<details>'
                f'<summary>引用記事 ({len(ep["articles"])})</summary>'
                f'<ul class="sources">{items}</ul>'
                f'</details>'
            )
        eps_html.append(
            f'<div class="ep">'
            f'<div class="ep-title">EP{ep["num"]}</div>'
            f'<div class="ep-summary">{html_mod.escape(ep["summary"])}</div>'
            f'<audio controls preload="none" src="./{ep["mp3"]}"></audio>'
            f'{articles_html}'
            f'</div>'
        )

    body = (
        f'<a class="back" href="../">← 一覧に戻る</a>\n'
        f'<h2>{fmt_date(folder.name)}</h2>\n'
        f'<p class="page-meta">全 {total_eps} エピソード · {total_articles} 記事</p>\n'
        + "\n".join(eps_html)
    )
    return HTML.format(title=f"Newsy — {fmt_date(folder.name)}", body=body)


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

    # トップページ
    index_html = build_index(folders)
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 各フォルダ
    for folder in folders:
        dest = DOCS_DIR / folder.name
        dest.mkdir(exist_ok=True)

        # EP 詳細ページ
        page_html = build_folder_page(folder)
        if page_html:
            (dest / "index.html").write_text(page_html, encoding="utf-8")

        # MP3 コピー（更新があった場合のみ）
        for mp3 in folder.glob("*.mp3"):
            dest_mp3 = dest / mp3.name
            if not dest_mp3.exists() or mp3.stat().st_mtime > dest_mp3.stat().st_mtime:
                shutil.copy2(mp3, dest_mp3)

    print(f"  静的サイト生成完了 → {DOCS_DIR}/")
    print(f"  {len(folders)} フォルダ")


if __name__ == "__main__":
    print("Newsy 静的サイト生成")
    build_site()
