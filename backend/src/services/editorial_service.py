"""Private source preparation and immutable editorial export jobs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from ..config import get_config
from ..editor_document import EditDocument, Segment, Word, atomic_json, editor_lock, run_render, write_ass
from ..editorial_document import EditorialDocument, kept_ranges, new_id, read_json, timeline


def owner_root(user_id: str) -> Path:
    return Path(get_config().temp_dir) / 'editorial' / hashlib.sha256(user_id.encode()).hexdigest()


def item_dir(user_id: str, kind: str, item_id: str) -> Path:
    if kind not in {'sources', 'edits'} or not isinstance(item_id, str) or not re.fullmatch(r'(source|edit)_[a-f0-9]{32}', item_id):
        raise FileNotFoundError('Not found')
    path = owner_root(user_id) / kind / item_id
    if not path.is_dir():
        raise FileNotFoundError('Not found')
    return path


def probe(path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    if not video:
        raise ValueError('Source has no video stream')
    duration = float(data['format']['duration'])
    if not math.isfinite(duration) or duration <= 0 or duration > get_config().max_video_duration:
        raise ValueError('Source duration exceeds the configured limit')
    return {'duration': duration, 'width': video['width'], 'height': video['height'],
            'has_audio': any(s['codec_type'] == 'audio' for s in data['streams'])}


def store_transcript(directory: Path, source_hash: str, words: list[dict], language: str, origin: str) -> dict:
    metadata = read_json(directory / 'source.json')
    if source_hash != metadata['sha256']:
        raise ValueError('Transcript hash does not match this source')
    if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2,3}', language):
        raise ValueError('Use an ISO language code')
    if not words or len(words) > 200000:
        raise ValueError('A transcript requires between 1 and 200000 words')
    normalized = []
    previous = -1.0
    for index, word in enumerate(words):
        start, end, text = word.get('start'), word.get('end'), word.get('text')
        if (isinstance(start, bool) or isinstance(end, bool) or
            not isinstance(start, (float, int)) or not isinstance(end, (float, int)) or
            not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or
            end > metadata['duration'] + 0.1 or start < previous or
            not isinstance(text, str) or not text.strip() or len(text) > 120):
            raise ValueError('Invalid or unordered transcript word')
        previous = start
        normalized.append({'id': f'w_{source_hash[:16]}_{index}', 'start': start,
                           'end': end, 'text': text.strip()})
    payload = {'language': language, 'origin': origin, 'source_sha256': source_hash, 'words': normalized}
    with editor_lock(directory):
        path = directory / 'transcript.json'
        if path.exists() and read_json(path) != payload:
            raise ValueError('A source transcript is immutable; create another source to replace it')
        atomic_json(path, payload)
        metadata.update(status='ready', word_count=len(normalized), language=language)
        atomic_json(directory / 'source.json', metadata)
    return {k: v for k, v in payload.items() if k != 'words'} | {'word_count': len(normalized)}


async def prepare_editorial_source(ctx, user_id: str, source_id: str, transcribe: bool):
    directory = item_dir(user_id, 'sources', source_id)
    metadata = read_json(directory / 'source.json')
    if metadata['status'] == 'ready':
        return
    try:
        metadata.update(await asyncio.to_thread(probe, directory / 'media.mp4'))
        if not transcribe:
            metadata.update(status='awaiting_transcript')
            atomic_json(directory / 'source.json', metadata)
            return
        metadata.update(status='transcribing')
        atomic_json(directory / 'source.json', metadata)
        from ..media.transcription import transcribe_with_whisper
        config = get_config()
        result = await asyncio.to_thread(transcribe_with_whisper, directory / 'media.mp4',
                                        config.whisper_model, config.transcription_language)
        words = [{'start': w['start'], 'end': w['end'], 'text': w['word']}
                 for segment in result['segments'] for w in segment.get('words', [])
                 if w['end'] > w['start'] and w['word'].strip()]
        store_transcript(directory, metadata['sha256'], words, result.get('language', 'pt'), 'local_whisper')
    except Exception:
        metadata.update(status='failed', error='Local source preparation failed; check worker diagnostics')
        atomic_json(directory / 'source.json', metadata)
        raise


def source_words(user_id: str, source_id: str) -> list[dict]:
    return read_json(item_dir(user_id, 'sources', source_id) / 'transcript.json')['words']


def create_edit(user_id: str, source_id: str, title: str, captions: dict | None = None) -> dict:
    source = read_json(item_dir(user_id, 'sources', source_id) / 'source.json')
    if source['status'] != 'ready':
        raise ValueError('Wait for the source transcript to be ready')
    edit_id = new_id('edit')
    directory = owner_root(user_id) / 'edits' / edit_id
    doc = EditorialDocument(source_id=source_id, title=title, **({"captions": captions} if captions is not None else {}))
    atomic_json(directory / 'draft.json', {'revision': 0, 'document': doc.model_dump(), 'requests': {}})
    return {'edit_id': edit_id, **get_edit(user_id, edit_id)}


def get_edit(user_id: str, edit_id: str) -> dict:
    directory = item_dir(user_id, 'edits', edit_id)
    state = read_json(directory / 'draft.json')
    doc = EditorialDocument.model_validate(state['document'])
    exports = [{'job_id': p.stem[4:], **export_state(directory, p.stem[4:])} for p in sorted(
        directory.glob('job-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]]
    return {'edit_id': edit_id, 'revision': state['revision'], 'document': doc.model_dump(),
            'timeline': timeline(doc), 'exports': exports}


def export_state(directory: Path, job_id: str) -> dict:
    state = read_json(directory/f'job-{job_id}.json')
    # The shared progress writer updates progress only. Preserve the immutable
    # request's revision in reads while the encode is in progress as well.
    state.setdefault('revision', read_json(directory/f'request-{job_id}.json')['revision'])
    return state


def list_items(user_id: str, kind: str, limit: int) -> list[dict]:
    root = owner_root(user_id)/kind
    filename = 'draft.json' if kind == 'edits' else 'source.json'
    entries = []
    for path in sorted(root.glob('*/'+filename), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        if kind == 'edits':
            state = read_json(path)
            entries.append({'edit_id': path.parent.name, 'title': state['document']['title'],
                            'source_id': state['document']['source_id'], 'revision': state['revision'],
                            'playback_seconds': timeline(EditorialDocument.model_validate(state['document']))['playback_seconds'],
                            'review_path': '/editorial/'+path.parent.name})
        else:
            entries.append(read_json(path))
    return entries


def render_editorial(directory: Path, job_id: str, snapshot: dict, user_id: str):
    """Encode once from the original. Separate audio/video concatenation avoids padding drift."""
    from ..clip_editor import _escape_filter_path
    from ..video_utils import ass_fonts_dir

    document = EditorialDocument.model_validate(snapshot['document'])
    source_dir = item_dir(user_id, 'sources', document.source_id)
    source = read_json(source_dir / 'source.json')
    words = source_words(user_id, document.source_id)
    document.validate_source(source['duration'])
    fps = 30
    width, height = (720, 1280) if document.framing.aspect == 'vertical' else (
        (720, 720) if document.framing.aspect == 'square' else (1280, 720))
    filters, videos, audios, caption_words, mapping, inputs = [], [], [], [], [], []
    cursor, frames = 0.0, 0
    for clip in document.clips:
        framing = clip.framing or document.framing
        scale = (max if framing.fit == 'cover' else min)(width/source['width'], height/source['height']) * framing.zoom
        rw, rh = max(width if framing.fit == 'cover' else 2, round(source['width']*scale/2)*2), max(2, round(source['height']*scale/2)*2)
        cw, ch = min(width, rw), min(height, rh)
        # Crop before upscaling: a 9:16 focus on a gallery tile must not
        # resize the entire 1440p gallery to an oversized intermediate frame.
        crop_w = min(source['width'], max(2, round(cw/scale/2)*2))
        crop_h = min(source['height'], max(2, round(ch/scale/2)*2))
        crop_x = max(0, min(source['width']-crop_w, round((rw-cw)*framing.x/scale/2)*2))
        crop_y = max(0, min(source['height']-crop_h, round((rh-ch)*framing.y/scale/2)*2))
        geometry = (f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={cw}:{ch},'
                    f'pad={width}:{height}:{(width-cw)*framing.x}:{(height-ch)*framing.y}:black,setsar=1')
        for start, end in kept_ranges(clip):
            index, length = len(videos), end-start
            target_frames = max(1, round((cursor+length)*fps)-frames)
            frames += target_frames
            # Seek each occurrence independently. Decoding a late first clip
            # from a single shared input buffers all earlier reordered clips.
            inputs += ['-threads', '1', '-ss', str(start), '-t', str(length), '-i', str(source_dir/'media.mp4')]
            filters.append(f'[{index}:v:0]setpts=PTS-STARTPTS,fps={fps},{geometry},'
                           f'tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame={target_frames},setpts=N/({fps}*TB)[v{index}]')
            videos.append(f'[v{index}]')
            if source['has_audio']:
                filters.append(f'[{index}:a:0]atrim=start=0:end={length},asetpts=PTS-STARTPTS[a{index}]')
                audios.append(f'[a{index}]')
            for word in words:
                a, b = max(start, word['start']), min(end, word['end'])
                # Do not caption a tiny remnant of a word at an approved edge.
                if b > a and b-a >= (word['end']-word['start']) * 0.5:
                    caption_words.append(Word(id=f'{clip.id}:{word["id"]}:{index}', start=cursor+a-start,
                                              end=cursor+b-start,
                                              text=document.word_text.get(clip.id+':'+word['id'], word['text'])))
            mapping.append({'clip_id': clip.id, 'source_id': document.source_id,
                            'source_start': start, 'source_end': end,
                            'playback_start': cursor, 'playback_end': cursor+length,
                            'framing': framing.model_dump()})
            cursor += length
    if not videos:
        raise ValueError('The edit has no playable footage')
    filters.append(''.join(videos)+f'concat=n={len(videos)}:v=1:a=0[video]')
    if audios:
        filters.append(''.join(audios)+f'concat=n={len(audios)}:v=0:a=1[audio]')
    caption_document = EditDocument(segments=[Segment(id='playback', start=0, end=cursor)],
                                    words=caption_words, captions=document.captions)
    ass = directory / f'captions-{job_id}.ass'
    write_ass(ass, caption_document, width, height)
    fonts = ass_fonts_dir(document.captions.font) or Path('fonts')
    filters.append(f'[video]ass={_escape_filter_path(ass)}:fontsdir={_escape_filter_path(fonts)}[outv]')
    graph = directory / f'filters-{job_id}.txt'
    graph.write_text(';'.join(filters))
    temporary, output = directory / f'.export-{job_id}.mp4', directory / f'export-{job_id}.mp4'
    command = ['ffmpeg', '-y', '-filter_complex_threads', '2', *inputs,
               '-filter_complex_script', str(graph), '-map', '[outv]']
    if audios:
        command += ['-map', '[audio]', '-c:a', 'aac', '-b:a', '192k']
    command += ['-c:v', 'libx264', '-threads', '4', '-preset', 'veryfast', '-crf', '20',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)]
    try:
        run_render(command, directory, job_id, cursor)
        if (directory/f'cancel-{job_id}').exists():
            raise InterruptedError('Export cancelled')
        temporary.replace(output)
        atomic_json(directory/f'map-{job_id}.json', {'revision': snapshot['revision'], 'ranges': mapping,
                    'playback_seconds': cursor, 'caption_words': [w.model_dump() for w in caption_words]})
        atomic_json(directory/f'job-{job_id}.json', {'status': 'completed', 'progress': 100,
                    'revision': snapshot['revision'], 'duration': cursor, 'width': width, 'height': height})
    finally:
        temporary.unlink(missing_ok=True)
        graph.unlink(missing_ok=True)


async def export_editorial(ctx, user_id: str, edit_id: str, job_id: str):
    directory = item_dir(user_id, 'edits', edit_id)
    job = read_json(directory/f'job-{job_id}.json')
    if job['status'] in {'completed', 'cancelled'}:
        return
    try:
        snapshot = read_json(directory/f'request-{job_id}.json')
        await asyncio.to_thread(render_editorial, directory, job_id, snapshot, user_id)
    except InterruptedError:
        atomic_json(directory/f'job-{job_id}.json', {'status': 'cancelled', 'progress': 0})
    except Exception:
        atomic_json(directory/f'job-{job_id}.json', {'status': 'failed', 'progress': 0,
                    'error': 'Export failed; check worker diagnostics'})
        raise
