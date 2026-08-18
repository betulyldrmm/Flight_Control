"""
Ana goruntu isleme boru hatti.

  kare -> (kilitlenme) tespit -> KCF takip -> durum + kutu
       -> UDP (ucus kontrol) + diske bindirmeli kayit

Durumlar (ucus kontrolun bekledigi "durum" alani):
  KILITLENIYOR : henuz onaylanmis hedef yok; kutu gonderilmez (HEDEF_KAYIP)
  TAKIP        : onaylanmis ve takip edilen hedef; kutu gonderilir
  HEDEF_KAYIP  : hedef kayboldu

Zaman sifiri: otonom moda gecis / pipeline baslangici (sartname).
timestamp UDP'de saniye, kayitta milisaniye.
"""

import time
from typing import Optional

from vision.camera import open_source
from vision.detector import Detector
from vision.tracker import TargetTracker
from vision.sender import FlightControlSender
from vision.recorder import Recorder


class VisionPipeline:
    def __init__(self, cfg):
        self.cfg = cfg
        self.detector = Detector(cfg)
        self.tracker = TargetTracker(cfg)
        self.sender = FlightControlSender(cfg.udp_host, cfg.udp_port)
        self.recorder = Recorder(cfg) if cfg.save_images or True else None

        self.state = "KILITLENIYOR"
        self.lock_count = 0
        self.lost_count = 0
        self.last_conf: Optional[float] = None
        self.frame_id = 0

    def _size_ok(self, box) -> bool:
        _, _, w, h = box
        return (w * h) >= self.cfg.min_blob_area

    def step(self, frame, t: float):
        """Tek kareyi isle; (durum, bbox, guven) doner ve UDP+kayit yapar."""
        durum = "HEDEF_KAYIP"
        bbox = None
        guven = None

        if self.state == "KILITLENIYOR":
            det = self.detector.detect(frame)
            if det is not None and self._size_ok(det.bbox):
                self.lock_count += 1
                self.last_conf = det.conf
                if self.lock_count >= self.cfg.lock_frames:
                    # kilitlenildi -> takibe gec
                    self.tracker.init(frame, det.bbox)
                    self.state = "TAKIP"
                    self.lost_count = 0
                    durum, bbox, guven = "TAKIP", det.bbox, det.conf
            else:
                self.lock_count = 0
            # kilitlenene kadar: hedef yok bilgisi (ucus kontrol hover/arama yapar)

        elif self.state == "TAKIP":
            box = self.tracker.update(frame)   # KCF kutusu (KCF yoksa None)

            # KCF yoksa her kare, KCF varsa periyodik olarak tespitle tazele
            need_detect = (box is None) or (self.frame_id % self.cfg.redetect_every == 0)
            if need_detect:
                det = self.detector.detect(frame)
                if det is not None and self._size_ok(det.bbox):
                    if self.tracker.has_kcf:
                        self.tracker.init(frame, det.bbox)
                    else:
                        self.tracker.observe(det.bbox)
                    box = det.bbox
                    self.last_conf = det.conf
                elif box is None:
                    box = self.tracker.predict_box()   # kisa kayipta Kalman tahmini

            if box is not None and self._size_ok(box):
                self.lost_count = 0
                durum, bbox, guven = "TAKIP", box, (self.last_conf or 0.8)
            else:
                self.lost_count += 1
                if self.lost_count >= self.cfg.max_lost_frames:
                    # uzun kayip -> kilitlenmeyi sifirla
                    self.state = "KILITLENIYOR"
                    self.lock_count = 0
                    self.tracker.reset()
                durum = "HEDEF_KAYIP"

        # -- gonder + kaydet ------------------------------------------------
        self.sender.send(durum, timestamp=t, frame_id=self.frame_id,
                         bbox=bbox, guven=guven)
        if self.recorder is not None:
            self.recorder.record(
                frame, kare_no=self.frame_id, zaman_ms=int(t * 1000),
                otonom=1, bbox=bbox, guven=guven)

        self.frame_id += 1
        return durum, bbox, guven

    def run(self, duration: Optional[float] = None, verbose: bool = True):
        cfg = self.cfg
        print(f"[vision] kaynak={cfg.source}  mod={self.detector.mode}  "
              f"-> UDP {cfg.udp_host}:{cfg.udp_port}  kayit={'acik' if cfg.save_images else 'kapali'}")
        src = open_source(cfg)
        t0 = time.time()
        last_report = 0.0
        try:
            for frame in src:
                t = time.time() - t0
                if duration and t > duration:
                    break
                durum, bbox, guven = self.step(frame, t)
                if verbose and t - last_report > 2.0:
                    last_report = t
                    b = (f"({bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f}x{bbox[3]:.0f})"
                         if bbox else "yok")
                    print(f"[vision] t={t:5.1f}s  {self.state:<12} "
                          f"kutu={b:<22} guven={guven if guven else 0:.2f}")
        except KeyboardInterrupt:
            print("\n[vision] durduruldu.")
        finally:
            self.sender.close()
            if self.recorder is not None:
                self.recorder.close()
            print("[vision] kapandi. Kayit klasoru:", cfg.save_dir if cfg.save_images else "(kapali)")
