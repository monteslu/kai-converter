
# KAI-Converter — Preprocessing CLI (v1.0, KAI-4 MVP)

**Status:** Implementation Spec (MVP — 4-stem only)  
**Date:** 2025-09-07T18:27:15Z  
**Targets:** Linux, Windows, macOS  
**License:** MIT for CLI glue; upstream libs remain their FOSS licenses

## 1. Purpose
`kai-pack` converts user audio (e.g., MP3) + lyrics text into a `.kai` bundle **v1.0** with:
- **KAI-4** stems at ZIP root: `vocals.mp3`, `drums.mp3`, `bass.mp3`, `other.mp3`
- `song.json` descriptor (alignment, metadata, **audio profile**, **meta/provenance**)
- Optional `features/*` analyses
- **No separate `manifest.json`** — provenance/hashes live in `song.json.meta`

## 2. Tech stack
- Python 3.10+ • PyTorch/torchaudio • Demucs v4 (`htdemucs_ft` preferred)
- librosa • madmom • Essentia • CREPE (`crepe`/`torchcrepe`) • dtw-python • numpy • scipy
- mutagen (ID3) • ffmpeg • zipfile

## 3. CLI
```
kai-pack INPUT_AUDIO LYRICS.txt -o OUT.kai [options]

Options:
  --gpu | --cpu
  --sr 44100
  --model htdemucs_ft|htdemucs
  --chunk 44100
  --overlap 0.25
  --stem-bitrate 160k
  --vocals-bitrate 128k
  --no-analysis
  --features f0,notes,tempo,keys,chords,onsets,mfcc
  --id3-raw true|false        # default true; controls meta.id3.raw inclusion
  --title "…" --artist "…"    # override ID3-derived values
  --cover cover.jpg
  --verbose
```

## 4. Pipeline

### 4.1 Decode & loudness
- `ffmpeg -i INPUT_AUDIO -ar 44100 -ac 2 -sample_fmt flt` → `input.wav`
- Normalize to ≈ −14 LUFS (EBU R128 `loudnorm`); record measured stats under `song.json.meta`

### 4.2 4-stem separation
- Demucs → `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`
- Record model + git SHA under `meta.processing.separation`

### 4.3 Lyrics alignment
- Inputs: `vocals.wav`, `LYRICS.txt`
- Output: `song.json.lines[]` (word/line timings), `timing.reference="aligned_to_vocals_wav"`, `offset_sec`

### 4.4 Optional analysis → `features/`
- F0, notes, onsets, tempo, keys, chords, vocal activity, MFCC

### 4.5 ID3 ingestion (mandatory)
- Read ID3v2/v1 via mutagen
- Populate `song.song` fields; fallback to filename stem for missing `title`; set `source_filename`
- Write normalized mapping and (optionally) raw frames to `song.json.meta.id3`

### 4.6 Encode stems (MP3 at root)
- `vocals/drums/bass/other` WAV → MP3 at configured bitrates
- Detect LAME encoder delay; set `audio.encoder_delay_samples` (default 1105 if unknown)

### 4.7 Finalize `song.json`
- Set `audio.profile="KAI-4"`, list four `audio.sources[]`
- Fill `meta.created_utc`, `meta.source.sha256`, and `meta.hashes` for each MP3

### 4.8 Package
- ZIP: `song.json`, `vocals.mp3`, `drums.mp3`, `bass.mp3`, `other.mp3`, optional `features/*`

## 5. Perf & quality
- GPU preferred; CPU works but is slower
- Chunk/overlap tunables expose speed/quality trade-offs

## 6. Logging & errors
- `--verbose` emits JSON logs; on low alignment confidence, still emit with `meta.processing.alignment.alignment_ok=false`

## 7. Tests
- Golden clips for timings; schema validation; encoder delay checks; stem presence & hash verification
