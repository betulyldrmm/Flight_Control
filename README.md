# Flight Control - TEKNOFEST FPV Dron Izleme Yarismasi

ArduPilot (Pixhawk 6C) tabanli, GPS'siz otonom ucus kontrol sistemi.

## Moduller
- connection.py - SITL/Pixhawk baglanti yonetimi
- flight_manager.py - Mod gecisi, arm, kalkis islemleri
- main.py - Ana calistirma dosyasi

## Gereksinimler
pip install pymavlink

## Kullanim
SITL calisirken: python3 src/main.py
