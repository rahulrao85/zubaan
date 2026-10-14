"""Dub an English Short into Hinglish: Whisper (local) -> Gemma 4 on DigitalOcean -> ElevenLabs voice -> ffmpeg.

python dub.py <short_dir> [--out out_dir]
  <short_dir> holds assets/voice.wav, assets/music.wav and renders/*.mp4 (a GAL HyperFrames Short).
Writes en.json, hi.json, vo/NN.mp3, dub_vo.wav and <name>_HINGLISH.mp4 into out_dir.
Each stage is cached on disk, so a rerun only redoes what changed.
Keys come from F:\\AGENTIC WORLD\\.env (DIGITALOCEAN_TOKEN, ELEVENLABS_API_KEY) and are never printed.
"""
import argparse, base64, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILES = [HERE / ".env", HERE.parent / ".env"]
DO_URL = "https://inference.do-ai.run/v1/chat/completions"
DO_MODEL = "gemma-4-31B-it"
TTS_MODEL = "eleven_v4"  # the voice is your own ElevenLabs clone: ELEVENLABS_VOICE_ID
MAX_SPEEDUP = 1.15  # beyond this the voice sounds rushed; let the line spill into the next gap instead


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    for f in ENV_FILES:
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    sys.exit(f"{name} is not set (environment or .env)")


def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True, check=True).stdout)


def transcribe(wav, out):
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(str(wav), language="en")
    data = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


PROMPT = """You dub a YouTube Short for an Indian AI channel from English into spoken Hinglish (Roman script, Mumbai conversational, the way a young Indian techie talks).
Rules:
- One output line per input line, same numbering. Keep each line speakable in roughly the seconds shown in brackets (Hinglish runs longer, so trim filler).
- Tech terms, product and model names stay in English. Write numbers as words the way a voice actor reads them ("twenty-eight", "fifty").
- The transcript comes from speech recognition and has errors: fix obvious mishearings from context (product and model names especially).
- Use "aap" consistently. No Devanagari, no emojis, no stage directions, no timing tags.
Spellings from the video's own on-screen text (trust these over the transcript for names): {glossary}
House style example (match this tone):
{style}

Input:
{src}

Return ONLY the numbered Hinglish lines."""


def on_screen_text(index_html):
    """Overlay cards and chips (not the word-by-word captions, which are the same misheard transcript)."""
    if not index_html.exists():
        return ""
    html = index_html.read_text(encoding="utf-8")
    bits = re.findall(r'class="(?:kpill|bigtitle|kick|ttl|sub|srcchip|mini)"[^>]*>(.*?)</div>|class="mini"[^>]*>(.*?)</span>', html)
    text = [re.sub(r"<[^>]+>", "", a or b).strip() for a, b in bits]
    return " | ".join(dict.fromkeys(t for t in text if t))


def translate(segs, style, glossary, out):
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    src = "\n".join(f'{i + 1}. [{s["end"] - s["start"]:.0f}s] {s["text"]}' for i, s in enumerate(segs))
    prompt = PROMPT.format(style=style, src=src, glossary=glossary or "(none)")
    body = json.dumps({"model": DO_MODEL, "temperature": 0.4, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(DO_URL, data=body, headers={"Authorization": "Bearer " + env("DIGITALOCEAN_TOKEN"),
                                                             "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=180))
    lines = {}
    for ln in r["choices"][0]["message"]["content"].splitlines():
        m = re.match(r"\s*(\d+)\.\s*(?:\[[^\]]*\]\s*)?(.+)", ln)
        if m:
            lines[int(m.group(1))] = m.group(2).strip()
    if sorted(lines) != list(range(1, len(segs) + 1)):
        sys.exit(f"model returned lines {sorted(lines)} for {len(segs)} segments")
    data = [{**s, "hi": lines[i + 1]} for i, s in enumerate(segs)]
    out.write_text(json.dumps({"model": DO_MODEL, "usage": r.get("usage"), "lines": data}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return json.loads(out.read_text(encoding="utf-8"))


def words(al):
    """Character alignment -> [{w, s, e}] per word, in seconds from the start of the clip."""
    out, cur, s, e = [], "", None, None
    for ch, cs, ce in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                out.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
            cur, s = "", None
            continue
        s = cs if s is None else s
        cur, e = cur + ch, ce
    if cur:
        out.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
    return out


def tts(text, mp3):
    txt, wj = mp3.with_suffix(".txt"), mp3.with_suffix(".words.json")
    if mp3.exists() and wj.exists() and txt.exists() and txt.read_text(encoding="utf-8") == text:
        return
    body = json.dumps({"text": text, "model_id": TTS_MODEL}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{env('ELEVENLABS_VOICE_ID')}/with-timestamps?output_format=mp3_44100_128",
                                 data=body, headers={"xi-api-key": env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=60))
            break
        except urllib.error.URLError:
            if attempt == 2:
                raise
            time.sleep(5)
    mp3.write_bytes(base64.b64decode(r["audio_base64"]))
    wj.write_text(json.dumps(words(r["alignment"]), ensure_ascii=False), encoding="utf-8")
    txt.write_text(text, encoding="utf-8")


def place(lines, vo_dir, total):
    """Start each line at its English start; speed up (capped) when it would run into the next line."""
    plan, cursor = [], 0.0
    for i, ln in enumerate(lines):
        mp3 = vo_dir / f"{i + 1:02d}.mp3"
        d = dur(mp3)
        start = max(ln["start"], cursor + 0.08)
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else total
        speed = min(MAX_SPEEDUP, max(1.0, d / max(nxt - start, 0.1)))
        plan.append({"n": i + 1, "start": round(start, 3), "len": round(d / speed, 3), "speed": round(speed, 3)})
        cursor = start + d / speed
    return plan


def bed(short_dir):
    """Music and sound effects exactly as the original composition placed them (<audio> tags other than the voice)."""
    html = (short_dir / "index.html").read_text(encoding="utf-8")
    out = []
    for tag in re.findall(r"<audio[^>]*>", html):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        if attr.get("id") != "vo":
            out.append((short_dir / attr["src"], float(attr.get("data-start", 0)), float(attr.get("data-volume", 1))))
    return out


def mix(plan, vo_dir, beds, length, out):
    ins, filt, labels = [], [], []
    for k, p in enumerate(plan):
        ins += ["-i", str(vo_dir / f'{p["n"]:02d}.mp3')]
        ms = int(p["start"] * 1000)
        filt.append(f"[{k}:a]aresample=44100,atempo={p['speed']},adelay={ms}|{ms}[v{k}]")
        labels.append(f"[v{k}]")
    for j, (src, start, vol) in enumerate(beds, len(plan)):
        ins += ["-i", str(src)]
        ms = int(start * 1000)
        filt.append(f"[{j}:a]aresample=44100,volume={vol},adelay={ms}|{ms}[b{j}]")
        labels.append(f"[b{j}]")
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                f"apad,atrim=0:{length},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    run("ffmpeg", "-y", *ins, "-filter_complex", ";".join(filt), "-map", "[a]", "-ac", "2", "-ar", "44100", str(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short_dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--style", type=Path, help="a Hinglish script whose tone the translation should copy")
    a = ap.parse_args()
    out = a.out or Path(__file__).resolve().parent / "out" / a.short_dir.name
    (out / "vo").mkdir(parents=True, exist_ok=True)
    render = sorted((a.short_dir / "renders").glob("*.mp4"))[0]

    segs = transcribe(a.short_dir / "assets" / "voice.wav", out / "en.json")
    style = a.style.read_text(encoding="utf-8") if a.style else ""
    glossary = on_screen_text(a.short_dir / "index.html")
    print("on-screen glossary:", glossary)
    hi = translate(segs, style, glossary, out / "hi.json")
    for i, ln in enumerate(hi["lines"]):
        tts(ln["hi"], out / "vo" / f"{i + 1:02d}.mp3")
    # The English voice track ends where the closing sting begins; the dub has to finish by then too.
    plan = place(hi["lines"], out / "vo", dur(a.short_dir / "assets" / "voice.wav"))
    (out / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    mix(plan, out / "vo", bed(a.short_dir), dur(render), out / "dub_vo.wav")
    # Voice alone, for the lip-sync model (music would confuse its audio encoder).
    mix(plan, out / "vo", [], dur(a.short_dir / "assets" / "base.mp4"), out / "voice_only.wav")
    run("ffmpeg", "-y", "-i", str(out / "voice_only.wav"), "-ac", "1", "-ar", "16000", str(out / "voice_only_16k.wav"))
    final = out / f"{render.stem}_HINGLISH.mp4"
    run("ffmpeg", "-y", "-i", str(render), "-i", str(out / "dub_vo.wav"), "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final))
    over = [p for p in plan if p["speed"] >= MAX_SPEEDUP]
    print(f"{final}\n{len(plan)} lines, {len(over)} at max speed-up, voice ends {plan[-1]['start'] + plan[-1]['len']:.1f}s "
          f"of {dur(render):.1f}s; Gemma usage {hi.get('usage', {}).get('total_tokens')} tokens")


if __name__ == "__main__":
    main()
