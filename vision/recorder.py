"""
Resmi teslim kaydi: her kareyi bindirmeyle diske yazar ve tespit_kaydi.csv'ye
satir ekler. src/resmi_kayit modulunu kullanir (tek dogru kaynak).

Cikti klasoru:
  teslim/
    goruntu/kare_000123_zaman_000004100.jpg
    tespit_kaydi.csv

Bindirme (dokuman Bolum 6): sag ust kose, yari saydam koyu arka plan + beyaz
metin; zaman_damgasi_ms + kare_no + OTONOM.
"""

import os
from typing import Optional, Tuple

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from src.resmi_kayit import ResmiKayit, bindirme_metni

Box = Tuple[float, float, float, float]


class Recorder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.enabled = cfg.save_images
        self.goruntu_dir = os.path.join(cfg.save_dir, "goruntu")
        if self.enabled:
            os.makedirs(self.goruntu_dir, exist_ok=True)
        self.rk = ResmiKayit(os.path.join(cfg.save_dir, "tespit_kaydi.csv"))

    # -- bindirme cizimi ------------------------------------------------
    def _draw_overlay(self, frame, kare_no, zaman_ms, otonom, bbox):
        if cv2 is None:
            return frame
        img = frame.copy()

        # tespit kutusu
        if bbox is not None:
            x, y, w, h = (int(v) for v in bbox)
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # sag ust bindirme (yari saydam koyu kutu + beyaz metin)
        metin = bindirme_metni(kare_no, zaman_ms, otonom).split("\n")
        pad = 8
        line_h = 22
        box_w = 260
        box_h = pad * 2 + line_h * len(metin)
        x0 = self.cfg.frame_w - box_w - 10
        y0 = 10
        overlay = img.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        for i, satir in enumerate(metin):
            cv2.putText(img, satir, (x0 + pad, y0 + pad + line_h * (i + 1) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                        cv2.LINE_AA)
        return img

    # -- kayit ----------------------------------------------------------
    def record(self, frame, kare_no: int, zaman_ms: int, otonom: int,
               bbox: Optional[Box], guven: Optional[float]):
        """
        CSV satiri + (istenirse) bindirmeli goruntu yazar.
        CSV'deki goruntu_adi ile diskteki dosya adi BIREBIR ayni olur.
        """
        ad = self.rk.kaydet(
            kare_no=kare_no, zaman_ms=zaman_ms, otonom=otonom,
            bbox=bbox, guven=guven,
            frame_w=self.cfg.frame_w, frame_h=self.cfg.frame_h,
            uzanti=self.cfg.save_ext,
        )
        if self.enabled and cv2 is not None:
            img = (self._draw_overlay(frame, kare_no, zaman_ms, otonom, bbox)
                   if self.cfg.draw_overlay else frame)
            cv2.imwrite(os.path.join(self.goruntu_dir, ad), img)
        return ad

    def close(self):
        self.rk.kapat()
