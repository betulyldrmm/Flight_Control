"""
SET_ATTITUDE_TARGET'i quaternion (mutlak aci) ile test eder.
ArduCopter GUIDED_NOGPS'te rate yerine hedef aci bekliyor olabilir.
"""

import sys, os, math, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connection import connect
from src import flight_manager as fm


def euler_to_quat(roll, pitch, yaw):
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    return [
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ]


def yaw_deg(master):
    att = fm.get_attitude(master, timeout=2)
    return math.degrees(att[2]) if att else None


def send_quat(master, roll, pitch, yaw, thrust=0.5, mask=0b00000111):
    """mask = 7: rate'leri yoksay, quaternion'u kullan."""
    master.mav.set_attitude_target_send(
        0, master.target_system, master.target_component,
        mask, euler_to_quat(roll, pitch, yaw),
        0, 0, 0, thrust)


def hold(master, seconds, thrust=0.5):
    t0 = time.time()
    while time.time() - t0 < seconds:
        fm.send_attitude_target(master, thrust=thrust)
        time.sleep(0.05)


def goto_yaw(master, target_deg, duration=5.0, thrust=0.5):
    y0 = yaw_deg(master)
    tgt = math.radians(target_deg)
    t0 = time.time()
    while time.time() - t0 < duration:
        send_quat(master, 0, 0, tgt, thrust)
        time.sleep(0.05)
    y1 = yaw_deg(master)
    print(f"  hedef {target_deg:>4} deg  ->  olculen {y1:+7.1f} deg  "
          f"(baslangic {y0:+.1f})")
    return y1


def main():
    master = connect("tcp:127.0.0.1:5760")
    fm.request_streams(master, rate_hz=10)
    time.sleep(1)

    fm.set_mode(master, "GUIDED_NOGPS")
    if not fm.arm(master):
        return

    print("\nYukseliyor...")
    hold(master, 6.0, thrust=0.70)
    print(f"Irtifa: {fm.get_altitude(master):.1f} m")
    print(f"Baslangic yaw: {yaw_deg(master):.1f} deg\n")

    print("Quaternion ile mutlak yaw hedefi (mask=0b00000111):")
    for target in (45, 90, 180, 0):
        goto_yaw(master, target)
        hold(master, 1.0)

    print("\nIniyor...")
    fm.land(master)


if __name__ == "__main__":
    main()