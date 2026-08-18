"""
Hedef tespiti.

Iki mod:
  1) YOLO (model_path verilirse ve ultralytics kuruluysa): dokumandaki
     asil yontem. Sercan egittigi .pt modelini config.model_path'e koyar.
  2) Renk (HSV) tespiti: model yokken yedek. Ayni zamanda tum boru hattini
     donanimsiz test etmeyi saglar (sahte kamera + sari hedef).

Cikti: en iyi tespit -> Detection(x, y, w, h, conf)  ya da  None.
Koordinatlar piksel, xywh (sol-ust kose + genislik/yukseklik).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


@dataclass
class Detection:
    x: float
    y: float
    w: float
    h: float
    conf: float

    @property
    def bbox(self):
        return (self.x, self.y, self.w, self.h)

    @property
    def area(self):
        return self.w * self.h


class Detector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.mode = "renk"
        if cfg.model_path:
            self._load_yolo(cfg.model_path)

    # -- YOLO -----------------------------------------------------------
    def _load_yolo(self, path: str):
        try:
            from ultralytics import YOLO
            self.model = YOLO(path)
            self.mode = "yolo"
            print(f"[detector] YOLO modeli yuklendi: {path}")
        except Exception as e:
            print(f"[detector] YOLO yuklenemedi ({e}); renk tespitine dusuluyor.")
            self.model = None
            self.mode = "renk"

    def _detect_yolo(self, frame) -> Optional[Detection]:
        res = self.model.predict(frame, verbose=False,
                                 conf=self.cfg.conf_threshold)
        best = None
        for r in res:
            if r.boxes is None:
                continue
            for b in r.boxes:
                cls = int(b.cls[0]) if b.cls is not None else -1
                if (self.cfg.target_class is not None
                        and cls != self.cfg.target_class):
                    continue
                conf = float(b.conf[0])
                x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
                det = Detection(x1, y1, x2 - x1, y2 - y1, conf)
                if best is None or det.conf > best.conf:
                    best = det
        return best

    # -- Renk (HSV) -----------------------------------------------------
    def _detect_color(self, frame) -> Optional[Detection]:
        if cv2 is None:
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array(self.cfg.hsv_lower, dtype=np.uint8)
        upper = np.array(self.cfg.hsv_upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        c = max(cnts, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < self.cfg.min_blob_area:
            return None
        x, y, w, h = cv2.boundingRect(c)
        # renk tespitinde "guven" olarak alanin makul bir olcegi kullanilir
        conf = float(min(1.0, 0.5 + area / (self.cfg.frame_w * self.cfg.frame_h)))
        return Detection(float(x), float(y), float(w), float(h), conf)

    # -- ortak ----------------------------------------------------------
    def detect(self, frame) -> Optional[Detection]:
        if self.mode == "yolo" and self.model is not None:
            return self._detect_yolo(frame)
        return self._detect_color(frame)
