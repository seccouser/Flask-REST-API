# Flask-REST-API

Eine Flask-basierte REST-API für Dateiübertragungen mit Hash-Verifizierung und Tastatur-Emulation.

## Features

- 📤 **Datei-Upload** mit automatischer SHA256-Hash-Berechnung
- 🔐 **Hash-Verifizierung** zur Sicherstellung der Dateiintegrität
- 📥 **Datei-Download** mit Hash-Header
- ⌨️ **Tastatur-Emulation** zur Steuerung anderer Prozesse (Linux uinput/evdev)
- 📋 **Dateiliste** mit Metadaten
- 🔧 **Cross-Origin Resource Sharing (CORS)** Support
- 🪵 **Umfassendes Logging**

## Systemanforderungen

- Python 3.8+
- Linux-Betriebssystem (für Tastatur-Emulation)
- Root-Rechte oder input-Gruppe-Mitgliedschaft (für Tastatur-Emulation)
- Kompatibel mit Radxa Rock 5b und Armbian Linux Kernel

## Installation

### Option 1: Automatische Installation (empfohlen)

```bash
# Als root oder mit sudo
sudo bash install.sh
```

Das Skript erstellt automatisch eine virtuelle Umgebung und installiert alle Abhängigkeiten.

### Option 2: Manuelle Installation

1. Repository klonen:
```bash
git clone https://github.com/seccouser/Flask-REST-API.git
cd Flask-REST-API
```

2. Virtuelle Umgebung erstellen (empfohlen für Python 3.11+):
```bash
# Python 3.11+ benötigt eine virtuelle Umgebung
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

**Alternative (nicht empfohlen):** Systemweite Installation auf älteren Systemen:
```bash
# Nur auf Python < 3.11 oder mit --break-system-packages (nicht empfohlen)
pip install -r requirements.txt
```

3. Für Tastatur-Emulation (optional, benötigt Root-Rechte):
```bash
# Benutzer zur input-Gruppe hinzufügen
sudo usermod -a -G input $USER

# Neuanmeldung erforderlich, oder:
sudo chmod 666 /dev/uinput
```

## Verwendung

### Server starten

```bash
# Mit virtueller Umgebung (empfohlen)
source venv/bin/activate
python app.py

# Oder direkt aus der virtuellen Umgebung
./venv/bin/python app.py

# Mit benutzerdefinierten Einstellungen
FLASK_HOST=0.0.0.0 FLASK_PORT=8080 FLASK_DEBUG=True ./venv/bin/python app.py

# Für Produktion mit gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

# Mit benutzerdefinierten Einstellungen
FLASK_HOST=0.0.0.0 FLASK_PORT=8080 FLASK_DEBUG=True python app.py

# Für Produktion mit gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## API-Endpunkte

### 1. API-Informationen
```
GET /
```

Gibt Informationen über verfügbare Endpunkte zurück.

**Beispiel:**
```bash
curl http://localhost:5000/
```

### 2. Health Check
```
GET /health
```

Überprüft den Server-Status.

**Beispiel:**
```bash
curl http://localhost:5000/health
```

### 3. Datei hochladen
```
POST /upload
```

Lädt eine Datei hoch und berechnet deren Hash.

**Parameter:**
- `file` (required): Die hochzuladende Datei
- `hash` (optional): Erwarteter Hash-Wert zur Verifizierung
- `algorithm` (optional): Hash-Algorithmus (default: sha256)

**Beispiele:**
```bash
# Einfacher Upload
curl -X POST -F "file=@dokument.pdf" http://localhost:5000/upload

# Upload mit Hash-Verifizierung
curl -X POST \
  -F "file=@dokument.pdf" \
  -F "hash=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
  http://localhost:5000/upload

# Upload mit anderem Hash-Algorithmus
curl -X POST \
  -F "file=@dokument.pdf" \
  -F "algorithm=md5" \
  http://localhost:5000/upload
```

**Response:**
```json
{
  "message": "File uploaded successfully",
  "filename": "dokument.pdf",
  "size": 12345,
  "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "algorithm": "sha256",
  "hash_verified": true
}
```

### 4. Datei herunterladen
```
GET /download/<filename>
```

Lädt eine hochgeladene Datei herunter.

**Beispiel:**
```bash
curl -O http://localhost:5000/download/dokument.pdf

# Hash aus Response-Header extrahieren
curl -I http://localhost:5000/download/dokument.pdf | grep X-File-Hash
```

**Response Header:**
- `X-File-Hash`: SHA256-Hash der Datei
- `X-Hash-Algorithm`: Verwendeter Hash-Algorithmus

### 5. Dateien auflisten
```
GET /files
```

Listet alle hochgeladenen Dateien mit Metadaten.

**Beispiel:**
```bash
curl http://localhost:5000/files
```

**Response:**
```json
{
  "count": 2,
  "files": [
    {
      "filename": "dokument.pdf",
      "size": 12345,
      "modified": 1700000000.0,
      "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  ]
}
```

### 6. Tastatur-Eingabe
```
POST /keyboard
```

Emuliert Tastatur-Eingaben zur Steuerung anderer Prozesse.

**JSON-Parameter:**
- `text` (optional): Text zum Tippen
- `keys` (optional): Liste von Tasten-Codes (z.B., ["KEY_ENTER", "KEY_TAB"])
- `delay` (optional): Verzögerung zwischen Tasten in Sekunden (default: 0.1)

**Beispiele:**
```bash
# Text tippen
curl -X POST http://localhost:5000/keyboard \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'

# Spezielle Tasten senden
curl -X POST http://localhost:5000/keyboard \
  -H "Content-Type: application/json" \
  -d '{"keys": ["KEY_ENTER", "KEY_TAB"]}'

# Kombination aus Text und Tasten
curl -X POST http://localhost:5000/keyboard \
  -H "Content-Type: application/json" \
  -d '{"text": "ls -la", "keys": ["KEY_ENTER"], "delay": 0.05}'

# Tastenkombination für Strg+C
curl -X POST http://localhost:5000/keyboard \
  -H "Content-Type: application/json" \
  -d '{"keys": ["KEY_LEFTCTRL", "KEY_C"]}'
```

**Unterstützte Tasten:**
Alle Standard-Linux-Tastencodes aus dem evdev-Modul, z.B.:
- Buchstaben: `KEY_A` bis `KEY_Z`
- Zahlen: `KEY_0` bis `KEY_9`
- Funktionstasten: `KEY_F1` bis `KEY_F12`
- Modifikatoren: `KEY_LEFTSHIFT`, `KEY_LEFTCTRL`, `KEY_LEFTALT`
- Navigation: `KEY_UP`, `KEY_DOWN`, `KEY_LEFT`, `KEY_RIGHT`
- Sonstige: `KEY_ENTER`, `KEY_TAB`, `KEY_SPACE`, `KEY_BACKSPACE`, `KEY_ESC`

### 7. Prozess starten
```
POST /process/start
```

Startet einen Prozess und überprüft optional, ob er bereits läuft.

**JSON-Parameter:**
- `command` (erforderlich): Befehl als String oder Array (z.B., "firefox" oder ["python3", "script.py"])
- `check_running` (optional): Überprüfen, ob bereits läuft (default: true)
- `cwd` (optional): Arbeitsverzeichnis für den Prozess
- `env` (optional): Umgebungsvariablen als Dictionary

**Beispiele:**
```bash
# Einfacher Befehl
curl -X POST http://localhost:5000/process/start \
  -H "Content-Type: application/json" \
  -d '{"command": "firefox"}'

# Befehl mit Argumenten
curl -X POST http://localhost:5000/process/start \
  -H "Content-Type: application/json" \
  -d '{"command": ["python3", "/path/to/script.py", "--arg1"]}'

# Mit Arbeitsverzeichnis
curl -X POST http://localhost:5000/process/start \
  -H "Content-Type: application/json" \
  -d '{"command": "npm start", "cwd": "/home/user/myapp"}'

# Prozess immer neu starten (ignoriert laufende Instanz)
curl -X POST http://localhost:5000/process/start \
  -H "Content-Type: application/json" \
  -d '{"command": "gedit", "check_running": false}'
```

**Response:**
```json
{
  "status": "started",
  "pid": 12345,
  "process": "firefox",
  "command": "firefox",
  "message": "Process started successfully with PID 12345"
}
```

Wenn Prozess bereits läuft:
```json
{
  "status": "already_running",
  "pid": 12340,
  "process": "firefox",
  "message": "Process is already running with PID 12340"
}
```

**Hinweise für GUI-Anwendungen:**
- GUI-Anwendungen werden automatisch mit der korrekten DISPLAY-Variable gestartet
- Die Prozesse laufen unabhängig vom API-Server (detached)
- Ausgaben werden nicht erfasst, um Zombie-Prozesse zu vermeiden
- Prozesse überleben den API-Server-Neustart und laufen weiter

### 8. Prozess stoppen
```
POST /process/stop
```

Stoppt einen laufenden Prozess.

**JSON-Parameter:**
- `process` (erforderlich): Prozessname

**Beispiel:**
```bash
curl -X POST http://localhost:5000/process/stop \
  -H "Content-Type: application/json" \
  -d '{"process": "firefox"}'
```

**Response:**
```json
{
  "status": "stopped",
  "pid": 12345,
  "process": "firefox",
  "message": "Process stopped successfully (PID 12345)"
}
```

### 9. Prozess-Status abfragen
```
GET /process/status/<process_name>
```

Gibt den Status eines Prozesses zurück.

**Beispiel:**
```bash
curl http://localhost:5000/process/status/firefox
```

**Response:**
```json
{
  "running": true,
  "process": "firefox",
  "pid": 12345,
  "status": "running",
  "cpu_percent": 5.2,
  "memory_mb": 450.5,
  "create_time": 1700000000.0
}
```

### 10. Verwaltete Prozesse auflisten
```
GET /process/list
```

Listet alle vom API verwalteten Prozesse.

**Beispiel:**
```bash
curl http://localhost:5000/process/list
```

**Response:**
```json
{
  "count": 2,
  "processes": [
    {
      "running": true,
      "process": "firefox",
      "pid": 12345,
      "status": "running",
      "cpu_percent": 5.2,
      "memory_mb": 450.5,
      "create_time": 1700000000.0
    },
    {
      "running": true,
      "process": "gedit",
      "pid": 12346,
      "status": "running",
      "cpu_percent": 0.5,
      "memory_mb": 50.2,
      "create_time": 1700000100.0
    }
  ]
}
```

### 11. System neu starten
```
POST /system/reboot
```

Startet das System neu. Erfordert dass der Flask-Service als root oder mit sudo-Berechtigung läuft.

**Request Body:**
```json
{
  "delay": 0
}
```

- `delay` (optional): Verzögerung in Sekunden vor dem Neustart (Standard: 0 = sofort)

**Beispiel (sofortiger Neustart):**
```bash
curl -X POST http://localhost:5000/system/reboot \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Beispiel (Neustart mit 60 Sekunden Verzögerung):**
```bash
curl -X POST http://localhost:5000/system/reboot \
  -H "Content-Type: application/json" \
  -d '{"delay": 60}'
```

**Response:**
```json
{
  "message": "System reboot initiated",
  "delay_seconds": 0
}
```

**Hinweis:** Die API wird nach dem Neustart-Befehl noch eine Response zurückgeben, aber die Verbindung wird kurz danach unterbrochen wenn das System herunterfährt.

## Python-Client-Beispiel

```python
import requests
import hashlib

# Datei hochladen mit Hash-Verifizierung
def upload_file_with_hash(filepath, server_url="http://localhost:5000"):
    # Hash berechnen
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    file_hash = sha256_hash.hexdigest()
    
    # Datei hochladen
    with open(filepath, 'rb') as f:
        files = {'file': f}
        data = {'hash': file_hash}
        response = requests.post(f"{server_url}/upload", files=files, data=data)
    
    return response.json()

# Datei herunterladen und Hash verifizieren
def download_and_verify(filename, server_url="http://localhost:5000"):
    response = requests.get(f"{server_url}/download/{filename}")
    
    if response.status_code == 200:
        # Hash aus Header
        expected_hash = response.headers.get('X-File-Hash')
        
        # Hash der heruntergeladenen Datei berechnen
        sha256_hash = hashlib.sha256()
        sha256_hash.update(response.content)
        actual_hash = sha256_hash.hexdigest()
        
        # Verifizieren
        if expected_hash == actual_hash:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True, "Hash verified"
        else:
            return False, "Hash mismatch"
    
    return False, f"Error: {response.status_code}"

# Tastatur-Eingabe senden
def send_keyboard_input(text=None, keys=None, server_url="http://localhost:5000"):
    data = {}
    if text:
        data['text'] = text
    if keys:
        data['keys'] = keys
    
    response = requests.post(f"{server_url}/keyboard", json=data)
    return response.json()

# Beispiel-Verwendung
if __name__ == "__main__":
    # Upload
    result = upload_file_with_hash("test.txt")
    print(f"Upload: {result}")
    
    # Download
    success, msg = download_and_verify("test.txt")
    print(f"Download: {msg}")
    
    # Keyboard
    result = send_keyboard_input(text="echo 'Hello from API'", keys=["KEY_ENTER"])
    print(f"Keyboard: {result}")
```

## Sicherheitshinweise

⚠️ **Wichtig:**

1. **Authentifizierung:** Diese API hat keine eingebaute Authentifizierung. Für den Produktionseinsatz sollte eine Authentifizierung implementiert werden (z.B., JWT, API-Keys).

2. **Tastatur-Emulation:** Die Tastatur-Emulation erfordert erhöhte Berechtigungen und sollte nur in vertrauenswürdigen Umgebungen verwendet werden.

3. **Dateigröße:** Die maximale Dateigröße ist auf 100 MB begrenzt. Dies kann in `app.py` angepasst werden.

4. **HTTPS:** Für den Produktionseinsatz sollte HTTPS verwendet werden.

5. **Firewall:** Stellen Sie sicher, dass nur vertrauenswürdige Clients Zugriff auf die API haben.

## Fehlerbehebung

### Tastatur-Emulation funktioniert nicht

```bash
# Prüfen Sie /dev/uinput Berechtigungen
ls -l /dev/uinput

# Berechtigung temporär erteilen
sudo chmod 666 /dev/uinput

# Dauerhaft: Benutzer zur input-Gruppe hinzufügen
sudo usermod -a -G input $USER
# Neuanmeldung erforderlich
```

### Import-Fehler: evdev nicht gefunden

```bash
# evdev installieren
pip install evdev

# Auf Armbian/Debian
sudo apt-get install python3-evdev
```

## Entwicklung

### Logging

Logs werden auf stdout ausgegeben. Logging-Level kann angepasst werden in `app.py`:

```python
logging.basicConfig(level=logging.DEBUG)  # Für detaillierte Logs
```

### Tests

```bash
# Tests lokal ausführen (benötigt pytest)
pip install pytest requests
pytest tests/
```

## Lizenz

MIT License - siehe LICENSE-Datei für Details.

## Mitwirkende

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder öffnen Sie ein Issue.

## Support

Bei Fragen oder Problemen öffnen Sie bitte ein Issue auf GitHub.