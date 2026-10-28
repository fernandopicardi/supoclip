"""Launch the local stdio server without placing credentials in Codex config."""
from pathlib import Path
import os
import sys

from dotenv import dotenv_values


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python local.py PATH_TO_PRIVATE_ENV')
    private = dotenv_values(Path(sys.argv[1]).resolve(strict=True))
    key = private.get('SUPOCLIP_MCP_TOKEN') or private.get('SUPOCLIP_API_KEY')
    if key:
        os.environ['SUPOCLIP_API_KEY'] = key
    elif private.get('SUPOCLIP_USER_ID') and private.get('BACKEND_AUTH_SECRET'):
        # Documented self-host authentication. No unsigned mode is enabled.
        os.environ.pop('SUPOCLIP_API_KEY', None)
        os.environ['SUPOCLIP_USER_ID'] = private['SUPOCLIP_USER_ID']
        os.environ['SUPOCLIP_AUTH_SECRET'] = private['BACKEND_AUTH_SECRET']
    else:
        raise SystemExit('Configure an API key or the documented signed self-host credentials')
    os.environ['SUPOCLIP_API_URL'] = private.get('SUPOCLIP_API_URL') or 'http://127.0.0.1:8000'
    os.environ['SUPOCLIP_DOWNLOAD_DIR'] = private.get('SUPOCLIP_DOWNLOAD_DIR') or str(Path.home()/'Downloads'/'SupoClip')
    os.environ['SUPOCLIP_MCP_TRANSPORT'] = 'stdio'
    os.environ['SUPOCLIP_MCP_REQUIRE_BEARER_AUTH'] = 'false'
    sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
    from supoclip_mcp.server import main as serve
    serve()


if __name__ == '__main__':
    main()
