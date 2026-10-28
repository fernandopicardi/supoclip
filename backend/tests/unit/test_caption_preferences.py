from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from src.caption_preferences import CaptionLayout, apply_caption_layout, editorial_defaults, load_caption_preferences


@pytest.mark.parametrize('value', [{'y': 0.09}, {'y': 0.91}, {'y': True}, {'wordsPerLine': 0}, {'wordsPerLine': 9}, {'wordsPerLine': 3.5}, {'background': 'yes'}, {'uppercase': 1}, {'accent': 'red'}, {'unknown': True}])
def test_rejects_invalid_or_unknown_layout_options(value):
    with pytest.raises(ValidationError):
        CaptionLayout.model_validate(value)


def test_style_adapter_keeps_position_and_contrast_without_mutating_template():
    template = {'animation': 'pop', 'font_color': '#FFFFFF', 'emoji': True}
    before = deepcopy(template)
    custom = apply_caption_layout(template, {'y': .5, 'wordsPerLine': 2, 'background': True, 'uppercase': True})
    assert template == before
    assert custom['position_y'] == .5
    assert custom['max_words_per_line'] == 2
    assert custom['background_color'] == '#000000A6'
    assert custom['uppercase'] and not custom['emoji']
    assert custom['animation'] == 'none'


def test_new_editor_defaults_use_account_font_and_map_font_size_units():
    prefs = {'default_font_family': 'NunitoSans', 'default_font_size': 24, 'default_font_color': '#FFFFFF', 'default_caption_style': {'y': .5, 'wordsPerLine': 3}}
    result = editorial_defaults(prefs)
    assert result['font'] == 'NunitoSans'
    assert result['size'] == 46
    assert result['y'] == .5 and result['wordsPerLine'] == 3
    assert result['color'] == '#FFFFFF' and not result['background']


async def test_preferences_read_is_scoped_to_authenticated_user():
    result = SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {'default_caption_style': {'y': .5}}))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    assert await load_caption_preferences(db, 'account-a') == {'default_caption_style': {'y': .5}}
    assert db.execute.await_args.args[1] == {'user_id': 'account-a'}


def test_centered_caption_ass_has_exact_position_and_no_karaoke(tmp_path):
    import json
    from src.caption_templates import get_template
    from src.media.captions import build_assemblyai_ass_subtitles
    video = tmp_path/'source.mp4'
    video.with_suffix('.transcript_cache.json').write_text(json.dumps({'version': 2,
        'words': [{'text': 'Caramelo', 'start': 0, 'end': 400}, {'text': 'Brasil', 'start': 400, 'end': 900}]}))
    output = tmp_path/'caption.ass'
    layout = {'y': .5, 'wordsPerLine': 2, 'uppercase': True, 'background': True}
    assert build_assemblyai_ass_subtitles(video, clip_start=0, clip_end=1,
        video_width=1080, video_height=1920, output_ass_path=output,
        template_override=apply_caption_layout(get_template('default'), layout),
        center_y_override=960)
    text = output.read_text()
    assert r'\pos(540,960)' in text
    assert 'CARAMELO' in text and 'BRASIL' in text
