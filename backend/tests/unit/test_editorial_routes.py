from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from src.api.routes import editorial
from src.config import get_config
from src.editor_document import atomic_json
from src.editorial_document import read_json
from src.services import editorial_service as service


@pytest.fixture
async def editorial_client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config(), 'temp_dir', str(tmp_path))
    app = FastAPI()
    app.state.queue_adapter = SimpleNamespace(enqueue_job=AsyncMock(return_value='job'))
    app.include_router(editorial.router)
    app.dependency_overrides[editorial.owner] = lambda: 'owner'
    source = 'source_' + 'a'*32
    root = service.owner_root('owner')/'sources'/source
    atomic_json(root/'source.json', {'source_id': source, 'sha256': 'abc', 'duration': 300, 'status': 'awaiting_transcript'})
    service.store_transcript(root, 'abc', [
        {'start': i, 'end': i+0.5, 'text': f'palavra{i}'} for i in range(200)
    ], 'pt', 'user_import')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client, source, app


async def test_transcript_pages_and_windows_keep_ids(editorial_client):
    http, source, _ = editorial_client
    page = (await http.get(f'/editorial/sources/{source}/transcript?limit=80')).json()
    second = (await http.get(f'/editorial/sources/{source}/transcript?offset=80&limit=80')).json()
    assert page['next_offset'] == 80 and second['offset'] == 80
    assert not set(w['id'] for w in page['words']) & set(w['id'] for w in second['words'])
    window = (await http.get(f'/editorial/sources/{source}/transcript?start=4&end=5')).json()
    assert window['words'][0]['id'] == page['words'][4]['id']


async def test_ownership_namespace_prevents_read_and_write(editorial_client):
    http, source, app = editorial_client
    edit = (await http.post('/editorial/edits', json={'source_id': source})).json()
    app.dependency_overrides[editorial.owner] = lambda: 'outsider'
    assert (await http.get(f'/editorial/sources/{source}')).status_code == 404
    assert (await http.get(f'/editorial/edits/{edit["edit_id"]}')).status_code == 404
    assert (await http.post('/editorial/edits', json={'source_id': source})).status_code == 404
    assert (await http.get('/editorial/edits')).json()['edits'] == []
    assert (await http.get('/editorial/sources')).json()['sources'] == []


async def test_discover_existing_edits_and_preserve_export_revision(editorial_client):
    http, source, _ = editorial_client
    edit = (await http.post('/editorial/edits', json={'source_id': source, 'title': 'Já aprovado'})).json()
    listed = (await http.get('/editorial/edits')).json()['edits']
    assert listed[0]['edit_id'] == edit['edit_id']
    assert listed[0]['title'] == 'Já aprovado'
    path = service.item_dir('owner', 'edits', edit['edit_id'])
    job_id = 'a'*32
    atomic_json(path/f'request-{job_id}.json', {'revision': 7})
    atomic_json(path/f'job-{job_id}.json', {'status': 'rendering', 'progress': 20})
    state = (await http.get(f'/editorial/edits/{edit["edit_id"]}/exports/{job_id}')).json()
    assert state['revision'] == 7 and state['progress'] == 20


async def test_mcp_style_roundtrip_and_manual_conflict(editorial_client):
    http, source, app = editorial_client
    edit = (await http.post('/editorial/edits', json={'source_id': source, 'title': 'Teste'})).json()
    base = f'/editorial/edits/{edit["edit_id"]}'
    cp = (await http.post(base+'/checkpoints', json={'revision': 0, 'request_id': 'before'})).json()
    body = {'revision': 0, 'request_id': 'insert', 'operations': [
        {'op': 'insert_clip', 'index': 0, 'clip': {'id': 'a', 'start': 1, 'end': 190}}]}
    result = await http.post(base+'/operations', json=body)
    assert result.status_code == 200
    assert result.json()['timeline']['playback_seconds'] == 189
    assert (await http.post(base+'/operations', json=body)).json()['replayed']
    bad = {'revision': 1, 'request_id': 'invalid', 'operations': [
        {'op': 'add_cut', 'clip_id': 'a', 'cut': {'id': 'bad', 'start': 0, 'end': 2}}]}
    assert (await http.post(base+'/operations', json=bad)).status_code == 400
    assert (await http.get(base)).json()['revision'] == 1
    assert (await http.post(base+f'/checkpoints/{cp["checkpoint_id"]}/restore',
        json={'revision': 0, 'request_id': 'restore'})).status_code == 409
    export = (await http.post(base+'/exports', json={'revision': 1, 'request_id': 'export'})).json()
    assert export['status'] == 'queued'
    args = app.state.queue_adapter.enqueue_job.await_args.args
    assert args[0] == 'export_editorial'
    assert (await http.post(base+'/exports', json={'revision': 1, 'request_id': 'export'})).json()['job_id'] == export['job_id']


async def test_transcript_import_requires_source_hash_and_is_immutable(editorial_client):
    http, source, _ = editorial_client
    data = {'source_sha256': 'wrong', 'words': [{'start': 0, 'end': 1, 'text': 'falso'}]}
    assert (await http.put(f'/editorial/sources/{source}/transcript', json=data)).status_code == 400
    data['source_sha256'] = 'abc'
    assert (await http.put(f'/editorial/sources/{source}/transcript', json=data)).status_code == 400


async def test_two_hour_word_transcript_is_separate_from_edit_document(editorial_client):
    http, _, _ = editorial_client
    source = 'source_'+'e'*32
    path = service.owner_root('owner')/'sources'/source
    atomic_json(path/'source.json', {'source_id': source, 'sha256': 'two-hour',
                'duration': 7200, 'status': 'awaiting_transcript'})
    service.store_transcript(path, 'two-hour', [
        {'start': i*0.35, 'end': i*0.35+0.2, 'text': f'palavra{i}'} for i in range(20000)
    ], 'pt', 'user_import')
    last = (await http.get(f'/editorial/sources/{source}/transcript?offset=19000&limit=1000')).json()
    assert last['total'] == 20000 and len(last['words']) == 1000 and last['next_offset'] is None
    assert last['words'][-1]['text'] == 'palavra19999'
    edit = (await http.post('/editorial/edits', json={'source_id': source})).json()
    assert edit['document']['source_id'] == source and 'words' not in edit['document']


async def test_source_preparation_can_bypass_transcription(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config(), 'temp_dir', str(tmp_path))
    source = 'source_'+'b'*32
    root = service.owner_root('owner')/'sources'/source
    atomic_json(root/'source.json', {'status': 'queued', 'sha256': 'abc'})
    monkeypatch.setattr(service, 'probe', lambda _: {'duration': 300, 'has_audio': True, 'width': 1280, 'height': 720})
    await service.prepare_editorial_source({}, 'owner', source, False)
    assert read_json(root/'source.json')['status'] == 'awaiting_transcript'
    assert not (root/'transcript.json').exists()


async def test_new_source_uses_whisper_even_if_default_provider_is_hosted(tmp_path, monkeypatch):
    from src.media import transcription
    config = get_config()
    monkeypatch.setattr(config, 'temp_dir', str(tmp_path))
    monkeypatch.setattr(config, 'transcription_provider', 'assemblyai')
    source = 'source_'+'f'*32
    root = service.owner_root('owner')/'sources'/source
    atomic_json(root/'source.json', {'status': 'queued', 'sha256': 'local'})
    monkeypatch.setattr(service, 'probe', lambda _: {'duration': 5, 'has_audio': True, 'width': 640, 'height': 360})
    called = []
    def local_whisper(*args):
        called.append(args)
        return {'language': 'pt', 'segments': [{'words': [{'start': 0.1, 'end': 0.4, 'word': 'local'}]}]}
    monkeypatch.setattr(transcription, 'transcribe_with_whisper', local_whisper)
    await service.prepare_editorial_source({}, 'owner', source, True)
    assert len(called) == 1 and called[0][0] == root/'media.mp4'
    assert read_json(root/'source.json')['status'] == 'ready'
    assert read_json(root/'transcript.json')['origin'] == 'local_whisper'
