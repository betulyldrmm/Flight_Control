"""
KTR raporuna tam uyumlu uctan uca sistem testi:
SET_ATTITUDE_TARGET + Tablo 4 PID + GCS Failsafe (Land modu).
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time, math
from connection import connect
from flight_manager import set_mode, arm, takeoff, send_attitude_target
from pid_controller import TrackingController
from failsafe import FailsafeMonitor


def fake_bbox(t):
    cx = 320 + 100 * math.sin(t)
    cy = 240 + 50 * math.cos(t * 0.7)
    w, h = 80, 60
    return cx - w/2, cy - h/2, w, h


if __name__ == "__main__":
    master = connect()
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')
    if not arm(master):
        sys.exit(1)

    takeoff(master, altitude=5)
    time.sleep(8)

    # KTR'deki GCS Failsafe mantigi: heartbeat kesilirse LAND
    monitor = FailsafeMonitor(master, timeout_seconds=3)
    monitor.start()

    controller = TrackingController(cam_width=640, cam_height=480, reference_area=4800)

    print("Tam sistem testi basliyor (15 sn): PID + failsafe aktif...")
    start = time.time()
    while time.time() - start < 15:
        if monitor.failsafe_triggered:
            print("FAILSAFE tetiklendi, dongu durduruluyor.")
            break

        t = time.time() - start
        x, y, w, h = fake_bbox(t)
        roll_rate, pitch_rate, yaw_rate, thrust_adj = controller.compute(x, y, w, h)
        thrust = max(0.0, min(1.0, 0.5 + thrust_adj))

        send_attitude_target(master, roll_rate, pitch_rate, yaw_rate, thrust)
        monitor.reset_timer()  # her basarili komut gonderiminde heartbeat sayacini tazele

        time.sleep(0.1)

    monitor.stop()
    print("Test tamamlandi.")

    print("Guvenlik icin inis komutu gonderiliyor...")
    from pymavlink import mavutil
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
    )
