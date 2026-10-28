from unittest.mock import Mock

import pytest
import requests

from src.media.local_whisper import transcribe_local


def transcript():
    return {"text": "Olá", "language": "pt", "segments": [
        {"start": 0.0, "end": 1.0, "text": "Olá", "words": [
            {"word": "Olá", "start": 0.0, "end": 1.0, "probability": 0.9}
        ]}
    ]}


def test_local_service_preserves_word_timings_and_streams_audio(tmp_path, monkeypatch):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"local-audio")
    response = Mock(status_code=200)
    response.json.return_value = transcript()

    def post(url, *, data, headers, timeout, allow_redirects):
        assert url == "http://transcription:9000/transcribe"
        assert data.read() == b"local-audio"
        assert headers["X-Whisper-Language"] == "pt"
        assert "Authorization" not in headers
        assert timeout == (10, 900)
        assert allow_redirects is False
        return response

    monkeypatch.setattr("src.media.local_whisper.requests.post", post)
    assert transcribe_local(audio, "http://transcription:9000/", "small", "pt", 900) == transcript()


@pytest.mark.parametrize("status", [302, 400, 500])
def test_local_service_rejects_failed_or_redirected_responses(tmp_path, monkeypatch, status):
    audio = tmp_path / "audio.mp3"
    audio.touch()
    monkeypatch.setattr("src.media.local_whisper.requests.post", Mock(return_value=Mock(status_code=status)))
    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        transcribe_local(audio, "http://transcription:9000", "small", None)


@pytest.mark.parametrize("invalid", [None, {"text": "Olá"}, {"text": "Olá", "segments": []},
    {"text": "Olá", "segments": [{"words": None}]},
    {"text": "Olá", "segments": [{"words": [{"start": 2, "end": 1}]}]},
    {"text": "Olá", "segments": [{"words": [{"start": float("nan"), "end": 1}]}]}])
def test_local_service_rejects_missing_or_invalid_timestamps(tmp_path, monkeypatch, invalid):
    audio = tmp_path / "audio.mp3"
    audio.touch()
    response = Mock(status_code=200)
    response.json.return_value = invalid
    monkeypatch.setattr("src.media.local_whisper.requests.post", Mock(return_value=response))
    with pytest.raises(RuntimeError):
        transcribe_local(audio, "http://transcription:9000", "small", None)


def test_local_service_does_not_log_response_body_on_timeout(tmp_path, monkeypatch):
    audio = tmp_path / "audio.mp3"
    audio.touch()
    monkeypatch.setattr("src.media.local_whisper.requests.post", Mock(side_effect=requests.Timeout("private input")))
    with pytest.raises(RuntimeError, match="unavailable or timed out") as error:
        transcribe_local(audio, "http://transcription:9000", "small", None)
    assert "private input" not in str(error.value)


def test_whisper_routes_to_local_service_and_preserves_caption_cache(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from src.media import transcription

    audio = tmp_path / "audio.mp3"
    audio.touch()
    monkeypatch.setattr(transcription, "_prepare_audio_for_transcription", lambda path: audio)
    monkeypatch.setattr(transcription, "get_config", lambda: SimpleNamespace(
        whisper_local_url="http://transcription:9000", whisper_local_timeout_seconds=900,
    ))
    load_model = Mock(side_effect=AssertionError("In-process Whisper must not run"))
    monkeypatch.setattr(transcription, "_get_whisper_model", load_model)
    remote = Mock(return_value=transcript())
    monkeypatch.setattr("src.media.local_whisper.transcribe_local", remote)
    result = transcription.transcribe_with_whisper(audio, "small", "pt_br")
    remote.assert_called_once_with(audio, "http://transcription:9000", "small", "pt", 900)
    cached = transcription._whisper_result_to_transcript_data(result)
    assert cached["words"][0]["start"] == 0
    assert cached["words"][0]["end"] == 1000
    assert cached["language_code"] == "pt"
