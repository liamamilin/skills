"""Local forced alignment; preserves raw output and refuses to guess mismatched text."""
import argparse
import json
import math
import os
from pathlib import Path
from media_common import write_json


def normalized(text):
    return ''.join(c.casefold() for c in text if c.isalnum())


def phrase_cues(lines, words, duration):
    expected = ''.join(normalized(line) for line in lines)
    actual = ''.join(normalized(w['text']) for w in words)
    if expected != actual:
        raise ValueError('Aligner text differs from transcript. Inspect alignment.raw.json; no guessed cues written.')
    spans, offset = [], 0
    for word in words:
        length = len(normalized(word['text']))
        if length:
            start, end = float(word['start']), float(word['end'])
            if not all(math.isfinite(v) for v in (start, end)) or not 0 <= start <= end <= duration + .05:
                raise ValueError('Invalid word timestamp in alignment.raw.json.')
            spans.append((offset, offset + length, start, end))
            offset += length
    cues, offset, previous_end = [], 0, 0
    for line in lines:
        end_offset = offset + len(normalized(line))
        hits = [s for s in spans if s[0] < end_offset and s[1] > offset]
        if not hits:
            raise ValueError('Phrase has no aligned words.')
        start, end = min(s[2] for s in hits), max(s[3] for s in hits)
        if end <= start or start < previous_end - .001:
            raise ValueError('Zero-duration/overlapping phrase; review raw alignment before making subtitles.')
        cues.append({'text': line, 'start': start, 'end': end, 'timing': 'machine_alignment_unreviewed'})
        offset, previous_end = end_offset, end
    return cues


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', required=True, type=Path)
    ap.add_argument('--model', required=True, type=Path)
    ap.add_argument('--transcript', required=True, type=Path)
    ap.add_argument('--language', default='Chinese')
    a = ap.parse_args()
    p = a.project.resolve(strict=True)
    for name in ('alignment.raw.json', 'cues.json', 'lyrics.srt'):
        if (p / name).exists():
            raise ValueError(f'{name} exists. Preserve it and use a new version directory.')
    lines = [s.strip() for s in a.transcript.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    if not lines or any(not normalized(s) or s.startswith('[') for s in lines):
        raise ValueError('Use one actual sung phrase per line; remove section headings before alignment.')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    import soundfile as sf
    from mlx_audio.stt.utils import load_model
    audio, sr = sf.read(p / 'alignment.wav', dtype='float32')
    if sr != 16000 or audio.ndim != 1:
        raise ValueError('Run prepare_project.py to create mono 16k alignment.wav.')
    model = load_model(str(a.model.resolve(strict=True)))
    result = model.generate(audio, text='\n'.join(lines), language=a.language)
    words = [{'text': i.text, 'start': float(i.start_time), 'end': float(i.end_time)} for i in result.items]
    duration = len(audio) / sr
    write_json(p / 'alignment.raw.json', {'method': 'local Qwen3 forced alignment', 'duration': duration,
                                        'listening_review': 'not_performed', 'words': words})
    cues = phrase_cues(lines, words, duration)
    write_json(p / 'cues.json', cues)
    (p / 'lyrics.srt').write_text('\n\n'.join(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}'
                                             for i, c in enumerate(cues, 1)) + '\n', encoding='utf-8')
    print(f'Wrote {len(cues)} machine-aligned phrases. Listening review still required.')


if __name__ == '__main__':
    main()
