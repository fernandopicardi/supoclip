"""MCP operations for explicit, reversible editing instead of automatic selection."""
from __future__ import annotations

import base64
import json

from mcp.types import ImageContent, TextContent


def register_editorial_tools(mcp, client, errors):
    def tool(name, readonly=False, idempotent=False):
        return mcp.tool(name=name, annotations={'readOnlyHint': readonly,
                        'destructiveHint': False, 'idempotentHint': idempotent,
                        'openWorldHint': False})

    async def call(method, path, body=None, params=None):
        return json.dumps(await client().request(method, '/editorial'+path,
                          json_body=body, params=params), ensure_ascii=False)

    @tool('supoclip_prepare_source')
    @errors
    async def prepare_source(path: str, transcribe: bool = True) -> str:
        """Upload a LOCAL video, prepare it without Ollama/automatic selection. Returns source_id and queued status. Read get_source until ready. transcribe=False awaits a hash-matched imported word transcript instead. No paid transcription API is used."""
        return json.dumps(await client().upload_source(path, transcribe), ensure_ascii=False)

    @tool('supoclip_get_source', readonly=True)
    @errors
    async def get_source(source_id: str) -> str:
        """Read preparation status, duration, SHA256 and transcript availability."""
        return await call('GET', f'/sources/{source_id}')

    @tool('supoclip_list_sources', readonly=True)
    @errors
    async def list_sources(limit: int = 30) -> str:
        """List your prepared editorial sources and their SHA256/status. Reuse a matching ready source instead of uploading and transcribing it again."""
        return await call('GET', '/sources', params={'limit': limit})

    @tool('supoclip_list_edits', readonly=True)
    @errors
    async def list_edits(limit: int = 30) -> str:
        """Find your DIRECTED montages by title, ID, duration and review path. Use this to discover an existing editorial project; the legacy list_tasks describes automatic clipping tasks."""
        return await call('GET', '/edits', params={'limit': limit})

    @tool('supoclip_retry_source')
    @errors
    async def retry_source(source_id: str) -> str:
        """Retry failed source preparation or transcribe a source awaiting import. Does not select clips."""
        return await call('POST', f'/sources/{source_id}/retry')

    @tool('supoclip_import_transcript', idempotent=True)
    @errors
    async def import_transcript(source_id: str, source_sha256: str, words: list[dict], language: str = 'pt') -> str:
        """Import existing local transcription for the EXACT SHA256-matched video. words: [{start: source seconds, end: source seconds, text: spoken word}]. Original timings are approximate. The transcript becomes immutable; get_transcript_words returns its real stable IDs."""
        return await call('PUT', f'/sources/{source_id}/transcript',
                          {'source_sha256': source_sha256, 'words': words, 'language': language})

    @tool('supoclip_get_transcript', readonly=True)
    @errors
    async def get_transcript(source_id: str, offset: int = 0, limit: int = 250,
                             start: float = 0, end: float | None = None) -> str:
        """Read paginated source transcript text AND word IDs/timings. Follow next_offset in the same source window until null; total counts words in the window. Read surrounding context before selecting. Does not summarize unseen pages."""
        params = {'offset': offset, 'limit': limit, 'start': start}
        if end is not None:
            params['end'] = end
        return await call('GET', f'/sources/{source_id}/transcript', params=params)

    @tool('supoclip_get_transcript_words', readonly=True)
    @errors
    async def get_transcript_words(source_id: str, start: float = 0, end: float | None = None,
                                   offset: int = 0, limit: int = 250) -> str:
        """Read actual stable word IDs in a source-time window, not segment IDs. Pagination matches get_transcript. Word timestamps are approximate, not verified acoustic cut boundaries."""
        return await get_transcript(source_id, offset, limit, start, end)

    @tool('supoclip_get_edit_schema', readonly=True)
    @errors
    async def get_edit_schema() -> str:
        """Read the current validated schema of all edit operations before constructing a batch. Includes insert/move/split/remove clip, set_clip_range, add/set/remove_cut, remove_words, set_word_text, set_captions, set_framing."""
        return await call('GET', '/schema')

    @tool('supoclip_create_edit')
    @errors
    async def create_edit(source_id: str, title: str = '') -> str:
        """Create an EMPTY editable timeline from a ready source. Does not generate or choose clips. Add complete contextual passages with insert_clip operations."""
        return await call('POST', '/edits', {'source_id': source_id, 'title': title})

    @tool('supoclip_get_edit', readonly=True)
    @errors
    async def get_edit(edit_id: str) -> str:
        """Read current document, revision, per-clip cuts and source/ruler/playback mapping. User edits are authoritative. Reread after each structural batch or conflict; never overwrite a newer revision."""
        return await call('GET', f'/edits/{edit_id}')

    @tool('supoclip_apply_edit_operations', idempotent=True)
    @errors
    async def apply_edit_operations(edit_id: str, revision: int, request_id: str, operations: list[dict]) -> str:
        """Apply 1-100 TYPED operations atomically at expected revision. Read get_edit_schema first. Every start/end/cut uses SOURCE seconds. Clips are distinct occurrences; cuts stay attached to clip_id through moves. Same request_id+payload replays safely; reuse it after uncertain timeout. Conflicts require reread and reconciliation, not forced save. Rejects invalid cuts instead of moving/removing them silently. Checkpoint before edits. remove_words uses exact timestamps and requires listening; prefer explicit pause-safe add_cut boundaries. set_word_text changes only captions, not audio. No automatic sentence repair, filler deletion, teasers or short-clip cap runs."""
        return await call('POST', f'/edits/{edit_id}/operations',
                          {'revision': revision, 'request_id': request_id, 'operations': operations})

    @tool('supoclip_create_checkpoint', idempotent=True)
    @errors
    async def create_checkpoint(edit_id: str, revision: int, request_id: str) -> str:
        """Save current timeline before edits. Requires current revision; use a stable unique request_id."""
        return await call('POST', f'/edits/{edit_id}/checkpoints', {'revision': revision, 'request_id': request_id})

    @tool('supoclip_restore_checkpoint', idempotent=True)
    @errors
    async def restore_checkpoint(edit_id: str, checkpoint_id: str, revision: int, request_id: str) -> str:
        """Restore a checkpoint ONLY after considering manual edits since it. Expected revision prevents racing newer work. Restore creates a new revision rather than rewinding revision numbers."""
        return await call('POST', f'/edits/{edit_id}/checkpoints/{checkpoint_id}/restore',
                          {'revision': revision, 'request_id': request_id})

    @tool('supoclip_export_edit', idempotent=True)
    @errors
    async def export_edit(edit_id: str, revision: int, request_id: str) -> str:
        """Queue local H264/AAC MP4 rendering of an immutable revision. Does not truncate duration or change explicit selections. Source-clock caption timing is remapped through cuts and clip order. Returns job_id; inspect status separately."""
        return await call('POST', f'/edits/{edit_id}/exports', {'revision': revision, 'request_id': request_id})

    @tool('supoclip_get_edit_export', readonly=True)
    @errors
    async def get_edit_export(edit_id: str, job_id: str) -> str:
        """Read queued/rendering/completed/failed/cancelled status and render progress."""
        return await call('GET', f'/edits/{edit_id}/exports/{job_id}')

    @tool('supoclip_cancel_edit_export', idempotent=True)
    @errors
    async def cancel_edit_export(edit_id: str, job_id: str) -> str:
        """Request cancellation of this render without changing the edit or its source."""
        return await call('DELETE', f'/edits/{edit_id}/exports/{job_id}')

    @tool('supoclip_download_edit_export', readonly=True)
    @errors
    async def download_edit_export(edit_id: str, job_id: str) -> str:
        """Download completed MP4 to the configured local download directory."""
        c = client()
        return json.dumps(await c.download(f'/editorial/edits/{edit_id}/exports/{job_id}/file',
                          c.settings.download_dir, f'editorial-{edit_id}-{job_id}.mp4'))

    @tool('supoclip_get_edit_source_map', readonly=True)
    @errors
    async def get_edit_source_map(edit_id: str, job_id: str) -> str:
        """Read exported source-to-playback ranges, revision and caption words to verify the actual render, not the current draft."""
        return await call('GET', f'/edits/{edit_id}/exports/{job_id}/map')

    @tool('supoclip_get_edit_frames', readonly=True)
    @errors
    async def get_edit_frames(edit_id: str, job_id: str, playback_seconds: list[float]):
        """Inspect 1-12 still images from a COMPLETED export, in effective playback seconds. Does not validate audio or naturalness of joins."""
        if not 1 <= len(playback_seconds) <= 12:
            raise ValueError('Request between 1 and 12 frames')
        c, content = client(), []
        for index, at in enumerate(playback_seconds):
            result = await c.download(f'/editorial/edits/{edit_id}/exports/{job_id}/frame',
                c.settings.download_dir, f'editorial-frame-{index}.jpg', params={'at': at})
            from pathlib import Path
            content.append(TextContent(type='text', text=f'{at}s effective playback'))
            content.append(ImageContent(type='image', mimeType='image/jpeg',
                           data=base64.b64encode(Path(result['path']).read_bytes()).decode()))
        return content
