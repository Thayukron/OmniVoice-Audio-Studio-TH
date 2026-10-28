"""
Thai text normalisation for TTS.

OmniVoice reads Thai script well but stumbles on things a Thai reader expands in
their head: digits, ๆ (mai yamok), ฯลฯ, common abbreviations and symbols. This
module rewrites those into plain spoken Thai before generation.
"""

import re

try:
    from pythainlp.util import num_to_thaiword
    from pythainlp.tokenize import word_tokenize
except ImportError:  # normaliser degrades to a no-op for digits / ๆ
    num_to_thaiword = None
    word_tokenize = None

THAI_CHAR = re.compile(r'[฀-๿]')
THAI_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
DIGIT_WORDS = ['ศูนย์', 'หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า']

# Applied in order, before numbers are expanded.
ABBREVIATIONS = [
    ('ฯลฯ', ' และอื่น ๆ '),
    ('กรุงเทพฯ', 'กรุงเทพมหานคร'),
    ('ร.ร.', 'โรงเรียน'),
    ('ร.พ.', 'โรงพยาบาล'),
    ('รพ.', 'โรงพยาบาล'),
    ('ม.ค.', 'มกราคม'), ('ก.พ.', 'กุมภาพันธ์'), ('มี.ค.', 'มีนาคม'),
    ('เม.ย.', 'เมษายน'), ('พ.ค.', 'พฤษภาคม'), ('มิ.ย.', 'มิถุนายน'),
    ('ก.ค.', 'กรกฎาคม'), ('ส.ค.', 'สิงหาคม'), ('ก.ย.', 'กันยายน'),
    ('ต.ค.', 'ตุลาคม'), ('พ.ย.', 'พฤศจิกายน'), ('ธ.ค.', 'ธันวาคม'),
    ('พ.ศ.', 'พุทธศักราช'), ('ค.ศ.', 'คริสต์ศักราช'),
    ('ดร.', 'ดอกเตอร์'), ('ศ.', 'ศาสตราจารย์'), ('ผศ.', 'ผู้ช่วยศาสตราจารย์'),
    ('รศ.', 'รองศาสตราจารย์'), ('นพ.', 'นายแพทย์'), ('พญ.', 'แพทย์หญิง'),
    ('จ.', 'จังหวัด'), ('อ.', 'อำเภอ'), ('ต.', 'ตำบล'),
    ('กม.', 'กิโลเมตร'), ('ซม.', 'เซนติเมตร'), ('มม.', 'มิลลิเมตร'),
    ('กก.', 'กิโลกรัม'), ('ชม.', 'ชั่วโมง'), ('นศ.', 'นักศึกษา'),
]

SYMBOLS = [
    ('%', 'เปอร์เซ็นต์'),
    ('฿', 'บาท'),
    ('$', ' ดอลลาร์ '),
    ('&', ' และ '),
    ('+', ' บวก '),
    ('=', ' เท่ากับ '),
    ('°C', 'องศาเซลเซียส'),
]

PAUSE_TAG = re.compile(r'\[pause[^\]]*\]', re.IGNORECASE)


def is_thai(text):
    return bool(THAI_CHAR.search(text or ''))


def _read_number(match):
    raw = match.group(0)
    num = raw.replace(',', '')
    if num_to_thaiword is None:
        return raw
    if '.' in num:
        whole, frac = num.split('.', 1)
        whole_words = num_to_thaiword(int(whole)) if whole else 'ศูนย์'
        # Decimals are read digit by digit: 3.25 -> สามจุดสองห้า
        return f'{whole_words}จุด{"".join(DIGIT_WORDS[int(d)] for d in frac)}'
    # Long digit strings (phone numbers, IDs) are read digit by digit
    if len(num) > 1 and num.startswith('0') or len(num) > 12:
        return ''.join(DIGIT_WORDS[int(d)] for d in num)
    return num_to_thaiword(int(num))


def _read_time(match):
    h, m = int(match.group(1)), int(match.group(2))
    if num_to_thaiword is None:
        return match.group(0)
    spoken = f'{num_to_thaiword(h)}นาฬิกา'
    if m:
        spoken += f'{num_to_thaiword(m)}นาที'
    return spoken


def _expand_mai_yamok(text):
    """ๆ repeats the preceding word: เด็กๆ -> เด็กเด็ก."""
    if 'ๆ' not in text or word_tokenize is None:
        return text
    out = []
    for tok in word_tokenize(text, engine='newmm', keep_whitespace=True):
        if tok.strip() == 'ๆ':
            prev = next((t for t in reversed(out) if t.strip()), '')
            out.append(prev)
        elif tok.endswith('ๆ') and len(tok) > 1:
            base = tok.rstrip('ๆ').rstrip()
            out.append(base + base)
        else:
            out.append(tok)
    return ''.join(out)


def _expand_abbreviations(text):
    # Longest first so ผศ. wins over ศ.; a one-letter abbreviation (จ. อ. ต.) must not
    # follow another Thai letter, otherwise the ต. ending a word would be expanded.
    for src, dst in sorted(ABBREVIATIONS, key=lambda a: -len(a[0])):
        guard = r'(?<![฀-๿])' if len(src) <= 3 else ''
        text = re.sub(guard + re.escape(src), dst, text)
    return text


def _normalise_segment(text):
    text = _expand_abbreviations(text)
    text = text.translate(THAI_DIGITS)
    text = re.sub(r'\b(\d{1,2})[:.](\d{2})\s*น\.', _read_time, text)
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _read_time, text)
    text = re.sub(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?', _read_number, text)
    for src, dst in SYMBOLS:
        text = text.replace(src, dst)
    text = _expand_mai_yamok(text)
    # Thai-to-Thai spacing: collapse runs of spaces, trim spaces next to punctuation
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+([,.!?)])', r'\1', text)
    text = re.sub(r'\(\s+', '(', text)
    return text.strip()


def normalize_thai(text):
    """Normalise Thai text for TTS, leaving [pause ...] tags untouched."""
    if not is_thai(text):
        return text
    parts, last = [], 0
    for m in PAUSE_TAG.finditer(text):
        parts.append(_normalise_segment(text[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(_normalise_segment(text[last:]))
    return ' '.join(p for p in parts if p)


if __name__ == '__main__':
    for sample in [
        'ราคา 1,250 บาท ลดเหลือ 999 บาท (ลด 20%)',
        'เด็กๆ ไปโรงเรียนตอน 7:30 น. ทุกวัน',
        'อุณหภูมิ 36.5 องศา โทร 0812345678',
        'พบกันที่กรุงเทพฯ วันที่ ๑๒ ม.ค. พ.ศ. 2569 [pause 1s] แล้วเจอกันนะ',
    ]:
        print(sample, '\n  ->', normalize_thai(sample))
