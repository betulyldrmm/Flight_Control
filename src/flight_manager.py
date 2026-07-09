"""
Mod gecisi, arm etme, kalkis ve SET_ATTITUDE_TARGET komutlari.

BIT MASKESI HAKKINDA ONEMLI NOT:
  MAVLink SET_ATTITUDE_TARGET'ta type_mask bitleri, hangi alanin
  YOKSAYILACAGINI belirtir (ignore flag), aktif olacagini degil.

      bit 0 (1)   : body_roll_rate  yoksay
      bit 1 (2)   : body_pitch_rate yoksay
      bit 2 (4)   : body_yaw_rate   yoksay
      bit 6 (64)  : thrust          yoksay
      bit 7 (128) : attitude (quaternion) yoksay

  KTR Raporu Tablo 5'te type_mask = 0b00000111 yazilmis ve "rate'ler
  aktif, quaternion devre disi" diye aciklanmis. Bu YANLIS: 0b00000111
  uc rate'i de yoksaydirir.

  Dogrusu: rate kontrolu icin type_mask = 0b10000000 (yalnizca
  quaternion yoksayilir, rate'ler ve thrust islenir).

OLCEKLEME:
  PID cikislari normalize [-0.5, 0.5] araligindadir. MAVLink rad/s bekler.
  Thrust ise [0, 1] araligindadir; hover ~0.5 kabul edilip PID throttle
  ciktisi bunun uzerine eklenir.
"""

import math
import time
from pymavlink import mavutil

# Rate olcekleme: normalize cikis -> rad/s
MAX_ROLL_RATE = math.radians(90.0)    # rad/s
MAX_PITCH_RATE = math.radians(90.0)
MAX_YAW_RATE = math.radians(120.0)

HOVER_THRUST = 0.5                    # itki/agirlik ~4.1 icin kaba baslangic
THRUST_MIN, THRUST_MAX = 0.20, 0.80   # guvenlik siniri

# Rate kontrolu: yalnizca quaternion yoksayilir
TYPE_MASK_RATES_ONLY = 0b10000000


def set_mode(master, mode_name: str, timeout: float = 5.0) -> bool:
    """Verilen moda gec ve gecisi dogrula (orn. GUIDED, GUIDED_NOGPS)."""
    mapping = master.mode_mapping()
    if mode_name not in mapping:
        raise ValueError(f"Bilinmeyen mod: {mode_name}. "
                         f"Mevcut: {sorted(mapping)}")

    mode_id = mapping[mode_name]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
    )

    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and hb.custom_mode == mode_id:
            print(f"Mod: {mode_name}")
            return True
    print(f"Mod degisimi dogrulanamadi: {mode_name}")
    return False


def arm(master, timeout: float = 5.0) -> bool:
    """Araci arm et, HEARTBEAT ile dogrula."""
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )

    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("Arm edildi.")
            return True
    print("Arm dogrulanamadi.")
    return False


def disarm(master):
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 0, 0, 0, 0, 0, 0, 0,
    )
    print("Disarm komutu gonderildi.")


def takeoff(master, altitude: float = 5.0):
    """Belirtilen irtifaya kalkis komutu gonder."""
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, altitude,
    )
    print(f"Kalkis komutu: {altitude} m")


def land(master):
    set_mode(master, "LAND")


def send_attitude_target(master,
                         roll_rate: float = 0.0,
                         pitch_rate: float = 0.0,
                         yaw_rate: float = 0.0,
                         thrust: float = HOVER_THRUST):
    """
    Ham SET_ATTITUDE_TARGET gonderir.
    roll_rate, pitch_rate, yaw_rate: rad/s
    thrust: [0, 1]
    """
    thrust = max(THRUST_MIN, min(THRUST_MAX, thrust))
    master.mav.set_attitude_target_send(
        0,                              # time_boot_ms
        master.target_system,
        master.target_component,
        TYPE_MASK_RATES_ONLY,
        [1, 0, 0, 0],                   # quaternion (yoksayiliyor)
        roll_rate,
        pitch_rate,
        yaw_rate,
        thrust,
    )


def send_control_output(master, out):
    """
    PID kontrolcusunun ControlOutput nesnesini SET_ATTITUDE_TARGET'a cevirir.

    out.roll, out.pitch  : normalize [-0.3, 0.4]
    out.yaw_rate         : normalize [-0.5, 0.5]
    out.throttle         : normalize [-0.3, 0.3], hover uzerine eklenir
    """
    send_attitude_target(
        master,
        roll_rate=(out.roll / 0.3) * MAX_ROLL_RATE,
        pitch_rate=(out.pitch / 0.4) * MAX_PITCH_RATE,
        yaw_rate=(out.yaw_rate / 0.5) * MAX_YAW_RATE,
        thrust=HOVER_THRUST + out.throttle,
    )


def get_attitude(master, timeout: float = 1.0):
    """Aracin anlik yonelimi (roll, pitch, yaw) - radyan."""
    msg = master.recv_match(type="ATTITUDE", blocking=True, timeout=timeout)
    if msg is None:
        return None
    return (msg.roll, msg.pitch, msg.yaw)


def get_altitude(master, timeout: float = 1.0):
    """Irtifa (metre, yukari pozitif). Once LOCAL_POSITION_NED, sonra GLOBAL."""
    msg = master.recv_match(type="LOCAL_POSITION_NED",
                            blocking=True, timeout=timeout)
    if msg:
        return -msg.z

    msg = master.recv_match(type="GLOBAL_POSITION_INT",
                            blocking=True, timeout=timeout)
    if msg:
        return msg.relative_alt / 1000.0
    return None


def request_streams(master, rate_hz: int = 10):
    """
    SITL/Pixhawk varsayilan olarak sinirli telemetri yayinlar.
    ATTITUDE ve LOCAL_POSITION_NED akislarini acar.
    """
    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, rate_hz, 1)

    # Yeni protokol (MAVLink 2) icin mesaj bazli istek
    for msg_id in (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
                   mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED,
                   mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT):
        master.mav.command_long_send(
            master.target_system, master.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0, msg_id, int(1e6 / rate_hz), 0, 0, 0, 0, 0)