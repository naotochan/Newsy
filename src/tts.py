"""音声合成モジュール — VOICEVOX を使って台本を音声ファイルに変換する"""

import io
import json
import subprocess
import tempfile
import os
import requests
import numpy as np
import soundfile as sf
import yaml
from typing import Optional


def _load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_base_url(config: dict) -> str:
    return config.get("voicevox", {}).get("base_url", "http://localhost:50021")


def _get_speaker_id(role: str, config: dict) -> int:
    return config.get("speakers", {}).get(role, {}).get("voicevox_id", 3)


def _get_speed_scale(config: dict) -> float:
    return config.get("voicevox", {}).get("speed_scale", 1.1)


def check_voicevox() -> bool:
    """VOICEVOX サーバーが起動しているか確認する"""
    try:
        res = requests.get("http://localhost:50021/version", timeout=3)
        return res.status_code == 200
    except Exception:
        return False


def synthesize(text: str, speaker_id: int, base_url: str, speed_scale: float = 1.1) -> Optional[bytes]:
    """テキストを VOICEVOX で音声合成し WAV バイト列を返す"""
    res = requests.post(
        f"{base_url}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=30,
    )
    res.raise_for_status()
    query = res.json()
    query["speedScale"] = speed_scale

    res = requests.post(
        f"{base_url}/synthesis",
        params={"speaker": speaker_id},
        headers={"Content-Type": "application/json"},
        data=json.dumps(query),
        timeout=60,
    )
    res.raise_for_status()
    return res.content


def _wav_bytes_to_array(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """WAV バイト列を numpy 配列と sample rate に変換する"""
    data, samplerate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    return data, samplerate


def _make_silence(duration_ms: int, samplerate: int, channels: int = 1) -> np.ndarray:
    samples = int(samplerate * duration_ms / 1000)
    return np.zeros((samples, channels) if channels > 1 else samples, dtype="float32")


def create_audio(lines: list[dict], config_path: str = "config/settings.yaml", output_path: str = "output/newsy.mp3") -> str:
    """台本の全行を音声合成して MP3 ファイルに書き出し、パスを返す"""
    config = _load_config(config_path)
    base_url = _get_base_url(config)
    speed_scale = _get_speed_scale(config)

    segments: list[np.ndarray] = []
    samplerate = 24000  # VOICEVOX のデフォルト
    prev_speaker = None
    total = len(lines)

    for i, line in enumerate(lines, 1):
        role = line["speaker"]
        text = line["text"]
        speaker_id = _get_speaker_id(role, config)

        print(f"  [{i}/{total}] {role}: {text[:40]}...")
        try:
            wav = synthesize(text, speaker_id, base_url, speed_scale)
            if wav:
                data, samplerate = _wav_bytes_to_array(wav)
                gap_ms = 700 if (prev_speaker and prev_speaker != role) else 400
                segments.append(_make_silence(gap_ms, samplerate))
                segments.append(data)
                prev_speaker = role
        except Exception as e:
            print(f"  [警告] 音声合成失敗: {e}")

    if not segments:
        raise RuntimeError("音声セグメントが生成されませんでした")

    combined = np.concatenate(segments)

    # WAV を一時ファイルに書き出して ffmpeg で MP3 に変換
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    sf.write(tmp_wav, combined, samplerate)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bitrate = config.get("output", {}).get("bitrate", "192k")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-b:a", bitrate, output_path],
        check=True,
        capture_output=True,
    )
    os.unlink(tmp_wav)

    return output_path
