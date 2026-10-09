cd C:\Users\HP\Flight_Control

@'
# Flight Control — TEKNOFEST FPV Drone Tracking

## Proje Hakkında

Bu proje, TEKNOFEST FPV Drone İzleme Yarışması kapsamında geliştirilen ArduPilot tabanlı uçuş kontrol ve görüntü işleme yazılımıdır.

Proje kapsamında GNSS kullanılmayan görsel takip senaryoları için nesne tespiti, hedef takibi, PID tabanlı kontrol, MAVLink haberleşmesi ve uçuş güvenliği bileşenleri ele alınmıştır.

Yazılım; görüntü işleme, uçuş kontrol, haberleşme ve test bileşenlerini birbirinden ayıran modüler bir mimariye sahiptir. Geliştirme ve doğrulama çalışmalarında ArduPilot SITL ortamından yararlanılmaktadır.

## Kullanılan Teknolojiler

| Alan | Teknoloji |
|---|---|
| Programlama | Python |
| Uçuş kontrol | ArduPilot, Pixhawk 6C |
| Haberleşme | MAVLink, pymavlink, UDP |
| Kontrol algoritmaları | PID |
| Görüntü işleme | OpenCV, YOLO, HSV |
| Hedef takibi | KCF, Kalman filtresi |
| Simülasyon | ArduPilot SITL |
| Test | Python test betikleri |

## Sistem Mimarisi

Sistem, görüntü işleme ve uçuş kontrol olmak üzere iki temel yazılım katmanından oluşmaktadır.

Görüntü işleme katmanında kamera veya video görüntülerinden hedef tespiti ve takibi gerçekleştirilir. Elde edilen takip bilgileri UDP üzerinden uçuş kontrol katmanına aktarılabilecek şekilde yapılandırılmıştır.

Uçuş kontrol katmanında takip verileri işlenerek kontrol algoritmalarına giriş sağlanır. MAVLink üzerinden ArduPilot SITL veya uygun uçuş kontrol donanımıyla haberleşme gerçekleştirilir.

```text
                 KAMERA / VİDEO
                       |
                       v
              GÖRÜNTÜ İŞLEME
                       |
              +----------------+
              | Nesne Tespiti  |
              |  YOLO / HSV    |
              +----------------+
                       |
                       v
              +----------------+
              | Hedef Takibi   |
              | KCF / Kalman   |
              +----------------+
                       |
                       v
              Takip Verilerinin
                Oluşturulması
                       |
                       v
                UDP Haberleşme
                       |
                       v
                 UÇUŞ KONTROL
                       |
              +----------------+
              | Veri İşleme    |
              | PID Kontrol    |
              +----------------+
                       |
                       v
                MAVLink Komutları
                       |
                       v
              ArduPilot / Pixhawk