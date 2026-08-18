"""
vision/ — Goruntu isleme ve hedef takip modulu (Sercan tarafi).

Ucus kontrol (src/) ile UYUMLU calisir:
  - Cikti UDP JSON formati: src/tracking_interface.TrackingData.from_dict
  - Goruntu/kayit formati:   src/resmi_kayit (tespit_kaydi.csv + bindirme)

Boru hatti:  kamera -> tespit (YOLO/renk) -> takip (KCF+Kalman)
             -> hata/kutu -> UDP (ucus kontrole) + diske kayit
"""
