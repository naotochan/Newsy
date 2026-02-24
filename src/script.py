"""脚本生成モジュール — LLM を使ってニュースをラジオ番組の台本に変換する"""

import os
import yaml
from dotenv import load_dotenv
from .fetcher import Article

load_dotenv(dotenv_path="config/.env")

SCRIPT_PROMPT = """\
あなたはラジオ番組「Newsy」の脚本家です。
以下のAI・テクノロジーニュースをもとに、2人のパーソナリティによる
自然な会話形式のラジオ番組台本を日本語で作成してください。

パーソナリティ:
- {host}（ホスト）: 落ち着いた話し方で番組を進行する。技術トピックを噛み砕いて説明する。
- {assistant}（アシスタント）: 明るく好奇心旺盛。素朴な疑問を投げかけ、リスナーの代弁をする。

エピソード情報: {ep_info}

ルール:
- 自然な日本語の会話にする（話し言葉で、固くなりすぎない）
- 専門用語は必ず簡単な言葉で補足説明する
- 番組全体で5〜8分（読み上げ時）になる量にする
- 各発言は1〜3文程度に収める
- 冒頭に番組のオープニング（エピソード番号を自然に触れる）、末尾にクロージングを入れる
- 必ず以下のフォーマットだけで出力し、他の説明文は一切入れない

出力フォーマット（厳守）:
概要: （このエピソードで扱うトピックを日本語で1〜2文で説明する）
{host}: （発言内容）
{assistant}: （発言内容）
...

ニュース記事:
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
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=cfg.get("model", "claude-opus-4-6"),
        max_tokens=cfg.get("max_tokens", 4096),
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
    prompt = SCRIPT_PROMPT.format(host=host, assistant=assistant, news=news_text, ep_info=ep_info)

    llm_cfg = config.get("llm", {})
    # .env の LLM_PROVIDER を優先、なければ settings.yaml の値
    provider = os.getenv("LLM_PROVIDER") or llm_cfg.get("provider", "lmstudio")

    print(f"  LLM プロバイダー: {provider}")

    if provider == "anthropic":
        return _call_anthropic(prompt, llm_cfg)
    else:
        return _call_lmstudio(prompt, llm_cfg)


def parse_script(script_text: str, config_path: str = "config/settings.yaml") -> list[dict]:
    """台本テキストを [{speaker: 'host'|'assistant', text: str}] に変換する"""
    config = _load_config(config_path)
    host, assistant = _load_speakers(config)

    lines = []
    for raw in script_text.splitlines():
        raw = raw.strip()
        if raw.startswith(f"{host}:"):
            text = raw[len(host) + 1:].strip()
            if text:
                lines.append({"speaker": "host", "text": text})
        elif raw.startswith(f"{assistant}:"):
            text = raw[len(assistant) + 1:].strip()
            if text:
                lines.append({"speaker": "assistant", "text": text})

    return lines
