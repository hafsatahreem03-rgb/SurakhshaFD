"""Records the SurakshaFD product walkthrough video (4-5 minutes, all 11 workflow steps).

    .venv\\Scripts\\python make_video.py               record + edit
    .venv\\Scripts\\python make_video.py --encode-only re-edit the last recording (no new capture)

Pipeline
  1. Narration is synthesised first (Piper, male "John" voice, ~1.25x pace), so every scene knows its length.
  2. Microsoft Edge runs the real app (FastAPI + database + Tesseract OCR) at 1600x810. A timestamped screencast
     recorder captures it; cursor, clicks, keystrokes, zooms and narration are logged on the same clock.
  3. Editing: the recording is scaled to 1920x972 and placed above a 108 px caption band (1920x1080 total), so
     captions never cover the website. Subtle zoom-ins, fades, quiet click/keyboard sounds and the voice are added.
Output: video\\SurakshaFD_Walkthrough.mp4 (1080p H.264 + AAC) and video\\SurakshaFD_Walkthrough.srt
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Playwright's screen-recording component lives inside the project (e2e\.pw-browsers), not the user profile.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).resolve().parent / ".pw-browsers"))

import imageio_ffmpeg  # noqa: E402
from playwright.sync_api import Locator, Page, expect, sync_playwright  # noqa: E402

from video_audio import Narrator, Recorder, mix, speechify  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BACKEND, FRONTEND, SAMPLES = ROOT / "backend", ROOT / "frontend", ROOT / "sample_documents"
OUT_DIR = ROOT / "video"
RAW_DIR = OUT_DIR / "_raw"
BASE = "http://localhost:5173"
VIEW = {"width": 1600, "height": 810}      # recorded website area -> scaled to 1920x972
OUT_W, SITE_H, BAND_H = 1920, 972, 108     # final frame: website on top, caption band below
FPS = 25
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
TOTAL_STEPS = 11
MIN_SECONDS, MAX_SECONDS = 240, 300
DEMO1_FDR = "JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf"
DEMO1_PROOF = "JUDGE_DEMO1_Payment_Proof.pdf"
SAMPLE_LISTING: list[dict] = []

# ---------------------------------------------------------------- in-page overlay (cursor, clicks, highlight, dialog, transitions)
OVERLAY_JS = r"""
(() => {
  if (window.__sfd || window.top !== window) return; window.__sfd = true;  // top page only, not the PDF viewer frame
  const ssGet = k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } };
  const ssSet = (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} };
  const css = `
    #__cur{position:fixed;left:0;top:0;width:20px;height:20px;z-index:2147483647;pointer-events:none;
      transition:transform .05s linear;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}
    .__rip{position:fixed;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;z-index:2147483646;
      pointer-events:none;border:2px solid rgba(18,176,154,.85);animation:__rip .45s ease-out forwards}
    @keyframes __rip{to{transform:scale(2.6);opacity:0}}
    .__hl{position:fixed;z-index:2147483640;pointer-events:none;border:3px solid #12b09a;border-radius:12px;
      box-shadow:0 0 0 5px rgba(18,176,154,.18);animation:__pulse 1.1s ease-in-out infinite alternate}
    @keyframes __pulse{from{box-shadow:0 0 0 3px rgba(18,176,154,.22)}to{box-shadow:0 0 0 9px rgba(18,176,154,.06)}}
    #__curtain{position:fixed;inset:0;z-index:2147483645;pointer-events:none;display:flex;flex-direction:column;
      align-items:center;justify-content:center;gap:10px;opacity:0;transition:opacity .35s ease;
      background:radial-gradient(circle at 75% 20%,rgba(18,176,154,.28),transparent 50%),#071533;
      font-family:Inter,'Segoe UI',sans-serif;color:#fff}
    #__curtain.on{opacity:1}
    #__curtain .k{font-size:15px;letter-spacing:.22em;text-transform:uppercase;color:#7dd3c8;font-weight:600}
    #__curtain .r{font-size:44px;font-weight:800}
    #__curtain .e{font-size:16px;color:#9fb3d6}
    #__curtain .end{display:flex;flex-direction:column;align-items:center;gap:18px;animation:__rise .9s ease-out}
    @keyframes __rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
    #__curtain .end h1{margin:0;font-size:68px;font-weight:800;letter-spacing:-1px;color:#fff}
    #__curtain .end h1 span{color:#2ccbb1}
    #__curtain .end .tag{font-size:22px;color:#cfd9ec}
    #__curtain .chips{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;max-width:1100px;margin-top:10px}
    #__curtain .chips span{opacity:0;padding:10px 18px;border-radius:999px;font-size:18px;font-weight:600;color:#e6fffb;
      background:rgba(18,176,154,.16);border:1px solid rgba(44,203,177,.55);animation:__chip .5s ease-out forwards}
    @keyframes __chip{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
    #__curtain .end .note{margin-top:8px;font-size:14px;color:#8ea3c7;letter-spacing:.04em}
    #__dlgwrap{position:fixed;inset:0;z-index:2147483600;background:rgba(7,21,51,.35);display:flex;align-items:center;justify-content:center;
      animation:__fade .25s ease-out;font-family:'Segoe UI',Inter,sans-serif}
    @keyframes __fade{from{opacity:0}to{opacity:1}}
    #__dlg{width:1040px;height:610px;background:#fff;border-radius:10px;box-shadow:0 30px 80px rgba(0,0,0,.45);display:flex;flex-direction:column;overflow:hidden;
      border:1px solid #c9ced6;animation:__pop .25s ease-out}
    @keyframes __pop{from{transform:scale(.97);opacity:.4}to{transform:none;opacity:1}}
    #__dlg .tb{height:38px;display:flex;align-items:center;justify-content:space-between;padding:0 4px 0 14px;background:#f3f3f3;font-size:13px;color:#1b1b1b}
    #__dlg .tb .x{width:42px;height:30px;display:flex;align-items:center;justify-content:center;color:#444;font-size:16px}
    #__dlg .bar{display:flex;gap:8px;align-items:center;padding:8px 12px;border-bottom:1px solid #e5e5e5;background:#fafafa}
    #__dlg .addr{flex:1;border:1px solid #d6d6d6;border-radius:5px;padding:5px 10px;font-size:13px;color:#222;background:#fff}
    #__dlg .addr span{color:#888;margin:0 6px}
    #__dlg .search{width:210px;border:1px solid #d6d6d6;border-radius:5px;padding:5px 10px;font-size:13px;color:#999;background:#fff}
    #__dlg .body{flex:1;display:flex;min-height:0}
    #__dlg .nav{width:170px;border-right:1px solid #eee;padding:10px 6px;font-size:13px;color:#333}
    #__dlg .nav div{padding:6px 10px;border-radius:5px}
    #__dlg .nav .on{background:#e5effa;font-weight:600}
    #__dlg .list{flex:1;overflow:hidden;font-size:13px}
    #__dlg .hdr,#__dlg .row{display:grid;grid-template-columns:1fr 150px 120px 80px;align-items:center;padding:0 12px;height:30px}
    #__dlg .hdr{color:#666;font-size:12px;border-bottom:1px solid #eee}
    #__dlg .row{color:#1b1b1b;cursor:default;border-radius:4px;margin:1px 6px}
    #__dlg .row:hover{background:#f0f5fb}
    #__dlg .row.sel{background:#cce4f7;outline:1px solid #99c9ef}
    #__dlg .nm{display:flex;align-items:center;gap:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #__dlg .ic{flex:none;width:16px;height:19px;border-radius:2px;font:700 6.5px/19px Arial;color:#fff;text-align:center}
    #__dlg .ic.pdf{background:#d83b2d}#__dlg .ic.jpg,#__dlg .ic.png{background:#2b7cd3}
    #__dlg .dim{color:#666}
    #__dlg .pv{width:250px;border-left:1px solid #eee;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:14px;color:#888;font-size:12px;text-align:center;gap:10px}
    #__dlg .pv img{max-width:220px;max-height:330px;box-shadow:0 2px 10px rgba(0,0,0,.25);background:#fff}
    #__dlg .foot{display:flex;align-items:center;gap:10px;padding:12px 14px;border-top:1px solid #e5e5e5;background:#fafafa;font-size:13px}
    #__dlg .fn{flex:1;border:1px solid #d6d6d6;border-radius:5px;padding:6px 10px;background:#fff;min-height:16px;color:#1b1b1b}
    #__dlg .flt{width:250px;border:1px solid #d6d6d6;border-radius:5px;padding:6px 10px;background:#fff;color:#333}
    #__dlg .btn{border-radius:5px;padding:7px 26px;border:1px solid #c7c7c7;background:#fff;font-size:13px}
    #__dlg .btn.open{background:#0067c0;border-color:#0067c0;color:#fff}`;
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const cur = document.createElement('div'); cur.id = '__cur';
    cur.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M3 2l7.5 19 2.4-7.6L20.5 11z" fill="#0b2047" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(cur);
    const p = JSON.parse(ssGet('__pos') || '[800,405]');
    cur.style.transform = `translate(${p[0]}px,${p[1]}px)`;
    const c = document.createElement('div'); c.id = '__curtain'; document.body.appendChild(c);
    if (ssGet('__curtain')) { c.innerHTML = ssGet('__curtain'); c.classList.add('on'); }
  };
  window.__curtain = (html) => {
    const c = document.getElementById('__curtain'); if (!c) return;
    if (html) { c.innerHTML = html; ssSet('__curtain', html); c.classList.add('on'); }
    else { ssSet('__curtain', ''); c.classList.remove('on'); }
  };
  window.__openDialog = (data) => {
    document.getElementById('__dlgwrap')?.remove();
    const w = document.createElement('div'); w.id = '__dlgwrap';
    const rows = data.files.map((f, i) => `<div class="row" data-name="${f.name}" data-i="${i}">
        <div class="nm"><span class="ic ${f.kind}">${f.kind.toUpperCase()}</span>${f.name}</div>
        <div class="dim">${f.modified}</div><div class="dim">${f.kind === 'pdf' ? 'PDF Document' : f.kind.toUpperCase() + ' File'}</div>
        <div class="dim" style="text-align:right">${f.size}</div></div>`).join('');
    w.innerHTML = `<div id="__dlg">
      <div class="tb"><span>Open</span><span class="x">✕</span></div>
      <div class="bar"><div class="addr">This PC<span>›</span>Desktop<span>›</span>SurakshaFD<span>›</span><b>sample_documents</b></div>
        <div class="search">Search sample_documents</div></div>
      <div class="body">
        <div class="nav"><div>Home</div><div class="on">Desktop</div><div>Downloads</div><div>Documents</div><div>This PC</div></div>
        <div class="list"><div class="hdr"><div>Name</div><div>Date modified</div><div>Type</div><div style="text-align:right">Size</div></div>${rows}</div>
        <div class="pv"><div>Select a file to preview</div></div>
      </div>
      <div class="foot"><span>File name:</span><div class="fn"></div>
        <div class="flt">Documents (*.pdf;*.jpg;*.jpeg;*.png)</div>
        <span class="btn open">Open</span><span class="btn">Cancel</span></div></div>`;
    document.body.appendChild(w);
    w.querySelectorAll('.row').forEach(r => r.addEventListener('mousedown', () => {
      w.querySelectorAll('.row').forEach(x => x.classList.remove('sel')); r.classList.add('sel');
      const f = data.files[+r.dataset.i];
      w.querySelector('.fn').textContent = f.name;
      w.querySelector('.pv').innerHTML = f.thumb ? `<img src="${f.thumb}"><div>${f.name}</div>` : `<div>${f.name}</div>`;
    }));
  };
  window.__closeDialog = () => document.getElementById('__dlgwrap')?.remove();
  window.__hl = (x, y, w, h, ms) => {
    const d = document.createElement('div'); d.className = '__hl';
    Object.assign(d.style, {left: (x - 6) + 'px', top: (y - 6) + 'px', width: (w + 12) + 'px', height: (h + 12) + 'px'});
    document.body.appendChild(d); setTimeout(() => d.remove(), ms);
  };
  addEventListener('mousemove', e => {
    const c = document.getElementById('__cur'); if (c) c.style.transform = `translate(${e.clientX}px,${e.clientY}px)`;
    ssSet('__pos', JSON.stringify([e.clientX, e.clientY]));
  }, true);
  addEventListener('mousedown', e => {
    const r = document.createElement('div'); r.className = '__rip';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.body.appendChild(r); setTimeout(() => r.remove(), 500);
  }, true);
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', mk) : mk();
})();
"""

THUMB_SCRIPT = r'''
import base64, io, json, sys
from pathlib import Path
import fitz
from PIL import Image
out = {}
for p in sorted(Path(sys.argv[1]).iterdir()):
    if p.suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg"):
        continue
    if p.suffix.lower() == ".pdf":
        with fitz.open(p) as d:
            img = Image.open(io.BytesIO(d[0].get_pixmap(dpi=40).tobytes("png")))
    else:
        img = Image.open(p); img.thumbnail((240, 340))
    b = io.BytesIO(); img.convert("RGB").save(b, "JPEG", quality=80)
    out[p.name] = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
print(json.dumps(out))
'''


def build_sample_listing() -> list[dict]:
    import json
    thumbs = json.loads(subprocess.run([PY, "-c", THUMB_SCRIPT, str(SAMPLES)], capture_output=True, text=True,
                                       check=True).stdout)
    rows = []
    for name in sorted(thumbs):
        st = (SAMPLES / name).stat()
        kind = (SAMPLES / name).suffix.lower().lstrip(".").replace("jpeg", "jpg")
        rows.append({"name": name, "kind": kind, "size": f"{max(1, round(st.st_size / 1024))} KB",
                     "modified": time.strftime("%d-%m-%Y %H:%M", time.localtime(st.st_mtime)), "thumb": thumbs[name]})
    return rows


# ---------------------------------------------------------------- narration text
def display_text(text: str) -> str:
    """Caption text: the narration without the spoken 'Step four:' lead-in (the band's step label shows it)."""
    return re.sub(r"^Step \w+[:.,]\s*", "", text).strip()


def caption_chunks(text: str, limit: int = 118) -> list[str]:
    """Split a caption into short pieces (one to two lines each in the band)."""
    parts = re.split(r"(?<=[.?!])\s+", display_text(text))
    out: list[str] = []
    for p in parts:
        while len(p) > limit:
            cut = p.rfind(", ", 0, limit)
            cut = cut + 1 if cut > limit * 0.4 else p.rfind(" ", 0, limit)
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            if out and len(out[-1]) + len(p) + 1 <= limit * 0.75:
                out[-1] = f"{out[-1]} {p}"
            else:
                out.append(p)
    return out


# ---------------------------------------------------------------- director
class Director:
    """Drives the app and logs everything on one wall clock (time.time()); the Recorder maps it to video time."""

    def __init__(self, page: Page, narrator: Narrator):
        self.page = page
        self.narrator = narrator
        self.cues: list[list] = []      # [start, end, step_label, text]
        self.speech: list[tuple[float, Path]] = []
        self.clicks: list[float] = []
        self.keys: list[float] = []
        self.zooms: list[list] = []     # [start, end, cx, cy, z]
        self.speech_end = 0.0
        self.label = ""

    def now(self) -> float:
        return time.time()

    def hold(self, s: float):
        if s > 0:
            self.page.wait_for_timeout(int(s * 1000))

    def wait_speech(self, pad: float = 0.0):
        self.hold(self.speech_end + pad - self.now())

    def say(self, text: str, step: int | None = None):
        """Narrate `text` (waits for the previous sentence first); captions follow the voice chunk by chunk."""
        self.wait_speech()
        if step:
            self.label = f"STEP {step} OF {TOTAL_STEPS}"
        path, dur = self.narrator.clip(speechify(text))
        start = self.now() + 0.15
        self.speech.append((start, path))
        self.speech_end = start + dur + 0.3
        chunks = caption_chunks(text)
        total = sum(len(c) for c in chunks) or 1
        t = start
        for c in chunks:
            span = dur * len(c) / total
            self.cues.append([t, t + span + 0.15, self.label, c])
            t += span

    # ---- camera
    def zoom(self, loc: Locator, seconds: float = 3.2, max_z: float = 1.35, highlight: bool = True):
        """Subtle zoom towards an element (applied in post-production, so the page itself is untouched)."""
        self.focus(loc)
        box = loc.first.bounding_box()
        if not box:
            return
        vw, vh = VIEW["width"], VIEW["height"]
        z = max(1.1, min(max_z, 0.9 * vw / box["width"], 0.9 * vh / box["height"]))
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        start = self.now()
        self.zooms.append([start, start + seconds, cx, cy, round(z, 3)])
        if highlight:
            self.page.evaluate("([x, y, w, h, ms]) => window.__hl(x, y, w, h, ms)",
                               [box["x"], box["y"], box["width"], box["height"], int(seconds * 1000)])
        self.hold(seconds)

    def highlight(self, loc: Locator, seconds: float = 2.4):
        self.focus(loc)
        box = loc.first.bounding_box()
        if box:
            self.page.evaluate("([x, y, w, h, ms]) => window.__hl(x, y, w, h, ms)",
                               [box["x"], box["y"], box["width"], box["height"], int(seconds * 1000)])
        self.hold(seconds)

    def focus(self, loc: Locator):
        loc.first.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
        self.hold(0.7)

    def scroll_by(self, dy: int, wait: float = 0.8):
        self.page.evaluate("dy => window.scrollBy({top: dy, behavior: 'smooth'})", dy)
        self.hold(wait)

    def top(self):
        self.page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
        self.hold(0.6)

    # ---- hands
    def move_to(self, loc: Locator, steps: int = 18):
        loc = loc.first
        loc.scroll_into_view_if_needed()
        box = loc.bounding_box()
        if box:
            self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
            self.hold(0.15)

    def click(self, loc: Locator, pause: float = 0.4, sound: bool = True):
        self.move_to(loc)
        if sound:
            self.clicks.append(self.now() + 0.02)
        loc.first.click()
        self.hold(pause)

    def type(self, loc: Locator, text: str):
        """Human-speed typing (60-110 ms per key), each keystroke logged for a very quiet key sound."""
        import random
        rng = random.Random(len(text))
        self.click(loc, 0.15)
        loc.first.fill("")
        for ch in text:
            self.keys.append(self.now())
            self.page.keyboard.type(ch)
            self.page.wait_for_timeout(int(rng.uniform(45, 95)))
        if loc.first.input_value() != text:  # never continue with a half-typed field
            loc.first.fill(text)
        self.hold(0.25)

    def choose_file(self, trigger: Locator, filename: str):
        """Click the real upload control; show an Open dialog listing sample_documents; pick the file; Open.

        The browser's genuine file-chooser event is intercepted and the real file handed to the app. The dialog is
        drawn by the recorder because Windows' own dialog cannot be captured on video."""
        with self.page.expect_file_chooser() as fc:
            self.click(trigger, 0.1)
        chooser = fc.value
        self.page.evaluate("data => window.__openDialog(data)", {"files": SAMPLE_LISTING})
        self.hold(0.9)
        self.click(self.page.locator(f'#__dlg .row[data-name="{filename}"]'), 1.1)
        self.click(self.page.locator("#__dlg .btn.open"), 0.25)
        self.page.evaluate("() => window.__closeDialog()")
        chooser.set_files(str(SAMPLES / filename))
        self.hold(0.2)

    def closing_card(self, statement: str):
        """Brief closing: SurakshaFD card, the five capabilities appearing as they are spoken, then a gentle hold."""
        path, dur = self.narrator.clip(speechify(statement))
        items = ["Document submission", "Automated validation", "Verification tracking", "Deadline monitoring",
                 "Approval management"]
        # each chip appears roughly when its words are spoken (by position within the sentence)
        low = statement.lower()
        delays = [0.6 + dur * low.index(i.lower()) / len(low) for i in items]
        chips = "".join(f'<span style="animation-delay:{t:.2f}s">{i}</span>' for i, t in zip(items, delays))
        shield = ('<svg viewBox="0 0 64 64" width="96" height="96"><path d="M32 4 8 13v17c0 15 10 26 24 30 14-4 24-15 '
                  '24-30V13Z" fill="#0b2047" stroke="#2ccbb1" stroke-width="1.5"/><path d="M32 10 14 17v13c0 11 7 20 18 '
                  '24 11-4 18-13 18-24V17Z" fill="#12b09a"/><path d="m22 32 7 7 14-15" fill="none" stroke="#fff" '
                  'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>')
        html = (f'<div class="end">{shield}<h1>Suraksha<span>FD</span></h1>'
                f'<div class="tag">Smart FDR &amp; Security Deposit Management Portal</div>'
                f'<div class="chips">{chips}</div>'
                f'<div class="note">Prototype demonstration · fictional sample data · simulated bank verification</div></div>')
        self.page.evaluate("h => window.__curtain(h)", html)
        self.hold(0.6)
        self.say(statement)
        self.wait_speech(pad=2.2)  # let the card breathe before the fade-out


    def switch_user(self, role_button: str, role_title: str):
        """Quick transition card while signing out and in as another role (no repetitive login clicks on screen)."""
        self.page.evaluate("h => window.__curtain(h)",
                           f'<div class="k">Switching account</div><div class="r">{role_title}</div>'
                           f'<div class="e">Each role signs in with its own demo account</div>')
        self.hold(0.4)
        self.page.get_by_role("button", name="Sign out").first.click()
        self.page.wait_for_url(re.compile("/login"))
        self.page.get_by_role("button", name=re.compile(role_button)).click()
        self.page.wait_for_url(re.compile(r"/(institution|officer|senior|admin)$"))
        self.hold(0.9)
        self.page.evaluate("() => window.__curtain('')")
        self.hold(0.45)


def side(d: Director, name: str):
    d.click(d.page.locator("aside a", has_text=name), 0.7)


# ---------------------------------------------------------------- the walkthrough (all 11 steps)
def walkthrough(d: Director):
    p = d.page
    p.goto(f"{BASE}/login")
    d.hold(0.8)
    d.say("Welcome to SurakshaFD, a smart digital platform designed to simplify FDR and security deposit "
          "management for technical education institutions and AICTE officials. Let's see how the system works.")
    d.hold(1.5)

    # Step 1 ---------------------------------------------------------------
    d.say("Step one: an institution signs in with its demo account.", step=1)
    d.click(p.get_by_role("button", name=re.compile("Institution")), 0.2)
    p.wait_for_url(re.compile("/institution$"))
    d.hold(0.6)
    d.say("Its dashboard shows the deposits on record, pending verifications, discrepancies, "
          "and FDRs that are approaching maturity.", step=1)
    d.zoom(p.locator("main .grid").first, 4.2, max_z=1.2)
    d.say("Below, charts summarise every case by its workflow stage and by its simulated bank-verification status.",
          step=1)
    d.scroll_by(330, 0.9)
    d.zoom(p.get_by_text("Case stage distribution").locator("xpath=ancestor::section"), 3.0, max_z=1.25)
    d.top()

    # Step 2 ---------------------------------------------------------------
    d.say("Step two: uploading an FDR. For this demonstration, we're using sample FDR data to show how the "
          "system works in a real-world scenario. The bank, the document and the amounts are all fictional.", step=2)
    side(d, "Upload FDR")
    drop = p.get_by_role("button", name=re.compile("Drop the FDR receipt"))
    d.highlight(drop, 1.6)
    d.say("The file is picked from the sample documents folder, exactly as a user would upload it.", step=2)
    d.choose_file(drop, DEMO1_FDR)
    d.say("The receipt goes straight to the server, where Tesseract OCR scans it.", step=2)
    expect(p.get_by_text("Review OCR results and deposit details")).to_be_visible(timeout=60000)
    p.wait_for_url(re.compile(r"/institution/upload/\d+"))
    fdr_ref = None
    d.hold(0.5)

    # Step 3 ---------------------------------------------------------------
    form = p.get_by_text("Review OCR results and deposit details").locator("xpath=ancestor::section")
    d.say("Step three: OCR extraction. In about a second, the system has read the bank name, the FDR number, "
          "the deposit amount of ₹10,00,000, and the maturity date, each with a confidence score.", step=3)
    d.zoom(form, 6.5, max_z=1.3)
    d.say("Because OCR reads the receipt automatically, nobody has to retype it, and typing errors are avoided.",
          step=3)
    d.say("Anything it is unsure about is marked for review, with the original document shown alongside.", step=3)
    d.zoom(p.get_by_text(re.compile(r"Needs review ·")).first.locator("xpath=ancestor::div[1]/.."), 3.2, max_z=1.35)

    # Step 4 ---------------------------------------------------------------
    amount = p.locator("input[type=number]").first
    d.say("Step four: automatic error detection. Let's deliberately enter ₹5,00,000 instead.", step=4)
    d.focus(amount)
    d.type(amount, "500000")
    d.say("The mismatch with the document is caught instantly.", step=4)
    d.zoom(p.get_by_text("Amount mismatch detected").first.locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]"),
           3.4, max_z=1.35)
    d.say("We attach the required payment proof and run the server's validation, which flags the mismatch "
          "for the officer instead of rejecting the submission outright.", step=4)
    d.focus(p.get_by_text("Supporting documents"))
    p.locator("select").first.select_option("payment_proof")
    d.choose_file(p.get_by_role("button", name=re.compile("Upload payment proof")), DEMO1_PROOF)
    expect(p.get_by_text("Payment proof uploaded.")).to_be_visible(timeout=20000)
    d.click(p.get_by_role("button", name="Run checks"), 1.0)
    d.zoom(p.get_by_text("Automatic validation").first.locator("xpath=ancestor::section"), 3.2, max_z=1.3)
    d.say("Real errors, such as a missing field or a maturity date before the issue date, "
          "would block submission until they are fixed.", step=4)

    # Step 5 ---------------------------------------------------------------
    d.say("Step five: one click restores the amount from the document, and the FDR is submitted.", step=5)
    d.focus(amount)
    d.click(p.get_by_role("button", name="Use document value").first, 0.8)
    d.click(p.get_by_role("button", name="Submit for review"), 0.2)
    p.wait_for_url(re.compile(r"/institution/fdrs/\d+"), timeout=20000)
    fdr_id = int(re.search(r"/fdrs/(\d+)", p.url).group(1))
    fdr_ref = p.locator("main h1").first.inner_text()
    d.hold(0.6)
    d.say("The confirmation appears, and the status tracker shows the record is now under document review.", step=5)
    d.zoom(p.locator("main ol").first, 3.6, max_z=1.3)

    # Step 6 ---------------------------------------------------------------
    d.wait_speech()
    d.switch_user("AICTE Officer", "AICTE Officer")
    d.say("Step six: the AICTE officer's dashboard. The new submission is already at the top of the review queue.",
          step=6)
    latest = p.get_by_text("Latest submissions").locator("xpath=ancestor::section")
    d.zoom(latest.locator("li").first, 3.0, max_z=1.3)
    d.say("The officer's dashboard also tracks pending reviews, flagged discrepancies and upcoming maturities "
          "across every institution.", step=6)
    d.top()
    d.zoom(p.locator("main .grid").first, 3.4, max_z=1.2)
    d.click(latest.get_by_text(fdr_ref), 0.9)
    d.click(p.get_by_role("link", name="OCR review"), 0.9)
    d.say("The OCR review puts the document, the extracted values and the submitted data side by side. "
          "Everything matches, so the officer marks the documents as checked.", step=6)
    d.zoom(p.get_by_text("OCR reading vs submitted record").locator("xpath=ancestor::section"), 3.6, max_z=1.25)
    d.click(p.get_by_role("button", name="Mark documents checked"), 0.5)
    d.type(p.locator("textarea"), "Documents verified.")
    d.click(p.get_by_role("button", name="Confirm"), 0.8)

    # Step 7 ---------------------------------------------------------------
    d.say("Step seven: bank verification. This prototype is not connected to a real bank, so the bank "
          "confirmation is simulated using sample data, and it is labelled as simulated everywhere.", step=7)
    d.click(p.get_by_role("link", name="Back to case"), 0.6)
    d.click(p.get_by_role("button", name="Bank verification"), 0.7)
    d.zoom(p.locator("main div.rounded-lg", has_text="This prototype does not contact any bank").last, 3.2, max_z=1.3)
    d.click(p.get_by_role("button", name="Bank confirmation received"), 0.4)
    d.type(p.locator("textarea"), "Simulated branch confirmation.")
    d.click(p.get_by_role("button", name=re.compile("Record simulated outcome")), 1.0)
    d.say("The simulated outcome is recorded with the officer, the time, and a simulation reference.", step=7)
    d.zoom(p.get_by_text("Verification history").locator("xpath=ancestor::section"), 3.4, max_z=1.3)
    d.say("Because the bank check runs through an adapter, a real bank interface can be connected later "
          "without changing this workflow.", step=7)

    # Step 8 ---------------------------------------------------------------
    d.say("Step eight: the dashboard updates straight away. Maturity dates are tracked automatically, with "
          "reminders sixty, thirty and seven days before an FDR matures.", step=8)
    side(d, "Dashboard")
    d.scroll_by(520, 1.0)
    d.zoom(p.get_by_text("Upcoming maturities").locator("xpath=ancestor::section"), 3.4, max_z=1.3)
    d.top()
    d.say("Alerts for maturing FDRs, overdue reviews and pending clearances appear in the notification centre.", step=8)
    side(d, "Notifications")
    d.zoom(p.locator("main section").first, 3.2, max_z=1.15)

    # Step 9 ---------------------------------------------------------------
    d.wait_speech()
    d.switch_user("Institution", "Institution")
    d.say("Step nine: back as the institution. With the documents checked and the bank confirmation recorded, "
          "the FDR is eligible for clearance.", step=9)
    p.goto(f"{BASE}/institution/fdrs/{fdr_id}?tab=clearance")
    d.zoom(p.get_by_text("Clearance prerequisites").locator("xpath=ancestor::section"), 3.0, max_z=1.3)
    d.say("The institution submits a clearance request.", step=9)
    d.type(p.locator("textarea"), "Tenure complete; requesting clearance.")
    d.click(p.get_by_role("button", name="Submit clearance request"), 1.0)
    d.say("The request now waits for the AICTE officer.", step=9)

    # Step 10 --------------------------------------------------------------
    d.wait_speech()
    d.switch_user("AICTE Officer", "AICTE Officer")
    d.say("Step ten: the officer reviews the clearance request and recommends approval.", step=10)
    side(d, "Clearance Review")
    d.click(p.locator("main").get_by_role("link", name="Review", exact=True).first, 0.9)
    d.click(p.get_by_role("button", name="Recommend approval"), 0.3)
    d.type(p.locator("textarea"), "All prerequisites met.")
    d.click(p.get_by_role("button", name="Submit recommendation"), 0.9)
    d.say("The recommendation and the officer's remarks are forwarded for the final decision.", step=10)
    d.wait_speech()
    d.switch_user("Senior Approver", "Senior Approving Officer")
    d.say("A separate senior approving officer makes the final decision. The system blocks anyone who "
          "recommended a request from also approving it.", step=10)
    side(d, "Pending Approvals")
    d.click(p.locator("main").get_by_role("link", name="Decide", exact=True).first, 0.9)
    d.click(p.get_by_role("button", name="Approve", exact=True), 0.3)
    d.type(p.locator("textarea"), "Approved after reviewing all evidence.")
    d.click(p.get_by_role("button", name="Record final decision"), 1.0)
    d.say("The approval is recorded. This is a demonstration approval only: no bank funds are actually released.",
          step=10)
    d.zoom(p.get_by_text("Outcome", exact=True).locator("xpath=ancestor::section"), 3.0, max_z=1.35)

    # Step 11 --------------------------------------------------------------
    d.say("Step eleven: the audit trail. Every action is recorded with the user, their role, a timestamp, and the "
          "change in status, from the upload and OCR to the simulated verification and the final approval.", step=11)
    d.click(p.get_by_role("link", name="Open full case"), 0.8)
    d.click(p.get_by_role("button", name="Audit timeline"), 0.8)
    d.zoom(p.locator("main ol").last.locator("li").first, 2.6, max_z=1.3, highlight=False)
    for _ in range(6):
        d.scroll_by(300, 1.0)
    d.say("The audit log is append-only: even the database itself rejects any attempt to edit or delete "
          "these entries.", step=11)
    d.say("This gives AICTE complete accountability and transparency for every deposit.", step=11)
    d.zoom(p.get_by_text("Clearance decided", exact=True).last.locator("xpath=ancestor::li[1]"), 3.0, max_z=1.35)
    d.wait_speech()
    d.closing_card("SurakshaFD brings document submission, automated validation, verification tracking, deadline "
                   "monitoring, and approval management into one secure and transparent platform.")


# ---------------------------------------------------------------- editing: caption band, zooms, audio
def narration_script() -> list[str]:
    """Every narrated sentence, in order, read from walkthrough()'s source (synthesised before recording)."""
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "walkthrough")
    calls = sorted((n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("say", "closing_card") and n.args and isinstance(n.args[0], ast.Constant)),
                   key=lambda n: (n.lineno, n.col_offset))
    return [speechify(c.args[0].value) for c in calls]


def render_band(label: str, text: str, path: Path):
    """One caption-band image (1920x108): step label, caption (max two lines), small team logo."""
    from PIL import Image, ImageDraw, ImageFont
    fonts = Path(r"C:\Windows\Fonts")
    img = Image.new("RGB", (OUT_W, BAND_H), (7, 21, 51))
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, OUT_W, 2], fill=(18, 176, 154))
    x = 40
    if label:
        f = ImageFont.truetype(str(fonts / "segoeuib.ttf"), 17)
        w = dr.textlength(label, font=f)
        dr.rounded_rectangle([x, 39, x + w + 30, 71], radius=16, fill=(18, 176, 154))
        dr.text((x + 15, 55), label, font=f, fill="white", anchor="lm")
        x += int(w) + 56
    logo = Image.open(ROOT / "LC-Logo.png").convert("RGBA")
    logo = logo.resize((int(logo.width * 26 / logo.height), 26), Image.LANCZOS)
    lx = OUT_W - 40 - logo.width - 20
    dr.rounded_rectangle([lx, 34, OUT_W - 40, 76], radius=8, fill="white")
    img.paste(logo, (lx + 10, 42), logo)
    if text:
        right = lx - 40
        for size in (31, 28, 25):
            f = ImageFont.truetype(str(fonts / "seguisb.ttf"), size)
            words, lines, cur = text.split(), [], ""
            for wd in words:
                trial = f"{cur} {wd}".strip()
                if dr.textlength(trial, font=f) <= right - x:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = wd
            lines.append(cur)
            if len(lines) <= 2:
                break
        lh = size + 9
        y0 = (BAND_H - lh * len(lines)) / 2 + 1
        for i, line in enumerate(lines[:2]):
            dr.text((x, y0 + i * lh), line, font=f, fill=(240, 246, 255))
    img.save(path)


def build_band(cues: list, total: float, out: Path):
    """Caption band as a video: one image per caption (or the step label between captions)."""
    frames_dir = RAW_DIR / "band"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)
    segs, t, label = [], 0.0, ""
    for start, end, lab, text in sorted(cues):
        if start > t:
            segs.append((t, start, label, ""))
        label = lab
        segs.append((max(start, t), end, lab, text))
        t = max(t, end)
    if t < total:
        segs.append((t, total, label, ""))
    lines, cache = [], {}
    for a, b, lab, text in segs:
        if b - a < 0.04:
            continue
        key = (lab, text)
        if key not in cache:
            cache[key] = frames_dir / f"b{len(cache):03}.png"
            render_band(lab, text, cache[key])
        lines += [f"file '{cache[key].as_posix()}'", f"duration {b - a:.3f}"]
    lines.append(f"file '{cache[(segs[-1][2], segs[-1][3])].as_posix()}'")
    lst = RAW_DIR / "band.txt"
    lst.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "12", "-t", f"{total:.3f}", str(out)], check=True)


def zoom_filter(zooms: list) -> str:
    """zoompan expression: smooth ease-in/out zoom towards each target (frame-number based; ffmpeg 4.2)."""
    W, H, R = VIEW["width"], VIEW["height"], 0.55
    z_terms, cx_expr, cy_expr = [], f"{W / 2}", f"{H / 2}"
    for a, b, cx, cy, z in sorted(zooms, reverse=True):
        T = f"(in/{FPS})"
        ramp = f"min(1,min(({T}-{a:.3f})/{R},({b:.3f}-{T})/{R}))"
        ease = f"(0.5-0.5*cos(PI*{ramp}))"
        z_terms.append(f"if(between({T},{a:.3f},{b:.3f}),{z - 1:.3f}*{ease},0)")
        cx_expr = f"if(between({T},{a:.3f},{b:.3f}),{cx:.1f},{cx_expr})"
        cy_expr = f"if(between({T},{a:.3f},{b:.3f}),{cy:.1f},{cy_expr})"
    zexpr = "1+" + "+".join(z_terms) if z_terms else "1"
    x = f"max(0,min(iw-iw/zoom,({cx_expr})-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,({cy_expr})-ih/zoom/2))"
    return f"zoompan=z='{zexpr}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={FPS}"


def encode():
    t = json.loads((RAW_DIR / "timeline.json").read_text(encoding="utf-8"))
    total = t["video_seconds"]
    print(f"Editing {total:.0f} s: {len(t['cues'])} captions, {len(t['zooms'])} zooms, "
          f"{len(t['clicks'])} clicks, {len(t['keys'])} keystrokes…")
    band = RAW_DIR / "band.mp4"
    build_band(t["cues"], total, band)
    audio = RAW_DIR / "audio.wav"
    mix(total, [(a, Path(p)) for a, p in t["speech"]], t["clicks"], t["keys"], audio)
    mp4 = OUT_DIR / "SurakshaFD_Walkthrough.mp4"
    fade_out = max(0.0, total - 2.0)
    graph = (f"[0:v]{zoom_filter(t['zooms'])},scale={OUT_W}:{SITE_H}:flags=lanczos,setsar=1[site];"
             f"[1:v]scale={OUT_W}:{BAND_H},setsar=1[band];"
             f"[site][band]vstack=inputs=2,fps=30,fade=t=in:st=0:d=0.6,fade=t=out:st={fade_out:.2f}:d=2.0,format=yuv420p[v];"
             f"[2:a]aformat=sample_fmts=fltp:channel_layouts=mono,loudnorm=I=-16:LRA=9:TP=-1.5,aresample=48000,"
             f"afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out:.2f}:d=2.0[a]")
    print("Encoding 1920x1080 MP4…")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(RAW_DIR / "screen.mp4"),
                    "-i", str(band), "-i", str(audio), "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-ac", "1", "-c:a", "aac", "-b:a", "160k",
                    "-t", f"{total:.3f}", "-movflags", "+faststart", str(mp4)], check=True)
    write_srt(OUT_DIR / "SurakshaFD_Walkthrough.srt", t["cues"])
    print(f"\nDone: {mp4}  ({mp4.stat().st_size / 1e6:.1f} MB, {total / 60:.2f} min)")
    if not MIN_SECONDS <= total <= MAX_SECONDS:
        print(f"WARNING: length {total:.0f} s is outside the {MIN_SECONDS}-{MAX_SECONDS} s target")


def write_srt(path: Path, cues: list):
    def ts(x):
        h, rem = divmod(max(0.0, x), 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"
    lines = []
    for i, (a, b, _label, text) in enumerate(sorted(cues), 1):
        lines += [str(i), f"{ts(a)} --> {ts(b)}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def up(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False


def ensure_servers() -> list[subprocess.Popen]:
    started = []
    if not up("http://127.0.0.1:8000/api/health"):
        print("Starting backend…")
        started.append(subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                                        cwd=BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if not up(BASE):
        print("Starting frontend…")
        started.append(subprocess.Popen("npm.cmd run demo", cwd=FRONTEND, shell=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for _ in range(120):  # the frontend builds first (~10-20 s)
        if up("http://127.0.0.1:8000/api/health") and up(BASE):
            return started
        time.sleep(1)
    raise SystemExit("Servers did not start. Run start.bat and check for errors.")


def stop_ports(*ports: int):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = {line.split()[-1] for line in out.splitlines()
            if "LISTENING" in line and any(f":{p} " in line for p in ports)}
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    narrator = Narrator()
    script = narration_script()
    print(f"Preparing narration ({len(script)} sentences, male voice 'John', public domain)…")
    speech_total = sum(narrator.clip(line)[1] for line in script)
    print(f"  {speech_total / 60:.1f} minutes of speech ready")
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    RAW_DIR.mkdir(parents=True)
    print("Resetting demo data…")
    subprocess.run([PY, "-m", "app.cli", "reset-demo", "--yes"], cwd=BACKEND, check=True, stdout=subprocess.DEVNULL)
    started = ensure_servers()
    SAMPLE_LISTING.extend(build_sample_listing())
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            ctx = browser.new_context(viewport=VIEW)
            ctx.add_init_script(OVERLAY_JS)
            page = ctx.new_page()
            page.on("pageerror", lambda e: print("  PAGE ERROR:", e))
            page.goto("about:blank")
            rec = Recorder(ctx, page, RAW_DIR / "screen.mp4", fps=FPS, size=(VIEW["width"], VIEW["height"]))
            d = Director(page, narrator)
            print("Recording walkthrough…")
            walkthrough(d)
            video_seconds = rec.stop()
            ctx.close()
            browser.close()
    finally:
        if started:
            stop_ports(8000, 5173)
    vt = rec.video_time
    timeline = {"video_seconds": video_seconds,
                "speech": [[vt(a), str(p)] for a, p in d.speech],
                "clicks": [vt(a) for a in d.clicks], "keys": [vt(a) for a in d.keys],
                "zooms": [[vt(a), vt(b), cx, cy, z] for a, b, cx, cy, z in d.zooms],
                "cues": [[vt(a), vt(b), lab, text] for a, b, lab, text in d.cues]}
    (RAW_DIR / "timeline.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    encode()


if __name__ == "__main__":
    if "--encode-only" in sys.argv:
        encode()
    else:
        main()
