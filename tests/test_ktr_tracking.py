"""
KTR raporuna uygun uctan uca test: SET_ATTITUDE_TARGET + Tablo 4 PID degerleri.
Sahte bounding box verisiyle (x, y, w, h formati) test edilir.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time, math
from connection import connect
from flight_manager import set_mode, arm, takeoff, send_attitude_target
from pid_controller import TrackingController


def fake_bbox(t):
    """Sahte bounding box: hareket eden x,y merkez + sabit boyut."""
    cx = 320 + 100 * math.sin(t)
    cy = 240 + 50 * math.cos(t * 0.7)
    w, h = 80, 60
    x = cx - w / 2
    y = cy - h / 2
    return x, y, w, h


if __name__ == "__main__":
    master = connect()
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')
    if not arm(master):
        print("Arm basarisiz.")
        sys.exit(1)

    takeoff(master, altitude=5)
    time.sleep(8)

    controller = TrackingController(cam_width=640, cam_height=480, reference_area=4800)

    print("KTR'ye uygun SET_ATTITUDE_TARGET ile takip basliyor (15 sn)...")
    start = time.time()
    while time.time() - start < 15:
        t = time.time() - start
        x, y, w, h = fake_bbox(t)

        roll_rate, pitch_rate, yaw_rate, thrust_adj = controller.compute(x, y, w, h)
        base_thrust = 0.5  # KTR: "throttle icin sabit referans deger tanimlanmis"
        thrust = max(0.0, min(1.0, base_thrust + thrust_adj))

        send_attitude_target(master, roll_rate, pitch_rate, yaw_rate, thrust)

        print(f"t:{t:.1f}s bbox:({x:.0f},{y:.0f},{w},{h}) -> roll:{roll_rate:.3f} pitch:{pitch_rate:.3f} yaw:{yaw_rate:.3f} thrust:{thrust:.3f}")
        time.sleep(0.1)

    print("Test tamamlandi. Inis yapiliyor...")
    from pymavlink import mavutil
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
    )
