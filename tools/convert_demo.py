"""Convert demo MP4 to GIF. Run: python tools/convert_demo.py"""
import sys, numpy as np
from pathlib import Path
from PIL import Image
import imageio.v3 as iio

ROOT = Path(__file__).parent.parent
mp4_path = ROOT / "docs" / "screenshot.mp4"
gif_path = ROOT / "docs" / "screenshot.gif"

if not mp4_path.exists():
    print(f"MP4 not found: {mp4_path}")
    sys.exit(1)

print(f"Reading {mp4_path} ({mp4_path.stat().st_size / 1024 / 1024:.1f} MB)...")

# Read all frames
frames = iio.imread(mp4_path, plugin="pyav")
nframes = len(frames)
print(f"Frames: {nframes}")

# Sample aggressively: aim for ~80 frames at 8fps (~10s demo)
target = 80
step = max(1, nframes // target)
target_fps = 8
scale = 3  # divide resolution by 3

print(f"Sampling every {step} frame(s) at {target_fps} fps, 1/{scale} resolution...")

small_frames = []
for i in range(0, nframes, step):
    img = Image.fromarray(frames[i])
    w, h = img.size
    img = img.resize((w // scale, h // scale), Image.LANCZOS)
    # Reduce colors for smaller file
    img = img.quantize(colors=128, method=Image.Quantize.MEDIANCUT).convert('RGB')
    small_frames.append(np.array(img))

print(f"Writing {len(small_frames)} frames to {gif_path}...")
iio.imwrite(gif_path, small_frames, fps=target_fps, loop=0, plugin="pillow")
size_mb = gif_path.stat().st_size / 1024 / 1024
print(f"Done: {gif_path} ({size_mb:.1f} MB)")
