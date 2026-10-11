#!/usr/bin/env python3
"""Decode PNG image data, beyond the header-only getimagesize contract."""
import json
from pathlib import Path
import struct
import zlib

APP = Path(__file__).resolve().parents[1] / 'KCMC-Connect-Phase6-Recreated'


def validate_png(data, size):
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'PNG signature'
    pos, compressed, chunks, dimensions = 8, [], [], None
    while pos < len(data):
        assert pos + 12 <= len(data), 'Truncated PNG chunk header'
        length, = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + length
        assert end <= len(data), 'PNG chunk exceeds file length'
        payload = data[pos + 8:pos + 8 + length]
        crc, = struct.unpack('>I', data[pos + 8 + length:end])
        assert zlib.crc32(kind + payload) & 0xffffffff == crc, 'PNG chunk CRC'
        chunks.append(kind)
        if kind == b'IHDR':
            assert len(chunks) == 1 and length == 13, 'Single leading IHDR'
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            assert (width, height) == (size, size), 'Declared dimensions'
            assert depth == 8 and color in (2, 6), 'Approved RGB/RGBA icon format'
            assert (compression, filtering, interlace) == (0, 0, 0), 'Standard noninterlaced PNG'
            dimensions = width, height, 3 if color == 2 else 4
        elif kind == b'IDAT':
            compressed.append(payload)
        elif kind == b'IEND':
            assert length == 0 and end == len(data), 'Complete PNG trailer'
        pos = end
    assert dimensions and chunks[-1] == b'IEND' and compressed, 'Complete PNG image'
    width, height, channels = dimensions
    stride = 1 + width * channels
    decoder = zlib.decompressobj()
    raw = decoder.decompress(b''.join(compressed), stride * height + 1)
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, 'Complete zlib payload'
    assert len(raw) == stride * height, 'Complete pixel rows'
    assert all(raw[row * stride] <= 4 for row in range(height)), 'Valid PNG row filters'


def run():
    manifest = json.loads((APP / 'manifest.webmanifest').read_text())
    icons = {icon['src'].split('?')[0]: int(icon['sizes'].split('x')[0]) for icon in manifest['icons']}
    for relative, size in icons.items():
        data = (APP / relative).read_bytes()
        validate_png(data, size)
        # Independent malformed-payload control: valid dimensions alone cannot pass.
        try:
            validate_png(data[:40], size)
        except AssertionError:
            pass
        else:
            raise AssertionError('Truncated PNG negative control was accepted')
        print('PASS:', relative, 'complete PNG chunks, CRCs and decoded pixel rows')


if __name__ == '__main__':
    run()
