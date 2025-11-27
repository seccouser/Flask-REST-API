# Installationsanleitung — hdmi-in-display (Armbian / Rock 5B)

Diese Anleitung beschreibt, wie du auf einem frischen Armbian-System (z. B. Rock 5B) alle nötigen Pakete installierst, das Projekt baust, Tests ausführst und das Programm als systemd-Service laufen lässt.

Hinweis: Rock 5B nutzt eine RK3588-Plattform mit Mali/GPU. Hardware-Beschleunigung (OpenGL ES / Mali-Treiber) ist auf Armbian je nach Image / Kernel unterschiedlich verfügbar. Wenn du proprietäre Mali-Treiber oder alternative OpenGL-Treiber brauchst, lies die Armbian-Dokumentation zu deinem Board/Kernel.

Inhalt
- Voraussetzungen
- Paketinstallation (APT)
- Benutzer-/Geräteberechtigungen
- Repository klonen & bauen
- Testen der V4L2-Quelle
- Optional: systemd-Service
- Troubleshooting / Hinweise

---

## Voraussetzungen
- Armbian (Debian/Ubuntu-basiert) installiert auf Rock 5B
- Internetzugang zum Installieren von Paketen
- Ein Benutzer mit sudo-Rechten (z. B. `seccouser`)

---

## Paketinstallation (empfohlen)
Führe die folgenden Befehle als Benutzer mit sudo-Rechten aus:

1) Paketlisten aktualisieren:
```bash
sudo apt update
sudo apt upgrade -y
```

2) Grundlegende Build-Tools, Multimedia- und Grafik-Bibliotheken installieren:
```bash
sudo apt install -y \
  build-essential cmake git pkg-config \
  libv4l-dev v4l-utils \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libsdl2-dev libglew-dev libgl1-mesa-dev libegl1-mesa-dev libgles2-mesa-dev \
  libx11-dev libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev \
  libdrm-dev libudev-dev
```

Erläuterung:
- libv4l-dev / v4l-utils: Zugriff auf V4L2-Geräte (Webcams, HDMI-Capture-Devices).
- libav* (FFmpeg-Dev): falls das Projekt FFmpeg-Bibliotheken nutzt.
- libsdl2-dev, libglew-dev, Mesa/EGL/GLES: für OpenGL / SDL2-Fenster und Shader.
- libdrm/libudev: niedrige Ebene für Grafik/Device-Handling.

Falls Abhängigkeiten fehlen, zeigt CMake beim Konfigurieren Fehlermeldungen — die in der Anleitung unten behandelt werden.

---

## GPU / Treiberhinweis (Rock 5B)
Auf Rock 5B (RK3588) wird eine Mali-GPU verwendet. Armbian kann entweder:
- Open-source Treiber (Mesa + panfrost) verwenden, oder
- proprietäre RK/Mali-Treiber benötigen.

Wenn du hardware-beschleunigte OpenGL ES benötigst, stelle sicher, dass dein Armbian-Image die richtige GPU-Unterstützung hat. Falls du Probleme mit OpenGL-Initialisierung hast, prüfe:
- `glxinfo` (falls installiert) oder dmesg/logs
- Armbian- und Board-Foren für RK3588/Mali-Treiber

---

## Benutzer- und Geräteberechtigungen
Damit du auf Video-/DRM-Geräte zugreifen kannst, füge den Benutzer zur Video- und ggf. render-Gruppe hinzu:
```bash
sudo usermod -aG video,render "$USER"
# entweder neu einloggen oder:
newgrp video
```
Prüfe, ob /dev/video0 bzw. /dev/dri/* existieren und welche Gruppenrechte gesetzt sind:
```bash
ls -l /dev/video* /dev/dri/*
```

---

## Repository klonen & bauen
Wechsle in ein Arbeitsverzeichnis, klone das Repo und baue das Projekt:

1) Klonen:
```bash
git clone git@github.com:seccouser/hdmi-in-display.git
# oder HTTPS:
# git clone https://github.com/seccouser/hdmi-in-display.git
cd hdmi-in-display
```

2) Empfohlene CMake-Build-Variante (Out-of-source build):
```bash
# Erstelle Build-Ordner
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
# Alternativ wenn CMakeLists oder Abhängigkeiten spezielle Flags brauchen:
# cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DOTHER_OPTION=ON

# Kompilieren
cmake --build build -j"$(nproc)"
```

3) Install (optional, falls Projekt ein `install` target bereitstellt):
```bash
sudo cmake --install build
```

Erwartetes Ergebnis: Binärdatei(en) liegen unter `build/`, z. B. `build/hdmi_simple_display`. Wenn CMake Fehler über fehlende Bibliotheken oder Header meldet, installiere die fehlenden dev-Pakete und wiederhole Schritt 2.

---

## Programm starten / testen
Allgemein:
```bash
# Beispiel — passe Pfade/Device-Optionen an, je nach Programm-CLI
./build/hdmi_simple_display --device /dev/video0
```

Testen des V4L2-Geräts mit ffplay (schnell prüfen, ob Input anliegt):
```bash
sudo apt install -y ffmpeg
ffplay -f v4l2 -framerate 30 -video_size 1280x720 /dev/video0
```

oder mit v4l2-ctl die Formate anzeigen:
```bash
v4l2-ctl --list-formats-ext -d /dev/video0
```

Falls dein Programm zusätzliche CLI-Optionen anbietet, starte `./build/hdmi_simple_display --help` oder sieh in README.md nach.

---

## Optional: systemd-Service einrichten (Autostart)
Erzeuge eine Service-Datei `/etc/systemd/system/hdmi-in-display.service` (als root):

```ini
[Unit]
Description=HDMI In Display
After=network.target

[Service]
User=seccouser
Group=video
WorkingDirectory=/home/seccouser/hdmi-in-display
ExecStart=/home/seccouser/hdmi-in-display/build/hdmi_simple_display --device /dev/video0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Anschließend aktivieren und starten:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hdmi-in-display.service
sudo systemctl start hdmi-in-display.service
sudo journalctl -u hdmi-in-display.service -f
```

Passe `User`, `WorkingDirectory` und `ExecStart` an deine Pfade und Optionen an.

---

## Weitere nützliche Tools/Tests
- `v4l2-ctl` (siehe oben)
- `ffplay` / `ffmpeg` für Debugging
- `gst-launch-1.0` (GStreamer) falls du Pipeline-Tests machen möchtest:
  ```bash
  sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
  gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink
  ```

---

## Troubleshooting — häufige Probleme
- OpenGL initialisiert nicht / GLSL Shader-Fehler:
  - Prüfe ob Mesa-EGL/GLES oder proprietäre Mali-Treiber korrekt installiert sind.
  - Starte ein simples GL-Testprogramm oder `es2info` / `glxinfo`.
- Keine / falsche Berechtigungen für `/dev/video0`:
  - Prüfe `ls -l /dev/video0` und Gruppenzugehörigkeit.
  - Füge Benutzer zur `video`-Gruppe und re-login.
- CMake findet Bibliotheken nicht:
  - Fehlende `-dev` Pakete installieren und CMake Cache neu generieren:
    ```bash
    rm -rf build && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    ```
- Capture-Gerät liefert kein Bild:
  - Teste mit `ffplay` oder `v4l2-ctl` ob das Gerät Frames liefert.
  - Prüfe Verkabelung und dass das HDMI-Capture-Device vom Kernel unterstützt wird.
