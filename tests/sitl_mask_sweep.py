"""
SET_ATTITUDE_TARGET type_mask degerlerini SITL'de tarar.
Amac: hangi maskenin gercekten yaw_rate komutunu isledigini olcmek.
"""

import sys, os, math, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymavlink import mavutil
from src.connection import connect
from src import flight_manager as fm

YAW_RATE = math.radians(180.0)   # 45 -> 180 derece/s
DURATION = 4.0

MASKS = [
    (0b00000111, "KTR Tablo 5"),
    (0b00000011, "roll+pitch rate yoksay"),
    (0b10000011, "quat + roll+pitch yoksay"),
]


def yaw_deg(master):
    att = fm.get_attitude(master, timeout=2)
    return math.degrees(att[2]) if att else None


def hold_altitude(master, seconds: float, thrust: float = 0.55):
    t0 = time.time()
    while time.time() - t0 < seconds:
        fm.send_attitude_target(master, thrust=thrust)
        time.sleep(0.05)


def test_mask(master, mask: int, label: str):
    y0 = yaw_deg(master)
    t0 = time.time()
    while time.time() - t0 < DURATION:
        master.mav.set_attitude_target_send(
            0, master.target_system, master.target_component,
            mask, [1, 0, 0, 0],
            0.0, 0.0, YAW_RATE, 0.55,
        )
        time.sleep(0.05)
    y1 = yaw_deg(master)
    delta = (y1 - y0 + 180) % 360 - 180
    alt = fm.get_altitude(master, timeout=1)
    print(f"  0b{mask:08b}  yaw {delta:+7.1f} deg   irtifa {alt:5.1f} m   {label}")
    return abs(delta)


def main():
    master = connect("tcp:127.0.0.1:5760")
    fm.request_streams(master, rate_hz=10)
    time.sleep(1)

    fm.set_mode(master, "GUIDED_NOGPS")
    if not fm.arm(master):
        return

    print("\nYukseliyor...")
    hold_altitude(master, 6.0, thrust=0.70)
    print(f"Irtifa: {fm.get_altitude(master):.1f} m")
    print(f"Beklenen yaw degisimi: {math.degrees(YAW_RATE) * DURATION:.0f} derece\n")

    for mask, label in MASKS:
        test_mask(master, mask, label)
        hold_altitude(master, 1.5)   # yaw'i durdur, irtifayi koru

    print("\nIniyor...")
    fm.land(master)


if __name__ == "__main__":
    main()