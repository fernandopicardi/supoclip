import struct
from pathlib import Path

import pytest

from src.caption_typography import _height_ratio, font_height_ratio, settings_ass_font_size
from src.font_registry import FONTS_DIR, get_font_family_name


def test_nunito_uses_a_real_static_bold_face_and_full_family():
    font = FONTS_DIR/'NunitoSans.ttf'
    data = font.read_bytes()
    tables = {struct.unpack_from('>4sIII', data, 12+i*16)[0]: struct.unpack_from('>4sIII', data, 12+i*16)[2]
              for i in range(struct.unpack_from('>H', data, 4)[0])}
    assert b'fvar' not in tables
    assert struct.unpack_from('>H', data, tables[b'OS/2']+4)[0] == 700
    assert get_font_family_name(font) == 'Nunito Sans'


def test_settings_size_matches_css_em_instead_of_ass_line_height():
    assert font_height_ratio('NunitoSans') == pytest.approx(1.364)
    assert settings_ass_font_size(24, 'NunitoSans', 1080) == 118
    assert settings_ass_font_size(24, 'NunitoSans', 720) == 79
    assert settings_ass_font_size(24, 'NunitoSans', 300) == 33
    # ASS / font metric ratio gives the same 12 CSS px as the 150px preview.
    assert settings_ass_font_size(24, 'NunitoSans', 720) / font_height_ratio('NunitoSans') * 150/720 == pytest.approx(12, abs=.1)


def test_unknown_or_invalid_font_metrics_have_a_safe_fallback(tmp_path):
    assert font_height_ratio('missing-font') == 1
    bad = tmp_path/'invalid.ttf'
    bad.write_bytes(b'bad font')
    assert _height_ratio(str(bad), 0, 8) == 1
