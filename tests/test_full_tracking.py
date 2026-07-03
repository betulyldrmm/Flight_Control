"""
Uctan uca test: Kalkis yap, sonra sahte hedefi PID ile takip et.
Gercek model/tracking hazir olunca, fake_tracking_data() fonksiyonu
Sercan'in gercek bounding box verisiyle degistirilecek.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import math
from connection import connect
from flight_manager import set_mode, arm, takeoff, send_velocity_command
from pid_controller import TrackingController
from pymavlink import mavutil


def fake_tracking_data(t):
    """Sahte hedef: goruntude sinuzoidal hareket eden bir nokta."""
    x = 320 + 100 * math.sin(t)
    y = 240 + 50 * math.cos(t * 0.7)
    return x, y


if __name__ == "__main__":
    master = connect()

    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')

    if not arm(master):
        print("Arm basarisiz, cikiliyor.")
        sys.exit(1)

    takeoff(master, altitude=5)
    print("Kalkis sonrasi 8 saniye stabilize olmasi icin bekleniyor...")
    time.sleep(8)

    controller = TrackingController(cam_width=640, cam_height=480,
                                     Kp=0.005, Ki=0.0, Kd=0.001, max_velocity=1.5)

    print("Sahte hedef takibi basliyor (15 saniye)...")
    start = time.time()
    while time.time() - start < 15:
        t = time.time() - start
        target_x, target_y = fake_tracking_data(t)

        vy, vz = controller.compute(target_x, target_y)

        # Ileri hiz sabit dusuk tutuluyor (takip sirasinda), asil hareket vy/vz'de
        send_velocity_command(master, vx=0.3, vy=vy, vz=vz)

        msg = master.recv_match(type='LOCAL_POSITION_NED', blocking=False)
        if msg:
            print(f"t:{t:.1f}s hedef:({target_x:.0f},{target_y:.0f}) -> vy:{vy:.2f} vz:{vz:.2f} | konum x:{msg.x:.2f} y:{msg.y:.2f} z:{msg.z:.2f}")

        time.sleep(0.2)

    print("Test tamamlandi. Inis yapiliyor...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
    )
