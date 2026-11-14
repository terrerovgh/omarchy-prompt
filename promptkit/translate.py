"""Language detection + translation to English with Google's keyless endpoints.

Vendored from omarchy-translate (io.github.terrerovgh.translate-selection).
The Chrome-extension endpoint is tried first; translate.googleapis.com
("gtx") often answers 429 with a captcha page, so it is only a fallback.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

DICT_ENDPOINT = "https://clients5.google.com/translate_a/t"
GTX_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
MAX_RESPONSE = 1024 * 1024
TIMEOUT = 10
# Google's GET-style endpoints reject very large bodies; translate in chunks.
CHUNK = 4500


class TranslateError(Exception):
    pass


def _post(url, params, text):
    req = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        data=urllib.parse.urlencode({"q": text}).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("response too large")
    return json.loads(raw.decode("utf-8"))


def _dict(text, target):
    data = _post(DICT_ENDPOINT, [("client", "dict-chrome-ex"), ("sl", "auto"), ("tl", target)], text)
    first = data[0]
    if isinstance(first, list):
        return str(first[0]), str(first[1]) if len(first) > 1 else ""
    return str(first), ""


def _gtx(text, target):
    data = _post(GTX_ENDPOINT, [("client", "gtx"), ("sl", "auto"), ("tl", target), ("dt", "t")], text)
    segments = data[0] or []
    translated = "".join(s[0] for s in segments if isinstance(s, list) and isinstance(s[0], str))
    source = data[2] if len(data) > 2 and isinstance(data[2], str) else ""
    return translated, source


def _one(text, target):
    try:
        translated, source = _dict(text, target)
        if translated:
            return translated, source[:16]
    except (urllib.error.URLError, ValueError, IndexError, TypeError, KeyError, TimeoutError):
        pass
    try:
        translated, source = _gtx(text, target)
    except urllib.error.HTTPError as e:
        raise TranslateError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise TranslateError(f"network: {getattr(e, 'reason', e)}") from e
    except (ValueError, IndexError, TypeError, KeyError) as e:
        raise TranslateError(f"bad response: {e}") from e
    return translated, source[:16]


def _chunks(text):
    """Split on paragraph boundaries so each piece stays under CHUNK chars."""
    if len(text) <= CHUNK:
        return [text]
    pieces, current = [], ""
    for para in text.split("\n"):
        while len(para) > CHUNK:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(para[:CHUNK])
            para = para[CHUNK:]
        if len(current) + len(para) + 1 > CHUNK:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def to_english(text):
    """Return (english_text, source_lang). English input is returned as is."""
    pieces = _chunks(text)
    out, source = [], ""
    for i, piece in enumerate(pieces):
        translated, src = _one(piece, "en")
        if i == 0:
            source = src
            if src.split("-")[0] == "en":
                return text, "en"
        out.append(translated)
    return "\n".join(out), source or "?"


def detect(text):
    """Language code of text (first 1000 characters), or '' if unknown."""
    try:
        _, source = _one(text[:1000], "en")
    except TranslateError:
        return ""
    return source.split("-")[0]
