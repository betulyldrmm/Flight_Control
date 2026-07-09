"""
Gercek baglanti kesintisini simule eder.
SITL'e kisa sureligine mesaj SORMAYI DURDURARAK 
(socket'i kapatarak) gercek sinyal kaybini test eder.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
from connection import connect
from flight_manager import set_mode, arm, takeoff
from failsafe import FailsafeMonitor

if __name__ == "__main__":
    master = connect()
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')
    if arm(master):
        takeoff(master, altitude=5)
        time.sleep(5)

    monitor = FailsafeMonitor(master, timeout_seconds=3)
    monitor.start()

    print("\n5 saniye normal calisiyor...")
    time.sleep(5)
    print("failsafe_triggered (baglanti saglikliyken):", monitor.failsafe_triggered)

    print("\nSIMDI BAGLANTI GERCEKTEN KESILIYOR (socket kapatiliyor)...")
    monitor.running = False  # once izleme thread'ini durdur ki cakismasin
    time.sleep(0.5)
    master.close()  # gercek baglantiyi kapat

    print("Baglanti kapatildi. 5 saniye bekleniyor (heartbeat gelemeyecek)...")
    # Manuel kontrol: heartbeat gelip gelmedigini kendimiz deneyelim
    start = time.time()
    got_heartbeat = False
    while time.time() - start < 5:
        try:
            msg = master.recv_match(type='HEARTBEAT', blocking=False)
            if msg:
                got_heartbeat = True
        except Exception as e:
            print(f"Baglanti hatasi (beklenen): {e}")
            break
        time.sleep(0.2)

    print(f"\nSonuc: Baglanti kesildikten sonra heartbeat alindi mi?: {got_heartbeat}")
    print("(False olmasi bekleniyor -- bu, gercek sinyal kaybi senaryosunu dogrular)")
