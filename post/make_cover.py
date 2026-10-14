"""DEV cover image (2000x840 = 1000:420 at 2x) in the GAL Aurora look: English frame vs Hinglish lip-synced frame."""
import io, subprocess
from pathlib import Path
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
TEST = HERE.parent / "lipsync_test"
FONTS = HERE.parents[1] / "grounded-ai-lab" / "shorts" / "01-ai-engineering-from-scratch" / "assets" / "fonts"
BG, SURFACE, TEXT, MUTED = "#FBFBF9", "#FFFFFF", "#14161C", "#5B6070"
BLUE, ORANGE, BORDER = "#2563EB", "#EA6A1F", "#E3E1D9"


def font(name, size):
    f = TTFont(FONTS / name)
    f.flavor = None
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    return ImageFont.truetype(buf, size)


def frame(video, t, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                    "-vf", "crop=760:760:340:300,scale=600:600", str(out)], check=True)
    return Image.open(out).convert("RGB")


def rounded(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, *img.size], r, fill=255)
    return img, m


def main():
    W, H = 2000, 840
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    grot, grot_m = font("space-grotesk-latin-700-normal.woff2", 84), font("space-grotesk-latin-500-normal.woff2", 40)
    mono = font("jetbrains-mono-latin-700-normal.woff2", 28)

    for i, (video, label, colour) in enumerate([(TEST / "clip.mp4", "ENGLISH  ·  ORIGINAL", MUTED),
                                                (TEST / "clip_ls15.mp4", "HINGLISH  ·  DUBBED + LIP-SYNCED", BLUE)]):
        x, y = 70 + i * 640, 120
        img, m = rounded(frame(video, 2.6, HERE / f"_f{i}.png"), 36)
        d.rounded_rectangle([x - 8, y - 8, x + 608, y + 608], 44, fill=colour if i else BORDER)
        c.paste(img, (x, y), m)
        tw = d.textlength(label, font=mono)
        d.rounded_rectangle([x, y + 630, x + tw + 36, y + 680], 25, fill=colour if i else SURFACE, outline=BORDER)
        d.text((x + 18, y + 641), label, font=mono, fill="#FFFFFF" if i else TEXT)

    tx = 1380
    d.text((tx, 96), "Zubaan", font=font("space-grotesk-latin-700-normal.woff2", 64), fill=ORANGE)
    d.text((tx, 178), "TONGUE · LANGUAGE · HF26", font=mono, fill=MUTED)
    y = 236
    for line in ["Your Short,", "now in", "Hinglish."]:
        d.text((tx, y), line, font=grot, fill=BLUE if line == "Hinglish." else TEXT)
        y += 92
    y += 22
    for line in ["Same face. Same voice.", "Open models do the work."]:
        d.text((tx, y), line, font=grot_m, fill=MUTED)
        y += 52
    y += 24
    d.text((tx, y), "WHISPER · GEMMA 4 ·", font=mono, fill=TEXT)
    d.text((tx, y + 40), "LATENTSYNC · DIGITALOCEAN", font=mono, fill=TEXT)
    d.rectangle([0, H - 12, W, H], fill=BLUE)
    d.rectangle([0, H - 12, 260, H], fill=ORANGE)
    c.save(HERE / "cover_2000x840.png", optimize=True)
    for p in HERE.glob("_f*.png"):
        p.unlink()
    print(HERE / "cover_2000x840.png")


if __name__ == "__main__":
    main()
