"""Explicit, lossless browser preparation. Never called by a GET or export."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import subprocess

from .editor_document import atomic_json, editor_lock


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def browser_media(directory: Path) -> Path:
    original = directory/'media.mp4'
    try:
        source = json.loads((directory/'source.json').read_text())
        cache = json.loads((directory/'browser-media.json').read_text())
        target = directory/'browser.mp4'
        if (cache.get('version') == 1 and cache.get('source_sha256') == source['sha256']
                and cache.get('packet_verified') is True and target.is_file()
                and target.stat().st_size == cache.get('bytes')):
            return target
    except (OSError, ValueError, KeyError):
        pass
    return original


def packet_clock(path: Path) -> list[dict]:
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_packets', '-show_data_hash', 'sha256',
        '-show_entries', 'packet=stream_index,pts_time,dts_time,data_hash', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True)
    return json.loads(result.stdout)['packets']


def verify_packets(original: list[dict], prepared: list[dict]) -> dict:
    # Muxers can interleave streams differently; compare each stream independently.
    streams = sorted({p['stream_index'] for p in original})
    if streams != sorted({p['stream_index'] for p in prepared}):
        raise ValueError('Browser preparation changed the streams')
    count, maximum = 0, Decimal('0')
    for index in streams:
        a = [p for p in original if p['stream_index'] == index]
        b = [p for p in prepared if p['stream_index'] == index]
        if len(a) != len(b):
            raise ValueError('Browser preparation changed packet counts')
        for before, after in zip(a, b):
            if not before.get('data_hash') or before['data_hash'] != after.get('data_hash'):
                raise ValueError('Browser preparation changed compressed audio/video')
            for key in ['pts_time', 'dts_time']:
                if (key in before) != (key in after):
                    raise ValueError('Browser preparation changed timestamp availability')
                if key in before:
                    maximum = max(maximum, abs(Decimal(before[key])-Decimal(after[key])))
            count += 1
    if maximum > Decimal('0.000002'):
        raise ValueError('Browser preparation changed the source clock')
    return {'packet_count': count, 'maximum_timestamp_difference': float(maximum)}


def prepare_browser_media(directory: Path) -> dict:
    """Repackage fragmented MP4 into indexed MP4, without encoding or changing originals."""
    directory = directory.resolve(strict=True)
    with editor_lock(directory):
        if browser_media(directory) != directory/'media.mp4':
            return json.loads((directory/'browser-media.json').read_text())
        original, temporary = directory/'media.mp4', directory/'.browser-preparing.mp4'
        source = json.loads((directory/'source.json').read_text())
        if source.get('status') != 'ready' or digest(original) != source.get('sha256'):
            raise ValueError('Source is not ready or its digest changed')
        try:
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-copyts', '-i', str(original),
                '-map', '0', '-c', 'copy', '-copytb', '1', '-avoid_negative_ts', 'disabled',
                '-movflags', '+faststart', str(temporary)], check=True, capture_output=True)
            verified = verify_packets(packet_clock(original), packet_clock(temporary))
            metadata = {'version': 1, 'source_sha256': source['sha256'], 'packet_verified': True,
                'sha256': digest(temporary), 'bytes': temporary.stat().st_size, **verified}
            temporary.replace(directory/'browser.mp4')
            atomic_json(directory/'browser-media.json', metadata)
            return metadata
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    import sys
    print(json.dumps(prepare_browser_media(Path(sys.argv[1]))))
