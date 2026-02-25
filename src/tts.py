"""音声合成モジュール — ElevenLabs / VOICEVOX で台本を音声ファイルに変換する"""

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
from dotenv import load_dotenv

load_dotenv(dotenv_path="config/.env")


def _load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_tts_provider(config: dict) -> str:
    return config.get("tts", {}).get("provider", "voicevox")


# ── ElevenLabs ─────────────────────────────────────────

def _get_elevenlabs_voice_id(role: str, config: dict) -> str:
    return config.get("speakers", {}).get(role, {}).get("elevenlabs_voice_id", "")


def _get_elevenlabs_config(config: dict) -> dict:
    return config.get("elevenlabs", {})


def check_elevenlabs() -> bool:
    """ElevenLabs API キーが設定されているか確認する"""
    return bool(os.getenv("ELEVEN_API_KEY"))


def synthesize_elevenlabs(text: str, voice_id: str, config: dict) -> bytes:
    """テキストを ElevenLabs で音声合成し MP3 バイト列を返す"""
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings

    el_cfg = _get_elevenlabs_config(config)
    client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

    audio_iter = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=el_cfg.get("model_id", "eleven_multilingual_v2"),
        output_format=el_cfg.get("output_format", "mp3_44100_128"),
        language_code="ja",
        voice_settings=VoiceSettings(
            stability=el_cfg.get("stability", 0.5),
            similarity_boost=el_cfg.get("similarity_boost", 0.75),
            style=el_cfg.get("style", 0.0),
            use_speaker_boost=True,
        ),
    )
    return b"".join(audio_iter)


def create_audio_elevenlabs(
    lines: list[dict],
    config_path: str = "config/settings.yaml",
    output_path: str = "output/newsy.mp3",
    part_line_counts: list[int] | None = None,
) -> tuple[str, list[float]]:
    """ElevenLabs で全行を音声合成し、連結して MP3 に書き出す"""
    config = _load_config(config_path)
    el_cfg = _get_elevenlabs_config(config)
    total = len(lines)

    # パート境界を計算
    part_boundaries: set[int] = set()
    if part_line_counts:
        acc = 0
        for count in part_line_counts[:-1]:
            acc += count
            part_boundaries.add(acc)

    # ElevenLabs の出力ビットレート（kbps）を取得
    fmt = el_cfg.get("output_format", "mp3_44100_128")
    bitrate_kbps = int(fmt.rsplit("_", 1)[-1]) if "_" in fmt else 128

    segments: list[bytes] = []
    part_timestamps = [0.0]
    cumulative_secs = 0.0

    for i, line in enumerate(lines):
        if i in part_boundaries:
            part_timestamps.append(cumulative_secs)

        role = line["speaker"]
        text = line["text"]
        voice_id = _get_elevenlabs_voice_id(role, config)

        print(f"  [{i + 1}/{total}] {role}: {text[:40]}...")
        try:
            mp3_bytes = synthesize_elevenlabs(text, voice_id, config)
            segments.append(mp3_bytes)
            cumulative_secs += len(mp3_bytes) * 8 / (bitrate_kbps * 1000)
        except Exception as e:
            print(f"  [警告] 音声合成失敗: {e}")

    if not segments:
        raise RuntimeError("音声セグメントが生成されませんでした")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 各セグメント（MP3）を一時ファイルに書き出し、ffmpeg で連結
    tmpdir = tempfile.mkdtemp()
    list_path = os.path.join(tmpdir, "filelist.txt")
    try:
        with open(list_path, "w") as f:
            for idx, seg in enumerate(segments):
                seg_path = os.path.join(tmpdir, f"seg_{idx:04d}.mp3")
                with open(seg_path, "wb") as sf_:
                    sf_.write(seg)
                f.write(f"file '{seg_path}'\n")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", output_path],
            check=True, capture_output=True,
        )
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    return output_path, part_timestamps


# ── VOICEVOX ───────────────────────────────────────────

def _get_voicevox_base_url(config: dict) -> str:
    return (
        os.getenv("VOICEVOX_BASE_URL")
        or config.get("voicevox", {}).get("base_url", "http://localhost:50021")
    )


def _get_voicevox_speaker_id(role: str, config: dict) -> int:
    return config.get("speakers", {}).get(role, {}).get("voicevox_id", 3)


def _get_voicevox_speed_scale(config: dict) -> float:
    return config.get("voicevox", {}).get("speed_scale", 1.1)


def check_voicevox(config: dict | None = None) -> bool:
    """VOICEVOX サーバーが起動しているか確認する"""
    base_url = _get_voicevox_base_url(config or {})
    try:
        res = requests.get(f"{base_url}/version", timeout=3)
        return res.status_code == 200
    except Exception:
        return False


def synthesize_voicevox(text: str, speaker_id: int, base_url: str, speed_scale: float = 1.1) -> Optional[bytes]:
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
    data, samplerate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    return data, samplerate


def _make_silence(duration_ms: int, samplerate: int, channels: int = 1) -> np.ndarray:
    samples = int(samplerate * duration_ms / 1000)
    return np.zeros((samples, channels) if channels > 1 else samples, dtype="float32")


def create_audio_voicevox(
    lines: list[dict],
    config_path: str = "config/settings.yaml",
    output_path: str = "output/newsy.mp3",
    part_line_counts: list[int] | None = None,
) -> tuple[str, list[float]]:
    """VOICEVOX で全行を音声合成し MP3 に書き出す"""
    config = _load_config(config_path)
    base_url = _get_voicevox_base_url(config)
    speed_scale = _get_voicevox_speed_scale(config)

    # パート境界を計算
    part_boundaries: set[int] = set()
    if part_line_counts:
        acc = 0
        for count in part_line_counts[:-1]:
            acc += count
            part_boundaries.add(acc)

    segments: list[np.ndarray] = []
    samplerate = 24000
    prev_speaker = None
    total = len(lines)
    cumulative_samples = 0
    part_timestamps = [0.0]

    for i, line in enumerate(lines):
        if i in part_boundaries:
            part_timestamps.append(cumulative_samples / samplerate)

        role = line["speaker"]
        text = line["text"]
        speaker_id = _get_voicevox_speaker_id(role, config)

        print(f"  [{i + 1}/{total}] {role}: {text[:40]}...")
        try:
            wav = synthesize_voicevox(text, speaker_id, base_url, speed_scale)
            if wav:
                data, samplerate = _wav_bytes_to_array(wav)
                gap_ms = 700 if (prev_speaker and prev_speaker != role) else 400
                silence = _make_silence(gap_ms, samplerate)
                segments.append(silence)
                segments.append(data)
                cumulative_samples += len(silence) + len(data)
                prev_speaker = role
        except Exception as e:
            print(f"  [警告] 音声合成失敗: {e}")

    if not segments:
        raise RuntimeError("音声セグメントが生成されませんでした")

    combined = np.concatenate(segments)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    sf.write(tmp_wav, combined, samplerate)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bitrate = config.get("output", {}).get("bitrate", "192k")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-b:a", bitrate, output_path],
        check=True, capture_output=True,
    )
    os.unlink(tmp_wav)

    return output_path, part_timestamps


# ── ディスパッチ ────────────────────────────────────────

def check_tts(config_path: str = "config/settings.yaml") -> bool:
    """設定された TTS プロバイダーが利用可能か確認する"""
    config = _load_config(config_path)
    provider = _get_tts_provider(config)
    if provider == "elevenlabs":
        return check_elevenlabs()
    else:
        return check_voicevox()


def create_audio(
    lines: list[dict],
    config_path: str = "config/settings.yaml",
    output_path: str = "output/newsy.mp3",
    part_line_counts: list[int] | None = None,
) -> tuple[str, list[float]]:
    """設定に応じた TTS で音声を生成する。(パス, パート開始秒リスト) を返す"""
    config = _load_config(config_path)
    provider = _get_tts_provider(config)
    if provider == "elevenlabs":
        return create_audio_elevenlabs(lines, config_path, output_path, part_line_counts)
    else:
        return create_audio_voicevox(lines, config_path, output_path, part_line_counts)
