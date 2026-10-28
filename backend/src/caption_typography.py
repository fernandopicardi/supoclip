"""Map the settings preview's CSS pixels to libass font-height units."""
from functools import lru_cache
from pathlib import Path
import struct

from .font_registry import find_font_path

SETTINGS_REFERENCE_WIDTH = 300


@lru_cache(maxsize=128)
def _height_ratio(path: str, modified_ns: int, size: int) -> float:
    try:
        data = Path(path).read_bytes()
        tables = {}
        for i in range(struct.unpack_from('>H', data, 4)[0]):
            tag, _, offset, length = struct.unpack_from('>4sIII', data, 12 + i * 16)
            if offset + length > len(data):
                return 1.0
            tables[tag] = offset
        units = struct.unpack_from('>H', data, tables[b'head'] + 18)[0]
        ascent, descent = struct.unpack_from('>hh', data, tables[b'hhea'] + 4)
        os2 = tables.get(b'OS/2')
        if os2 is not None and struct.unpack_from('>H', data, os2 + 62)[0] & 128:
            ascent, descent = struct.unpack_from('>hh', data, os2 + 68)
        ratio = (ascent - descent) / units
        return ratio if 0.5 <= ratio <= 4 else 1.0
    except (OSError, KeyError, struct.error, ZeroDivisionError):
        return 1.0


def font_height_ratio(font: str) -> float:
    path = find_font_path(font, allow_all_user_fonts=True)
    if not path:
        return 1.0
    try:
        stat = path.stat()
        return _height_ratio(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return 1.0


def settings_ass_font_size(font_size: int, font: str, width: int = 1080) -> int:
    return max(1, round(font_size * width / SETTINGS_REFERENCE_WIDTH * font_height_ratio(font)))
