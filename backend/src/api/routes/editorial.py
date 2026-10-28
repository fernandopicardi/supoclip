"""Authenticated source-clock editing, separate from automatic clip selection."""
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...editor_document import RevisionConflict, atomic_json, editor_lock
from ...editorial_document import EditorialDocument, OPERATIONS, change, edit_operations, new_id, read_json
from ...services import editorial_service as service
from ...utils.async_helpers import run_in_thread
from .tasks import _get_user_id_from_headers

router = APIRouter(prefix='/editorial', tags=['editorial'])


async def owner(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await _get_user_id_from_headers(request, db)
    await db.close()
    return user_id


def directory(user_id: str, kind: str, item_id: str):
    try:
        return service.item_dir(user_id, kind, item_id)
    except FileNotFoundError:
        raise HTTPException(404, 'Not found') from None


def identifier(value: str):
    if not re.fullmatch(r'[a-f0-9]{32}', value):
        raise HTTPException(404, 'Not found')
    return value


async def payload(request: Request):
    if len(await request.body()) > 32 * 1024 * 1024:
        raise HTTPException(413, 'Request is too large')
    try:
        value = await request.json()
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise HTTPException(400, 'Expected a JSON object') from None


def revision(body):
    value = body.get('revision')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HTTPException(400, 'Expected a nonnegative revision')
    return value


def request_id(body):
    value = body.get('request_id')
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise HTTPException(400, 'A stable request_id is required for retries')
    return value


@router.post('/sources', status_code=202)
async def prepare_source(request: Request, file: UploadFile = File(...),
                         transcribe: bool = Form(True), user_id: str = Depends(owner)):
    source_id = new_id('source')
    path = service.owner_root(user_id)/'sources'/source_id
    path.mkdir(parents=True)
    digest, size = hashlib.sha256(), 0
    try:
        with (path/'media.mp4').open('wb') as output:
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size > 4*1024**3:
                    raise HTTPException(413, 'Source upload exceeds 4 GiB')
                digest.update(chunk)
                output.write(chunk)
        atomic_json(path/'source.json', {'source_id': source_id, 'sha256': digest.hexdigest(),
                    'bytes': size, 'status': 'queued'})
        await request.app.state.queue_adapter.enqueue_job('prepare_editorial_source', user_id, source_id, transcribe)
    except BaseException:
        (path/'media.mp4').unlink(missing_ok=True)
        atomic_json(path/'source.json', {'source_id': source_id, 'status': 'failed'})
        raise
    finally:
        await file.close()
    return read_json(path/'source.json')


@router.get('/sources/{source_id}')
async def get_source(source_id: str, user_id: str = Depends(owner)):
    return read_json(directory(user_id, 'sources', source_id)/'source.json')


@router.get('/sources/{source_id}/media')
async def source_media(source_id: str, user_id: str = Depends(owner)):
    from ...browser_media import browser_media
    path = browser_media(directory(user_id, 'sources', source_id))
    if not path.is_file():
        raise HTTPException(404, 'Media not found')
    return FileResponse(path, media_type='video/mp4', headers={'Cache-Control': 'private, no-store'})


@router.get('/sources')
async def list_sources(limit: int = 30, user_id: str = Depends(owner)):
    if not 1 <= limit <= 100:
        raise HTTPException(400, 'Limit must be between 1 and 100')
    return {'sources': await run_in_thread(service.list_items, user_id, 'sources', limit)}


@router.post('/sources/{source_id}/retry', status_code=202)
async def retry_source(source_id: str, request: Request, user_id: str = Depends(owner)):
    path = directory(user_id, 'sources', source_id)
    with editor_lock(path):
        state = read_json(path/'source.json')
        if state['status'] not in {'failed', 'awaiting_transcript'} or not (path/'media.mp4').exists():
            raise HTTPException(409, 'Only a failed or untranscribed source can be retried')
        state.update(status='queued')
        atomic_json(path/'source.json', state)
    await request.app.state.queue_adapter.enqueue_job('prepare_editorial_source', user_id, source_id, True)
    return {'source_id': source_id, 'status': 'queued'}


@router.put('/sources/{source_id}/transcript')
async def import_transcript(source_id: str, request: Request, user_id: str = Depends(owner)):
    path = directory(user_id, 'sources', source_id)
    body = await payload(request)
    if read_json(path/'source.json')['status'] not in {'awaiting_transcript', 'ready'}:
        raise HTTPException(409, 'Wait for source inspection before importing')
    try:
        return await run_in_thread(service.store_transcript, path, body.get('source_sha256'),
                                   body.get('words'), body.get('language', 'pt'), 'user_import')
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(400, str(exc)) from None


@router.get('/sources/{source_id}/transcript')
async def get_transcript(source_id: str, offset: int = 0, limit: int = 250,
                         start: float = 0, end: float | None = None, user_id: str = Depends(owner)):
    path = directory(user_id, 'sources', source_id)
    if not (path/'transcript.json').exists():
        raise HTTPException(409, 'Source transcript is not ready')
    if offset < 0 or not 1 <= limit <= 1000 or not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise HTTPException(400, 'Invalid transcript window or pagination')
    data = await run_in_thread(read_json, path/'transcript.json')
    words = [w for w in data['words'] if w['end'] > start and (end is None or w['start'] < end)]
    selected = words[offset:offset+limit]
    return {k: v for k, v in data.items() if k != 'words'} | {
        'total': len(words), 'offset': offset, 'words': selected,
        'text': ' '.join(w['text'] for w in selected),
        'next_offset': offset+len(selected) if offset+len(selected) < len(words) else None}


@router.get('/schema')
async def schema(user_id: str = Depends(owner)):
    return {'operations': OPERATIONS.json_schema(), 'clock': 'source seconds',
            'atomic': True, 'word_edge_warning': 'Word timings are approximate; inspect context and listen to joins'}


@router.get('/caption-defaults')
async def caption_defaults(user_id: str = Depends(owner), db: AsyncSession = Depends(get_db)):
    from ...caption_preferences import load_caption_preferences, editorial_defaults
    return {'captions': editorial_defaults(await load_caption_preferences(db, user_id))}


@router.post('/edits', status_code=201)
async def create_edit(request: Request, user_id: str = Depends(owner), db: AsyncSession = Depends(get_db)):
    body = await payload(request)
    directory(user_id, 'sources', body.get('source_id', ''))
    try:
        from ...caption_preferences import load_caption_preferences, editorial_defaults
        preferences = await load_caption_preferences(db, user_id)
        captions = editorial_defaults(preferences)
        from ...caption_preferences import validate_caption_font
        validate_caption_font(captions['font'], user_id)
        return await run_in_thread(service.create_edit, user_id, body['source_id'], body.get('title', ''), captions)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.get('/edits/{edit_id}')
async def get_edit(edit_id: str, user_id: str = Depends(owner)):
    directory(user_id, 'edits', edit_id)
    return await run_in_thread(service.get_edit, user_id, edit_id)


@router.get('/edits/{edit_id}/preview-data')
async def preview_data(edit_id: str, user_id: str = Depends(owner)):
    path = directory(user_id, 'edits', edit_id)
    doc = EditorialDocument.model_validate(read_json(path/'draft.json')['document'])
    source = read_json(directory(user_id, 'sources', doc.source_id)/'source.json')
    from ...services.editor_service import caption_looks
    return {'source': source, 'words': await run_in_thread(service.source_words, user_id, doc.source_id),
            'captionLooks': caption_looks()}


@router.post('/edits/{edit_id}/draft')
async def save_draft(edit_id: str, request: Request, user_id: str = Depends(owner)):
    path, body = directory(user_id, 'edits', edit_id), await payload(request)
    expected, retry_id = revision(body), request_id(body)
    def update(current):
        updated = EditorialDocument.model_validate(body.get('document'))
        if updated.source_id != current.source_id:
            raise ValueError('A montage cannot change its source')
        source = read_json(directory(user_id, 'sources', current.source_id)/'source.json')
        updated.validate_source(source['duration'])
        from ...caption_preferences import validate_caption_font
        validate_caption_font(updated.captions.font, user_id)
        words = service.source_words(user_id, current.source_id)
        valid = {clip.id+':'+w['id'] for clip in updated.clips for w in words
                 if w['start'] >= clip.start and w['end'] <= clip.end}
        for key, text in updated.word_text.items():
            if current.word_text.get(key) == text:
                continue
            if key not in valid or not isinstance(text, str) or not text.strip() or len(text) > 200:
                raise ValueError('Caption correction must reference a word in its clip (1–200 characters)')
        checkpoint = hashlib.sha256(retry_id.encode()).hexdigest()[:32]
        atomic_json(path/f'checkpoint-{checkpoint}.json', {'revision': expected, 'document': current.model_dump()})
        return updated
    try:
        return await run_in_thread(change, path, expected, retry_id, body, update)
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from None


@router.get('/edits')
async def list_edits(limit: int = 30, user_id: str = Depends(owner)):
    if not 1 <= limit <= 100:
        raise HTTPException(400, 'Limit must be between 1 and 100')
    return {'edits': await run_in_thread(service.list_items, user_id, 'edits', limit)}


@router.post('/edits/{edit_id}/operations')
async def apply_operations(edit_id: str, request: Request, user_id: str = Depends(owner)):
    path, body = directory(user_id, 'edits', edit_id), await payload(request)
    doc = EditorialDocument.model_validate(read_json(path/'draft.json')['document'])
    source = read_json(directory(user_id, 'sources', doc.source_id)/'source.json')
    words = await run_in_thread(service.source_words, user_id, doc.source_id)
    def update(current):
        updated = edit_operations(current, body.get('operations', []), source['duration'], words)
        if any(op.get('op') == 'set_captions' for op in body.get('operations', [])):
            from ...caption_preferences import validate_caption_font
            validate_caption_font(updated.captions.font, user_id)
        return updated
    try:
        return await run_in_thread(change, path, revision(body), request_id(body), body,
            update)
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from None


@router.post('/edits/{edit_id}/checkpoints', status_code=201)
async def create_checkpoint(edit_id: str, request: Request, user_id: str = Depends(owner)):
    path, body = directory(user_id, 'edits', edit_id), await payload(request)
    with editor_lock(path):
        state = read_json(path/'draft.json')
        if state['revision'] != revision(body):
            raise HTTPException(409, 'The edit changed; reread it')
        checkpoint = hashlib.sha256(request_id(body).encode()).hexdigest()[:32]
        target = path/f'checkpoint-{checkpoint}.json'
        if target.exists():
            saved = read_json(target)
            if saved['revision'] != state['revision']:
                raise HTTPException(409, 'Checkpoint request ID already used at another revision')
        else:
            atomic_json(target, {'revision': state['revision'], 'document': state['document']})
    return {'checkpoint_id': checkpoint, 'revision': state['revision']}


@router.post('/edits/{edit_id}/checkpoints/{checkpoint_id}/restore')
async def restore_checkpoint(edit_id: str, checkpoint_id: str, request: Request, user_id: str = Depends(owner)):
    path, body = directory(user_id, 'edits', edit_id), await payload(request)
    target = path/f'checkpoint-{identifier(checkpoint_id)}.json'
    if not target.exists():
        raise HTTPException(404, 'Checkpoint not found')
    try:
        return await run_in_thread(change, path, revision(body), request_id(body),
            body | {'checkpoint_id': checkpoint_id},
            lambda _: EditorialDocument.model_validate(read_json(target)['document']))
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from None


@router.post('/edits/{edit_id}/exports', status_code=202)
async def export_edit(edit_id: str, request: Request, user_id: str = Depends(owner)):
    path, body = directory(user_id, 'edits', edit_id), await payload(request)
    job_id = hashlib.sha256(request_id(body).encode()).hexdigest()[:32]
    with editor_lock(path):
        target = path/f'request-{job_id}.json'
        if target.exists():
            saved = read_json(target)
            if saved['revision'] != revision(body):
                raise HTTPException(409, 'Export request ID was used at another revision')
            return {'job_id': job_id, **read_json(path/f'job-{job_id}.json')}
        state = read_json(path/'draft.json')
        if state['revision'] != revision(body):
            raise HTTPException(409, 'The edit changed; reread it')
        duration = service.timeline(EditorialDocument.model_validate(state['document']))['playback_seconds']
        if not duration:
            raise HTTPException(400, 'The edit has no playable footage')
        atomic_json(target, {'revision': state['revision'], 'document': state['document']})
        atomic_json(path/f'job-{job_id}.json', {'status': 'queued', 'progress': 0, 'revision': state['revision']})
    try:
        await request.app.state.queue_adapter.enqueue_job('export_editorial', user_id, edit_id, job_id)
    except Exception:
        atomic_json(path/f'job-{job_id}.json', {'status': 'failed', 'error': 'Could not enqueue export'})
        raise HTTPException(503, 'Worker is unavailable; retry with a new request_id') from None
    return {'job_id': job_id, 'status': 'queued', 'revision': state['revision']}


@router.get('/edits/{edit_id}/exports/{job_id}')
async def get_export(edit_id: str, job_id: str, user_id: str = Depends(owner)):
    target = directory(user_id, 'edits', edit_id)/f'job-{identifier(job_id)}.json'
    if not target.exists():
        raise HTTPException(404, 'Export not found')
    return service.export_state(target.parent, job_id)


@router.delete('/edits/{edit_id}/exports/{job_id}')
async def cancel_export(edit_id: str, job_id: str, user_id: str = Depends(owner)):
    path = directory(user_id, 'edits', edit_id)
    target = path/f'job-{identifier(job_id)}.json'
    if not target.exists():
        raise HTTPException(404, 'Export not found')
    if read_json(target)['status'] not in {'completed', 'failed', 'cancelled'}:
        (path/f'cancel-{job_id}').touch()
    return {'cancel_requested': True}


@router.get('/edits/{edit_id}/exports/{job_id}/{asset}')
async def export_asset(edit_id: str, job_id: str, asset: str, at: float = 0, user_id: str = Depends(owner)):
    path = directory(user_id, 'edits', edit_id)
    identifier(job_id)
    if asset not in {'file', 'map', 'frame'}:
        raise HTTPException(404, 'Not found')
    if not (path/f'export-{job_id}.mp4').exists():
        raise HTTPException(409, 'Wait for the export to finish')
    if asset == 'map':
        return read_json(path/f'map-{job_id}.json')
    if asset == 'file':
        return FileResponse(path/f'export-{job_id}.mp4', media_type='video/mp4', filename='editorial.mp4')
    state = read_json(path/f'job-{job_id}.json')
    if not 0 <= at < state['duration']:
        raise HTTPException(400, 'Frame time must be in exported playback seconds')
    frame = path/f'frame-{job_id}-{round(at*1000)}.jpg'
    if not frame.exists():
        try:
            await run_in_thread(subprocess.run, ['ffmpeg', '-v', 'error', '-y', '-ss', str(at), '-i',
                str(path/f'export-{job_id}.mp4'), '-frames:v', '1', '-update', '1', str(frame)],
                check=True, capture_output=True)
        except subprocess.SubprocessError:
            raise HTTPException(500, 'Could not extract frame') from None
    return FileResponse(frame, media_type='image/jpeg')
