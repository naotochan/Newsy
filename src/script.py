"""脚本生成モジュール — LLM を使ってニュースをラジオ番組の台本に変換する"""

import os
import yaml
from dotenv import load_dotenv
from .fetcher import Article

load_dotenv(dotenv_path="config/.env")

SCRIPT_PROMPT = """\
あなたはポッドキャスト「Newsy」の脚本家です。
Google NotebookLM の音声概要のような、聞き入ってしまう掛け合いトークを作ってください。

## パーソナリティ（役割の非対称性が最重要）
- {host}（ホスト / 詳しい側）: 技術に詳しく、背景知識を持っている。複雑な話題をアナロジーや身近な例えで噛み砕いて説明する。「例えるなら〜みたいな感じで」「要するに〜ということなんだけど」のように語る。
- {assistant}（アシスタント / 好奇心旺盛な聞き手）: リスナーの代弁者。驚き・疑問・発見を素直に表現する。「え、ちょっと待って」「それってつまり…」「へえ、知らなかった！」と割り込み、深掘りの質問をする。

## エピソード情報: {ep_info}

## 会話の力学（これが自然さの鍵）
- 相手の発言を一言で拾ってから自分の話を続ける（「まさにそれで」「そうなんですよ、で」「いや、それがね」）
- 短い反応（1文: 「え、それすごくないですか！」）と長めの説明（2〜3文）を交互に繰り返すリズムにする
- 話し言葉のフィラーを自然に混ぜる（「えーっと」「あの」「うーん」「なるほどね」「っていうか」）
- 驚き・好奇心・発見の感情をしっかり表現する（「うそ、まじで？」「それは面白い！」「いや〜、それは衝撃だな」）
- 複雑な概念は必ずアナロジーや日常の例えで説明する
- 「それって私たちの生活にどう関係するの？」「つまり何が変わるの？」という視点を必ず入れる

## 構成ルール
- 1つの記事につき5〜8往復の掛け合いでじっくり深掘りする（ニュースの紹介で終わらず、背景・影響・自分たちの生活との関連まで広げる）
- トピック間は有機的に繋ぐ（「そういえばさ」「それで思い出したんだけど」「ちょうどそれに関連して」）
- {opening_rule}
- パート末尾に次のトピックや次パートの予告（「次は〜について」「続いては〜を」など）を入れない
- 番組全体で8〜12分（読み上げ時）になる量にする
- 各発言は1〜3文に収める

## 出力フォーマット（厳守 — これ以外の説明文やメタコメントは一切入れない）
概要: （このエピソードで扱うトピックを1〜2文で）
{host}: （発言内容）
{assistant}: （発言内容）
...

## ニュース記事:
{news}
"""


def _load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_speakers(config: dict) -> tuple[str, str]:
    speakers = config.get("speakers", {})
    host = speakers.get("host", {}).get("name", "ホスト")
    assistant = speakers.get("assistant", {}).get("name", "アシスタント")
    return host, assistant


def _format_articles(articles: list[Article]) -> str:
    parts = []
    for i, a in enumerate(articles, 1):
        body = a.content or a.summary or "（本文なし）"
        parts.append(f"【記事{i}】{a.title}\n出典: {a.source}\n{body[:400]}")
    return "\n\n".join(parts)


def _call_anthropic(prompt: str, llm_cfg: dict) -> str:
    import anthropic
    cfg = llm_cfg.get("anthropic", {})
    model = os.getenv("ANTHROPIC_MODEL") or cfg.get("model", "claude-sonnet-4-6")
    max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS") or cfg.get("max_tokens", 4096))
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def _call_lmstudio(prompt: str, llm_cfg: dict) -> str:
    from openai import OpenAI
    cfg = llm_cfg.get("lmstudio", {})
    base_url = os.getenv("LM_STUDIO_BASE_URL") or cfg.get("base_url", "http://localhost:1234/v1")
    model = os.getenv("LM_STUDIO_MODEL") or cfg.get("model", "local-model")
    client = OpenAI(base_url=base_url, api_key="lm-studio")
    response = client.chat.completions.create(
        model=model,
        max_tokens=cfg.get("max_tokens", 4096),
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generate_script(
    articles: list[Article],
    config_path: str = "config/settings.yaml",
    ep: int = 1,
    total_eps: int = 1,
) -> str:
    config = _load_config(config_path)
    host, assistant = _load_speakers(config)
    news_text = _format_articles(articles)
    ep_info = f"第{ep}回 / 全{total_eps}回" if total_eps > 1 else "単独エピソード"

    if ep == 1:
        opening_rule = "冒頭に番組のオープニング（挨拶・エピソード番号を自然に触れる）、末尾にクロージングを入れる"
    elif ep == total_eps:
        opening_rule = "冒頭は「次のトピックです」「続いては」など自然な繋ぎで始める（挨拶や番組紹介は不要）。末尾に番組全体のクロージングを入れる"
    else:
        opening_rule = "冒頭は「次のトピックです」「続いては」など自然な繋ぎで始める（挨拶や番組紹介は不要）。末尾のクロージングも不要"

    prompt = SCRIPT_PROMPT.format(
        host=host, assistant=assistant, news=news_text,
        ep_info=ep_info, opening_rule=opening_rule,
    )

    llm_cfg = config.get("llm", {})
    # .env の LLM_PROVIDER を優先、なければ settings.yaml の値
    provider = os.getenv("LLM_PROVIDER") or llm_cfg.get("provider", "lmstudio")

    print(f"  LLM プロバイダー: {provider}")

    if provider == "anthropic":
        return _call_anthropic(prompt, llm_cfg)
    else:
        return _call_lmstudio(prompt, llm_cfg)


def _clean_script_text(text: str) -> str:
    """LLM 出力のノイズを除去して parse しやすい形に整形する"""
    import re
    cleaned = []
    for line in text.splitlines():
        line = line.strip()
        # 区切り線・空行をスキップ
        if not line or line.startswith("---"):
            continue
        # セクションヘッダ（### ニュース1, **オープニング** 等）をスキップ
        if line.startswith("#"):
            continue
        if line.startswith("**") and not any(
            name in line for name in _SPEAKER_NAMES_CACHE
        ):
            continue
        # ト書き行（*(音楽が流れる)* のみの行）をスキップ
        if re.match(r"^[*_]*[（(].+[)）][*_]*$", line):
            continue
        # マークダウン太字の話者名: **めたん:** → めたん:
        line = re.sub(r"\*\*(.+?)[：:]\*\*", r"\1:", line)
        # 行頭のト書き（(笑み) や *(音楽)* など）を除去
        line = re.sub(r"^[*_]*[（(][^)）]*[)）][*_]*\s*", "", line)
        line = line.strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


# parse_script 内で話者名キャッシュを使うためのグローバル変数
_SPEAKER_NAMES_CACHE: list[str] = []


def parse_script(script_text: str, config_path: str = "config/settings.yaml") -> list[dict]:
    """台本テキストを [{speaker: 'host'|'assistant', text: str}] に変換する"""
    config = _load_config(config_path)
    host, assistant = _load_speakers(config)

    # クリーンアップ用に話者名をキャッシュ
    _SPEAKER_NAMES_CACHE.clear()
    _SPEAKER_NAMES_CACHE.extend([host, assistant])

    cleaned = _clean_script_text(script_text)
    raw_lines = cleaned.splitlines()

    lines = []
    i = 0
    while i < len(raw_lines):
        raw = raw_lines[i]
        for prefix, role in [(host, "host"), (assistant, "assistant")]:
            if raw.startswith(f"{prefix}:") or raw.startswith(f"{prefix}："):
                text = raw[len(prefix) + 1:].strip()
                # 話者名だけの行 → 次の行がセリフ本文
                if not text and i + 1 < len(raw_lines):
                    i += 1
                    text = raw_lines[i].strip()
                # 「」で囲まれたセリフから括弧を除去
                if text.startswith("「") and text.endswith("」"):
                    text = text[1:-1]
                if text:
                    lines.append({"speaker": role, "text": text})
                break
        i += 1

    return lines
