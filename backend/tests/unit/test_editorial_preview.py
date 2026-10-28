from src.services.editorial_service import background_filter
from src.editorial_document import EditorialDocument
from src.editor_document import atomic_json
from src.config import get_config
from src.services import editorial_service as service
import pytest


def test_background_legacy_and_blur_filter_without_encoding():
    assert EditorialDocument(source_id='source').background == 'black'
    black = background_filter(0, 720, 1280, 720, 1032, .53, .5, 'black')
    assert black == '[fg0]pad=720:1280:0:124:black[framed0]'
    blur = background_filter(2, 720, 1280, 720, 1032, .53, .5, 'blur')
    assert 'split=2' in blur and 'boxblur=24:2:12:1' in blur
    assert 'overlay=0:124:shortest=1[framed2]' in blur
    assert 'ass=' not in blur  # Captions are burned after the background composition.


def test_blur_export_graph_keeps_audio_and_caption_clock_without_running_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config(), 'temp_dir', str(tmp_path))
    source_id = 'source_'+'a'*32
    source = service.owner_root('test')/'sources'/source_id
    atomic_json(source/'source.json', {'duration': 20, 'width': 1280, 'height': 720, 'has_audio': True})
    monkeypatch.setattr(service, 'source_words', lambda *_: [{'id': 'word', 'start': 10.1, 'end': 10.5, 'text': 'teste'}])
    doc = EditorialDocument.model_validate({'source_id': source_id, 'background': 'blur',
        'framing': {'fit': 'contain', 'zoom': 2.55},
        'clips': [{'id': 'a', 'start': 10, 'end': 14, 'cuts': [{'id': 'c', 'start': 11, 'end': 12}]}]})
    directory = tmp_path/'edit'; directory.mkdir()
    captured = []
    def intercept(command, path, job, duration):
        captured.append((command, (path/f'filters-{job}.txt').read_text(), duration))
        raise RuntimeError('encoding deliberately blocked')
    monkeypatch.setattr(service, 'run_render', intercept)
    with pytest.raises(RuntimeError, match='deliberately blocked'):
        service.render_editorial(directory, 'test', {'revision': 1, 'document': doc.model_dump()}, 'test')
    command, graph, duration = captured[0]
    assert duration == 3 and command.count('-i') == 2
    assert 'overlay=0:124:shortest=1[framed0]' in graph
    assert '[framed0]tpad=' in graph and '[framed1]tpad=' in graph
    assert '[a0][a1]concat=n=2:v=0:a=1[audio]' in graph
    assert graph.index('boxblur=') < graph.index('[video]ass=')
    assert not list(directory.glob('*.mp4'))
