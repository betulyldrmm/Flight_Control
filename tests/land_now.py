import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from connection import connect
from pymavlink import mavutil

master = connect()
print("LAND komutu gonderiliyor...")
master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
)
print("Gonderildi. Harita penceresinden inisi izleyebilirsin.")
