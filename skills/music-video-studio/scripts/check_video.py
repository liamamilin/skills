"""Technical media and declarative-role checks, never a claim of auditory review."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
from media_common import binary, probe, sha256, write_json


def check_cast(cast):
    if 'assistant' in cast and 'mascot' in cast:
        if cast['assistant']['id'] != cast['mascot']['represents']:
            raise ValueError('Assistant and mascot identity mismatch.')
        return
    characters = {c['id']: c['name'] for c in cast['characters']}
    assets = {a['path']: a['represents'] for a in cast['assets']}
    if len(characters) != len(cast['characters']) or len(assets) != len(cast['assets']):
        raise ValueError('Duplicate character or asset identity.')
    if any(owner not in characters for owner in assets.values()):
        raise ValueError('Asset represents an unknown character.')
    for binding in cast['bindings']:
        cid = binding['character_id']
        if cid not in characters or binding['display_name'] != characters[cid] or assets.get(binding['asset']) != cid:
            raise ValueError(f'Role/name/asset conflict in {binding.get("scene", "unknown scene")}')


def check_cues(cues, duration):
    previous_end = 0
    for cue in cues:
        start, end = float(cue['start']), float(cue['end'])
        if not cue['text'].strip() or not all(math.isfinite(x) for x in (start, end)):
            raise ValueError('Invalid subtitle text or timestamp.')
        if not 0 <= start < end <= duration + .05 or start < previous_end - .001:
            raise ValueError('Subtitle overlaps, reverses or extends beyond output.')
        previous_end = end


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'out', 'cues', 'cast', 'source-audio'):
        ap.add_argument('--' + name, required=name in ('video', 'out'), type=Path)
    ap.add_argument('--expected-duration', type=float)
    ap.add_argument('--ffmpeg')
    ap.add_argument('--ffprobe')
    a = ap.parse_args()
    if a.out.exists():
        raise ValueError('QA report already exists; use a new output name.')
    ff, fp = binary('ffmpeg', a.ffmpeg), binary('ffprobe', a.ffprobe)
    info = probe(a.video, fp)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic'))
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    duration = float(video.get('duration', info['format']['duration']))
    audio_duration = float(audio.get('duration', info['format']['duration']))
    issues = []
    result = subprocess.run([ff, '-nostdin', '-v', 'error', '-i', str(a.video), '-f', 'null', '-'], capture_output=True, text=True)
    if result.returncode or result.stderr.strip():
        issues.append('Full decode failed: ' + result.stderr[-1000:])
    if abs(duration - audio_duration) > .1:
        issues.append('Audio/video duration delta exceeds 100 ms.')
    if a.expected_duration is not None and abs(duration - a.expected_duration) > .1:
        issues.append('Unexpected output duration.')
    for path, fn in ((a.cues, lambda value: check_cues(value, duration)), (a.cast, check_cast)):
        if path:
            try:
                fn(json.loads(path.read_text(encoding='utf-8')))
            except (ValueError, KeyError, TypeError) as error:
                issues.append(str(error))
    correlation = None
    if a.source_audio:
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as tmp:
            signals = []
            for i, source in enumerate((a.source_audio, a.video)):
                wav = Path(tmp) / f'{i}.wav'
                process = subprocess.run([ff, '-nostdin', '-v', 'error', '-i', str(source), '-t', str(duration),
                                          '-map', '0:a:0', '-ac', '1', '-ar', '16000', str(wav)], capture_output=True)
                if process.returncode:
                    raise ValueError('Audio decode for correlation failed.')
                signals.append(sf.read(wav)[0])
            n = min(map(len, signals))
            if n < int((duration - .1) * 16000):
                issues.append('Source audio shorter than the retained interval.')
            if n and min(float(np.std(x[:n])) for x in signals) > 1e-8:
                correlation = float(np.corrcoef(signals[0][:n], signals[1][:n])[0, 1])
                if not math.isfinite(correlation) or correlation < .99:
                    issues.append('Audio differs from source prefix; inspect intended edits/mix.')
            else:
                issues.append('Silent/empty audio cannot establish source correlation.')
    report = {'passed': not issues, 'issues': issues, 'video_sha256': sha256(a.video),
              'size': [video['width'], video['height']], 'fps': video['r_frame_rate'],
              'video_duration': duration, 'audio_duration': audio_duration,
              'prefix_audio_correlation': correlation, 'decode_returncode': result.returncode,
              'visual_review': 'not_performed_by_script', 'listening_review': 'not_performed_by_script',
              'cast_scope': 'manifest consistency only; inspect rendered identities separately'}
    write_json(a.out, report)
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if not issues else 1)


if __name__ == '__main__':
    main()
