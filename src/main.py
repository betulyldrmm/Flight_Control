"""
Ana calistirma dosyasi - butun modulleri birlestirir.
"""
from connection import connect
from flight_manager import set_mode, arm, takeoff, monitor_altitude
import time

if __name__ == "__main__":
    master = connect()
    
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)
    
    set_mode(master, 'GUIDED')
    
    if arm(master):
        takeoff(master, altitude=5)
        monitor_altitude(master, duration=10)
    else:
        print("Arm basarisiz oldu.")
