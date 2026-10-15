"""Side-by-side demo for the DEV post: English face on the left, Zubaan's Hinglish lip sync on the right, Hinglish audio.

python make_demo.py <original_base.mp4> <lipsynced_base.mp4> <dub_audio.wav> <out.mp4>
"""
import subprocess, sys
from pathlib import Path
from make_cover import font, BLUE, TEXT, MUTED, SURFACE, BORDER
from PIL import Image, ImageDraw

W, H, BAR = 1440, 720, 84  # two 720x720 face crops, label bar on top


def labels(out):
    img = Image.new("RGBA", (W, BAR), SURFACE)
    d = ImageDraw.Draw(img)
    mono = font("jetbrains-mono-latin-700-normal.woff2", 30)
    for i, (text, colour) in enumerate([("ENGLISH · ORIGINAL LIPS", MUTED), ("ZUBAAN · HINGLISH LIP SYNC", BLUE)]):
        x = i * 720 + (720 - d.textlength(text, font=mono)) / 2
        d.text((x, 24), text, font=mono, fill=colour)
    d.line([(720, 0), (720, BAR)], fill=BORDER, width=2)
    img.save(out)


def main(orig, synced, audio, out):
    bar = Path(out).with_suffix(".labels.png")
    labels(bar)
    face = "crop=1080:1080:180:200,scale=720:720,fps=25"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", orig, "-i", synced, "-i", audio, "-i", str(bar),
                    "-filter_complex", f"[0:v]{face}[l];[1:v]{face}[r];[l][r]hstack[f];"
                    f"[3:v][f]vstack,format=yuv420p[v]",
                    "-map", "[v]", "-map", "2:a", "-shortest", "-c:v", "libx264", "-crf", "22", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "160k", out], check=True)
    bar.unlink()
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:5])
