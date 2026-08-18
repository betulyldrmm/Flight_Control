"""
Goruntu isleme boru hattini calistirir (Sercan tarafi).

Ornekler:
  # Donanimsiz test (sahte kamera + renk tespiti), ucus koduna baglanir:
  python -m vision.run --source fake --duration 30

  # Gercek webcam + YOLO modeli:
  python -m vision.run --source webcam --model runs/best.pt

  # Kayitli video uzerinde:
  python -m vision.run --source video --video test.mp4 --model runs/best.pt

Ucus kontrol tarafini ayni anda calistir:
  python -m src.main --source socket --target none   (ya da --target sitl)
"""

import argparse

from vision.config import VisionConfig
from vision.pipeline import VisionPipeline


def main():
    p = argparse.ArgumentParser(description="FPV Drone Izleme - Goruntu Isleme")
    p.add_argument("--source", choices=["fake", "webcam", "video"], default="fake")
    p.add_argument("--video", default=None, help="video dosya yolu (--source video)")
    p.add_argument("--webcam", type=int, default=0, help="webcam indeksi")
    p.add_argument("--model", default=None,
                   help="YOLO .pt yolu; verilmezse renk tespiti (test)")
    p.add_argument("--conf", type=float, default=0.35, help="YOLO min guven")
    p.add_argument("--udp-host", default="127.0.0.1")
    p.add_argument("--udp-port", type=int, default=5005,
                   help="ucus kontrolun dinledigi port (src/main.py ile ayni)")
    p.add_argument("--no-save", action="store_true", help="goruntu kaydini kapat")
    p.add_argument("--save-dir", default="teslim")
    p.add_argument("--lock-frames", type=int, default=5)
    p.add_argument("--duration", type=float, default=None, help="saniye")
    args = p.parse_args()

    cfg = VisionConfig(
        source=args.source,
        video_path=args.video,
        webcam_index=args.webcam,
        model_path=args.model,
        conf_threshold=args.conf,
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        save_images=not args.no_save,
        save_dir=args.save_dir,
        lock_frames=args.lock_frames,
    )
    VisionPipeline(cfg).run(duration=args.duration)


if __name__ == "__main__":
    main()
