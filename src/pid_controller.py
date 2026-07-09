"""
Goruntu isleme/takip modulunden gelen normalize hata sinyallerini
ucus komutlarina ceviren PID kontrolcu.

TASARIM NOTLARI:

1. Hata hesabi burada YAPILMAZ. tracking_interface.TrackingData zaten
   x_error, y_error, bbox_area uretir. PID sadece hazir hata alir.

2. DEADBAND (acisal): Yarisma Bilgilendirme Dokumani, "Takip icin hedef
   dronu goruntu merkezinde tutma sarti bulunmamaktadir" diyor. Basari
   kriteri bbox boyutu ve IoU. Hedef kadrajin orta bolgesindeyken
   yaw/pitch komutu uretilmez -> gereksiz salinim onlenir.

   Alan (mesafe) kontrolunde deadband YOK: mesafeyi surekli korumak
   gerekiyor, cunku bbox boyutu dogrudan basari kriteri.

3. ROLL ayri bir PID degil. Yaw ile ayni hataya (x_error) bagli iki
   bagimsiz kontrolcu birbirini pompalar ve salinim uretir. Roll,
   yaw_rate'ten turetilir (koordineli donus).

4. COASTING: Hedef kisa sureligine kaybolursa komut aniden sifirlanmaz.
   Son komut sonumlenerek korunur (coast_frames boyunca). Bu, KTR'deki
   "Kalman tahmini ile kisa sureli devam" davranisinin basit karsiligi.

5. Cikis limitleri KTR Raporu Tablo 4'ten alinmistir.
"""

import time
from dataclasses import dataclass
from typing import Optional

# KTR Tablo 4: cikis araliklari
YAW_LIMITS = (-0.5, 0.5)
PITCH_LIMITS = (-0.4, 0.4)
ROLL_LIMITS = (-0.3, 0.3)
THROTTLE_LIMITS = (-0.3, 0.3)


class PID:
    def __init__(self, Kp: float, Ki: float, Kd: float,
                 output_min: float, output_max: float,
                 integral_limit: float = 2.0):
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        self.reset()

    def update(self, error: float, dt: Optional[float] = None) -> float:
        """dt verilmezse gercek zamandan hesaplanir; verilirse simulasyon adimi."""
        if dt is None:
            now = time.time()
            dt = 0.033 if self.last_time is None else max(now - self.last_time, 0.001)
            self.last_time = now

        self.integral += error * dt
        self.integral = max(-self.integral_limit,
                            min(self.integral_limit, self.integral))

        derivative = (error - self.last_error) / dt if dt > 0 else 0.0

        raw = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        output = max(self.output_min, min(self.output_max, raw))

        # Anti-windup: cikis doygunlugundaysa integrali buyutme
        if raw != output:
            self.integral -= error * dt

        self.last_error = error
        return output

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None


@dataclass
class ControlOutput:
    roll: float
    pitch: float
    yaw_rate: float
    throttle: float
    in_deadband: bool = False
    coasting: bool = False

    def as_tuple(self):
        return (self.roll, self.pitch, self.yaw_rate, self.throttle)


ZERO_OUTPUT = ControlOutput(0.0, 0.0, 0.0, 0.0, in_deadband=True)


class TrackingController:
    """
    TrackingData -> (roll, pitch, yaw_rate, throttle)

    reference_area: hedefin kaplamasi istenen normalize bbox alani.
        Dogrudan verilmezse cam + desired_distance_m'den hesaplanir.
        Sartname minimumu 4096 px (1280x720'de normalize 0.00444).
    """

    def __init__(self,
                 reference_area: Optional[float] = None,
                 desired_distance_m: float = 4.0,
                 cam=None,
                 deadband_xy: float = 0.10,
                 deadband_area: float = 0.0,
                 roll_coupling: float = 0.40,
                 coast_frames: int = 15):
        if reference_area is None:
            if cam is None:
                reference_area = 0.0075
            else:
                side = cam.size_at(desired_distance_m)
                reference_area = (side * side) / (cam.w * cam.h)

        self.reference_area = reference_area
        self.desired_distance_m = desired_distance_m
        self.deadband_xy = deadband_xy
        self.deadband_area = deadband_area
        self.roll_coupling = roll_coupling
        self.coast_frames = coast_frames

        self.pid_yaw = PID(0.45, 0.02, 0.08, *YAW_LIMITS)
        self.pid_pitch = PID(0.50, 0.02, 0.10, *PITCH_LIMITS)
        self.pid_throttle = PID(0.60, 0.03, 0.12, *THROTTLE_LIMITS)

        self.lost_frames = 0
        self._last = ControlOutput(0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _apply_deadband(error: float, band: float) -> float:
        """Olu bant disindaki hatayi yeniden olcekler (surekli gecis)."""
        if band <= 0.0:
            return error
        if abs(error) <= band:
            return 0.0
        sign = 1.0 if error > 0 else -1.0
        return sign * (abs(error) - band) / (1.0 - band)

    def compute(self, data, dt: Optional[float] = None) -> ControlOutput:
        """data: TrackingData nesnesi."""
        if not data.is_valid():
            self.lost_frames += 1

            # Kisa sureli kayip: son komutu sonumlendirerek koru
            if self.lost_frames <= self.coast_frames:
                decay = 1.0 - (self.lost_frames / self.coast_frames)
                return ControlOutput(
                    roll=self._last.roll * decay,
                    pitch=self._last.pitch * decay,
                    yaw_rate=self._last.yaw_rate * decay,
                    throttle=self._last.throttle * decay,
                    coasting=True,
                )

            self.reset()
            return ZERO_OUTPUT

        self.lost_frames = 0

        x_err = self._apply_deadband(data.x_error, self.deadband_xy)
        y_err = self._apply_deadband(data.y_error, self.deadband_xy)

        # Hedef kucukse pozitif (yaklas), buyukse negatif (uzaklas)
        area_raw = (self.reference_area - data.bbox_area) / self.reference_area
        area_err = self._apply_deadband(area_raw, self.deadband_area)

        in_db = (x_err == 0.0 and y_err == 0.0 and area_err == 0.0)

        yaw_rate = self.pid_yaw.update(x_err, dt)
        pitch = self.pid_pitch.update(y_err, dt)
        throttle = self.pid_throttle.update(area_err, dt)

        # Koordineli donus: yaw yonunde hafif yatis
        roll = max(ROLL_LIMITS[0], min(ROLL_LIMITS[1],
                                       self.roll_coupling * yaw_rate))

        out = ControlOutput(roll=roll, pitch=pitch,
                            yaw_rate=yaw_rate, throttle=throttle,
                            in_deadband=in_db)
        self._last = out
        return out

    def reset(self):
        self.pid_yaw.reset()
        self.pid_pitch.reset()
        self.pid_throttle.reset()
        self.lost_frames = 0
        self._last = ControlOutput(0.0, 0.0, 0.0, 0.0)