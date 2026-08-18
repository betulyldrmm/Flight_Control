"""
Goruntu isleme ayarlari. Tek merkezi yer — sahada/testte buradan degistirilir.

UYUMLULUK NOTU:
  UDP_HOST/UDP_PORT, ucus kontrol kodunun dinledigi adresle AYNI olmali.
  Ucus kontrol: src/main.py -> source_socket, varsayilan 127.0.0.1:5005.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class VisionConfig:
    # -- kamera / kare --------------------------------------------------
    source: str = "fake"          # "fake" | "webcam" | "video"
    video_path: Optional[str] = None
    webcam_index: int = 0
    frame_w: int = 1280
    frame_h: int = 720
    fps: int = 30

    # -- ucus kontrol ile baglanti (UDP) --------------------------------
    udp_host: str = "127.0.0.1"   # ucus kontrolun dinledigi adres
    udp_port: int = 5005          # src/main.py source_socket ile AYNI

    # -- tespit (YOLO) --------------------------------------------------
    model_path: Optional[str] = None   # verilirse YOLO, yoksa renk tespiti
    conf_threshold: float = 0.35       # min guven skoru
    target_class: Optional[int] = None # YOLO sinif filtresi (None = hepsi)

    # -- renk tespiti (YOLO yoksa yedek; ayni zamanda test icin) --------
    # Sari hedef icin HSV araligi (dokumandaki "sari dron" ornegi).
    hsv_lower: Tuple[int, int, int] = (20, 100, 100)
    hsv_upper: Tuple[int, int, int] = (35, 255, 255)
    min_blob_area: int = 400           # piksel; gurultu elemek icin

    # -- takip / kilitlenme ---------------------------------------------
    redetect_every: int = 20           # KCF surerken kac karede bir YOLO ile tazele
    lock_frames: int = 5               # kac kare kesintisiz tespit = kilitlenme
    max_lost_frames: int = 45          # bu kadar kare bulunamazsa "HEDEF_KAYIP"

    # -- sartname kontrolu ----------------------------------------------
    min_bbox_side: int = 64            # sartname: 64x64 minimum (bilgi/uyari icin)

    # -- kayit (resmi teslim) -------------------------------------------
    save_images: bool = True
    save_dir: str = "teslim"           # teslim/goruntu + teslim/tespit_kaydi.csv
    save_ext: str = "jpg"
    draw_overlay: bool = True          # sag ust bindirme + kutu ciz

    def bbox_side_at_ok(self, w: float, h: float) -> bool:
        """Sartname 64x64 alanini saglar mi (bilgi amacli)."""
        return (w * h) >= (self.min_bbox_side ** 2)
