"""Recording + audio helpers for make_video.py.

- Recorder: captures the page through the browser's screencast with each frame's own timestamp, so video
  time equals real time and narration, click sounds and captions stay in sync.
- Narrator: offline neural text-to-speech with Piper. Default voice: "John" (en_US-john-medium, male,
  public-domain LibriVox recordings), at length_scale 0.74 (~160 words/min, about 1.25x its natural pace).
  It was picked with voice_bench.py as the clearest male voice (lowest Whisper word-error rate).
  Clips are cached in e2e/.tts_cache.
- Sounds: a soft mouse click and a very quiet keystroke, synthesised in code (no third-party audio files).
"""
import base64
import hashlib
import math
import random
import re
import subprocess
import time
import wave
from array import array
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
VOICE = HERE / ".voices" / "en_US-john-medium.onnx"
CACHE = HERE / ".tts_cache"
RATE = 22050  # Piper output rate (medium and high voices); the whole mix uses it


# ---------------------------------------------------------------- video
class Recorder:
    """Screencast frames -> ffmpeg at a constant frame rate. Each frame is repeated until the next frame's
    timestamp, using the running total, so no time is lost to rounding."""

    def __init__(self, context, page, out_path: Path, fps: int = 25, size=(1600, 900)):
        self.fps = fps
        self.t0: float | None = None
        self.written = 0
        self.last: bytes | None = None
        self.proc = subprocess.Popen(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
             "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p",
             str(out_path)], stdin=subprocess.PIPE)
        self.cdp = context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": size[0],
                                               "maxHeight": size[1], "everyNthFrame": 1})

    def _on_frame(self, ev):
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass
        ts = ev["metadata"].get("timestamp") or time.time()
        if self.t0 is None:
            self.t0 = ts
        self._fill(ts)
        self.last = base64.b64decode(ev["data"])

    def _fill(self, ts: float):
        if self.last is None or self.t0 is None:
            return
        target = int((ts - self.t0) * self.fps)
        while self.written < target:
            self.proc.stdin.write(self.last)
            self.written += 1

    def video_time(self, wall: float) -> float:
        return max(0.0, wall - (self.t0 or wall))

    def stop(self) -> float:
        try:
            self.cdp.send("Page.stopScreencast")
        except Exception:
            pass
        self._fill(time.time())
        if self.last is not None:  # always end on a complete frame
            self.proc.stdin.write(self.last)
            self.written += 1
        self.proc.stdin.close()
        self.proc.wait()
        return self.written / self.fps


# ---------------------------------------------------------------- speech
ACRONYMS = {
    # Spellings chosen by testing with a speech recogniser (Whisper) for the clearest pronunciation.
    "SurakshaFD": "Soo-ruck-sha F D", "FastAPI": "Fast A P I", "SQLite": "S Q Lite", "LynxCode": "Lynx Code",
    "Lynxcode": "Lynx Code", "FDRs": "F D Rs", "FDR": "F D R", "OCR": "O C R", "AICTE": "A, I, C, T, E",
    "API": "A P I", "CSV": "C S V", "SMS": "S M S", "SIH": "S I H", "PDF": "P D F", "JPG": "J P G", "PNG": "P N G",
    "MB": "megabytes",
}


def speechify(html: str) -> str:
    """Caption HTML -> natural spoken English."""
    t = re.sub(r"<[^>]+>", "", html).replace("&amp;", "and").replace("&", " and ")
    t = re.sub(r"₹\s?(\d[\d,]*\d)", lambda m: _rupees(m.group(1)), t)
    t = t.replace("60 / 30 / 7-day", "60, 30 and 7 day").replace("→", " to ").replace("…", ", ").replace("·", ",")
    t = t.replace("sample_documents", "sample documents").replace("Demo / Simulated", "demo, simulated")
    t = t.replace(" / ", " or ")
    for k, v in ACRONYMS.items():
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    t = re.sub(r"\s+", " ", t).strip(" ,")
    return t if t.endswith((".", "!", "?")) else t + "."


def _rupees(num: str) -> str:
    n = int(num.replace(",", ""))
    if n >= 100000 and n % 100000 == 0:
        return f"{n // 100000} lakh rupees"
    if n >= 100000 and n % 10000 == 0:
        return f"{n / 100000:g} lakh rupees"
    return f"{n} rupees"


class Narrator:
    def __init__(self, length_scale: float = 0.74):
        self.length_scale = length_scale
        self._voice = None
        CACHE.mkdir(exist_ok=True)

    def _path(self, text: str) -> Path:
        key = hashlib.sha1(f"{VOICE.name}|{self.length_scale}|{text}".encode()).hexdigest()[:20]
        return CACHE / f"{key}.wav"

    def clip(self, text: str) -> tuple[Path, float]:
        """Synthesised WAV for `text` (cached) and its duration in seconds."""
        p = self._path(text)
        if not p.exists():
            if self._voice is None:
                from piper import PiperVoice
                self._voice = PiperVoice.load(str(VOICE))
            from piper import SynthesisConfig
            tmp = p.with_suffix(".tmp")
            with wave.open(str(tmp), "wb") as w:
                self._voice.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=self.length_scale))
            tmp.replace(p)
        with wave.open(str(p)) as w:
            return p, w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- sound effects (synthesised, subtle)
def _bandpass(x: list[float], f0: float, q: float) -> list[float]:
    """2nd-order band-pass (RBJ biquad) so noise sounds like a key or switch, not a hiss or a beep."""
    w = 2 * math.pi * f0 / RATE
    alpha = math.sin(w) / (2 * q)
    b0, b2, a0, a1, a2 = alpha, -alpha, 1 + alpha, -2 * math.cos(w), 1 - alpha
    y, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
    for v in x:
        out = (b0 * v + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, v, y1, out
        y.append(out)
    return y


def _transient(rng: random.Random, length: float, decay: float, f0: float, q: float, thump_hz: float,
               thump: float) -> list[float]:
    n = int(RATE * length)
    noise = [rng.uniform(-1, 1) * math.exp(-(i / RATE) / decay) for i in range(n)]
    body = _bandpass(noise, f0, q)
    out = [b + thump * math.sin(2 * math.pi * thump_hz * i / RATE) * math.exp(-(i / RATE) / 0.006)
           for i, b in enumerate(body)]
    peak = max(abs(v) for v in out) or 1
    return [v / peak for v in out]


def _click(rng: random.Random) -> list[float]:
    """Mouse button: short, dry 'tick' (press) plus a softer release, about -26 dB below the narration."""
    press = _transient(rng, 0.03, 0.0018, 3200 + rng.uniform(-200, 200), 1.6, 900, 0.15)
    release = _transient(rng, 0.025, 0.0012, 3800, 1.8, 1100, 0.1)
    gap = int(RATE * rng.uniform(0.055, 0.075))
    out = [0.05 * v for v in press] + [0.0] * max(0, gap - len(press))
    return out + [0.025 * v for v in release]


def _key(rng: random.Random) -> list[float]:
    """Laptop keystroke: muted mid-range 'tap' with a little low body, about -36 dB below the narration."""
    v = _transient(rng, 0.045, 0.004, 1500 + rng.uniform(-250, 250), 0.9, 160 + rng.uniform(-20, 20), 0.6)
    g = 0.016 * rng.uniform(0.7, 1.0)
    return [g * x for x in v]


def _read_wav(p: Path) -> list[float]:
    with wave.open(str(p)) as w:
        assert w.getframerate() == RATE and w.getsampwidth() == 2
        a = array("h")
        a.frombytes(w.readframes(w.getnframes()))
    return [s / 32768 for s in a]


def mix(duration: float, speech: list[tuple[float, Path]], clicks: list[float], keys: list[float], out: Path,
        speech_gain: float = 1.0):
    """Mixes narration clips and effects at their video times into one mono 16-bit WAV."""
    n = int(duration * RATE) + RATE
    track = array("f", bytes(4 * n))
    rng = random.Random(42)

    def add(at: float, samples: list[float], gain: float = 1.0):
        start = int(at * RATE)
        for i, s in enumerate(samples):
            j = start + i
            if 0 <= j < n:
                track[j] += s * gain

    for at, p in speech:
        add(at, _read_wav(p), speech_gain)
    for at in clicks:
        add(at, _click(rng))
    for at in keys:
        add(at, _key(rng))
    pcm = array("h", (max(-32767, min(32767, int(s * 32767))) for s in track))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
