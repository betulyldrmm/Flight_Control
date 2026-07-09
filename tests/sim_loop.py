"""
Kapali cevrim simulasyon dongusu.

Hedefin gercek rotasi -> goreceli konum -> kamera projeksiyonu -> bbox
-> TrackingData -> PID -> ucus komutlari -> takipci dinamigi -> yeni konum

AMAC VE SINIRLAR:
  Bu modul, PID kontrolcusunun mantiksal davranisini (isaret yonleri,
  deadband, doygunluk, coasting) dogrulamak icin yazilmistir.

  Takipci dinamigi basit bir nokta-kutle modelidir. Gercek ucus dinamigi
  (motor tepkisi, atalet tensoru, aerodinamik) modellenmemistir; bu
  dogrulama ArduPilot SITL uzerinde yapilacaktir.

TAKIPCI DINAMIK MODELI:
  KTR Raporu: itki/agirlik orani (TWR) = 4.1, MTOW 1884 g.

  Yatay ivme:  a = g * tan(tilt).  30 derece -> 5.66 m/s^2
  Dikey ivme:  a = (TWR - 1) * g = 30.4 m/s^2 teorik, %50 marj ile 15.2
  Suruklenme:  lineer model. Denge hizi = a / drag.

KAMERA YONELIMI:
  Quadcopter tirmanirken govdesi yatay kalir; burun sadece YATAY ivme
  icin egilir. Bu yuzden govde pitch acisi, ileri ivme komutundan
  (out.throttle) turetilir; dikey komut (out.pitch) govde acisini
  degistirmez, sadece tirmanis ivmesi verir.

  KTR: kamera govdeye ~15 derece yukari egik monte edilmistir. Bu aci,
  ileri ucusta burnun asagi egilmesini kismen telafi eder. Etkisi
  camera_mount_deg parametresiyle taranabilir.
"""

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from src.pid_controller import TrackingController
from src.tracking_interface import TrackingData
from src.metrics import ManeuverEvaluator
from tests.fake_target import CameraModel, DEFAULT_CAM

G = 9.81
TWR = 4.1                                    # KTR: itki/agirlik orani
MAX_TILT_RAD = math.radians(30.0)            # KTR: 25-30 derece pitch
MAX_FWD_ACCEL = G * math.tan(MAX_TILT_RAD)   # ~5.66 m/s^2
MAX_CLIMB_ACCEL = (TWR - 1.0) * G * 0.5      # ~15.2 m/s^2 (%50 marj)
MAX_YAW_RATE = math.radians(120.0)           # rad/s

DEFAULT_DRAG = 0.3
PITCH_RESPONSE = 2.5                         # govde acisinin yerlesme hizi (1/s)


@dataclass
class ChaserState:
    """Takipci drone'un dunya koordinatlarindaki durumu."""
    x: float = 0.0        # ileri (kuzey)
    y: float = 0.0        # saga (dogu)
    z: float = 5.0        # yukari
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    heading: float = 0.0  # radyan, +x yonunden saat yonunde
    pitch: float = 0.0    # govde egim acisi (rad), + = burun yukari


def cmd_to_accel(out, heading: float) -> Tuple[float, float, float]:
    """
    PID cikisini dunya koordinatlarinda ivmeye cevirir.

      throttle (area_error'den): hedef uzaksa ileri git   -> yatay ivme
      pitch    (y_error'den):    hedef yukardaysa tirman  -> dikey ivme
      roll     (yaw'dan turemis): koordineli donus        -> yan ivme
    """
    a_fwd = (out.throttle / 0.3) * MAX_FWD_ACCEL
    a_lat = (out.roll / 0.3) * MAX_FWD_ACCEL * 0.5
    a_up = -(out.pitch / 0.4) * MAX_CLIMB_ACCEL   # y_error negatif = hedef yukarda

    ax = a_fwd * math.cos(heading) - a_lat * math.sin(heading)
    ay = a_fwd * math.sin(heading) + a_lat * math.cos(heading)
    return ax, ay, a_up


def world_to_body(target_xyz, chaser: ChaserState,
                  mount_rad: float = 0.0) -> Tuple[float, float, float]:
    """
    Hedefin dunya konumunu KAMERA eksenine cevirir.
    Sirasiyla: yaw donusu -> pitch donusu (govde egimi + kamera montaj acisi).
    """
    dx = target_xyz[0] - chaser.x
    dy = target_xyz[1] - chaser.y
    dz = target_xyz[2] - chaser.z

    # 1) Yaw donusu
    c, s = math.cos(-chaser.heading), math.sin(-chaser.heading)
    fwd = dx * c - dy * s
    right = dx * s + dy * c
    up = dz

    # 2) Pitch donusu (govde egimi + kamera montaj acisi)
    theta = chaser.pitch + mount_rad
    ct, st = math.cos(-theta), math.sin(-theta)
    fwd2 = fwd * ct - up * st
    up2 = fwd * st + up * ct

    return (fwd2, right, up2)


@dataclass
class SimResult:
    evaluator: ManeuverEvaluator
    distances: List[float] = field(default_factory=list)
    bbox_sides: List[float] = field(default_factory=list)
    saturated_frames: int = 0
    lost_frames: int = 0

    def summary(self) -> dict:
        s = self.evaluator.summary()
        n = max(len(self.distances), 1)
        s.update({
            "ort_mesafe_m": round(sum(self.distances) / n, 2),
            "max_mesafe_m": round(max(self.distances), 2) if self.distances else 0.0,
            "min_bbox_px": round(min(self.bbox_sides), 1) if self.bbox_sides else 0.0,
            "doygun_frame": self.saturated_frames,
            "kayip_frame": self.lost_frames,
        })
        return s


def run_closed_loop(name: str,
                    target_path: Callable[[float], Tuple[float, float, float]],
                    duration: float,
                    fps: int = 30,
                    cam: CameraModel = DEFAULT_CAM,
                    controller: Optional[TrackingController] = None,
                    initial_dist: float = 4.0,
                    drag: float = DEFAULT_DRAG,
                    camera_mount_deg: float = 0.0) -> SimResult:
    """
    target_path(t) -> hedefin dunya koordinatlari (x, y, z)
    duration: simulasyon suresi (saniye)
    camera_mount_deg: kameranin govdeye gore yukari egim acisi
    """
    ctrl = controller or TrackingController(cam=cam)
    dt = 1.0 / fps
    mount_rad = math.radians(camera_mount_deg)

    # Takipci, hedefin initial_dist gerisinde baslar
    t0 = target_path(0.0)
    chaser = ChaserState(x=t0[0] - initial_dist, y=t0[1], z=t0[2])

    res = SimResult(evaluator=ManeuverEvaluator(name))
    steps = int(duration * fps)

    for i in range(steps):
        t = i * dt
        tgt = target_path(t)

        # 1) Algi: goreceli konum -> kamera ekseni -> bbox
        body = world_to_body(tgt, chaser, mount_rad)
        ref_box = cam.project(*body)

        res.distances.append(math.dist((chaser.x, chaser.y, chaser.z), tgt))
        if ref_box:
            res.bbox_sides.append(ref_box[2])
        else:
            res.lost_frames += 1

        # 2) Metrik (tracker gurultusuz varsayiliyor: tracked == reference)
        res.evaluator.add(ref_box, ref_box, t)

        # 3) Kontrol
        data = TrackingData.from_boxes(ref_box, t, i,
                                       frame_w=cam.w, frame_h=cam.h)
        out = ctrl.compute(data, dt=dt)

        if (abs(out.throttle) >= 0.299 or abs(out.pitch) >= 0.399
                or abs(out.yaw_rate) >= 0.499):
            res.saturated_frames += 1

        # 4) Dinamik: ivme -> hiz -> konum
        ax, ay, az = cmd_to_accel(out, chaser.heading)
        chaser.vx += (ax - drag * chaser.vx) * dt
        chaser.vy += (ay - drag * chaser.vy) * dt
        chaser.vz += (az - drag * chaser.vz) * dt
        chaser.x += chaser.vx * dt
        chaser.y += chaser.vy * dt
        chaser.z += chaser.vz * dt
        chaser.heading += (out.yaw_rate / 0.5) * MAX_YAW_RATE * dt

        # Govde pitch acisi ileri ivmeden gelir: ileri gitmek icin burun asagi.
        # Tirmanis govde acisini degistirmez (quadcopter yatay kalarak yukselir).
        pitch_cmd = -(out.throttle / 0.3) * MAX_TILT_RAD
        chaser.pitch += (pitch_cmd - chaser.pitch) * min(1.0, PITCH_RESPONSE * dt)

    return res