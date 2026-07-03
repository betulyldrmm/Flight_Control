"""
SITL / Pixhawk baglanti modulu.
Bu modul, pymavlink baglantisini kurmak icin tek merkezi yer olacak.
"""
from pymavlink import mavutil

def connect(address='udp:127.0.0.1:14551'):
    """SITL veya gercek Pixhawk'a baglan, heartbeat bekle."""
    print(f"Bağlanılıyor: {address}")
    master = mavutil.mavlink_connection(address)
    master.wait_heartbeat()
    print(f"Heartbeat alındı! Sistem: {master.target_system}")
    return master
