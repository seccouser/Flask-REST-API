#!/usr/bin/env python3
"""
Beispiel-Client für Flask REST API
Demonstriert alle verfügbaren Funktionen
"""

import requests
import hashlib
import sys
import os

# API-Konfiguration
API_URL = "http://localhost:5000"

def print_section(title):
    """Drucke Abschnittsüberschrift"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def test_api_info():
    """API-Informationen abrufen"""
    print_section("API Informationen")
    
    response = requests.get(f"{API_URL}/")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Name: {data['name']}")
        print(f"Version: {data['version']}")
        print(f"Tastatur-Emulation: {data['keyboard_emulation']}")
        print("\nVerfügbare Endpunkte:")
        for endpoint, description in data['endpoints'].items():
            print(f"  {endpoint:30} - {description}")
    
    return response.status_code == 200

def upload_file(filepath, verify_hash=True):
    """Datei hochladen mit optionaler Hash-Verifizierung"""
    print_section(f"Datei hochladen: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"Fehler: Datei nicht gefunden: {filepath}")
        return None
    
    # Hash berechnen
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    file_hash = sha256_hash.hexdigest()
    
    print(f"Berechne SHA256-Hash...")
    print(f"Hash: {file_hash}")
    
    # Datei hochladen
    with open(filepath, 'rb') as f:
        files = {'file': f}
        data = {}
        
        if verify_hash:
            data['hash'] = file_hash
            print(f"Upload mit Hash-Verifizierung...")
        else:
            print(f"Upload ohne Hash-Verifizierung...")
        
        response = requests.post(f"{API_URL}/upload", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        print(f"✓ Upload erfolgreich!")
        print(f"  Dateiname: {result['filename']}")
        print(f"  Größe: {result['size']} Bytes")
        print(f"  Hash: {result['hash']}")
        print(f"  Hash verifiziert: {result['hash_verified']}")
        return result['filename']
    else:
        print(f"✗ Upload fehlgeschlagen: {response.json()}")
        return None

def list_files():
    """Alle hochgeladenen Dateien auflisten"""
    print_section("Dateiliste")
    
    response = requests.get(f"{API_URL}/files")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Anzahl Dateien: {data['count']}")
        
        if data['count'] > 0:
            print("\nDateien:")
            for file_info in data['files']:
                print(f"  - {file_info['filename']}")
                print(f"    Größe: {file_info['size']} Bytes")
                print(f"    Hash: {file_info['hash']}")
                print()

def download_file(filename, save_as=None):
    """Datei herunterladen und Hash verifizieren"""
    print_section(f"Datei herunterladen: {filename}")
    
    if save_as is None:
        save_as = f"downloaded_{filename}"
    
    response = requests.get(f"{API_URL}/download/{filename}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        # Hash aus Header
        expected_hash = response.headers.get('X-File-Hash')
        algorithm = response.headers.get('X-Hash-Algorithm', 'sha256')
        
        print(f"Server-Hash ({algorithm}): {expected_hash}")
        
        # Datei speichern
        with open(save_as, 'wb') as f:
            f.write(response.content)
        
        # Hash berechnen und verifizieren
        if algorithm == 'sha256':
            hash_func = hashlib.sha256()
        else:
            hash_func = hashlib.new(algorithm)
        
        hash_func.update(response.content)
        actual_hash = hash_func.hexdigest()
        
        print(f"Lokaler Hash: {actual_hash}")
        
        if expected_hash == actual_hash:
            print(f"✓ Hash verifiziert! Datei gespeichert als: {save_as}")
            return True
        else:
            print(f"✗ Hash-Fehler! Datei könnte beschädigt sein.")
            return False
    else:
        print(f"✗ Download fehlgeschlagen: {response.json()}")
        return False

def send_keyboard_text(text):
    """Text über Tastatur-Emulation senden"""
    print_section("Tastatur-Emulation: Text senden")
    
    print(f"Text: '{text}'")
    
    data = {"text": text, "delay": 0.05}
    response = requests.post(f"{API_URL}/keyboard", json=data)
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    if response.status_code == 200:
        print(f"✓ Text erfolgreich gesendet!")
    elif response.status_code == 503:
        print(f"⚠ Tastatur-Emulation nicht verfügbar")
        print(f"  Grund: {result['message']}")
    else:
        print(f"✗ Fehler: {result.get('error')}")

def send_keyboard_keys(keys):
    """Spezielle Tasten über Tastatur-Emulation senden"""
    print_section("Tastatur-Emulation: Tasten senden")
    
    print(f"Tasten: {keys}")
    
    data = {"keys": keys, "delay": 0.1}
    response = requests.post(f"{API_URL}/keyboard", json=data)
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    if response.status_code == 200:
        print(f"✓ Tasten erfolgreich gesendet!")
    elif response.status_code == 503:
        print(f"⚠ Tastatur-Emulation nicht verfügbar")
        print(f"  Grund: {result['message']}")
    else:
        print(f"✗ Fehler: {result.get('error')}")

def main():
    """Hauptprogramm"""
    print("=" * 60)
    print("  Flask REST API - Beispiel-Client")
    print("=" * 60)
    
    # Server-Erreichbarkeit prüfen
    try:
        print(f"\nVerbinde mit {API_URL}...")
        requests.get(f"{API_URL}/health", timeout=2)
        print("✓ Server erreichbar\n")
    except requests.exceptions.ConnectionError:
        print(f"✗ Fehler: Kann nicht mit {API_URL} verbinden")
        print("  Stellen Sie sicher, dass der Server läuft: python app.py")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Fehler: {e}")
        sys.exit(1)
    
    # 1. API-Informationen
    test_api_info()
    
    # 2. Test-Datei erstellen
    test_file = "/tmp/api_test_file.txt"
    with open(test_file, 'w') as f:
        f.write("Dies ist eine Test-Datei für die Flask REST API.\n")
        f.write("Sie enthält mehrere Zeilen Text.\n")
        f.write("Und wird für Upload/Download-Tests verwendet.\n")
    
    # 3. Datei hochladen (mit Hash-Verifizierung)
    uploaded_filename = upload_file(test_file, verify_hash=True)
    
    # 4. Alle Dateien auflisten
    list_files()
    
    # 5. Datei herunterladen (wenn Upload erfolgreich)
    if uploaded_filename:
        download_file(uploaded_filename)
    
    # 6. Tastatur-Emulation testen
    send_keyboard_text("echo 'Hello from Flask API'")
    send_keyboard_keys(["KEY_ENTER"])
    
    # Aufräumen
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("\n" + "=" * 60)
    print("  Alle Tests abgeschlossen!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
