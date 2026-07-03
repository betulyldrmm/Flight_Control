"""
Basit PID kontrolcu sinifi.
Hedefin goruntudeki piksel hatasini alip duzeltici hiz komutuna cevirir.
"""
import time

class PID:
    def __init__(self, Kp, Ki, Kd, output_limit=None):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.output_limit = output_limit
        
        self.integral = 0
        self.last_error = 0
        self.last_time = None

    def update(self, error):
        """Yeni bir hata degeri ile PID ciktisini hesapla."""
        now = time.time()
        if self.last_time is None:
            dt = 0.1
        else:
            dt = now - self.last_time
            if dt <= 0:
                dt = 0.01
        
        self.integral += error * dt
        derivative = (error - self.last_error) / dt
        
        output = (self.Kp * error) + (self.Ki * self.integral) + (self.Kd * derivative)
        
        if self.output_limit is not None:
            output = max(-self.output_limit, min(self.output_limit, output))
        
        self.last_error = error
        self.last_time = now
        return output

    def reset(self):
        """Integral ve turev hafizasini sifirla (mod degisince kullanilir)."""
        self.integral = 0
        self.last_error = 0
        self.last_time = None


class TrackingController:
    """
    Goruntudeki hedef merkez koordinatini alip,
    kameranin optik merkezine gore duzeltici hiz komutlarina cevirir.
    """
    def __init__(self, cam_width=640, cam_height=480,
                 Kp=0.005, Ki=0.0, Kd=0.001, max_velocity=2.0):
        self.cam_center_x = cam_width / 2
        self.cam_center_y = cam_height / 2
        
        self.pid_x = PID(Kp, Ki, Kd, output_limit=max_velocity)
        self.pid_y = PID(Kp, Ki, Kd, output_limit=max_velocity)

    def compute(self, target_x, target_y):
        """
        target_x, target_y: hedefin goruntudeki piksel koordinati
        (Sercan'in tracking modulunden gelecek bounding box merkezi)
        
        Donus: (vy, vz) -> sag/sol ve yukari/asagi hiz komutlari (m/s)
        """
        error_x = target_x - self.cam_center_x
        error_y = target_y - self.cam_center_y
        
        vy = self.pid_x.update(error_x)
        vz = self.pid_y.update(error_y)
        
        return vy, vz

    def reset(self):
        self.pid_x.reset()
        self.pid_y.reset()
