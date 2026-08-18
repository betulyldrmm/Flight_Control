"""
Takip: KCF (varsa) + Kalman.

KTR mantigi:
  - Tespit (YOLO/renk) kutu verir; sonraki karelerde her seferinde yeniden
    tespit yerine KCF ile dusuk gecikmeli takip yapilir.
  - KCF kaybederse / KCF yoksa Kalman filtresi son konum+hiz ile tahmin eder.

SAGLAMLIK: KCF yalnizca opencv-contrib ile gelir. Kurulu degilse modul
CROKMEZ; has_kcf=False olur ve boru hatti "her karede tespit + Kalman"
moduna gecer. Jetson'da opencv-contrib kuruluysa KCF otomatik devreye girer.
"""

from typing import Optional, Tuple

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

Box = Tuple[float, float, float, float]


def _try_make_kcf():
    """KCF tracker uret; yoksa None (contrib kurulu degil)."""
    if cv2 is None:
        return None
    try:
        if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerKCF_create"):
            return cv2.legacy.TrackerKCF_create()
        if hasattr(cv2, "TrackerKCF_create"):
            return cv2.TrackerKCF_create()
    except Exception:
        return None
    return None


class TargetTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self._kcf = None
        self.has_kcf = False
        self._last_box: Optional[Box] = None
        self.kalman = self._make_kalman()
        self._kalman_ready = False

    # -- Kalman ---------------------------------------------------------
    def _make_kalman(self):
        if cv2 is None:
            return None
        kf = cv2.KalmanFilter(4, 2)   # durum: x,y,vx,vy ; olcum: x,y
        kf.measurementMatrix = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.5
        return kf

    def _kalman_correct(self, cx, cy):
        if self.kalman is None:
            return
        if not self._kalman_ready:
            self.kalman.statePost = np.array([[cx], [cy], [0], [0]], np.float32)
            self._kalman_ready = True
        self.kalman.correct(np.array([[np.float32(cx)], [np.float32(cy)]]))

    def _kalman_predict(self) -> Optional[Tuple[float, float]]:
        if self.kalman is None or not self._kalman_ready:
            return None
        p = self.kalman.predict()
        return float(p[0]), float(p[1])

    # -- disari acik --------------------------------------------------
    def init(self, frame, box: Box):
        """Yeni tespitle (yeniden) baslat. KCF varsa init eder; her durumda Kalman."""
        x, y, w, h = box
        self._last_box = (float(x), float(y), float(w), float(h))
        self._kcf = _try_make_kcf()
        self.has_kcf = self._kcf is not None
        if self.has_kcf:
            try:
                self._kcf.init(frame, (int(x), int(y), int(w), int(h)))
            except Exception:
                self._kcf, self.has_kcf = None, False
        self._kalman_correct(x + w / 2.0, y + h / 2.0)

    def update(self, frame) -> Optional[Box]:
        """
        KCF varsa bir adim ilerlet; kutu doner (KCF ya da Kalman tahmini).
        KCF yoksa None doner -> cagiran taraf tespit yapmali.
        """
        if not self.has_kcf or self._kcf is None:
            return None
        ok, box = self._kcf.update(frame)
        if ok:
            x, y, w, h = box
            self._last_box = (float(x), float(y), float(w), float(h))
            self._kalman_correct(x + w / 2.0, y + h / 2.0)
            return self._last_box
        return self.predict_box()

    def observe(self, box: Box):
        """Bir tespiti Kalman'a besle ve son kutuyu guncelle (KCF'siz mod)."""
        x, y, w, h = box
        self._last_box = (float(x), float(y), float(w), float(h))
        self._kalman_correct(x + w / 2.0, y + h / 2.0)

    def predict_box(self) -> Optional[Box]:
        """Kalman tahmini + son kutu boyutuyla bir kutu uret (kisa kayipta)."""
        pred = self._kalman_predict()
        if pred is None or self._last_box is None:
            return None
        _, _, w, h = self._last_box
        cx, cy = pred
        self._last_box = (cx - w / 2.0, cy - h / 2.0, w, h)
        return self._last_box

    def reset(self):
        self._kcf = None
        self.has_kcf = False
        self._last_box = None
        self._kalman_ready = False
        self.kalman = self._make_kalman()
