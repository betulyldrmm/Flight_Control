"""
Kamera modeli ve sartname kaynakli optik kisitlar.

Yarisma Bilgilendirme Dokumani, Bolum 3:
  "Hedef IHA 30x30x30 cm boyutlarinda standart bir govde mimarisine
   sahip olacaktir."
  "Gorus alani ve cozunurluk farketmeksizin manevra boyunca hedef drone
   tespit karesi icerisinde 64*64 (4096) piksel alani boyutundan daha
   buyuk bir alan kaplamalidir."

Bu iki kisit birlikte, kamera secimine bir ust sinir koyar:
takip mesafesi arttikca hedefin piksel alani kucuur.
"""

import math
from typing import Optional, Tuple

Box = Tuple[float, float, float, float]  # (x, y, w, h)

MIN_BBOX_SIDE_PX = 64.0          # sartname: 64x64 minimum
MIN_BBOX_PX = MIN_BBOX_SIDE_PX ** 2
TARGET_SIZE_M = 0.30             # hedef IHA govde boyutu


class CameraModel:
    """
    Pinhole kamera. 3B goreceli konumu bounding box'a projekte eder.

    Koordinat sistemi (kamera ekseni):
        +X: ileri (bakis yonu)
        +Y: saga
        +Z: yukari
    """

    def __init__(self, width: int = 1280, height: int = 720,
                 fov_deg: float = 70.0, target_size_m: float = TARGET_SIZE_M):
        self.w = width
        self.h = height
        self.fov = fov_deg
        self.target_size = target_size_m
        self.focal_px = width / (2 * math.tan(math.radians(fov_deg) / 2))

    # -- projeksiyon -----------------------------------------------------

    def project(self, x_fwd: float, y_right: float, z_up: float) -> Optional[Box]:
        """Hedef arkadaysa veya kadraj disindaysa None doner."""
        if x_fwd <= 0.1:
            return None

        u = self.w / 2 + (y_right / x_fwd) * self.focal_px
        v = self.h / 2 - (z_up / x_fwd) * self.focal_px
        size_px = (self.target_size / x_fwd) * self.focal_px

        if u < 0 or u > self.w or v < 0 or v > self.h:
            return None

        return (u - size_px / 2, v - size_px / 2, size_px, size_px)

    # -- optik kisitlar --------------------------------------------------

    def size_at(self, distance_m: float) -> float:
        """Verilen mesafede hedefin kenar uzunlugu (piksel)."""
        return (self.target_size / distance_m) * self.focal_px

    def area_at(self, distance_m: float) -> float:
        """Verilen mesafede hedefin normalize bbox alani [0, 1]."""
        side = self.size_at(distance_m)
        return (side * side) / (self.w * self.h)

    def max_range_for_min_size(self, min_px_side: float = MIN_BBOX_SIDE_PX) -> float:
        """Sartname kriterini saglayabilecegimiz en uzak mesafe (m)."""
        return (self.target_size * self.focal_px) / min_px_side

    def vertical_half_fov_deg(self) -> float:
        """Dikey yari gorus acisi. Kamera montaj acisi bundan kucuk olmali."""
        return math.degrees(math.atan(self.h / 2 / self.focal_px))

    def horizontal_half_fov_deg(self) -> float:
        return self.fov / 2

    def __repr__(self):
        return (f"CameraModel({self.w}x{self.h}, {self.fov}deg, "
                f"f={self.focal_px:.0f}px, max_menzil={self.max_range_for_min_size():.1f}m)")


# Aday konfigurasyonlar (bkz. tests/camera_range_analysis.py)
CAM_720P_70 = CameraModel(1280, 720, 70)     # mevcut varsayim: max 4.3 m
CAM_720P_50 = CameraModel(1280, 720, 50)     # max 6.4 m
CAM_720P_40 = CameraModel(1280, 720, 40)     # max 8.2 m
CAM_1080P_50 = CameraModel(1920, 1080, 50)   # max 9.7 m

DEFAULT_CAM = CAM_720P_70