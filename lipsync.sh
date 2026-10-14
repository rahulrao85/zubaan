#!/usr/bin/env bash
# Lip-sync a face video to the Hinglish voice with LatentSync 1.5 (ByteDance, open weights).
# Runs inside a LatentSync checkout (https://github.com/bytedance/LatentSync) with its venv and the 1.5 checkpoint.
# Usage: bash lipsync.sh <face_video.mp4> <voice_16k_mono.wav> <out.mp4> "[cut seconds, e.g. 21 42 62.88]" [latentsync_dir]
#
# Use configs/unet/stage2.yaml (256 px) with the 1.5 weights. stage2_512.yaml is for the 1.6 weights only:
# pairing it with 1.5 weights runs ~15x slower and garbles the mouth.
# LatentSync holds every frame in RAM (~12 MB per 1440x1920 frame), so a 70 s Short gets OOM-killed on a 24 GB machine.
# Cut it into chunks at pauses between lines (dub.py's plan.json shows the gaps), sync each, then join.
set -euo pipefail
VIDEO=$(realpath "$1"); AUDIO=$(realpath "$2"); OUT=$(realpath -m "$3"); CUTS=${4:-}; LS=${5:-$HOME/LatentSync}
WORK="${OUT%.*}_chunks"; mkdir -p "$WORK"; rm -f "$WORK/list.txt"  # kept on failure so finished chunks are reused
cd "$LS" && . .venv/bin/activate

LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$AUDIO")
EDGES=(0 $CUTS "$LEN")
for i in $(seq 0 $(( ${#EDGES[@]} - 2 ))); do
  S=${EDGES[$i]}; E=${EDGES[$((i + 1))]}; D=$(python -c "print($E - $S)")
  ffmpeg -v error -y -ss "$S" -t "$D" -i "$VIDEO" -an -r 25 -c:v libx264 -crf 14 "$WORK/v$i.mp4"
  ffmpeg -v error -y -ss "$S" -t "$D" -i "$AUDIO" -ac 1 -ar 16000 "$WORK/a$i.wav"
  echo "chunk $i: ${S}s-${E}s"
  [ -s "$WORK/o$i.mp4" ] && { echo "file '$WORK/o$i.mp4'" >> "$WORK/list.txt"; echo "  cached"; continue; }
  python -m scripts.inference \
    --unet_config_path configs/unet/stage2.yaml \
    --inference_ckpt_path checkpoints/latentsync_unet.pt \
    --inference_steps 20 --guidance_scale 1.5 --enable_deepcache \
    --video_path "$WORK/v$i.mp4" --audio_path "$WORK/a$i.wav" --video_out_path "$WORK/o$i.mp4" > "$WORK/log$i.txt" 2>&1 \
    || { tail -20 "$WORK/log$i.txt"; exit 1; }
  echo "file '$WORK/o$i.mp4'" >> "$WORK/list.txt"
done
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$OUT"
rm -rf "$WORK"
echo "done: $OUT"
