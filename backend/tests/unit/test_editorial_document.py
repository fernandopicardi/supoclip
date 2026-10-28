import pytest

from src.editor_document import RevisionConflict, atomic_json
from src.editorial_document import (
    Clip, Cut, EditorialDocument, change, edit_operations, kept_ranges, read_json, timeline,
)


def fixture_document():
    return EditorialDocument(source_id='source_test', clips=[
        Clip(id='first', start=20, end=30, cuts=[Cut(id='a', start=22, end=24), Cut(id='b', start=23, end=25)]),
        Clip(id='second', start=0, end=5),
        Clip(id='repeat', start=20, end=30),
    ])


def test_union_counts_per_occurrence_and_keeps_playback_order():
    doc = fixture_document()
    assert kept_ranges(doc.clips[0]) == [(20, 22), (25, 30)]
    state = timeline(doc)
    assert state['ruler_seconds'] == 25
    assert state['playback_seconds'] == 22
    assert [c['playback_start'] for c in state['clips']] == [0, 7, 12]
    assert state['clips'][2]['kept_source_ranges'] == [(20, 30)]


def test_move_retains_cuts_and_repeated_word_is_occurrence_scoped():
    doc = fixture_document()
    words = [{'id': 'w1', 'start': 25.5, 'end': 26, 'text': 'assim'}]
    changed = edit_operations(doc, [
        {'op': 'move_clip', 'clip_id': 'first', 'index': 2},
        {'op': 'remove_words', 'clip_id': 'repeat', 'word_ids': ['w1']},
        {'op': 'set_word_text', 'clip_id': 'first', 'word_id': 'w1', 'text': 'português'},
    ], 40, words)
    assert [c.id for c in changed.clips] == ['second', 'repeat', 'first']
    assert [c.id for c in changed.clips[-1].cuts] == ['a', 'b']
    assert len(changed.clips[1].cuts) == 1
    assert changed.word_text == {'first:w1': 'português'}
    assert doc.word_text == {}  # input is not mutated


def test_invalid_batch_is_atomic_and_does_not_shift_or_drop_cuts():
    doc = fixture_document()
    before = doc.model_dump()
    with pytest.raises(ValueError, match='outside its clip'):
        edit_operations(doc, [
            {'op': 'move_clip', 'clip_id': 'first', 'index': 1},
            {'op': 'set_clip_range', 'clip_id': 'first', 'start': 26, 'end': 30},
        ], 40, [])
    assert doc.model_dump() == before


def test_split_distributes_overlapping_cuts_without_losing_them():
    doc = fixture_document()
    result = edit_operations(doc, [{'op': 'split_clip', 'clip_id': 'first', 'at': 23.5, 'new_clip_id': 'right'}], 40, [])
    assert timeline(result)['playback_seconds'] == timeline(doc)['playback_seconds']
    assert result.clips[0].end == result.clips[1].start == 23.5


def test_split_keeps_caption_corrections_on_the_right_occurrence():
    doc = fixture_document()
    doc.word_text['first:w1'] = 'Sam'
    result = edit_operations(doc, [{'op': 'split_clip', 'clip_id': 'first', 'at': 26, 'new_clip_id': 'right'}],
                             40, [{'id': 'w1', 'start': 27, 'end': 28, 'text': 'Sun'}])
    assert result.word_text['right:w1'] == 'Sam'


@pytest.mark.parametrize('operation', [
    {'op': 'insert_clip', 'index': 1, 'clip': {'id': 'first', 'start': 1, 'end': 2}},
    {'op': 'set_clip_range', 'clip_id': 'second', 'start': 0, 'end': 41},
    {'op': 'remove_words', 'clip_id': 'second', 'word_ids': ['not-a-real-id']},
    {'op': 'move_clip', 'clip_id': 'second', 'index': 99},
    {'op': 'add_cut', 'clip_id': 'second', 'cut': {'id': 'nan', 'start': float('nan'), 'end': 4}},
])
def test_rejects_unknown_ids_invalid_ranges_and_nonfinite_numbers(operation):
    with pytest.raises(ValueError):
        edit_operations(fixture_document(), [operation], 40, [])


def test_cas_idempotency_and_restore_never_rewind_revision(tmp_path):
    doc = fixture_document()
    atomic_json(tmp_path/'draft.json', {'revision': 0, 'document': doc.model_dump(), 'requests': {}})
    body = {'operations': [{'op': 'move_clip', 'clip_id': 'second', 'index': 0}]}
    result = change(tmp_path, 0, 'request1', body, lambda d: edit_operations(d, body['operations'], 40, []))
    assert result['revision'] == 1
    replay = change(tmp_path, 0, 'request1', body, lambda _: pytest.fail('replay changed state'))
    assert replay['revision'] == 1 and replay['replayed']
    with pytest.raises(RevisionConflict):
        change(tmp_path, 0, 'restore', {}, lambda _: doc)
    with pytest.raises(RevisionConflict):
        change(tmp_path, 1, 'request1', {'different': True}, lambda _: doc)
    restored = change(tmp_path, 1, 'restore', {}, lambda _: doc)
    assert restored['revision'] == 2
    assert restored['document'] == doc.model_dump()
    assert read_json(tmp_path/'draft.json')['revision'] == 2


def test_explicit_long_selection_has_no_short_clip_cap():
    doc = EditorialDocument(source_id='long', clips=[Clip(id='c', start=400, end=590)])
    doc.validate_source(7200)
    assert timeline(doc)['playback_seconds'] == 190
