# Uçuş Kontrol Yazılımı — Test Planı

Saha gününe kadar aşamalar: masa başı → SITL → bench (donanım, pervanesiz) → uçuş.
Bir aşama geçilmeden sonrakine geçme. Her aşamada log dosyasını sakla.

---

## Aşama 0 — Masa başı (bugün, donanımsız)

```
pytest                                        # tüm birim testler (test_search.py dahil)
python -m src.main --source fake --duration 20
```

Kontrol et:
- [ ] 12-15. saniyede hedef kaybı: önce `coasting`, sonra `searching` görünmeli
- [ ] logs/ altındaki CSV'de `searching` kolonu var, rate raporu "YETERLI"
- [ ] `python -m src.main --source stdin` ile bozuk JSON'da çökmeme

## Aşama 1 — SITL (donanımsız, saha gününden ÖNCE evde bitmeli)

```
sim_vehicle.py -v ArduCopter -f quad --console   # ArduPilot SITL
python -m src.main --source fake --target sitl --duration 60
```

Doğrulanacaklar (kritik bilinmeyenler):
- [ ] **Rate kontrolü**: GUIDED_NOGPS'te type_mask=0b10000000 ile body-rate
      komutlarına araç gerçekten tepki veriyor mu? (`tests/sitl_attitude_check.py`)
- [ ] **Thrust semantiği**: 0.5 = irtifa koru mu? 0.70 ile tırmanma hızı ne?
      Kalkışta hedef irtifada duruyor mu (yeni kapalı çevrim kalkış)?
- [ ] **GUID_TIMEOUT**: komut akışı kesilince aracın davranışı (varsayılan 3 sn)

Failsafe senaryoları (SITL'de üçü de denenecek):
- [ ] FS_GCS_ENABLE=1 iken script'i öldür (kill -9) → FC kendi kendine LAND'e geçmeli
- [ ] UDP kaynağını kes → DATA_TIMEOUT → hover → 5 sn sonra LAND
- [ ] Hedefi kaybettir (fake 12-15 sn) → coasting → arama (yavaş yaw) → geri yakalama
- [ ] 15 sn'den uzun hedef kaybı → LAND

## Aşama 2 — Bench: Jetson + Pixhawk, PERVANESİZ

- [ ] `tests/find_pixhawk_port.py` → port doğrula (/dev/ttyTHS1)
- [ ] SERIALx_BAUD=921 (921600), SERIALx_PROTOCOL=2 (MAVLink2)
- [ ] Heartbeat iki yönlü: bizden FC'ye gidiyor mu? (Mission Planner'da GCS sayısı)
- [ ] Sercan'ın gerçek tracking modülüyle UDP entegrasyonu — gerçek JSON formatı
      `tracking_interface.from_dict` ile uyumlu mu? (alan adları, birimler!)
- [ ] Pervanesiz arm + komut: Mission Planner motor çıkışlarında yaw komutuna tepki
- [ ] Jetson CPU/ısı yükü altında döngü hızı ≥ 20 Hz kalıyor mu? (KTR'de FPS sorunu notu var)

ArduPilot parametreleri (uçuştan önce kontrol listesi):
| Parametre | Değer | Amaç |
|---|---|---|
| FS_GCS_ENABLE | 1 | Jetson heartbeat kesilince LAND |
| BATT_FS_LOW_ACT | 2 (LAND) | Batarya failsafe |
| FS_THR_ENABLE | 1 | RC kumanda failsafe |
| GUID_TIMEOUT | 3 | Komut akışı kesilme davranışı |
| ANGLE_MAX | 3000-4500 | Açı sınırı (agresiflik) |
| LAND_SPEED | 50-70 | İniş hızı cm/s |

## Aşama 3 — Uçuş günü (kademeli!)

1. **Manuel uçuş** (pilot, STABILIZE/ALT_HOLD): titreşim, trim, batarya sağlığı.
2. **Yerde takip provası**: drone yerde, `--target none`, Sercan'ın kamerasıyla
   hedef gezdir → PID çıkışları mantıklı mı? (hedef sağda → yaw_cmd pozitif)
3. **Düşük irtifa otonom** (2-3 m, açık alan): kalkış + hover + LAND.
   Pilot eli kumandada — mod anahtarıyla her an STABILIZE'a geçebilmeli.
4. **Hedef takip denemesi**: yürüyen kişi/ikinci drone ile. Önce sadece yaw
   takibi izle, sonra tam takip.

Emniyet kuralları:
- Pilot her testte kumandayla hazır; mod anahtarı STABILIZE/LAND'e atanmış olmalı
- İlk otonom denemede takip mesafesi 4 m yerine 6-8 m (çarpışma payı)
- Her uçuş sonrası CSV log + FC dataflash logu birlikte arşivle

## Rapor düzeltmeleri (unutma!)

- [ ] KTR Tablo 5: type_mask **0b00000111 yanlış** → doğrusu 0b10000000
      (bitler "yoksay" anlamında). Kodda düzeltildi, ÖTR/SunumRaporu'na işlenecek.
- [ ] Kamera kararı: `main.py`'de CAM_720P_40 geçici. 4 m takipte 70° bile yetiyor
      (maks 4.3 m), ama 6-8 m takip istenirse 40-50° şart. Takım kararı → rapora.

## Bilinen açık konular

- Arama modu yalnızca yaw taraması yapar; 4. manevradaki 50 m dikey tırmanışta
  hedef yukarı kaçarsa bulamayabilir (pitch taraması yok — bilinçli tercih, riskli).
- `wait_ready` pre-arm bitine bakar; GPS'siz konfigürasyonda bazı kontroller
  kapatılmış olmalı (ARMING_CHECK), yoksa hep uyarı verir.
- Loglama formatı komiteden gelecek ek dokümanla değişebilir — CSV kolonları
  tek yerden (logger.HEADER) yönetiliyor, uyarlaması kolay.
