"""
Kare kaynagi: gercek kamera (webcam/video) ya da sahte (sentetik) kareler.

Sahte kaynak, donanimsiz test icindir: koyu arka planda hareket eden sari bir
dikdortgen (hedef). 12-15. saniye arasi hedef yok (kayip/arama testi). Renk
tespiti bu sari hedefi bulur, boylece TUM boru hatti dronsuz calisir.
"""

import math
import time
from typing import Iterator

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def fake_frames(cfg) -> Iterator["np.ndarray"]:
    """Sentetik kareler uret (BGR, cfg.frame_h x cfg.frame_w)."""
    w, h = cfg.frame_w, cfg.frame_h
    t0 = time.time()
    dt = 1.0 / cfg.fps
    while True:
        t = time.time() - t0
        frame = np.full((h, w, 3), 30, dtype=np.uint8)  # koyu arka plan

        if not (12.0 <= t < 15.0):  # 12-15 sn arasi hedef yok
            cx = w / 2 + 0.23 * w * math.sin(t * 0.8)
            cy = h / 2 + 0.17 * h * math.sin(t * 0.5)
            side = 90 + 20 * math.sin(t * 0.3)
            x1, y1 = int(cx - side / 2), int(cy - side / 2)
            x2, y2 = int(cx + side / 2), int(cy + side / 2)
            # sari (BGR) dolu kare = hedef
            if cv2 is not None:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 220), -1)
            else:
                frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = (0, 220, 220)
        yield frame
        time.sleep(dt)


def open_source(cfg) -> Iterator["np.ndarray"]:
    """cfg.source'a gore kare akisi dondur."""
    if cfg.source == "fake":
        return fake_frames(cfg)

    if cv2 is None:
        raise RuntimeError("Gercek kamera icin opencv gerekli.")

    if cfg.source == "webcam":
        cap = cv2.VideoCapture(cfg.webcam_index)
    elif cfg.source == "video":
        cap = cv2.VideoCapture(cfg.video_path)
    else:
        raise ValueError(f"Bilinmeyen kaynak: {cfg.source}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_h)

    def gen():
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[1] != cfg.frame_w or frame.shape[0] != cfg.frame_h:
                frame = cv2.resize(frame, (cfg.frame_w, cfg.frame_h))
            yield frame
        cap.release()

    return gen()
