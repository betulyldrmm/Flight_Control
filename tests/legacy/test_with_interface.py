"""
Arayuz (TrackingData) uzerinden calisan test.
Sercan'in gercek modulu hazir oldugunda, sadece 
fake_tracking_source() cagrisi onun gercek fonksiyonuyla degisecek.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
from connection import connect
from flight_manager import set_mode, arm, takeoff, send_attitude_target
from pid_controller import TrackingController
from failsafe import FailsafeMonitor
from tracking_interface import fake_tracking_source
from pymavlink import mavutil

if __name__ == "__main__":
    master = connect()
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')
    if not arm(master):
        sys.exit(1)

    takeoff(master, altitude=5)
    time.sleep(8)

    monitor = FailsafeMonitor(master, timeout_seconds=3)
    monitor.start()

    controller = TrackingController(cam_width=640, cam_height=480, reference_area=4800)

    print("Arayuz uzerinden takip basliyor (15 sn)...")
    start = time.time()
    while time.time() - start < 15:
        if monitor.failsafe_triggered:
            print("FAILSAFE tetiklendi.")
            break

        t = time.time() - start
        # --- BURASI ILERIDE Sercan'in gercek fonksiyonuyla degisecek ---
        tracking_data = fake_tracking_source(t)
        # ------------------------------------------------------------

        if not tracking_data.is_valid():
            print(f"t:{t:.1f}s | Hedef gecerli degil, durum: {tracking_data.durum}")
            time.sleep(0.1)
            continue

        roll_rate, pitch_rate, yaw_rate, thrust_adj = controller.compute(
            tracking_data.x, tracking_data.y, tracking_data.w, tracking_data.h
        )
        thrust = max(0.0, min(1.0, 0.5 + thrust_adj))
        send_attitude_target(master, roll_rate, pitch_rate, yaw_rate, thrust)
        monitor.reset_timer()

        print(f"t:{t:.1f}s guven:{tracking_data.guven_skoru} -> roll:{roll_rate:.2f} pitch:{pitch_rate:.2f} yaw:{yaw_rate:.2f}")
        time.sleep(0.1)

    monitor.stop()
    print("Guvenlik icin inis komutu gonderiliyor...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
    )
