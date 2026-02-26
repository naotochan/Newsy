# Newsy

ウォッチしたいニュースを毎朝自動収集し、会話形式のラジオ番組として音声ファイルを生成する．
私が不定期で収集している内容は下記リンクに公開してあります．

https://naotochan.github.io/Newsy/

※本アプリは VOICEVOX の音声エンジンを使わせていただいております．
https://voicevox.hiroshiba.jp/

## 仕組み

1. **RSS 取得** — 登録フィードから最新記事を収集（重複記事は自動スキップ）
2. **脚本生成** — LLM が 2 人の会話形式で台本を作成（記事数に応じてパート分割）
3. **音声合成** — VOICEVOX または ElevenLabs で読み上げ → 全パート統合して 1 つの MP3 出力

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

主な設定項目：

| 変数 | 説明 |
|------|------|
| `LLM_PROVIDER` | `lmstudio` or `anthropic` |
| `LM_STUDIO_BASE_URL` | LM Studio の API URL |
| `ANTHROPIC_API_KEY` | Anthropic API キー |
| `VOICEVOX_BASE_URL` | VOICEVOX Engine の URL |
| `ELEVEN_API_KEY` | ElevenLabs API キー |

### 必要なサービス

- **VOICEVOX** または **ElevenLabs** — 音声合成（`config/settings.yaml` の `tts.provider` で切り替え）
- **LM Studio** または **Anthropic API** — LLM（`config/settings.yaml` の `llm.provider` で切り替え）

## 使い方

```bash
# VOICEVOX と LM Studio を起動した状態で
python main.py
```

`output/YYYYMMDD_HHMM/` に以下が生成されます：

| ファイル | 内容 |
|---------|------|
| `newsy.mp3` | 全パート統合の音声ファイル |
| `script_partN.txt` | パートごとの会話台本 |
| `sources_partN.md` | パートごとの元記事メモ |
| `README.md` | パート別概要 + 記事一覧 + タイムスタンプ |

## RSS フィード（39 本）

| カテゴリ | フィード数 | 例 |
|----------|-----------|-----|
| 国内メディア | 7 | ITmedia NEWS, WIRED.jp, GIZMODO JAPAN |
| UI/UX・デザイン | 4 | UX Collective, Nielsen Norman Group |
| 海外メディア | 6 | The Verge, Ars Technica, TechCrunch |
| arXiv | 9 | cs.AI, cs.LG, cs.CL, cs.RO, cs.HC 他 |
| AI 企業・技術ブログ | 11 | OpenAI, Google AI, Anthropic, Hacker News |

既出記事は `output/seen_urls.txt` で管理し、自動的にスキップされます。

## 設定

`config/settings.yaml` で変更可能：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `max_articles_per_feed` | 3 | フィードごとの最大記事数 |
| `max_articles_per_episode` | 5 | 1 パートあたりの記事数 |
| `min_articles_per_episode` | 3 | これ未満なら前のパートにまとめる |
| `max_articles_total` | 50 | 1 回の実行で取得する最大記事数 |

## 技術スタック

- Python 3.13
- feedparser / trafilatura（RSS + 本文抽出）
- OpenAI 互換 API / Anthropic API（脚本生成）
- VOICEVOX / ElevenLabs（音声合成）
- soundfile + numpy + ffmpeg（音声処理）
