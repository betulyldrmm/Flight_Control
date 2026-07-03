"""
Failsafe'in GERCEKTEN tetiklendigini kanitlayan test.
Bağlantıyı bilerek "koparıyoruz" (heartbeat okumayi durduruyoruz),
sistemin gercekten LAND komutu gonderip gondermedigini goruyoruz.
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

    # 3 saniye timeout ile baslat
    monitor = FailsafeMonitor(master, timeout_seconds=3)
    monitor.start()

    print("\nHicbir 'reset_timer' cagrisi YAPILMAYACAK.")
    print("Bu, gercek bir sinyal kaybini simule eder.")
    print("3 saniye sonra failsafe'in kendiliginden tetiklenmesini bekliyoruz...\n")

    for i in range(10):
        time.sleep(1)
        print(f"{i+1}. saniye | failsafe_triggered: {monitor.failsafe_triggered}")
        if monitor.failsafe_triggered:
            print(">>> FAILSAFE TETIKLENDI! LAND komutu gonderildi. <<<")
            break

    monitor.stop()
    print(f"\nSonuc: failsafe_triggered = {monitor.failsafe_triggered}")
