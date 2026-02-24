#!/usr/bin/env python3
"""Newsy — AI ラジオ番組を自動生成する CLI"""

import argparse
import sys
from src.pipeline import run


def main():
    parser = argparse.ArgumentParser(
        description="Newsy: AI・テクノロジーニュースをラジオ番組に変換して音声を生成する"
    )
    parser.add_argument("--config", default="config/settings.yaml", help="設定ファイルのパス")
    parser.add_argument("--output", default="output", help="出力ディレクトリ")
    args = parser.parse_args()

    results = run(config_path=args.config, output_dir=args.output)
    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
