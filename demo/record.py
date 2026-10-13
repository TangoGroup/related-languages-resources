#!/usr/bin/env python
"""Record a narrated product demo of the RLR demo UI.

Drives the running demo server (``rlr serve``) with Playwright, records the
browser as video, narrates each scene with ElevenLabs text-to-speech, and muxes
the two with ffmpeg into an MP4.

Usage (from the repo root, with the server running on :8765)::

    python demo/record.py --out demo/out

Requires: the ``playwright`` package with Chromium installed, ``ffmpeg`` and
``ffprobe`` on PATH, and an ElevenLabs key at ``~/.config/elevenlabs.key``
(text-to-speech permission is enough). Narration audio is cached by content
hash under ``<out>/tts`` so re-recording does not re-bill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from narration import MODEL_ID, SCENES, VOICE_ID

URL = "http://127.0.0.1:8765/"
W, H = 1440, 900

CURSOR_JS = r"""
(() => {
  if (window.__rlrCursor) return;
  const c = document.createElement('div');
  c.id = 'rlr-cursor';
  c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:30px;pointer-events:none;z-index:2147483647;transform:translate(-3px,-2px);transition:opacity .3s;opacity:0';
  c.innerHTML = `<svg width="22" height="30" viewBox="0 0 22 30"><path d="M2 2 L2 24 L8 18 L12 28 L16 26 L12 17 L20 17 Z" fill="#1d1a16" stroke="#f3ecdf" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  const ring = document.createElement('div');
  ring.style.cssText = 'position:fixed;width:36px;height:36px;border:2px solid #8a2b1c;border-radius:50%;pointer-events:none;z-index:2147483646;transform:translate(-50%,-50%) scale(.2);opacity:0';
  document.documentElement.appendChild(c); document.documentElement.appendChild(ring);
  window.addEventListener('mousemove', (e) => { c.style.opacity = '1'; c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px'; }, true);
  window.addEventListener('mousedown', (e) => {
    ring.style.transition = 'none'; ring.style.transform = 'translate(-50%,-50%) scale(.2)'; ring.style.opacity = '.9';
    requestAnimationFrame(() => { ring.style.transition = 'transform .45s ease-out, opacity .45s ease-out'; ring.style.transform = 'translate(-50%,-50%) scale(1.6)'; ring.style.opacity = '0'; });
  }, true);
  window.__rlrCursor = true;
})();
"""


def tts(text: str, out_dir: Path, key: str) -> Path:
    """Fetch narration audio for ``text`` (cached by hash)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{VOICE_ID}|{MODEL_ID}|{text}".encode()).hexdigest()[:16]
    path = out_dir / f"{digest}.mp3"
    if path.exists():
        return path
    body = json.dumps(
        {
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "style": 0.15,
                "speed": 0.97,
            },
        },
    ).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        path.write_bytes(resp.read())
    return path


def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
    )
    return float(out.decode().strip())


class Stage:
    """Camera and hand: scrolling, pointing, typing, clicking, with a visible cursor."""

    def __init__(self, page) -> None:  # noqa: ANN001
        self.page = page

    def settle(self, seconds: float) -> None:
        time.sleep(seconds)

    def scroll_to(self, selector: str, block: str = "start", offset: int = 24) -> None:
        self.page.evaluate(
            """([sel, block, off]) => { const el = document.querySelector(sel); if (!el) return;
               const y = el.getBoundingClientRect().top + window.scrollY - off;
               window.scrollTo({ top: block === 'start' ? y : y - (window.innerHeight - el.offsetHeight) / 2, behavior: 'smooth' }); }""",
            [selector, block, offset],
        )
        time.sleep(0.9)

    def scroll_by(self, dy: int) -> None:
        self.page.evaluate("(dy) => window.scrollBy({ top: dy, behavior: 'smooth' })", dy)
        time.sleep(0.8)

    def scroll_top(self) -> None:
        self.page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        time.sleep(0.9)

    def point(self, selector: str, dx: float = 0.5, dy: float = 0.5, steps: int = 28) -> bool:
        box = self.page.locator(selector).first.bounding_box()
        if not box:
            return False
        self.page.mouse.move(
            box["x"] + box["width"] * dx, box["y"] + box["height"] * dy, steps=steps
        )
        return True

    def click(self, selector: str) -> None:
        if self.point(selector):
            time.sleep(0.25)
            self.page.locator(selector).first.click()

    def type_into(self, selector: str, text: str) -> None:
        self.click(selector)
        self.page.locator(selector).first.fill("")
        self.page.locator(selector).first.press_sequentially(text, delay=70)

    def wait_for_briefing(self) -> None:
        self.page.wait_for_selector(".reading, .plaque", timeout=60000)
        time.sleep(0.6)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo/out")
    ap.add_argument("--key", default=str(Path.home() / ".config" / "elevenlabs.key"))
    ap.add_argument(
        "--no-audio", action="store_true", help="Record video only, timed from a 6 s/scene default."
    )
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    key = Path(args.key).read_text().strip() if not args.no_audio else ""
    clips: list[tuple[str, Path | None, float]] = []
    for scene in SCENES:
        if args.no_audio:
            clips.append((scene.id, None, 6.0))
            continue
        path = tts(scene.text, out / "tts", key)
        clips.append((scene.id, path, duration(path)))
    total = sum(d for _, _, d in clips)
    print(f"{len(clips)} scenes, {total:.1f}s of narration")

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    video_dir = out / "video"
    video_dir.mkdir(exist_ok=True)
    timeline: list[dict[str, float | str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(video_dir),
            record_video_size={"width": W, "height": H},
        )
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.monotonic()
        page.goto(URL)
        page.wait_for_selector(".reading", timeout=90000)
        page.mouse.move(W * 0.62, H * 0.55, steps=10)
        stage = Stage(page)
        lead_in = 1.2
        time.sleep(max(0.0, lead_in - (time.monotonic() - t0)))
        for scene, (_, _clip, dur) in zip(SCENES, clips, strict=True):
            start = time.monotonic() - t0
            timeline.append({"scene": scene.id, "start": round(start, 3), "duration": dur})
            print(f"[{start:7.2f}s] {scene.id} ({dur:.1f}s)")
            scene_t0 = time.monotonic()
            scene.action(stage)
            elapsed = time.monotonic() - scene_t0
            time.sleep(max(0.0, dur + scene.pad - elapsed))
        time.sleep(1.5)
        page.close()
        ctx.close()
        browser.close()
    webm = next(video_dir.glob("*.webm"))
    (out / "timeline.json").write_text(json.dumps(timeline, indent=2))

    # ---- mux: place each narration clip at its scene's start offset ----
    final = out / "rlr-demo.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(webm)]
    filters = []
    labels = []
    for i, (entry, (_, clip, _)) in enumerate(zip(timeline, clips, strict=True), start=1):
        if clip is None:
            continue
        cmd += ["-i", str(clip)]
        ms = int(float(entry["start"]) * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    if labels:
        filters.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[aout]"
        )
        cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(final),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"wrote {final} ({duration(final):.1f}s)")


if __name__ == "__main__":
    main()
