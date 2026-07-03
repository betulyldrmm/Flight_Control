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

def send_velocity_command(master, vx, vy, vz):
    """
    Body-frame velocity komutu gonder.
    vx: ileri/geri (m/s)
    vy: sag/sol (m/s)
    vz: asagi/yukari (m/s) -- NOT: pozitif z = asagi (NED koordinat sistemi)
    
    Bu fonksiyon, PID kontrolcunun ciktisini gercekten drone'a iletecek yer.
    """
    master.mav.set_position_target_local_ned_send(
        0,
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
        0b0000111111000111,  # sadece velocity kullan
        0, 0, 0,
        vx, vy, vz,
        0, 0, 0,
        0, 0
    )

def send_attitude_target(master, roll_rate, pitch_rate, yaw_rate, thrust=0.5):
    """
    KTR raporuna uygun SET_ATTITUDE_TARGET komutu gonderir.
    type_mask = 0b00000111 -> roll_rate, pitch_rate, yaw_rate aktif, quaternion yok saylir.
    
    roll_rate, pitch_rate, yaw_rate: rad/s cinsinden aci hizlari (PID ciktisi)
    thrust: 0.0 - 1.0 arasi normalize itki degeri
    """
    master.mav.set_attitude_target_send(
        0,                                  # time_boot_ms (otomatik)
        master.target_system,
        master.target_component,
        0b00000111,                        # type_mask: sadece rate'ler aktif
        [1, 0, 0, 0],                       # quaternion (kullanilmiyor, dummy deger)
        roll_rate,
        pitch_rate,
        yaw_rate,
        thrust
    )
