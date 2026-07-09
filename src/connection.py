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


def wait_ready(master, timeout: float = 30.0) -> bool:
    """EKF ve pre-arm kontrolleri tamamlanana kadar bekle."""
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        msg = master.recv_match(type="SYS_STATUS", blocking=True, timeout=2)
        if msg:
            return True
    return False