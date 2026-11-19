"""Prepare a new, non-overwriting MV working directory from supplied media."""
import argparse
from pathlib import Path
import shutil
import wave
from media_common import binary, probe, run, sha256, write_json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audio', required=True, type=Path)
    ap.add_argument('--lyrics', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--ffmpeg')
    ap.add_argument('--ffprobe')
    a = ap.parse_args()
    ff, fp = binary('ffmpeg', a.ffmpeg), binary('ffprobe', a.ffprobe)
    audio, lyrics, out = a.audio.resolve(strict=True), a.lyrics.resolve(strict=True), a.out.resolve()
    content = lyrics.read_text(encoding='utf-8-sig')
    if not content.strip():
        raise ValueError('Lyrics are empty.')
    info = probe(audio, fp)
    if not any(s['codec_type'] == 'audio' for s in info['streams']):
        raise ValueError('No audio stream found.')
    out.mkdir(parents=True, exist_ok=False)
    source = out / ('song' + audio.suffix.lower())
    shutil.copy2(audio, source)
    (out / 'lyrics.txt').write_text(content, encoding='utf-8')
    run([ff, '-v', 'error', '-nostdin', '-n', '-i', str(source), '-map', '0:a:0',
         '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(out / 'alignment.wav')])
    with wave.open(str(out / 'alignment.wav')) as wav:
        duration = wav.getnframes() / wav.getframerate()
    write_json(out / 'project.json', {
        'stage': 'audio_received', 'source_audio': str(audio), 'audio_file': source.name,
        'source_sha256': sha256(source), 'lyrics_sha256': sha256(out / 'lyrics.txt'),
        'decoded_duration': duration, 'audio_speed': 1.0, 'source_edits': [],
        'alignment_status': 'not_started', 'listening_review': 'not_performed',
        'next_action': 'Prepare actual sung transcript, align, inspect tail, design scenes and render.'})
    write_json(out / 'media.json', info)
    print(f'Prepared {out}; decoded duration {duration:.3f}s. No video generated yet.')


if __name__ == '__main__':
    main()
