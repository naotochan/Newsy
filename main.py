#!/usr/bin/env python3
"""Newsy — AI ラジオ番組を自動生成する CLI"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.pipeline import run


class Tee:
    """stdout/stderr をコンソールとファイルの両方に出力する"""

    def __init__(self, log_file, stream):
        self.log_file = log_file
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()

    def flush(self):
        self.stream.flush()
        self.log_file.flush()


def setup_logging() -> Path:
    """logs/ にログファイルを作成し、stdout/stderr を tee する"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{datetime.now().strftime('%Y%m%d_%H%M')}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    sys.stdout = Tee(log_file, sys.__stdout__)
    sys.stderr = Tee(log_file, sys.__stderr__)
    return log_path


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
        subprocess.run(["git", "push"], check=True)
        print(f"\n[push] GitHub に push しました ({now})")
    except subprocess.CalledProcessError as e:
        print(f"\n[push] git push に失敗しました: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Newsy: AI・テクノロジーニュースをラジオ番組に変換して音声を生成する"
    )
    parser.add_argument("--config", default="config/settings.yaml", help="設定ファイルのパス")
    parser.add_argument("--output", default="output", help="出力ディレクトリ")
    parser.add_argument("--no-push", action="store_true", help="自動 push を無効化")
    args = parser.parse_args()

    log_path = setup_logging()
    print(f"ログ: {log_path}\n")

    results = run(config_path=args.config, output_dir=args.output)

    if results and not args.no_push:
        git_push()

    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
