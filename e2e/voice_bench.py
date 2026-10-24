"""Picks the clearest narration voice objectively: synthesise demo sentences, transcribe them with Whisper,
and compare word error rate (WER) and speaking rate. (Used during video production; not needed at runtime.)"""
import re
import sys
import time
import wave
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # this PC's antivirus intercepts HTTPS; trust the Windows certificate store
sys.stdout.reconfigure(encoding="utf-8")
from faster_whisper import WhisperModel  # noqa: E402
from piper import PiperVoice, SynthesisConfig  # noqa: E402

from video_audio import speechify  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / ".tts_cache" / "bench"
OUT.mkdir(parents=True, exist_ok=True)
SENTENCES = [
    "Welcome to SurakshaFD, a smart digital platform designed to simplify FDR and security deposit management for technical education institutions and AICTE officials.",
    "OCR automatically reads the bank name, the FDR number, the deposit amount of ₹10,00,000 and the maturity date.",
    "The officer records a simulated bank confirmation, because this prototype is not connected to a real bank.",
    "Every action is a real request to the FastAPI server, stored in the database with a timestamp.",
    "A different senior approving officer records the final decision. This is a demonstration approval, not a release of funds.",
]


def load16k(p: Path):
    import numpy as np
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        sr = w.getframerate()
    n = int(len(a) * 16000 / sr)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def norm(s: str) -> list[str]:
    s = s.lower().replace("₹10,00,000", "10 lakh rupees")
    s = re.sub(r"\b([a-z])\s(?=[a-z]\b)", r"\1", s)          # "f d r" -> "fdr"
    s = s.replace("suraksha fd", "surakshafd").replace("fast api", "fastapi").replace("10", "ten")
    return re.sub(r"[^a-z0-9 ]", " ", s).split()


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[len(hyp)] / max(1, len(ref))


def main():
    args = sys.argv[1:]
    SCALES = [float(x) for x in (args[args.index("--scales") + 1] if "--scales" in args else "0.82,0.87").split(",")]
    if "--scales" in args:
        del args[args.index("--scales"):args.index("--scales") + 2]
    asr = WhisperModel("base.en", device="cpu", compute_type="int8")
    print(f"{'voice':22} {'scale':>5} {'wpm':>5} {'WER':>6}")
    for voice in args or ["en_US-norman-medium", "en_US-john-medium", "en_US-bryce-medium", "en_US-ljspeech-high"]:
        v = PiperVoice.load(str(HERE / ".voices" / f"{voice}.onnx"))
        for scale in SCALES:
            errs, words, secs = 0.0, 0, 0.0
            for k, text in enumerate(SENTENCES):
                p = OUT / f"{voice}_{scale}_{k}.wav"
                with wave.open(str(p), "wb") as w:
                    v.synthesize_wav(speechify(text), w, syn_config=SynthesisConfig(length_scale=scale))
                with wave.open(str(p)) as w:
                    secs += w.getnframes() / w.getframerate()
                hyp = " ".join(s.text for s in asr.transcribe(load16k(p), language="en", beam_size=5)[0])
                ref = norm(text)
                errs += wer(ref, norm(hyp)) * len(ref)
                words += len(ref)
            print(f"{voice:22} {scale:>5} {words / secs * 60:>5.0f} {errs / words:>6.1%}")


if __name__ == "__main__":
    main()
