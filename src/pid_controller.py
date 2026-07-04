"""
KTR Raporu Tablo 4 mantigina uygun, ancak normalize edilmis hataya
gore YENIDEN OLCEKLENMIS Kp katsayilariyla calisan PID kontrolcu.

TUNING NOTU: Orijinal KTR Kp degerleri piksel-bazli hata icin tasarlanmisti.
Hata normalize edilince (-1..1 araligina), Kp'lerin de output_max'a yakin
olacak sekilde yeniden olceklenmesi gerekti. Oran korunarak (Yaw > Pitch >
Throttle > Roll) yeniden hesaplandi.
"""
import time


class PID:
    def __init__(self, Kp, Ki, Kd, output_min, output_max):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral = 0
        self.last_error = 0
        self.last_time = None

    def update(self, error):
        now = time.time()
        dt = 0.1 if self.last_time is None else max(now - self.last_time, 0.01)

        self.integral += error * dt
        self.integral = max(-2.0, min(2.0, self.integral))  # windup onleme

        derivative = (error - self.last_error) / dt
        output = (self.Kp * error) + (self.Ki * self.integral) + (self.Kd * derivative)
        output = max(self.output_min, min(self.output_max, output))

        self.last_error = error
        self.last_time = now
        return output

    def reset(self):
        self.integral = 0
        self.last_error = 0
        self.last_time = None


class TrackingController:
    def __init__(self, cam_width=640, cam_height=480, reference_area=5000):
        self.frame_center_x = cam_width / 2
        self.frame_center_y = cam_height / 2
        self.half_width = cam_width / 2
        self.half_height = cam_height / 2
        self.reference_area = reference_area

        # YENIDEN OLCEKLENMIS Kp: normalize hata (max ±1) icin, output_max'a
        # yakin bir maksimum tepki uretecek sekilde ayarlandi. KTR'deki
        # oransal iliski (Yaw en agresif, Roll en yumusak) korundu.
        self.pid_yaw = PID(Kp=0.45, Ki=0.02, Kd=0.08, output_min=-0.5, output_max=0.5)
        self.pid_pitch = PID(Kp=0.35, Ki=0.015, Kd=0.06, output_min=-0.4, output_max=0.4)
        self.pid_roll = PID(Kp=0.22, Ki=0.01, Kd=0.04, output_min=-0.3, output_max=0.3)
        self.pid_throttle = PID(Kp=0.28, Ki=0.01, Kd=0.05, output_min=-0.3, output_max=0.3)

    def compute(self, bbox_x, bbox_y, bbox_w, bbox_h):
        x_merkez = bbox_x + bbox_w / 2
        y_merkez = bbox_y + bbox_h / 2
        area = bbox_w * bbox_h

        x_error = (x_merkez - self.frame_center_x) / self.half_width
        y_error = (y_merkez - self.frame_center_y) / self.half_height
        area_error = (self.reference_area - area) / self.reference_area

        yaw_rate = self.pid_yaw.update(x_error)
        pitch_rate = self.pid_pitch.update(y_error)
        roll_rate = self.pid_roll.update(x_error)
        thrust_adj = self.pid_throttle.update(area_error)

        return roll_rate, pitch_rate, yaw_rate, thrust_adj

    def reset(self):
        self.pid_yaw.reset()
        self.pid_pitch.reset()
        self.pid_roll.reset()
        self.pid_throttle.reset()
