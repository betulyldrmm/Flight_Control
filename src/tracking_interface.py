"""
Sercan'in tracking modulunden beklenen veri formatini tanimlayan arayuz.
Bu dosya, ekip arasinda "veri sozlesmesi" gorevi gorur.

BEKLENEN VERI FORMATI (Sercan -> Betul):
{
    "durum": "TAKIP" | "HEDEF_KAYIP" | "ARIYOR",
    "bbox": {
        "x": float,      # sol-ust kose x koordinati (piksel)
        "y": float,      # sol-ust kose y koordinati (piksel)
        "w": float,      # genislik (piksel)
        "h": float,      # yukseklik (piksel)
    },
    "guven_skoru": float,  # 0.0 - 1.0 arasi (KTR'deki PSR benzeri skor)
    "timestamp": float,     # veri uretim zamani (senkronizasyon icin)
}

NOT: "HEDEF_KAYIP" durumunda bbox alani None olabilir.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackingData:
    durum: str  # "TAKIP", "HEDEF_KAYIP", "ARIYOR"
    x: Optional[float] = None
    y: Optional[float] = None
    w: Optional[float] = None
    h: Optional[float] = None
    guven_skoru: Optional[float] = None
    timestamp: Optional[float] = None

    def is_valid(self):
        """Takip icin kullanilabilir veri var mi kontrol eder."""
        return (
            self.durum == "TAKIP"
            and self.x is not None
            and self.y is not None
            and self.w is not None
            and self.h is not None
        )

    @classmethod
    def from_dict(cls, data: dict):
        """Sercan'dan gelen dict/JSON veriyi TrackingData nesnesine cevirir."""
        bbox = data.get("bbox", {})
        return cls(
            durum=data.get("durum", "HEDEF_KAYIP"),
            x=bbox.get("x"),
            y=bbox.get("y"),
            w=bbox.get("w"),
            h=bbox.get("h"),
            guven_skoru=data.get("guven_skoru"),
            timestamp=data.get("timestamp"),
        )


def fake_tracking_source(t, cam_width=640, cam_height=480):
    """
    GECICI test verisi ureten fonksiyon.
    Sercan'in gercek modulu hazir olunca, bu fonksiyon YERINE
    onun gercek veri kaynagi kullanilacak (ayni TrackingData formatinda).
    """
    import math
    cx = cam_width / 2 + 100 * math.sin(t)
    cy = cam_height / 2 + 50 * math.cos(t * 0.7)
    w, h = 80, 60
    return TrackingData(
        durum="TAKIP",
        x=cx - w / 2,
        y=cy - h / 2,
        w=w,
        h=h,
        guven_skoru=0.85,
        timestamp=t,
    )
