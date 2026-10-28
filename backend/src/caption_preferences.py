"""Validated caption defaults and per-generation overrides, without media encoding."""
from copy import deepcopy
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import text


class CaptionLayout(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    y: float = Field(default=0.78, ge=0.1, le=0.9)
    wordsPerLine: int = Field(default=4, ge=1, le=8)
    background: bool = False
    uppercase: bool = False
    karaoke: bool = False
    accent: Annotated[str, StringConstraints(pattern=r'^#[0-9A-Fa-f]{6}$')] = '#D6F777'


async def load_caption_preferences(db, user_id: str) -> dict:
    result = await db.execute(text('SELECT default_font_family, default_font_size, default_font_color, default_caption_style FROM users WHERE id = :user_id'), {'user_id': user_id})
    row = result.mappings().first()
    return dict(row) if row else {}


def apply_caption_layout(template: dict, layout: dict) -> dict:
    style = CaptionLayout.model_validate(layout)
    result = deepcopy(template)
    result.update(position_y=style.y, max_words_per_line=style.wordsPerLine, background=style.background,
                  background_color='#000000A6' if style.background else None, uppercase=style.uppercase,
                  animation='karaoke' if style.karaoke else 'none', highlight_color=style.accent if style.karaoke else template.get('font_color', '#FFFFFF'),
                  emphasis_color=style.accent if style.karaoke else None, word_pop=style.karaoke, emoji=False)
    return result


def editorial_defaults(preferences: dict) -> dict:
    from .editor_document import CaptionStyle
    layout = CaptionLayout.model_validate(preferences.get('default_caption_style') or {}).model_dump()
    return CaptionStyle(**layout, font=preferences.get('default_font_family') or 'TikTokSans-Regular',
                        size=round((preferences.get('default_font_size') or 24) * 1080 / 560),
                        color=preferences.get('default_font_color') or '#FFFFFF').model_dump()


def validate_caption_font(font: str, user_id: str):
    from .font_registry import find_font_path
    if not find_font_path(font, user_id=user_id):
        raise ValueError('Selected caption font is unavailable for this account')
