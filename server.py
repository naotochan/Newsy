#!/usr/bin/env python3
"""Newsy HTTP server — スマホからエピソードを聴けるシンプルなウェブサーバ"""

import html as html_mod
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
PORT = 8080

HTML = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Newsy</title>
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
    """'20260224_1937' → '2026年02月24日 19:37'"""
    d = folder_name
    return f"{d[0:4]}年{d[4:6]}月{d[6:8]}日 {d[9:11]}:{d[11:13]}"


class NewsyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        path = urllib.parse.unquote(self.path).rstrip("/")

        parts = [p for p in path.split("/") if p]

        # /YYYYMMDD_HHMM/newsy_epN.mp3
        if len(parts) == 2 and parts[1].endswith(".mp3"):
            self._serve_mp3(parts[0], parts[1])
        # /YYYYMMDD_HHMM
        elif len(parts) == 1 and re.match(r"\d{8}_\d{4}", parts[0]):
            self._serve_folder(parts[0])
        # /
        else:
            self._serve_index()

    # ------------------------------------------------------------------
    def _serve_index(self):
        folders = sorted(
            [d for d in OUTPUT_DIR.iterdir()
             if d.is_dir() and re.match(r"\d{8}_\d{4}", d.name)],
            key=lambda d: d.name,
            reverse=True,
        )

        cards = []
        for folder in folders:
            meta = ""
            readme = folder / "README.md"
            if readme.exists():
                total_eps, total_articles, _ = parse_readme(readme)
                meta = f"{total_eps} エピソード · {total_articles} 記事"

            cards.append(
                f'<a class="card-link" href="/{folder.name}">'
                f'<div class="card">'
                f'<div class="card-date">{fmt_date(folder.name)}</div>'
                f'<div class="card-meta">{meta}</div>'
                f'</div></a>'
            )

        content = "\n".join(cards) if cards else "<p>エピソードがありません</p>"
        self._send_html(f"<h1>Newsy</h1>\n{content}")

    def _serve_folder(self, folder_name: str):
        folder_path = OUTPUT_DIR / folder_name
        readme = folder_path / "README.md"
        if not readme.exists():
            self._send_404()
            return

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
                f'<audio controls preload="none" src="/{folder_name}/{ep["mp3"]}"></audio>'
                f'{articles_html}'
                f'</div>'
            )

        body = (
            f'<a class="back" href="/">← 一覧に戻る</a>\n'
            f'<h2>{fmt_date(folder_name)}</h2>\n'
            f'<p class="page-meta">全 {total_eps} エピソード · {total_articles} 記事</p>\n'
            + "\n".join(eps_html)
        )
        self._send_html(body)

    def _serve_mp3(self, folder_name: str, filename: str):
        file_path = (OUTPUT_DIR / folder_name / filename).resolve()
        if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
            self._send_404()
            return
        if not file_path.exists():
            self._send_404()
            return

        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range", "")

        if range_header:
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if not m:
                self._send_404()
                return
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            length = end - start + 1

            self.send_response(206)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(file_path, "rb") as f:
                f.seek(start)
                self.wfile.write(f.read(length))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())

    # ------------------------------------------------------------------
    def _send_html(self, body: str):
        html = HTML.format(body=body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _send_404(self):
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), NewsyHandler)
    print(f"Newsy サーバ起動")
    print(f"  ローカル  : http://localhost:{PORT}")
    print(f"  Tailscale : http://<your-tailscale-ip>:{PORT}")
    print("Ctrl+C で停止\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました")
