"""
Mod gecisi, arm etme ve kalkis komutlarini yoneten modul.
"""
from pymavlink import mavutil
import time

def set_mode(master, mode_name):
    """Verilen moda gec (orn. GUIDED, GUIDED_NOGPS)."""
    mode_id = master.mode_mapping()[mode_name]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    time.sleep(1)
    print(f"Mod değiştirildi: {mode_name}")

def arm(master):
    """Aracı arm et, sonucu dogrula."""
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0
    )
    ack = master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
    hb = master.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"Arm ACK: {ack}, Armlı mı: {armed}")
    return armed

def takeoff(master, altitude=5):
    """Belirtilen irtifaya kalkis yap."""
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, altitude
    )
    print(f"Kalkış komutu gönderildi: {altitude}m")

def monitor_altitude(master, duration=15):
    """Belirtilen sure boyunca irtifayi izle ve yazdir."""
    for i in range(duration * 2):
        msg = master.recv_match(type='LOCAL_POSITION_NED', blocking=True, timeout=2)
        if msg:
            print(f"z: {msg.z:.2f}")
        time.sleep(0.5)
