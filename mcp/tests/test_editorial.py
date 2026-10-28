import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from supoclip_mcp import server


def test_tools_are_registered_and_atomic_contract_is_exposed():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {'supoclip_get_transcript_words', 'supoclip_create_edit', 'supoclip_apply_edit_operations',
            'supoclip_restore_checkpoint', 'supoclip_get_edit_frames'} <= names
    tool = next(t for t in tools if t.name == 'supoclip_apply_edit_operations')
    assert {'revision', 'request_id', 'operations'} <= set(tool.inputSchema['properties'])


def test_real_tool_dispatch_forwards_revision_and_idempotency(monkeypatch):
    request = AsyncMock(return_value={'revision': 3})
    monkeypatch.setattr(server, 'CLIENT', SimpleNamespace(request=request))
    async def run():
        result = await server.mcp.call_tool('supoclip_apply_edit_operations',
            {'edit_id': 'edit1', 'revision': 2, 'request_id': 'stable',
             'operations': [{'op': 'move_clip', 'clip_id': 'c', 'index': 0}]})
        return result
    asyncio.run(run())
    assert request.await_args.args == ('POST', '/editorial/edits/edit1/operations')
    assert request.await_args.kwargs['json_body']['revision'] == 2
    assert request.await_args.kwargs['json_body']['request_id'] == 'stable'
