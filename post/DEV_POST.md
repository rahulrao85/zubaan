*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

I run a small AI channel, [Grounded AI Lab](https://youtube.com/@groundedailab), for Indian viewers. On 11 October I switched it to Hinglish only, because that's how my audience actually talks. That left four finished English Shorts stuck on hold. Re-recording them meant another evening in front of the camera for videos that were already done.

So I built **Zubaan**. In Hindi, *zubaan* means "tongue", and it also means "language". This tool changes both. You give it an English Short and get back the same Short in Hinglish, with my face, my voice, my lips moving to the new words, and Hinglish captions. The cards, cuts, music and sound effects all stay where they were.

**Who pays for this:** Indian creators, teachers and coaches who record in English and want the much bigger Hindi-speaking audience, without recording everything twice. Paid dubbing tools charge per minute of video. Writing *natural* Hinglish (Roman-script Hindi with the English tech words left alone) is the hard part, and that's exactly the job I gave an open model.

What I'd charge: **₹99 per Short, or ₹1,499 a month for 20.** My cost per 70-second Short is under ₹1 of DigitalOcean inference plus about 1,000 characters of the creator's own voice-clone plan. The GPU work runs on a gaming card I already owned.

## Demo

<!-- Govu: paste the YouTube links after uploading -->
**Side by side: English original on the left, Hinglish dub on the right (with the Hinglish audio):**
{% embed https://youtu.be/REPLACE_SIDE_BY_SIDE %}

Same frame, same moment. Top: the English original. Bottom: Zubaan's Hinglish lip sync.

![Before and after: English original on top, Hinglish lip sync below](REPLACE_UPLOADED_IMAGE_URL)

**The finished Hinglish Short, as it goes out on the channel:**
{% embed https://youtube.com/shorts/REPLACE_FULL %}

## Code

{% embed https://github.com/rahulrao85/zubaan %}

## How I Built It

Five steps. Every one except the voice uses open software.

| Step | Tool | Where it runs |
|---|---|---|
| English speech → timed transcript | **Whisper** (`faster-whisper`, small.en) | My laptop's CPU: 70 s of audio in 31 s |
| Transcript → spoken Hinglish | **Gemma 4 31B** on **DigitalOcean Serverless Inference** | DigitalOcean, 6 s per Short |
| Hinglish → my voice + word timings | ElevenLabs voice clone | ElevenLabs |
| Face → lips that match the Hinglish | **LatentSync 1.5** (ByteDance) | RTX 3060 12 GB, under WSL |
| Re-render with Hinglish captions | **HyperFrames** + ffmpeg | My laptop |

**Picking the translator.** I gave the same transcript to four open models on DigitalOcean and compared the output line by line:

| Model | Time | Verdict |
|---|---|---|
| **Gemma 4 31B** | 6.4 s | Most natural, consistent "aap", fixed both mishearings. **Picked.** |
| DeepSeek V4 Pro | 25 s | The punchiest lines ("Catch? Hai na ek catch."), but it switched between "aap" and "tum" |
| Llama 4 Maverick | 24 s | Translated "catch" as *pakad*, which nobody says |
| Qwen 3.5 397B | — | Came back empty; I didn't chase it |

**The bug that taught me something.** Whisper heard "GPT-6 Astra" as "Astra 6" and the model name "Jev" as "Gev". Gemma then translated the mistakes faithfully. Hand-written hints worked for that one video only, so I looked for a source of truth that every video already has: **its own on-screen text**. The composition has an overlay that says *"Try GPT-6 Astra without a subscription"*. `dub.py` now pulls every overlay card out of the composition and gives it to Gemma as the spelling authority. Both names came out right, and Gemma even added *"har mahine"* (every month) from a card, where the transcript had only said "the list keeps changing".

**Timing.** Hinglish runs 10–15% longer than English. Each line starts where its English line started and can speed up by at most 15% before it runs into the next one. Beyond that, the voice starts to sound rushed. 5 of the 18 lines needed the full 15%.

**The mistake that cost me 48 minutes.** My machine already had LatentSync installed from an earlier experiment, and I assumed it was version 1.6 (512 px). I ran it with the 1.6 config, and it took 48 minutes for 6 seconds of video while my 12 GB card spilled into system RAM. Then it produced a mouth that looked like crumpled foil. While I was downloading the "real" 1.5 weights, I compared fingerprints: **the installed file *was* 1.5**, byte for byte. With the correct 256 px config, the same 6 seconds took 3.3 minutes and looked right.

Then the full 70-second run was killed for running out of memory. LatentSync keeps every frame in RAM, about 12 MB per 1440×1920 frame, so 70 seconds needed around 20 GB on a 24 GB machine. `lipsync.sh` now cuts the video into chunks of 16 seconds or less **at the pauses between dubbed lines** (`dub.py`'s timing plan already knows where they are), syncs each chunk and joins them, so no word gets split. The full 70-second Short then took about 31 minutes on the RTX 3060, in 7 chunks, with no visible seams. Both lessons are comments in `lipsync.sh`, so nobody else loses that hour.

**What I couldn't use.** I wanted to run the lip sync on a DigitalOcean GPU Droplet (RTX 4000 Ada, $0.76/h, enough for the sharper 1.6 model). My new account didn't have GPU access yet, and the limit request is still pending. So the GPU step runs locally for now, and the Droplet is the obvious next step for anyone without a gaming card.

## Why Does Open Innovation Matter?

Three things here wouldn't have worked with a closed API:

1. **The fix lives in my pipeline, not in someone's roadmap.** The on-screen-glossary trick works because I control exactly what goes into the model and can swap models freely. When Gemma's first run regressed on a name, I changed the prompt and re-ran it for a fraction of a paisa. With a closed dubbing product, I'd have filed a ticket.
2. **Model choice is a 10-minute experiment.** DigitalOcean serves a dozen open-weight models behind one endpoint, so comparing four translators cost less than a cup of tea, and I picked on quality, not on whichever vendor I happened to be locked into.
3. **The expensive part runs on hardware I already own.** Lip sync is the GPU-heavy step, and an open model meant it ran free on my gaming card. A per-minute service would make this side hustle's margins depend on someone else's pricing page.

Being honest about the one closed piece: **the voice.** I kept the ElevenLabs clone my channel already uses, because my audience knows that voice. Testing an open voice-cloning model on Hinglish is the next experiment, and the voice step is a single function, so swapping it out is a small change.

**On consent:** the tool is built to dub *your own* face and voice. The voice comes from your own clone, and lip sync only runs on footage you supply. The output gets YouTube's "altered or synthetic content" label, as it should.

## My First User

Me, as a creator. The dubbed GAL-012 goes out on Grounded AI Lab this week, and the three other held English Shorts are next in the queue. That's four videos rescued from the archive without re-recording. Nobody has paid yet. The next test is whether a creator friend who records in English will pay ₹99 to have one of theirs done.

## Prize Categories

- **Best Use of DigitalOcean**: Gemma 4 runs on DigitalOcean Serverless Inference as the translation core, and four open models were compared on the same endpoint.
- **Best Use of Gemma**: Gemma 4 31B writes all the Hinglish, using the on-screen-glossary technique.
- **ElevenLabs**: my ElevenLabs voice clone speaks the Hinglish, and its word-level timestamps drive the captions.
