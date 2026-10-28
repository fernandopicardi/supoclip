import pytest
from src.browser_media import browser_media, verify_packets
from src.editor_document import atomic_json


def test_cache_is_bound_to_original_and_falls_back_when_stale(tmp_path):
    atomic_json(tmp_path/'source.json', {'sha256': 'original'})
    assert browser_media(tmp_path) == tmp_path/'media.mp4'
    (tmp_path/'browser.mp4').write_bytes(b'cache')
    cache = {'version': 1, 'source_sha256': 'original', 'packet_verified': True, 'bytes': 5}
    atomic_json(tmp_path/'browser-media.json', cache)
    assert browser_media(tmp_path) == tmp_path/'browser.mp4'
    atomic_json(tmp_path/'source.json', {'sha256': 'other'})
    assert browser_media(tmp_path) == tmp_path/'media.mp4'
    atomic_json(tmp_path/'source.json', {'sha256': 'original'})
    (tmp_path/'browser.mp4').write_bytes(b'incomplete')
    assert browser_media(tmp_path) == tmp_path/'media.mp4'


def test_packets_can_interleave_but_clock_and_payload_must_match():
    video = {'stream_index': 0, 'pts_time': '.033333', 'dts_time': '0', 'data_hash': 'video'}
    audio = {'stream_index': 1, 'pts_time': '0', 'dts_time': '0', 'data_hash': 'audio'}
    assert verify_packets([video, audio], [audio, video])['packet_count'] == 2
    with pytest.raises(ValueError, match='clock'):
        verify_packets([video], [video | {'pts_time': '.133333'}])
    with pytest.raises(ValueError, match='compressed'):
        verify_packets([audio], [audio | {'data_hash': 'changed'}])
    with pytest.raises(ValueError, match='counts'):
        verify_packets([video, video], [video])


def test_explicit_preparation_preserves_original_and_never_uses_an_encoder(tmp_path, monkeypatch):
    from src import browser_media as media
    original = tmp_path/'media.mp4'; original.write_bytes(b'original fixture')
    atomic_json(tmp_path/'source.json', {'status': 'ready', 'sha256': media.digest(original)})
    commands = []
    def copy_only(command, **kwargs):
        commands.append(command)
        assert command[command.index('-c')+1] == 'copy' and '-copyts' in command
        assert command[command.index('-movflags')+1] == '+faststart'
        from pathlib import Path
        Path(command[-1]).write_bytes(b'indexed fixture')
    monkeypatch.setattr(media.subprocess, 'run', copy_only)
    monkeypatch.setattr(media, 'packet_clock', lambda _: [{'stream_index':0,'pts_time':'0','dts_time':'0','data_hash':'unchanged'}])
    result = media.prepare_browser_media(tmp_path)
    assert result['packet_verified'] and original.read_bytes() == b'original fixture'
    assert media.browser_media(tmp_path) == tmp_path/'browser.mp4'
    assert media.prepare_browser_media(tmp_path) == result and len(commands) == 1
