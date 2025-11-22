# Flask REST API - Zusammenfassung

## Übersicht

Diese Flask-basierte REST-API wurde speziell für den Radxa Rock 5b mit Armbian Linux entwickelt und bietet folgende Hauptfunktionen:

### ✅ Implementierte Features

1. **Dateiübertragung mit Hash-Verifizierung**
   - Upload von Dateien beliebiger Größe (konfigurierbar, Standard: 100 MB)
   - Automatische SHA256-Hash-Berechnung bei jedem Upload
   - Optional: Hash-Verifizierung beim Upload zur Integritätsprüfung
   - Download mit Hash-Information in Response-Headern
   - Auflistung aller hochgeladenen Dateien mit Metadaten

2. **Tastatur-Emulation**
   - Linux uinput/evdev-basierte Tastatur-Emulation
   - Unterstützung für Text-Eingabe
   - Unterstützung für spezielle Tasten (F-Keys, Pfeiltasten, Modifikatoren, etc.)
   - Konfigurierbare Verzögerung zwischen Tastendrücken
   - Ermöglicht Steuerung anderer Prozesse über die API

3. **Weitere Features**
   - RESTful API mit JSON-Antworten
   - CORS-Unterstützung
   - Umfassendes Logging
   - Error Handling mit aussagekräftigen Fehlermeldungen
   - Health-Check-Endpoint
   - Konfigurierbar über Umgebungsvariablen

## Projektstruktur

```
Flask-REST-API/
├── app.py                      # Haupt-Anwendung (Flask Server)
├── keyboard_emulator.py        # Tastatur-Emulations-Modul
├── requirements.txt            # Python-Abhängigkeiten
├── config.example.json         # Beispiel-Konfiguration
├── CONFIG.md                   # Konfigurationsdokumentation
├── README.md                   # Hauptdokumentation (Deutsch)
├── DEPLOYMENT.md              # Deployment-Anleitung
├── LICENSE                     # MIT-Lizenz
├── .gitignore                 # Git-Ignore-Datei
├── Dockerfile                 # Docker-Container-Definition
├── docker-compose.yml         # Docker Compose Konfiguration
├── flask-api.service          # Systemd Service-Definition
├── install.sh                 # Automatisches Installations-Skript
├── test_api.py                # Automatische Tests
└── example_client.py          # Beispiel-Client (Deutsch)
```

## API-Endpunkte

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/` | GET | API-Informationen |
| `/health` | GET | Health Check |
| `/upload` | POST | Datei hochladen (mit optionaler Hash-Verifizierung) |
| `/download/<filename>` | GET | Datei herunterladen |
| `/files` | GET | Alle Dateien auflisten |
| `/keyboard` | POST | Tastatur-Eingabe senden |

## Sicherheit

### Implementierte Sicherheitsmaßnahmen

1. ✅ **Dependency Security**: Alle Abhängigkeiten auf Sicherheitslücken geprüft
   - Werkzeug auf Version 3.0.3 aktualisiert (behebt CVE)
2. ✅ **Input Validation**: Dateinamen werden mit `secure_filename()` gesichert
3. ✅ **Hash Verification**: SHA256-Hash-Verifizierung für Dateiintegrität
4. ✅ **File Size Limits**: Konfigurierbare maximale Dateigröße
5. ✅ **Error Handling**: Sichere Fehlerbehandlung ohne sensitive Informationen
6. ✅ **CodeQL Scan**: Keine Sicherheitslücken gefunden

### Empfohlene zusätzliche Maßnahmen für Produktion

⚠️ Diese API ist derzeit **OHNE Authentifizierung**. Für den Produktionseinsatz empfohlen:

1. **Authentifizierung hinzufügen**
   - JWT-Tokens
   - API-Keys
   - OAuth2

2. **HTTPS verwenden**
   - Let's Encrypt Zertifikat
   - Nginx als Reverse Proxy mit SSL

3. **Rate Limiting**
   - Schutz vor DoS-Angriffen
   - Flask-Limiter verwenden

4. **Firewall konfigurieren**
   - Nur notwendige Ports öffnen
   - IP-Whitelisting für vertrauenswürdige Clients

## Installation

### Schnellstart (Radxa Rock 5b / Armbian)

```bash
# Repository klonen
git clone https://github.com/seccouser/Flask-REST-API.git
cd Flask-REST-API

# Automatische Installation (benötigt Root-Rechte)
sudo bash install.sh

# Server starten
sudo systemctl start flask-api
```

### Manuelle Installation

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Server starten
python3 app.py
```

### Docker

```bash
# Docker-Image bauen und starten
docker-compose up -d
```

## Nutzungsbeispiele

### 1. Datei hochladen mit Hash-Verifizierung

```bash
# Hash berechnen
HASH=$(sha256sum meine_datei.pdf | awk '{print $1}')

# Datei hochladen
curl -X POST \
  -F "file=@meine_datei.pdf" \
  -F "hash=$HASH" \
  http://localhost:5000/upload
```

### 2. Datei herunterladen

```bash
curl -O http://localhost:5000/download/meine_datei.pdf
```

### 3. Tastatur-Emulation

```bash
# Text eingeben
curl -X POST http://localhost:5000/keyboard \
  -H "Content-Type: application/json" \
  -d '{"text": "ls -la", "keys": ["KEY_ENTER"]}'
```

### 4. Python-Client

```python
import requests
import hashlib

# Datei hochladen
with open('datei.txt', 'rb') as f:
    files = {'file': f}
    hash_value = hashlib.sha256(f.read()).hexdigest()
    data = {'hash': hash_value}
    response = requests.post('http://localhost:5000/upload', 
                            files=files, data=data)

print(response.json())
```

## Tests

```bash
# Automatische Tests ausführen
python3 test_api.py

# Beispiel-Client ausführen
python3 example_client.py
```

## Performance

- **Worker-Empfehlung**: 2 × CPU-Kerne + 1 (für Radxa Rock 5b: ~17 Worker)
- **Maximale Dateigröße**: Standard 100 MB (konfigurierbar)
- **Gleichzeitige Verbindungen**: Abhängig von Gunicorn-Konfiguration

## Kompatibilität

✅ **Getestet auf**:
- Radxa Rock 5b mit Armbian Linux
- Standard Linux-Distributionen (Ubuntu, Debian)
- Python 3.8+

✅ **Tastatur-Emulation**:
- Benötigt Linux mit uinput-Unterstützung
- Root-Rechte oder input-Gruppe-Mitgliedschaft erforderlich
- Funktioniert auf allen ARM- und x86-Linux-Systemen

## Lizenz

MIT License - Siehe LICENSE-Datei

## Support und Dokumentation

- **README.md**: Vollständige API-Dokumentation (Deutsch)
- **DEPLOYMENT.md**: Ausführliche Deployment-Anleitung
- **CONFIG.md**: Konfigurationsoptionen
- **GitHub Issues**: Für Bug-Reports und Feature-Requests

## Entwickler-Notizen

### Code-Qualität

✅ Alle Code-Reviews bestanden
✅ Keine Sicherheitslücken gefunden (CodeQL)
✅ Abhängigkeiten auf aktuellem Stand
✅ PEP 8 konform
✅ Umfassende Dokumentation

### Nächste Schritte (Optional)

Mögliche Erweiterungen für die Zukunft:
- [ ] Authentifizierung (JWT, API-Keys)
- [ ] Rate Limiting
- [ ] Datei-Verschlüsselung
- [ ] WebSocket-Support für Echtzeit-Updates
- [ ] Admin-Dashboard
- [ ] Multi-User-Support
- [ ] Datei-Versionierung

## Credits

Entwickelt für Radxa Rock 5b mit Armbian Linux Kernel.
