# Newsy

AI・テクノロジーニュースを毎朝自動収集し、会話形式のラジオ番組として音声ファイルを生成する Python CLI。

私が不定期で収集している内容は下記リンクに公開してあります．

https://naotochan.github.io/Newsy/

※本アプリは VOICEBOX の音声エンジンを使わせていただいております．

https://voicevox.hiroshiba.jp/

## 仕組み

1. **RSS 取得** — 国内外 10 フィードから最新記事を収集
2. **脚本生成** — LLM が 2 人の会話形式で台本を作成
3. **音声合成** — VOICEVOX で読み上げ → MP3 出力
4. **静的サイト生成** — GitHub Pages 用の HTML を自動生成

## セットアップ

```bash
git clone https://github.com/naotochan/Newsy.git
cd Newsy
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 環境変数

`config/.env.example` をコピーして `config/.env` を作成：

```bash
cp config/.env.example config/.env
```

### 必要なサービス

- **VOICEVOX** — 音声合成エンジン（ローカル起動）
- **LM Studio** または **Anthropic API** — LLM（`config/settings.yaml` で切り替え）

※お好きな 音声エンジン，AI が使えます

## 使い方

```bash
# VOICEVOX と LM Studio を起動した状態で
python main.py
```

`output/YYYYMMDD_HHMM/` に以下が生成されます：

| ファイル | 内容 |
|---------|------|
| `newsy_epN.mp3` | エピソード音声 |
| `script_epN.txt` | 会話台本 |
| `sources_epN.md` | 元記事メモ |
| `README.md` | EP 概要 + 記事一覧 |

同時に `docs/` に GitHub Pages 用の静的サイトも生成されます。

## 設定

`config/settings.yaml` で変更可能：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `max_articles_per_feed` | 3 | フィードごとの最大記事数 |
| `max_articles_per_episode` | 5 | 1EP あたりの記事数 |
| `min_articles_per_episode` | 3 | これ未満なら前の EP にまとめる |
| `max_articles_total` | 50 | 1 回の実行で取得する最大記事数 |

## 技術スタック

- Python 3.13
- feedparser / trafilatura（RSS + 本文抽出）
- OpenAI 互換 API / Anthropic API（脚本生成）
- VOICEVOX（音声合成）
- soundfile + numpy + ffmpeg（音声処理）

