"""
SITL / Pixhawk baglanti modulu.
pymavlink baglantisini kurmak icin tek merkezi yer.

KTR: "Jetson Orin Nano'da calisan Python yazilimi, pymavlink kutuphanesiyle
Pixhawk 6C Mini'ye UART hattindan baglanmaktadir. Baud hizi 921600."
"""

from pymavlink import mavutil

SITL_TCP = "tcp:127.0.0.1:5760"
PIXHAWK_BAUD = 921600            # KTR: gecikmeyi dusuk tutmak icin


def connect(address: str = SITL_TCP, baud: int = PIXHAWK_BAUD,
            timeout: float = 15.0):
    """
    SITL veya gercek Pixhawk'a baglan, heartbeat bekle.

    address ornekleri:
        SITL:     "tcp:127.0.0.1:5760"
        Pixhawk:  "/dev/ttyTHS1"  veya  "COM5"
    """
    print(f"Baglaniliyor: {address}")

    if address.startswith(("tcp:", "udp:", "udpin:", "udpout:")):
        master = mavutil.mavlink_connection(address)
    else:
        master = mavutil.mavlink_connection(address, baud=baud)

    hb = master.wait_heartbeat(timeout=timeout)
    if hb is None:
        raise TimeoutError(f"Heartbeat alinamadi ({timeout} sn): {address}")

    print(f"Heartbeat alindi. Sistem: {master.target_system}, "
          f"Bilesen: {master.target_component}")
    return master


def send_gcs_heartbeat(master):
    """
    Jetson -> FC heartbeat. KTR'deki GCS Failsafe tasarimi
    (FS_GCS_ENABLE=1) bizim tarafin FC'ye duzenli heartbeat
    gondermesini gerektirir; pymavlink bunu otomatik YAPMAZ.
    ~1 Hz cagrilmali, yoksa FC baglantiyi kopmus sayar ve LAND'e gecer.
    """
    master.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)


def wait_ready(master, timeout: float = 30.0) -> bool:
    """
    Pre-arm kontrolleri gecene kadar bekle.
    SYS_STATUS.onboard_control_sensors_health icindeki PREARM bitine
    bakar (ArduPilot tum pre-arm kontrolleri gecince set eder).
    Beklerken GCS heartbeat gondermeye devam eder.
    """
    import time
    prearm_bit = getattr(mavutil.mavlink,
                         "MAV_SYS_STATUS_PREARM_CHECK", 0x10000000)
    t0 = time.time()
    last_hb = 0.0
    while time.time() - t0 < timeout:
        if time.time() - last_hb > 1.0:
            send_gcs_heartbeat(master)
            last_hb = time.time()
        msg = master.recv_match(type="SYS_STATUS", blocking=True, timeout=2)
        if msg and (msg.onboard_control_sensors_health & prearm_bit):
            print("Pre-arm kontrolleri gecildi.")
            return True
    return False