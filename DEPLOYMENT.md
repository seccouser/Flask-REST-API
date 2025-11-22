# Deployment Guide - Flask REST API auf Radxa Rock 5b

## Systemanforderungen

- **Hardware**: Radxa Rock 5b (oder kompatible ARM-Boards)
- **OS**: Armbian Linux (aktueller Kernel)
- **Python**: 3.8 oder höher
- **RAM**: Mindestens 512 MB verfügbar
- **Storage**: Mindestens 100 MB für die Anwendung + Speicherplatz für hochgeladene Dateien

## Schnellinstallation

### Option 1: Automatische Installation (empfohlen)

```bash
# Als root oder mit sudo
sudo bash install.sh
```

Das Skript installiert automatisch:
- Alle Python-Abhängigkeiten
- System-Bibliotheken für evdev
- Konfiguriert uinput-Berechtigungen
- Richtet systemd-Service ein

### Option 2: Manuelle Installation

#### 1. System-Updates und Abhängigkeiten

```bash
# System aktualisieren
sudo apt-get update
sudo apt-get upgrade -y

# Python und Entwicklungs-Tools installieren
sudo apt-get install -y python3 python3-pip python3-dev git

# evdev-Systemabhängigkeiten
sudo apt-get install -y gcc linux-headers-$(uname -r)
```

#### 2. Anwendung installieren

```bash
# Repository klonen
git clone https://github.com/seccouser/Flask-REST-API.git
cd Flask-REST-API

# Python-Abhängigkeiten installieren
pip3 install -r requirements.txt
```

#### 3. uinput für Tastatur-Emulation konfigurieren

```bash
# uinput-Modul laden
sudo modprobe uinput

# Automatisch beim Booten laden
echo "uinput" | sudo tee -a /etc/modules

# udev-Regel erstellen für Berechtigungen
sudo tee /etc/udev/rules.d/99-uinput.rules << 'EOF'
KERNEL=="uinput", MODE="0666", GROUP="input"
EOF

# udev neu laden
sudo udevadm control --reload-rules
sudo udevadm trigger

# Benutzer zur input-Gruppe hinzufügen
sudo usermod -a -G input $USER

# Ausloggen und wieder einloggen für Gruppenzugehörigkeit
```

## Server starten

### Manuell

```bash
# Im Projektverzeichnis
python3 app.py

# Mit benutzerdefinierten Einstellungen
FLASK_HOST=0.0.0.0 FLASK_PORT=8080 python3 app.py

# Im Hintergrund mit nohup
nohup python3 app.py > flask-api.log 2>&1 &
```

### Als systemd-Service (empfohlen für Produktion)

```bash
# Service-Datei kopieren
sudo cp flask-api.service /etc/systemd/system/

# Pfade in Service-Datei anpassen falls nötig
sudo nano /etc/systemd/system/flask-api.service

# Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable flask-api
sudo systemctl start flask-api

# Status überprüfen
sudo systemctl status flask-api

# Logs anzeigen
sudo journalctl -u flask-api -f
```

### Mit Docker

```bash
# Docker-Image bauen
docker build -t flask-api .

# Container starten
docker run -d \
  --name flask-api \
  -p 5000:5000 \
  -v $(pwd)/uploads:/app/uploads \
  --device /dev/uinput \
  --privileged \
  flask-api

# Oder mit docker-compose
docker-compose up -d
```

## Produktions-Deployment

### Mit Gunicorn (empfohlen)

```bash
# Gunicorn installieren
pip3 install gunicorn

# Server starten
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Mit Systemd-Service
# Erstelle /etc/systemd/system/flask-api-gunicorn.service:
```

```ini
[Unit]
Description=Flask REST API with Gunicorn
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/Flask-REST-API
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Mit Nginx als Reverse Proxy

```bash
# Nginx installieren
sudo apt-get install -y nginx

# Nginx-Konfiguration erstellen
sudo nano /etc/nginx/sites-available/flask-api
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Für große Datei-Uploads
        client_max_body_size 100M;
    }
}
```

```bash
# Konfiguration aktivieren
sudo ln -s /etc/nginx/sites-available/flask-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### HTTPS mit Let's Encrypt

```bash
# Certbot installieren
sudo apt-get install -y certbot python3-certbot-nginx

# SSL-Zertifikat erstellen
sudo certbot --nginx -d your-domain.com

# Automatische Erneuerung testen
sudo certbot renew --dry-run
```

## Konfiguration

### Umgebungsvariablen

```bash
# In ~/.bashrc oder /etc/environment
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
export FLASK_DEBUG=False
```

### Konfigurationsdatei

```bash
# config.json erstellen (basierend auf config.example.json)
cp config.example.json config.json
nano config.json
```

## Firewall-Konfiguration

```bash
# UFW (Uncomplicated Firewall)
sudo ufw allow 5000/tcp
sudo ufw enable
sudo ufw status

# iptables
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

## Monitoring und Logging

### Logs anzeigen

```bash
# Systemd-Service-Logs
sudo journalctl -u flask-api -f

# Manuelle Logs (wenn mit nohup gestartet)
tail -f flask-api.log
```

### Log-Rotation einrichten

```bash
# /etc/logrotate.d/flask-api erstellen
sudo nano /etc/logrotate.d/flask-api
```

```
/opt/Flask-REST-API/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        systemctl reload flask-api > /dev/null 2>&1 || true
    endscript
}
```

## Performance-Tuning

### Worker-Anzahl (Gunicorn)

```bash
# Formel: (2 x CPU_Cores) + 1
# Für Radxa Rock 5b mit 8 Cores:
gunicorn -w 17 -b 0.0.0.0:5000 app:app
```

### Upload-Größe anpassen

In `app.py`:
```python
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB
```

## Backup und Wartung

### Backup-Skript

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/flask-api"
SOURCE_DIR="/opt/Flask-REST-API/uploads"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz $SOURCE_DIR

# Alte Backups löschen (älter als 30 Tage)
find $BACKUP_DIR -name "uploads_*.tar.gz" -mtime +30 -delete
```

### Automatische Updates

```bash
# Cron-Job für automatische Updates
sudo crontab -e

# Täglich um 2 Uhr morgens
0 2 * * * cd /opt/Flask-REST-API && git pull && systemctl restart flask-api
```

## Fehlerbehebung

### Server startet nicht

```bash
# Logs überprüfen
sudo journalctl -u flask-api -n 50

# Port bereits in Verwendung?
sudo lsof -i :5000

# Python-Abhängigkeiten überprüfen
pip3 list | grep -i flask
```

### Tastatur-Emulation funktioniert nicht

```bash
# uinput-Modul geladen?
lsmod | grep uinput

# Berechtigungen überprüfen
ls -l /dev/uinput

# evdev installiert?
python3 -c "import evdev; print('OK')"

# Als root starten (temporär)
sudo python3 app.py
```

### Hohe CPU-Last

```bash
# Worker reduzieren
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Prozesse überwachen
htop
```

## Sicherheitshinweise

1. **Authentifizierung hinzufügen**: Die API hat standardmäßig keine Authentifizierung
2. **HTTPS verwenden**: Für Produktion immer HTTPS verwenden
3. **Firewall konfigurieren**: Nur notwendige Ports öffnen
4. **Regelmäßige Updates**: System und Abhängigkeiten aktuell halten
5. **Logs überwachen**: Auf verdächtige Aktivitäten achten
6. **Backup**: Regelmäßige Backups der hochgeladenen Dateien

## Support

Bei Problemen:
1. Logs überprüfen
2. GitHub Issues durchsuchen
3. Neues Issue erstellen mit:
   - Systeminformationen (`uname -a`)
   - Python-Version (`python3 --version`)
   - Fehlermeldungen aus den Logs
   - Reproduktionsschritte
