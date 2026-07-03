# Flight Control - TEKNOFEST FPV Dron Izleme Yarismasi

ArduPilot (Pixhawk 6C) tabanli, GPS'siz otonom ucus kontrol sistemi.
KTR raporuna uygun mimari: SET_ATTITUDE_TARGET + Tablo 4 PID katsayilari.

## Moduller (src/)
- connection.py - SITL/Pixhawk baglanti yonetimi
- flight_manager.py - Mod gecisi, arm, kalkis, SET_ATTITUDE_TARGET komutlari
- pid_controller.py - KTR Tablo 4'e uygun 4 eksenli PID (Yaw/Pitch/Roll/Throttle)
- failsafe.py - Python-tarafi heartbeat izleme (yardimci katman)

## Guncel Testler (tests/)
- test_ktr_tracking.py - KTR uyumlu uctan uca takip testi
- test_full_system.py - PID + failsafe birlesik tam sistem testi (EN GUNCEL)
- test_failsafe_disconnect.py - Gercek baglanti kopmasi testi (kanitlanmis)
- set_gcs_failsafe.py - ArduPilot'un kendi FS_GCS_ENABLE parametresini ayarlar (KRITIK)
- land_now.py - Acil durumda hizli inis icin yardimci script

## Eski/Denemeler (tests/legacy/)
Gelistirme surecinde yazilan, artik kullanilmayan ama referans icin saklanan dosyalar.

## Onemli Bulgu
Python-tarafi FailsafeMonitor tek basina yeterli degildir. Asil guvenlik ArduPilot'un 
kendi GCS Failsafe parametresinde (FS_GCS_ENABLE) olmalidir - bu ayarlanmis ve 
dogrulanmistir.

## Gereksinimler
pip install pymavlink

## Kullanim
SITL calisirken:
python3 tests/test_full_system.py
