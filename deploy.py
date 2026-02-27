#!/usr/bin/env python3
"""GitHub Pages へのデプロイ — build_site + git push"""

import subprocess
from datetime import datetime

from build_site import build_site


def git_push():
    """docs/ を自動コミット & push する"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        subprocess.run(["git", "add", "docs/"], check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if result.returncode == 0:
            print("\n[push] docs/ に変更なし。スキップします。")
            return
        subprocess.run(
            ["git", "commit", "-m", f"Update: {now}"],
            check=True,
        )
        subprocess.run(["git", "pull", "--rebase"], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"\n[push] GitHub に push しました ({now})")
    except subprocess.CalledProcessError as e:
        print(f"\n[push] git push に失敗しました: {e}")


def main():
    print("静的サイト生成中...")
    build_site()
    git_push()


if __name__ == "__main__":
    main()
