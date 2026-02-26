#!/usr/bin/env python3
"""Newsy — AI ラジオ番組を自動生成する CLI"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(
        description="Newsy: ニュースを会話形式のラジオ番組に変換して音声を生成する"
    )
    parser.add_argument("--config", default="config/settings.yaml", help="設定ファイルのパス")
    parser.add_argument("--output", default="output", help="出力ディレクトリ")
    args = parser.parse_args()

    log_path = setup_logging()
    print(f"ログ: {log_path}\n")

    results = run(config_path=args.config, output_dir=args.output)

    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
