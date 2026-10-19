#!/usr/bin/env python3
"""Deterministic KCMC mark: white letters above a left-facing gold ichthys."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'KCMC-Connect-Phase6-Recreated/assets/icons'
OUT.mkdir(parents=True, exist_ok=True)
NAVY, GOLD, WHITE = '#0d2235', '#e7b34f', '#f5f7fa'

def curve(points, count=100):
    a, b, c, d = points
    return [((1-t)**3*a[0]+3*(1-t)**2*t*b[0]+3*(1-t)*t*t*c[0]+t**3*d[0],
             (1-t)**3*a[1]+3*(1-t)**2*t*b[1]+3*(1-t)*t*t*c[1]+t**3*d[1])
            for t in (i/count for i in range(count+1))]

canvas = Image.new('RGB', (1024, 1024), NAVY)
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 210)
draw.text((512, 362), 'KCMC', font=font, fill=WHITE, anchor='mm', stroke_width=0)
# Rounded head at left, crossing tail at right. All meaningful pixels remain in maskable safe area.
upper = curve(((184, 626), (365, 452), (605, 452), (824, 750)))
lower = curve(((184, 626), (365, 800), (605, 800), (824, 502)))
draw.line(upper, fill=GOLD, width=32, joint='curve')
draw.line(lower, fill=GOLD, width=32, joint='curve')
for size in (192, 512):
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(OUT / ('icon-%d.png' % size))
print('Built 192/512 RGB icons with KCMC above a left-facing gold fish.')
