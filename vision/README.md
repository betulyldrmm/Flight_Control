# vision/ — Görüntü İşleme ve Hedef Takip (Sercan tarafı)

Uçuş kontrol koduyla (`src/`) **birebir uyumlu** çalışan görüntü işleme modülü.

## Ne yapar

```
kamera → tespit (YOLO / renk) → takip (KCF + Kalman)
       → hata kutusu → UDP ile uçuş kontrole  +  diske bindirmeli kayıt
```

- **Tespit:** YOLO modeli verilirse onu kullanır; verilmezse renk (HSV) tespiti (hem yedek hem test için).
- **Takip:** KCF ile kareler arası hızlı takip; kayıpta Kalman tahmini. (KCF yoksa her karede tespit + Kalman — çökmeden çalışır.)
- **Kilitlenme:** `lock_frames` kadar kesintisiz tespit görmeden "TAKIP" demez.
- **Çıktı:** Uçuş kontrole UDP (`127.0.0.1:5005`) + `teslim/` klasörüne resmi kayıt (bindirmeli görüntü + `tespit_kaydi.csv`).

## Uyumluluk (kritik)

- **UDP formatı** = `src/tracking_interface.TrackingData.from_dict` (alan adları: `durum`, `bbox{x,y,w,h}`, `guven_skoru`, `timestamp`, `frame_id`). Değiştirme.
- **Port** = uçuş kontrolün dinlediği port. `src/main.py --source socket` varsayılanı **5005**. İkisi aynı olmalı.
- **Kayıt** = `src/resmi_kayit.py` kullanır → `tests/paket_dogrula.py` ile doğrulanır (test edildi, "Format GEÇERLİ").

## Çalıştırma

Donanımsız test (sahte kamera + renk tespiti):
```
python -m vision.run --source fake --duration 30
```

Gerçek webcam + YOLO modeli:
```
python -m vision.run --source webcam --model yol/best.pt
```

Kayıtlı video üzerinde:
```
python -m vision.run --source video --video test.mp4 --model yol/best.pt
```

Uçuş kontrol tarafını **ayrı bir terminalde** aynı anda çalıştır:
```
python -m src.main --source socket --target none      # sadece PID çıktısı
python -m src.main --source socket --target sitl       # SITL'de uçur
```

## Sercan'ın yapması gereken tek şey: YOLO modelini takmak

Modül hazır; Sercan sadece eğittiği modeli `--model` ile verir:
```
python -m vision.run --source webcam --model runs/detect/train/weights/best.pt
```
Renk tespiti yerine YOLO otomatik devreye girer. Model sınıf filtresi gerekirse
`vision/config.py` → `target_class`.

## Ayarlar (vision/config.py)

| Ayar | Ne | Varsayılan |
|---|---|---|
| `udp_port` | Uçuş kontrol portu | 5005 |
| `frame_w/h` | Kare boyutu | 1280×720 |
| `model_path` | YOLO .pt | None (renk) |
| `conf_threshold` | YOLO min güven | 0.35 |
| `hsv_lower/upper` | Renk tespiti aralığı (sarı hedef) | — |
| `lock_frames` | Kilitlenme için kare | 5 |
| `redetect_every` | KCF sürerken tespitle tazeleme | 20 |
| `save_dir` | Teslim klasörü | teslim/ |

## Bağımlılıklar

`opencv-python` (KCF için `opencv-contrib-python`), `numpy`, tespit için `ultralytics` (YOLO). Hepsi `requirements.txt`'te.

## Notlar

- **KCF** yalnızca `opencv-contrib-python` ile gelir. Yoksa modül çökmez; her karede tespit + Kalman'a düşer. Jetson'da contrib kuruluysa KCF otomatik açılır.
- **5 Hz şartı:** Her kareyi diske kaydetmek yavaştır; loglama hızı 5/sn altına düşerse `save_ext="jpg"` (küçük dosya) yeterli, gerekirse Jetson'da donanım hızlandırma. Kayıt hızını `teslim` doğrulamasıyla kontrol et.
- `teslim/` klasörü bir çalıştırmanın çıktısıdır; git'e eklemene gerek yok.
