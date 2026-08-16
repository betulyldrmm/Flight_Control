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

from src.connection import send_gcs_heartbeat

# Rate olcekleme: normalize cikis -> rad/s
MAX_ROLL_RATE = math.radians(90.0)    # rad/s
MAX_PITCH_RATE = math.radians(90.0)
MAX_YAW_RATE = math.radians(120.0)

HOVER_THRUST = 0.5                    # itki/agirlik ~4.1 icin kaba baslangic
THRUST_MIN, THRUST_MAX = 0.20, 0.80   # guvenlik siniri

# Rate kontrolu: yalnizca quaternion yoksayilir
TYPE_MASK_RATES_ONLY = 0b10000000

# --- K1: EKSEN ESLEMESI (SITL'de DOGRULANACAK) --------------------------
# Cok rotorlu + ileri bakan kamera fizigi:
#   mesafe kontrolu  (area_error -> out.throttle) -> ileri/geri = PITCH
#   dikey ortalama   (y_error    -> out.pitch)    -> yukari/asagi = THRUST
# Bu, sim_loop.cmd_to_accel'in kullandigi DOGRU fiziksel eslemedir.
# Onceki kod pitch<->throttle kanallarini ters bagliyordu: out.throttle
# thrust'a (dikey), out.pitch pitch_rate'e (ileri) gidiyordu. Sim bu yuzden
# geciyor ama gercek dronda mesafe kontrolu irtifayi surerdi (yukari flyaway).
#
# ISARETLER: asagidaki sabitler ilk mantikli tahmindir; SITL'de tek eksen
# test edip (sitl_attitude_check.py mantigi) gerekirse -1.0 <-> +1.0 cevir.
#   area_error>0 (hedef uzak)     -> ileri git  -> burun asagi = NEGATIF pitch rate
#   y_error<0    (hedef yukarida) -> tirman      -> thrust ARTAR
PITCH_CMD_SIGN = -1.0     # area_error -> pitch_rate isareti
THRUST_CMD_SIGN = -1.0    # y_error (out.pitch) -> thrust isareti
THRUST_AUTHORITY = 0.3    # out.pitch [-0.4,0.4] -> +-0.3 thrust yetkisi


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

def arm(master, timeout: float = 8.0) -> bool:
    """Araci arm et. COMMAND_ACK ve HEARTBEAT ile dogrula."""
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )

    ack = master.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    if ack and ack.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        if ack.result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            print(f"Arm reddedildi (result={ack.result})")
            return False

    # HEARTBEAT ile dogrula
    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("Arm edildi.")
            return True

    print("Arm dogrulanamadi (ACK geldi ama heartbeat teyit etmedi).")
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


def wait_landed(master, timeout: float = 90.0) -> bool:
    """
    LAND komutu sonrasi inisi izler: disarm gorulene kadar bekler.
    Bu sirada GCS heartbeat gondermeye devam eder (FS_GCS_ENABLE=5
    varken inis ortasinda ikinci bir failsafe tetiklenmesin diye).
    """
    print("Inis izleniyor...")
    t0 = time.time()
    last_hb = 0.0
    last_alt_print = 0.0

    while time.time() - t0 < timeout:
        now = time.time()
        if now - last_hb > 1.0:
            send_gcs_heartbeat(master)
            last_hb = now

        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and not (hb.base_mode &
                       mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("Inis tamamlandi (disarm).")
            return True

        if now - last_alt_print > 2.0:
            alt = get_altitude(master, timeout=0.2)
            if alt is not None:
                print(f"  inis... irtifa {alt:.1f} m")
            last_alt_print = now

    print(f"UYARI: {timeout:.0f} sn icinde disarm gorulmedi.")
    return False


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


def send_control_output(master, out, hover: float = None):
    """
    ControlOutput -> SET_ATTITUDE_TARGET.

    EKSEN ESLEMESI (K1 - SITL'de dogrula, yukaridaki sabitlere bak):
      out.yaw_rate (x_error)   -> yaw_rate    : yatay ortalama
      out.throttle (area_err)  -> pitch_rate  : ileri/geri  -> MESAFE
      out.pitch    (y_error)   -> thrust      : yukari/asagi -> DIKEY ortalama
      out.roll     (yaw kupla) -> roll_rate   : koordineli donus

    NOT: Isim benzerligine ragmen pitch<->throttle kanallarinin FIZIKSEL
    karsiligi mesafe<->dikeydir (bkz. sim_loop.cmd_to_accel). hover None ise
    modul HOVER_THRUST'i kullanilir; bench'te MOT_THST_HOVER'a hizala (K2).
    """
    h = HOVER_THRUST if hover is None else hover
    send_attitude_target(
        master,
        roll_rate=(out.roll / 0.3) * MAX_ROLL_RATE,
        pitch_rate=PITCH_CMD_SIGN * (out.throttle / 0.3) * MAX_PITCH_RATE,
        yaw_rate=(out.yaw_rate / 0.5) * MAX_YAW_RATE,
        thrust=h + THRUST_CMD_SIGN * (out.pitch / 0.4) * THRUST_AUTHORITY,
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


def read_param(master, name: str, timeout: float = 3.0):
    """Tek bir FC parametresini oku (yoksa None)."""
    master.mav.param_request_read_send(
        master.target_system, master.target_component,
        name.encode("utf-8"), -1)
    msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=timeout)
    return msg.param_value if msg else None


def read_hover_thrust(master):
    """
    FC'nin ogrendigi hover gazini (MOT_THST_HOVER) okur ve yazdirir.
    HOVER_THRUST bu degere hizalanmali (K2). TWR ~4.1 icin ~0.20-0.30 beklenir;
    0.5 gercekte tirmanis demek olabilir.
    """
    v = read_param(master, "MOT_THST_HOVER")
    if v is not None:
        print(f"MOT_THST_HOVER = {v:.3f}  ->  HOVER_THRUST'i buna gore ayarla "
              f"(--hover {v:.2f}); modul varsayilani {HOVER_THRUST}")
    else:
        print("MOT_THST_HOVER okunamadi.")
    return v


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