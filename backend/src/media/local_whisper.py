"""Client for an optional, private faster-whisper service."""
import math
from pathlib import Path
from typing import Any

import requests


def transcribe_local(
    audio_path: Path,
    base_url: str,
    model_name: str,
    language: str | None,
    timeout_seconds: int = 10800,
) -> dict[str, Any]:
    """Stream audio to the local service and require usable word timings.

    The service returns the same result shape as openai-whisper. No hosted
    provider credentials are forwarded, and redirects are not followed.
    """
    try:
        with audio_path.open("rb") as audio:
            response = requests.post(
                base_url.rstrip("/") + "/transcribe",
                data=audio,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Whisper-Model": model_name,
                    "X-Whisper-Language": language or "auto",
                },
                timeout=(10, timeout_seconds),
                allow_redirects=False,
            )
        if response.status_code != 200:
            raise RuntimeError(f"Local Whisper service returned HTTP {response.status_code}")
        result = response.json()
    except requests.RequestException:
        raise RuntimeError("Local Whisper service is unavailable or timed out") from None
    except ValueError:
        raise RuntimeError("Local Whisper service returned invalid JSON") from None

    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise RuntimeError("Local Whisper service returned an invalid transcript")
    segments = result.get("segments")
    if not isinstance(segments, list) or not all(isinstance(segment, dict) for segment in segments):
        raise RuntimeError("Local Whisper service returned invalid segments")
    if not all(isinstance(segment.get("words", []), list) for segment in segments):
        raise RuntimeError("Local Whisper service returned invalid word timestamps")
    words = [word for segment in segments for word in segment.get("words", [])]
    if result["text"].strip() and not words:
        raise RuntimeError("Local Whisper service returned no word timestamps")
    for word in words:
        if not isinstance(word, dict):
            raise RuntimeError("Local Whisper service returned invalid word timestamps")
        start, end = word.get("start"), word.get("end")
        if (
            not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end < start
        ):
            raise RuntimeError("Local Whisper service returned invalid word timestamps")
    return result
