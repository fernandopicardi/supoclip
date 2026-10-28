"""Source-clock editorial timelines. Never repair or shorten explicit selections."""
from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .editor_document import CaptionStyle, Framing, Model, RevisionConflict, atomic_json, editor_lock


def new_id(prefix: str) -> str:
    return prefix + '_' + uuid.uuid4().hex


class Cut(Model):
    id: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start:
            raise ValueError('Cut end must follow start')
        return self


class Clip(Model):
    id: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    cuts: list[Cut] = Field(default_factory=list, max_length=500)
    framing: Framing | None = None


class EditorialDocument(Model):
    version: Literal[1] = 1
    source_id: str
    title: str = Field(default='', max_length=300)
    clips: list[Clip] = Field(default_factory=list, max_length=500)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    framing: Framing = Field(default_factory=Framing)
    # Caption corrections belong to word occurrences, not every repeated word.
    word_text: dict[str, str] = Field(default_factory=dict, max_length=20000)

    def validate_source(self, duration: float):
        if len({c.id for c in self.clips}) != len(self.clips):
            raise ValueError('Clip IDs must be unique')
        for clip in self.clips:
            if clip.end <= clip.start or clip.end > duration + 0.001:
                raise ValueError('Clip range is outside the source')
            if len({cut.id for cut in clip.cuts}) != len(clip.cuts):
                raise ValueError('Cut IDs must be unique within each clip')
            if any(t.start < clip.start or t.end > clip.end for t in clip.cuts):
                raise ValueError('A cut is outside its clip; adjust the cut explicitly')


def kept_ranges(clip: Clip) -> list[tuple[float, float]]:
    """Subtract the union of cuts for this occurrence of the source."""
    merged: list[list[float]] = []
    for cut in sorted(clip.cuts, key=lambda t: t.start):
        if merged and cut.start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], cut.end)
        else:
            merged.append([cut.start, cut.end])
    cursor, kept = clip.start, []
    for start, end in merged:
        if start > cursor:
            kept.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < clip.end:
        kept.append((cursor, clip.end))
    return kept


def timeline(document: EditorialDocument) -> dict:
    ruler, playback, clips = 0.0, 0.0, []
    for clip in document.clips:
        ranges = kept_ranges(clip)
        duration = sum(e - s for s, e in ranges)
        clips.append({**clip.model_dump(), 'ruler_start': ruler,
                      'ruler_end': ruler + clip.end - clip.start,
                      'playback_start': playback, 'playback_end': playback + duration,
                      'kept_source_ranges': ranges})
        ruler += clip.end - clip.start
        playback += duration
    return {'clips': clips, 'ruler_seconds': ruler, 'playback_seconds': playback,
            'time_base': 'clip start/end and cut start/end are source seconds; ruler includes cuts; playback excludes their union'}


class Insert(Model):
    op: Literal['insert_clip']
    index: int = Field(ge=0)
    clip: Clip


class Target(Model):
    clip_id: str


class Move(Target):
    op: Literal['move_clip']
    index: int = Field(ge=0)


class RemoveClip(Target):
    op: Literal['remove_clip']


class SetRange(Target):
    op: Literal['set_clip_range']
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class Split(Target):
    op: Literal['split_clip']
    at: float = Field(ge=0)
    new_clip_id: str = Field(min_length=1, max_length=100)


class AddCut(Target):
    op: Literal['add_cut']
    cut: Cut


class SetCut(Target):
    op: Literal['set_cut']
    cut: Cut


class RemoveCut(Target):
    op: Literal['remove_cut']
    cut_id: str


class RemoveWords(Target):
    op: Literal['remove_words']
    word_ids: list[str] = Field(min_length=1, max_length=200)


class SetWord(Target):
    op: Literal['set_word_text']
    word_id: str
    text: str = Field(max_length=120)


class SetFraming(Model):
    op: Literal['set_framing']
    clip_id: str | None = None
    framing: Framing


class SetCaptions(Model):
    op: Literal['set_captions']
    captions: CaptionStyle


Operation = Annotated[Insert | Move | RemoveClip | SetRange | Split | AddCut | SetCut |
                      RemoveCut | RemoveWords | SetWord | SetFraming | SetCaptions,
                      Field(discriminator='op')]
OPERATIONS = TypeAdapter(list[Operation])


def edit_operations(document: EditorialDocument, raw: list[dict], duration: float, words: list[dict]) -> EditorialDocument:
    if not 1 <= len(raw) <= 100:
        raise ValueError('Use between 1 and 100 operations per batch')
    operations = OPERATIONS.validate_python(raw)
    doc = document.model_copy(deep=True)
    word_map = {w['id']: w for w in words}
    for operation in operations:
        if isinstance(operation, Insert):
            if operation.index > len(doc.clips):
                raise ValueError('Insertion index is outside the timeline')
            doc.clips.insert(operation.index, operation.clip.model_copy(deep=True))
        elif isinstance(operation, SetCaptions):
            doc.captions = operation.captions
        elif isinstance(operation, SetFraming) and operation.clip_id is None:
            doc.framing = operation.framing
        else:
            clip = next((c for c in doc.clips if c.id == operation.clip_id), None)
            if clip is None:
                raise ValueError('Unknown clip ID')
            if isinstance(operation, Move):
                if operation.index >= len(doc.clips):
                    raise ValueError('Move index is outside the timeline')
                doc.clips.remove(clip)
                doc.clips.insert(operation.index, clip)
            elif isinstance(operation, RemoveClip):
                doc.clips.remove(clip)
            elif isinstance(operation, SetRange):
                clip.start, clip.end = operation.start, operation.end
            elif isinstance(operation, Split):
                if not clip.start < operation.at < clip.end:
                    raise ValueError('Split must be inside the clip')
                right = clip.model_copy(deep=True, update={'id': operation.new_clip_id, 'start': operation.at})
                for word in words:
                    correction = clip.id + ':' + word['id']
                    if word['end'] > operation.at and correction in doc.word_text:
                        doc.word_text[right.id + ':' + word['id']] = doc.word_text[correction]
                right.cuts = [c.model_copy(update={'start': max(c.start, operation.at)}) for c in clip.cuts if c.end > operation.at]
                clip.cuts = [c.model_copy(update={'end': min(c.end, operation.at)}) for c in clip.cuts if c.start < operation.at]
                clip.end = operation.at
                doc.clips.insert(doc.clips.index(clip) + 1, right)
            elif isinstance(operation, AddCut):
                clip.cuts.append(operation.cut)
            elif isinstance(operation, (RemoveCut, SetCut)):
                cut_id = operation.cut.id if isinstance(operation, SetCut) else operation.cut_id
                cut = next((c for c in clip.cuts if c.id == cut_id), None)
                if cut is None:
                    raise ValueError('Unknown cut ID')
                index = clip.cuts.index(cut)
                clip.cuts.pop(index)
                if isinstance(operation, SetCut):
                    clip.cuts.insert(index, operation.cut)
            elif isinstance(operation, (RemoveWords, SetWord)):
                ids = operation.word_ids if isinstance(operation, RemoveWords) else [operation.word_id]
                for word_id in ids:
                    word = word_map.get(word_id)
                    if word is None or word['start'] < clip.start or word['end'] > clip.end:
                        raise ValueError('Word must belong entirely to the selected clip; timestamps are approximate')
                    if isinstance(operation, RemoveWords):
                        clip.cuts.append(Cut(id=new_id('cut'), start=word['start'], end=word['end']))
                    else:
                        doc.word_text[clip.id + ':' + word_id] = operation.text
            elif isinstance(operation, SetFraming):
                clip.framing = operation.framing
        # Reject invalid intermediate states rather than silently losing cuts.
        doc.validate_source(duration)
    return doc


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def change(directory: Path, revision: int, request_id: str, request: dict, transform) -> dict:
    """CAS, audit and idempotency are committed in one atomic state file."""
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, allow_nan=False).encode()).hexdigest()
    with editor_lock(directory):
        state = read_json(directory / 'draft.json')
        previous = state.get('requests', {}).get(request_id)
        if previous:
            if previous['fingerprint'] != fingerprint:
                raise RevisionConflict('Request ID was already used for another operation')
            return {**deepcopy(previous['result']), 'replayed': True}
        if state['revision'] != revision:
            raise RevisionConflict('The edit changed; reread it before applying or restoring')
        document = transform(EditorialDocument.model_validate(state['document']))
        result = {'revision': revision + 1, 'document': document.model_dump(), 'timeline': timeline(document)}
        state.update(revision=revision + 1, document=document.model_dump())
        state.setdefault('requests', {})[request_id] = {'fingerprint': fingerprint, 'result': result}
        # Bound the durable retry window; never silently replay an evicted ID.
        if len(state['requests']) > 1000:
            raise ValueError('This edit reached its operation history limit; create another edit')
        atomic_json(directory / 'draft.json', state)
        return result
