# Audio & Subtitles

## Audio

Provider-neutral interfaces for voice, music, and SFX (`src/capos/audio/interfaces.py`).

- Track licensing / provenance on `AudioClip`  
- Voice tracks independently replaceable  
- `NullAudioBackend` reports unavailable — does not fake synthesis  

## Subtitles

Generated from **approved script dialogue**, never OCR of images.

Formats: **SRT** and **VTT** via `write_srt` / `write_vtt`.
