"""
Gercek Pixhawk baglandiginda, hangi USB/UART portunda oldugunu bulmaya yarar.
Donanim gelince ilk calistirilacak script budur.

NOT: WSL, USB cihazlarini otomatik gormeyebilir cunku sanallastirma katmanidir.
Eger hicbir port bulunmazsa, Windows tarafinda 'usbipd' araci kurulup
Pixhawk'in WSL'e "bagli" (attached) hale getirilmesi gerekebilir.
"""
import subprocess

print("Bagli seri portlar araniyor...\n")

try:
    result = subprocess.run(['ls', '-la', '/dev/'], capture_output=True, text=True)
    lines = result.stdout.split('\n')
    tty_lines = [l for l in lines if 'ttyUSB' in l or 'ttyACM' in l or 'ttyAMA' in l]

    if tty_lines:
        print("Bulunan olasi Pixhawk portlari:")
        for line in tty_lines:
            print(" ", line)
        print("\nBu portlardan birini connection.py'deki 'connect()' fonksiyonuna")
        print("gerceklestirmek icin kullanacaksin. Ornek:")
        print("  connect('/dev/ttyUSB0', baud=921600)")
    else:
        print("Hicbir seri port bulunamadi.")
        print("Kontrol et: Pixhawk USB ile bagli mi? WSL, USB cihazlarini")
        print("otomatik gormeyebilir -- 'usbipd' araci gerekebilir (WSL2 icin).")
except Exception as e:
    print(f"Hata: {e}")
