"""
Sahte hedef IHA veri ureteci.

Yarisma Bilgilendirme Dokumani Bolum 2'deki manevra setlerini,
kamera projeksiyonu ile bounding box'a cevirir.

Hedef IHA: 30x30x30 cm (dokuman Bolum 3).
Varsayilan kamera: 1280x720, ~70 derece yatay FOV (Arducam B0429).

Koordinat sistemi (takipci drone govde ekseni):
    +X: ileri (kamera bakis yonu)
    +Y: saga
    +Z: yukari
"""

import math
import random
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

Box = Tuple[float, float, float, float]  # (x, y, w, h)

MIN_BBOX_SIDE_PX = 64.0  # sartname: 64x64 minimum tespit alani


# ---------------------------------------------------------------
# Kamera modeli
# ---------------------------------------------------------------

class CameraModel:
    """Pinhole kamera. 3B konumu bounding box'a projekte eder."""

    def __init__(self, width: int = 1280, height: int = 720,
                 fov_deg: float = 70.0, target_size_m: float = 0.30):
        self.w = width
        self.h = height
        self.fov = fov_deg
        self.target_size = target_size_m
        self.focal_px = width / (2 * math.tan(math.radians(fov_deg) / 2))

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

    def max_range_for_min_size(self, min_px_side: float = MIN_BBOX_SIDE_PX) -> float:
        """Hedefin min_px_side kenar uzunlugu kaplayabilecegi max mesafe (m)."""
        return (self.target_size * self.focal_px) / min_px_side

    def size_at(self, distance_m: float) -> float:
        """Verilen mesafede hedefin kenar uzunlugu (piksel)."""
        return (self.target_size / distance_m) * self.focal_px

    def __repr__(self):
        return f"CameraModel({self.w}x{self.h}, {self.fov}deg, f={self.focal_px:.0f}px)"


DEFAULT_CAM = CameraModel()


# ---------------------------------------------------------------
# Frame
# ---------------------------------------------------------------

@dataclass
class Frame:
    """Tek kare: hedefin gercek (referans) kutusu ve tracker'in urettigi kutu."""
    t: float                            # otonom moddan itibaren gecen sure (sn)
    frame_id: int
    reference: Optional[Box]            # hakemin referans kutusu = gercek konum
    tracked: Optional[Box]              # bizim tracker'in urettigi kutu
    pos_3d: Tuple[float, float, float]  # hedefin govde eksenindeki konumu (m)

    @property
    def distance(self) -> float:
        """Hedefe olan oklid mesafesi (m)."""
        x, y, z = self.pos_3d
        return math.sqrt(x * x + y * y + z * z)


def add_tracker_noise(ref: Optional[Box], jitter: float = 0.05,
                      drop_prob: float = 0.0, rng=None) -> Optional[Box]:
    """Gercek tracker'i taklit eder: hafif kayma + ara sira tespit kaybi."""
    if ref is None:
        return None
    rng = rng or random
    if rng.random() < drop_prob:
        return None

    x, y, w, h = ref
    dx = rng.uniform(-jitter, jitter) * w
    dy = rng.uniform(-jitter, jitter) * h
    dw = rng.uniform(-jitter, jitter) * w
    return (x + dx, y + dy, w + dw, h + dw)


def _emit(t: float, fid: int, pos, jitter, drop, rng, cam: CameraModel) -> Frame:
    ref = cam.project(*pos)
    return Frame(t=t, frame_id=fid, reference=ref,
                 tracked=add_tracker_noise(ref, jitter, drop, rng),
                 pos_3d=pos)


# ---------------------------------------------------------------
# Manevra istasyonlari
#
# NOT: pos_3d, hedefin TAKIPCI GOVDE EKSENINDEKI goreceli konumudur.
# Takipci mukemmel takip etmez; hedefin hareketinin bir kismini
# yakalayamaz, kalan hata kameraya yansir. 'lag' bu eksikligi temsil eder.
# ---------------------------------------------------------------

def station_1_linear(fps: int = 30, follow_dist: float = 6.0,
                     speed: float = 3.0, jitter: float = 0.05,
                     drop_prob: float = 0.0, seed: int = 42,
                     lag: float = 0.85,
                     cam: CameraModel = DEFAULT_CAM) -> Iterator[Frame]:
    """Ilk istasyon: 7m ileri, 5m saga, 7m yukari, 5m sola."""
    rng = random.Random(seed)
    segments = [(7.0, (1, 0, 0)), (5.0, (0, 1, 0)),
                (7.0, (0, 0, 1)), (5.0, (0, -1, 0))]

    tx, ty, tz = follow_dist, 0.0, 0.0
    t, fid = 0.0, 0
    dt = 1.0 / fps

    for dist, (dx, dy, dz) in segments:
        steps = int((dist / speed) * fps)
        for _ in range(steps):
            step = speed * dt * (1 - lag)
            tx += dx * step
            ty += dy * step
            tz += dz * step
            yield _emit(t, fid, (tx, ty, tz), jitter, drop_prob, rng, cam)
            t += dt
            fid += 1


def station_2_sine_x(fps: int = 30, follow_dist: float = 6.0,
                     speed: float = 5.0, length: float = 15.0,
                     amplitude: float = 2.0, jitter: float = 0.05,
                     drop_prob: float = 0.0, seed: int = 42,
                     lag: float = 0.85,
                     cam: CameraModel = DEFAULT_CAM) -> Iterator[Frame]:
    """Ikinci istasyon: sabit irtifa, yatay sinus, 15m hat."""
    rng = random.Random(seed)
    dt = 1.0 / fps
    steps = int((length / speed) * fps)
    residual = 1 - lag

    for i in range(steps):
        t = i * dt
        s = (i / steps) * length
        lateral = amplitude * math.sin(2 * math.pi * s / (length / 1.5))
        yield _emit(t, i, (follow_dist, lateral * residual, 0.0),
                    jitter, drop_prob, rng, cam)


def station_3_sine_y(fps: int = 30, follow_dist: float = 6.0,
                     speed: float = 6.0, length: float = 15.0,
                     amplitude: float = 2.0, jitter: float = 0.05,
                     drop_prob: float = 0.0, seed: int = 42,
                     lag: float = 0.85,
                     cam: CameraModel = DEFAULT_CAM) -> Iterator[Frame]:
    """Ucuncu istasyon: 8m baslangic irtifasi, dusey sinus, 15m hat."""
    rng = random.Random(seed)
    dt = 1.0 / fps
    steps = int((length / speed) * fps)
    residual = 1 - lag

    for i in range(steps):
        t = i * dt
        s = (i / steps) * length
        vertical = amplitude * math.sin(2 * math.pi * s / (length / 1.5))
        yield _emit(t, i, (follow_dist, 0.0, vertical * residual),
                    jitter, drop_prob, rng, cam)


def station_4_3d(fps: int = 30, follow_dist: float = 6.0,
                 speed: float = 8.0, length: float = 15.0,
                 amplitude: float = 2.0, jitter: float = 0.05,
                 drop_prob: float = 0.0, seed: int = 42,
                 lag: float = 0.85,
                 cam: CameraModel = DEFAULT_CAM) -> Iterator[Frame]:
    """
    Dorduncu istasyon: 3D helisel sinus -> 50m irtifaya ani tirmanis
    -> 25m ileri, 20m irtifadaki noktaya dalis.

    En zorlu bolum. Tirmanis sirasinda takipci geride kalir,
    hedef uzaklasir ve bbox 64x64'un altina dusebilir.
    """
    rng = random.Random(seed)
    dt = 1.0 / fps
    residual = 1 - lag
    fid, t = 0, 0.0

    # 1) Helisel (3D) sinus
    steps = int((length / speed) * fps)
    for i in range(steps):
        s = (i / steps) * length
        phase = 2 * math.pi * s / (length / 1.5)
        yield _emit(t, fid, (follow_dist,
                             amplitude * math.sin(phase) * residual,
                             amplitude * math.cos(phase) * residual),
                    jitter, drop_prob, rng, cam)
        t += dt
        fid += 1

    # 2) Ani tirmanis: 8m -> 50m irtifa
    climb_m = 42.0
    climb_speed = 15.0
    steps = int((climb_m / climb_speed) * fps)
    for i in range(steps):
        prog = i / steps
        rel_z = climb_m * prog * 0.40   # takipci tirmanisin %60'ini yakalar
        rel_x = follow_dist + climb_m * prog * 0.20
        yield _emit(t, fid, (rel_x, 0.0, rel_z), jitter, drop_prob, rng, cam)
        t += dt
        fid += 1

    # 3) Dalis: 50m -> 20m irtifa, 25m ileri
    steps = int(3.0 * fps)
    z0 = climb_m * 0.40
    x0 = follow_dist + climb_m * 0.20
    for i in range(steps):
        prog = i / steps
        rel_z = z0 * (1 - prog)
        rel_x = x0 + 25.0 * prog * 0.30
        yield _emit(t, fid, (rel_x, 0.0, rel_z), jitter, drop_prob, rng, cam)
        t += dt
        fid += 1


def with_target_lost(source: Iterator[Frame], lost_start: float,
                     lost_duration: float) -> Iterator[Frame]:
    """Belirli bir zaman araliginda tracker'i kor eder (hedef kaybi senaryosu)."""
    for f in source:
        if lost_start <= f.t < lost_start + lost_duration:
            yield Frame(t=f.t, frame_id=f.frame_id, reference=f.reference,
                        tracked=None, pos_3d=f.pos_3d)
        else:
            yield f


STATIONS = {
    "1_linear": station_1_linear,
    "2_sine_x": station_2_sine_x,
    "3_sine_y": station_3_sine_y,
    "4_3d": station_4_3d,
}