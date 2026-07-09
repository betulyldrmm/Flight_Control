"""
SITL'de SET_ATTITUDE_TARGET bit maskesini dogrular.

Beklenen: yaw_rate komutu gonderilince aracin yaw acisi degisir.
KTR'deki type_mask = 0b00000111 ile hicbir sey olmamalidir (tum rate'ler
yoksayilir); dogru maske 0b10000000 ile arac donmelidir.
"""

import sys, os, math, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymavlink import mavutil
from src.connection import connect
from src import flight_manager as fm


def yaw_deg(master):
    att = fm.get_attitude(master, timeout=2)
    return math.degrees(att[2]) if att else None


def test_mask(master, mask: int, label: str, duration: float = 4.0):
    """Verilen maske ile yaw_rate gonder, aci degisimini olc."""
    y0 = yaw_deg(master)
    t0 = time.time()
    while time.time() - t0 < duration:
        master.mav.set_attitude_target_send(
            0, master.target_system, master.target_component,
            mask, [1, 0, 0, 0],
            0.0, 0.0, math.radians(45.0), 0.5,   # 45 deg/s yaw
        )
        time.sleep(0.05)
    y1 = yaw_deg(master)

    delta = (y1 - y0 + 180) % 360 - 180
    print(f"{label:<28} maske=0b{mask:08b}  yaw degisimi: {delta:+7.1f} derece")
    return abs(delta)

def main():
    master = connect("tcp:127.0.0.1:5760")
    fm.request_streams(master, rate_hz=10)
    time.sleep(1)

    # SITL varsayilan olarak sinirli mesaj yayinlar; tum akisi ac
    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    time.sleep(1)

    print("\nMod: GUIDED_NOGPS")
    fm.set_mode(master, "GUIDED_NOGPS")

    if not fm.arm(master):
        print("Arm edilemedi. SITL pre-arm kontrollerini bekle veya "
              "ARMING_CHECK=0 ayarla.")
        return

    # Havalan
    print("Yukseliyor...")
    t0 = time.time()
    last_print = 0.0
    while time.time() - t0 < 8.0:
        fm.send_attitude_target(master, thrust=0.75)
        time.sleep(0.05)
        if time.time() - t0 - last_print > 2.0:
            last_print = time.time() - t0
            a = fm.get_altitude(master, timeout=0.2)
            print(f"  irtifa: {a:.2f} m" if a is not None else "  irtifa: yok")

    alt = fm.get_altitude(master)
    print(f"Irtifa: {alt:.1f} m\n" if alt is not None else "Irtifa: okunamadi\n")

    alt = fm.get_altitude(master)
    print(f"Irtifa: {alt:.1f} m\n" if alt is not None else "Irtifa: okunamadi\n")

    d_ktr = test_mask(master, 0b00000111, "KTR Tablo 5 (0b00000111)")
    time.sleep(1)
    d_fix = test_mask(master, 0b10000000, "Duzeltilmis (0b10000000)")

    print()
    if d_fix > 20 and d_ktr < 5:
        print("SONUC: KTR'deki maske rate'leri yoksayiyor. Duzeltilmis maske dogru.")
    else:
        print(f"SONUC belirsiz. KTR: {d_ktr:.1f} deg, duzeltilmis: {d_fix:.1f} deg")

    print("\nIniyor...")
    fm.land(master)
    
if __name__ == "__main__":
      main()