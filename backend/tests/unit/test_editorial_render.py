import json
import subprocess

from src.config import get_config
from src.editor_document import CaptionStyle, Framing, atomic_json
from src.editorial_document import Clip, Cut, EditorialDocument
from src.services.editorial_service import item_dir, owner_root, render_editorial, store_transcript


def test_render_preserves_order_duration_and_word_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config(), 'temp_dir', str(tmp_path))
    source_id = 'source_'+'c'*32
    source = owner_root('render-test')/'sources'/source_id
    source.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=320x180:rate=30:duration=3', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=3',
                    '-c:v', 'libx264', '-threads', '2', '-c:a', 'aac', str(source/'media.mp4')], check=True)
    atomic_json(source/'source.json', {'sha256': 'render', 'duration': 3, 'width': 320,
                'height': 180, 'has_audio': True, 'status': 'awaiting_transcript'})
    store_transcript(source, 'render', [
        {'start': 0.1, 'end': 0.4, 'text': 'não'},
        {'start': 1.2, 'end': 1.5, 'text': 'retirar'},
        {'start': 2.1, 'end': 2.4, 'text': 'soberania'},
    ], 'pt', 'user_import')
    document = EditorialDocument(source_id=source_id,
        clips=[Clip(id='last-first', start=2, end=2.7),
               Clip(id='beginning-last', start=0, end=1.7, cuts=[Cut(id='internal', start=1.1, end=1.6)])],
        captions=CaptionStyle(font='TikTokSans-Bold', karaoke=True),
        framing=Framing(fit='contain'))
    directory = owner_root('render-test')/'edits'/('edit_'+'d'*32)
    directory.mkdir(parents=True)
    render_editorial(directory, 'test', {'revision': 7, 'document': document.model_dump()}, 'render-test')
    result = json.loads((directory/'map-test.json').read_text())
    assert result['revision'] == 7
    assert [r['clip_id'] for r in result['ranges']] == ['last-first', 'beginning-last', 'beginning-last']
    assert [w['text'] for w in result['caption_words']] == ['soberania', 'não']
    assert abs(result['playback_seconds']-1.9) < 0.001
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                                               '-of', 'json', str(directory/'export-test.mp4')]))
    video = next(s for s in probe['streams'] if s['codec_type']=='video')
    assert (video['width'], video['height']) == (720,1280)
    assert abs(float(probe['format']['duration'])-1.9) <= 0.1
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(directory/'export-test.mp4'), '-f', 'null', '-'], check=True)
