"""Rebuild a GAL Short with the Hinglish dub: lip-synced face, dubbed voice, Hinglish word captions.

python recaption.py <short_dir> <lipsynced_base.mp4> [--out out_dir]
Copies the composition to <out_dir>/comp (the original Short is never touched), swaps assets/base.mp4 and
assets/voice.wav, replaces the English caption clips and their pop-in tweens with Hinglish ones from the
ElevenLabs word timings that dub.py saved, then renders with HyperFrames and masters to -11 LUFS like GAL does.
"""
import argparse, json, re, shutil, subprocess
from pathlib import Path

WORDS_PER_CAP = 3
# Highlighted words (the composition's .w.em style): numbers, prices and the names the video is about.
EM = re.compile(r"^(free|catch|comment|openrouter|gpt-six|astra|jev|students|perfect|twenty-eight|fifty|\d+)$", re.I)
CAP_DIV = re.compile(r'<div id="cap\d+" class="clip cap".*?</div></div>\n', re.S)
CAP_TWEEN = re.compile(r'tl\.fromTo\("#c\d+w\d+".*\n')
TWEEN = ('tl.fromTo("#{id}", {{opacity:0, y:24, scale:0.86}}, '
         '{{opacity:1, y:0, scale:1, duration:0.14, ease:"back.out(2.4)"}}, {t});\n')


def timed_words(dub_dir):
    plan = json.loads((dub_dir / "plan.json").read_text(encoding="utf-8"))
    lines = []
    for p in plan:
        ws = json.loads((dub_dir / "vo" / f'{p["n"]:02d}.words.json').read_text(encoding="utf-8"))
        lines.append([{"w": w["w"], "s": p["start"] + w["s"] / p["speed"], "e": p["start"] + w["e"] / p["speed"]} for w in ws])
    return lines


def caption_html(lines, end):
    caps = [line[i:i + WORDS_PER_CAP] for line in lines for i in range(0, len(line), WORDS_PER_CAP)]
    divs, tweens = [], []
    for n, cap in enumerate(caps):
        start = cap[0]["s"]
        stop = caps[n + 1][0]["s"] if n + 1 < len(caps) else end
        stop = min(stop, cap[-1]["e"] + 0.6)  # don't leave a caption hanging through a pause
        spans = []
        for k, w in enumerate(cap):
            text = w["w"].strip(",.?!\"'")
            em = " em" if EM.match(text) else ""
            spans.append(f'<span id="c{n}w{k}" class="w{em}">{w["w"].rstrip(",.")}</span>')
            tweens.append(TWEEN.format(id=f"c{n}w{k}", t=round(w["s"], 3)))
        divs.append(f'<div id="cap{n}" class="clip cap" data-start="{start:.3f}" data-duration="{stop - start:.3f}" '
                    f'data-track-index="9"><div class="capline">{"".join(spans)}</div></div>\n')
    return "".join(divs), "".join(tweens), len(caps)


def splice_silences(original, synced, silences_json, out):
    """Where the dub is silent, show the original frames: the lip-sync model keeps moving the mouth on silence,
    and with the dub fitted to the English speech spans the original face is quiet in those same stretches."""
    gaps = json.loads(Path(silences_json).read_text(encoding="utf-8")) if Path(silences_json).exists() else []
    if not gaps:
        shutil.copy(synced, out)
        return
    enable = "+".join(f"between(t,{a},{b})" for a, b in gaps)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(synced), "-i", str(original), "-filter_complex",
                    f"[1:v]fps=25[o];[0:v][o]overlay=enable='{enable}'[v]", "-map", "[v]", "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short_dir", type=Path)
    ap.add_argument("lipsynced", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    dub_dir = a.out or Path(__file__).resolve().parent / "out" / a.short_dir.name
    comp = dub_dir / "comp"
    if comp.exists():
        shutil.rmtree(comp)
    shutil.copytree(a.short_dir, comp, ignore=shutil.ignore_patterns("renders", "node_modules"))
    splice_silences(a.short_dir / "assets" / "base.mp4", a.lipsynced, dub_dir / "silences.json", comp / "assets" / "base.mp4")
    shutil.copy(dub_dir / "voice_only.wav", comp / "assets" / "voice.wav")

    html = (comp / "index.html").read_text(encoding="utf-8")
    base_len = float(re.search(r'<video id="base"[^>]*data-duration="([\d.]+)"', html).group(1))
    divs, tweens, n = caption_html(timed_words(dub_dir), base_len)
    first_div, first_tween = CAP_DIV.search(html).start(), CAP_TWEEN.search(html).start()
    html = html[:first_tween] + "@@TWEENS@@" + html[first_tween:]
    html = html[:first_div] + "@@DIVS@@" + html[first_div:]
    html = CAP_TWEEN.sub("", CAP_DIV.sub("", html))
    html = html.replace("@@DIVS@@", divs).replace("@@TWEENS@@", tweens)
    (comp / "index.html").write_text(html, encoding="utf-8")
    print(f"{n} Hinglish caption clips")

    raw = comp / "renders" / "raw.mp4"
    subprocess.run(["npx", "--yes", "hyperframes@0.8.91", "render", "-o", "renders/raw.mp4"], cwd=comp, check=True, shell=True)
    final = dub_dir / (a.short_dir.name + "_HINGLISH_LIPSYNC.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "copy", "-af", "loudnorm=I=-11:TP=-1.4:LRA=11",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(final)], check=True)
    print(final)


if __name__ == "__main__":
    main()
