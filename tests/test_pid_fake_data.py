"""
Sahte (uydurma) tracking verisiyle PID kontrolcusunu test eder.
Gercek model/tracking hazir olunca, bu sahte veri kaynagi
Sercan'in tracking modulu ile degistirilecek.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import math
from pid_controller import TrackingController

def fake_tracking_data(t):
    """Sahte hedef: goruntude sinuzoidal hareket eden bir nokta."""
    x = 320 + 100 * math.sin(t)
    y = 240 + 50 * math.cos(t * 0.7)
    return x, y

if __name__ == "__main__":
    controller = TrackingController(cam_width=640, cam_height=480,
                                     Kp=0.005, Ki=0.0, Kd=0.001, max_velocity=2.0)
    
    print("Sahte veri ile PID testi basliyor (10 saniye)...")
    start = time.time()
    while time.time() - start < 10:
        t = time.time() - start
        target_x, target_y = fake_tracking_data(t)
        
        vy, vz = controller.compute(target_x, target_y)
        
        print(f"t:{t:.1f}s  hedef:({target_x:.0f},{target_y:.0f})  -> vy:{vy:.3f} vz:{vz:.3f}")
        time.sleep(0.1)
    
    print("Test tamamlandi.")
