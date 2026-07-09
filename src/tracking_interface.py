"""
Tracking modulunden gelen veriyi ucus kontrol icin standart forma cevirir.
Bu dosya, ekip arasinda veri sozlesmesi gorevi gorur.

Iki giris formati desteklenir:
  Format A (bbox):  {"durum", "bbox": {x,y,w,h}, "guven_skoru", "timestamp"}
  Format B (error): {"durum", "x_error", "y_error", "bbox_area", ...}

Cikis her zaman TrackingData'dir.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

MIN_BBOX_PX = 4096  # sartname: 64x64 minimum tespit alani


@dataclass
class TrackingData:
    durum: str                      # "TAKIP" | "HEDEF_KAYIP" | "ARIYOR"
    timestamp: float
    frame_id: int = 0

    # normalize hatalar, [-1, 1]
    x_error: Optional[float] = None
    y_error: Optional[float] = None
    bbox_area: Optional[float] = None   # normalize, [0, 1]

    # ham veri (metrics.py IoU hesabi icin)
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x, y, w, h)
    bbox_px: Optional[float] = None     # w * h, ham piksel

    guven_skoru: Optional[float] = None
    frame_w: int = 1280
    frame_h: int = 720

    def is_valid(self) -> bool:
        return (
            self.durum == "TAKIP"
            and self.x_error is not None
            and self.y_error is not None
        )

    def meets_size_requirement(self) -> bool:
        """Sartname: hedef en az 64x64 piksel alan kaplamali."""
        return self.bbox_px is not None and self.bbox_px >= MIN_BBOX_PX

    @classmethod
    def from_bbox(cls, data: dict, frame_w: int = 1280, frame_h: int = 720):
        durum = data.get("durum", "HEDEF_KAYIP")
        bbox = data.get("bbox")

        if durum != "TAKIP" or not bbox:
            return cls(durum=durum, timestamp=data.get("timestamp", 0.0),
                       frame_id=data.get("frame_id", 0),
                       frame_w=frame_w, frame_h=frame_h)

        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        cx, cy = x + w / 2, y + h / 2

        return cls(
            durum=durum,
            timestamp=data.get("timestamp", 0.0),
            frame_id=data.get("frame_id", 0),
            x_error=(cx - frame_w / 2) / (frame_w / 2),
            y_error=(cy - frame_h / 2) / (frame_h / 2),
            bbox_area=(w * h) / (frame_w * frame_h),
            bbox=(x, y, w, h),
            bbox_px=w * h,
            guven_skoru=data.get("guven_skoru"),
            frame_w=frame_w,
            frame_h=frame_h,
        )

    @classmethod
    def from_error(cls, data: dict, frame_w: int = 1280, frame_h: int = 720):
        durum = data.get("durum", "HEDEF_KAYIP")
        area = data.get("bbox_area")
        return cls(
            durum=durum,
            timestamp=data.get("timestamp", 0.0),
            frame_id=data.get("frame_id", 0),
            x_error=data.get("x_error"),
            y_error=data.get("y_error"),
            bbox_area=area,
            bbox_px=area * frame_w * frame_h if area is not None else None,
            guven_skoru=data.get("guven_skoru"),
            frame_w=frame_w,
            frame_h=frame_h,
        )

    @classmethod
    def from_dict(cls, data: dict, frame_w: int = 1280, frame_h: int = 720):
        """Otomatik format tespiti."""
        if "bbox" in data:
            return cls.from_bbox(data, frame_w, frame_h)
        return cls.from_error(data, frame_w, frame_h)

    @classmethod
    def from_boxes(cls, box, t: float, frame_id: int = 0,
                   frame_w: int = 1280, frame_h: int = 720,
                   guven: float = 0.9):
        """fake_target.Frame.tracked gibi bir (x,y,w,h) tuple'dan uretir."""
        if box is None:
            return cls.lost(t, frame_id)
        x, y, w, h = box
        cx, cy = x + w / 2, y + h / 2
        return cls(
            durum="TAKIP", timestamp=t, frame_id=frame_id,
            x_error=(cx - frame_w / 2) / (frame_w / 2),
            y_error=(cy - frame_h / 2) / (frame_h / 2),
            bbox_area=(w * h) / (frame_w * frame_h),
            bbox=(x, y, w, h), bbox_px=w * h,
            guven_skoru=guven, frame_w=frame_w, frame_h=frame_h,
        )

    @classmethod
    def lost(cls, timestamp: float, frame_id: int = 0):
        return cls(durum="HEDEF_KAYIP", timestamp=timestamp, frame_id=frame_id)