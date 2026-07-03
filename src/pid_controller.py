"""
KTR Raporu Tablo 4'e uygun PID kontrolcu.
4 eksen: Yaw (x_error), Pitch (y_error), Roll (x_error), Throttle (area_error)
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
    """
    KTR Tablo 4'teki katsayilarla 4 eksenli kontrol.
    Girdiler: bounding box (x, y, w, h) -> x_error, y_error, area_error hesaplanir.
    Cikti: roll_rate, pitch_rate, yaw_rate, thrust (SET_ATTITUDE_TARGET icin)
    """
    def __init__(self, cam_width=640, cam_height=480, reference_area=5000):
        self.frame_center_x = cam_width / 2
        self.frame_center_y = cam_height / 2
        self.reference_area = reference_area  # hedefle olan referans mesafe (bbox alani)

        # KTR Tablo 4 degerleri
        self.pid_yaw = PID(Kp=0.08, Ki=0.004, Kd=0.012, output_min=-0.5, output_max=0.5)
        self.pid_pitch = PID(Kp=0.06, Ki=0.003, Kd=0.010, output_min=-0.4, output_max=0.4)
        self.pid_roll = PID(Kp=0.04, Ki=0.002, Kd=0.007, output_min=-0.3, output_max=0.3)
        self.pid_throttle = PID(Kp=0.05, Ki=0.002, Kd=0.008, output_min=-0.3, output_max=0.3)

    def compute(self, bbox_x, bbox_y, bbox_w, bbox_h):
        """
        bbox_x, bbox_y: bounding box sol-ust kose koordinati
        bbox_w, bbox_h: bounding box genislik/yukseklik
        
        Donus: (roll_rate, pitch_rate, yaw_rate, thrust_adjustment)
        """
        x_merkez = bbox_x + bbox_w / 2
        y_merkez = bbox_y + bbox_h / 2
        area = bbox_w * bbox_h

        x_error = x_merkez - self.frame_center_x
        y_error = y_merkez - self.frame_center_y
        area_error = self.reference_area - area  # pozitifse hedef uzak (yaklas), negatifse yakin (uzaklas)

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
