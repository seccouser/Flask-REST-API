# feature/auto-resize-v4l2 — Per‑Tile Ausgabe‑Offsets + Laufzeit Drehen/Spiegeln + Gap‑Support

## Zusammenfassung
Dieser Branch fügt pixelgenaue Ausgabe‑Offsets pro Kachel (insgesamt 150 Kacheln) hinzu, Laufzeitsteuerungen zum Drehen und Spiegeln des Eingangsbildes sowie konfigurierbare vertikale „Gaps“ (Abstände) zwischen Kachel‑Zeilen, um physische Display‑Pitches abzubilden. Die Offsets werden aus drei Moduldateien (modul1.txt, modul2.txt, modul3.txt) geladen und können zur Laufzeit neu eingelesen werden. Die Änderung belässt die Quell‑Sampling‑Logik unverändert und verschiebt nur die angezeigten Kachel‑Rechtecke; zusätzlich werden Uniform‑Uploads und Textur‑Neuzuordnungen bei V4L2‑Formatänderungen robuster gemacht.

## Warum
- Korrigiert fehlerhaft ausgerichtete Kacheln durch pixelgenaue Offsets, ohne das Quell‑Sampling zu verändern.  
- Modelliert physische vertikale Nähte/Abstände zwischen zusammengeschalteten Displays, indem der vertikale Abstand an bestimmten Stellen auf 0 gesetzt wird.  
- Ermöglicht einfache Laufzeitanpassung über Textdateien und eine Reload‑Taste.  
- Beibehaltung leistungsfähiger Shader‑ und Upload‑Logik für NV12/NV21 Formate.

## Kernfunktionen
- Per‑Tile Ausgabe‑Offsets:
  - 150 ivec2‑Offsets (`offsetxy1[150]`) werden per `glUniform2iv` an den Fragment‑Shader übergeben.
  - Interpretation: `offset.x` positiv → Kachel nach rechts verschieben; negativ → nach links. `offset.y` positiv → Kachel nach unten verschieben; negativ → nach oben.
  - Offsets verschieben ausschließlich die ausgegebenen Kachel‑Rechtecke; das Sampling aus der Eingangstextur bleibt unverändert.

- Laufzeit‑Reload:
  - `modul1.txt` / `modul2.txt` / `modul3.txt` (je bis zu 50 Paare) werden vom Programm gelesen.
  - Taste `k` lädt die Dateien zur Laufzeit neu und lädt die Offsets in den Shader.

- Eingangstransformationen:
  - Uniform `rot` (0/1/2/3 → 0°/90°/180°/270° CW) wird auf die Input‑UVs vor dem Sampling angewandt.
  - `flip_x` und `flip_y` schalten horizontales/vertikales Spiegeln des Eingangs ein/aus.
  - Tasten: `r` = Rotieren (Branch nutzt standardmäßig 180°-Schritt), `h` = horizontales Spiegeln, `v` = vertikales Spiegeln.

- Gap‑Kontrolle (neu):
  - Shader‑Uniforms `gap_count` und `gap_rows` definieren vertikale Gaps zwischen Kachel‑Zeilen.
  - Jeder Eintrag in `gap_rows` ist ein 1‑basierter Zeilenindex `g`, der bedeutet: „der Abstand zwischen Zeile g und g+1 wird als 0 behandelt“.
  - Beispiel‑Default: `gap_rows = {5, 10}` → kein vertikaler Abstand zwischen Reihen 5↔6 und 10↔11 (modelliert Display‑Nähte).
  - Setzung aus C++ via `glUniform1i(loc_gap_count, ...)` und `glUniform1iv(loc_gap_rows, ARRAY_SIZE, ...)`.
  - Array‑Größe im Shader ist standardmäßig 8; bei Bedarf anpassbar.

- Robustheit / Benutzerfreundlichkeit:
  - Uniforms werden pro Frame hochgeladen, um Optimierungen durch den Treiber (Uniform wird entfernt) zu vermeiden.
  - Loader prüft ausführbares Verzeichnis und aktuelles Arbeitsverzeichnis, loggt Versuche und Einlese‑Anzahlen.
  - Texturen werden bei V4L2‑Formatwechseln neu alloziert; UV‑Swap‑Erkennung und optionales CPU‑UV‑Swap werden unterstützt.
  - Umfangreiche Konsolenlogs zur Debugging‑Unterstützung (Uniform‑Locations, geladene Offsets).

## Geänderte / wichtige Dateien
- `hdmi_simple_display.cpp`
  - Aktualisiert: Loader für Moduldateien + Logging, Uniform‑Uploads für `offsetxy1`, `rot`, `flip_x`, `flip_y`, `gap_count`, `gap_rows`, Tastatur‑Handling (`k`, `h`, `v`, `r`), Textur‑Neuzuordnung.
- `shaders/shader.frag.glsl`
  - Aktualisiert: wendet per‑tile Ausgabe‑Offsets auf die angezeigten Kachel‑Rechtecke an, unterstützt Input‑UV Dreh/Flip und gap‑aware Y‑Positionierung.
- (Vertex‑Shader unverändert.)

## Vom Shader verwendete Uniforms
- ivec2 offsetxy1[150]        — per‑Tile Ausgabe‑Offsets (Pixel)
- int rot                    — Rotation des Eingangs (0..3)
- int flip_x, flip_y         — Spiegeln des Eingangs
- int gap_count              — Anzahl gültiger Einträge in gap_rows
- int gap_rows[8]            — Liste (1‑basiert) von Zeilen, nach denen spacing = 0 gelten soll
- int uv_swap, full_range, use_bt709, view_mode, segmentIndex

## Format der Moduldateien (`modul1.txt` / `modul2.txt` / `modul3.txt`)
- Bis zu 50 Zeilen pro Datei (fehlende Einträge werden mit 0,0 aufgefüllt).
- Jede gültige Zeile: zwei ganze Zahlen, durch Whitespace getrennt:
  ```
  <x> <y>
  ```
  Beispiel:
  ```
  -3 5
  0 0
  2 -1
  ```
- Zeilen, die mit `#` beginnen oder leer sind, werden ignoriert.
- Dateien werden im ausführbaren Verzeichnis (exe dir) und im aktuellen Arbeitsverzeichnis gesucht.

## Gaps konfigurieren (C++)
- Default im Code: zwei Gaps nach Zeile 5 und nach Zeile 10 (passend für drei vertikal gestapelte Displays mit von dir erwähnter Kachel‑Pitch).
- Stelle im Code (nach Shader‑Link / `glGetUniformLocation`):
  ```c++
  const int GAP_ARRAY_SIZE = 8;
  int gap_count = 2;
  int gap_rows_arr[GAP_ARRAY_SIZE] = { 5, 10, 0, 0, 0, 0, 0, 0 };
  if (loc_gap_count >= 0) glUniform1i(loc_gap_count, gap_count);
  if (loc_gap_rows >= 0)  glUniform1iv(loc_gap_rows, GAP_ARRAY_SIZE, gap_rows_arr);
  ```
- Zur Laufzeit ändern:
  - Noch nicht standardmäßig vorhanden; kann aber leicht per Konfigurationsdatei oder CLI‑Optionen nachgerüstet werden.

## Build & Test
1. Build:
   ```bash
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j$(nproc)
   ```
2. Moduldateien anlegen (Beispiel):
   ```bash
   echo "-3 5" > modul1.txt   # erste Kachel: 3px links, 5px nach unten
   # modul2.txt / modul3.txt analog oder leer lassen
   ```
3. Starten:
   ```bash
   ./build/hdmi_simple_display
   ```
4. Steuerung:
   - `k` : reload modul1/2/3 und Offsets hochladen  
   - `h` : horizontales Spiegeln (Input) toggle  
   - `v` : vertikales Spiegeln (Input) toggle  
   - `r` : Input rotieren (Branch‑Default: 180° pro Druck)  
   - `f` : Fullscreen toggle  
   - `ESC`: Beenden

## Beispiel‑Ablauf
1. Leg `modul1.txt` in das Verzeichnis der ausführbaren Datei; für die erste Kachel:
   ```
   -3 5
   ```
2. Programm starten und `k` drücken. Die Konsole zeigt gelesene Einträge und Upload‑Bestätigung. Ergebnis: erste Kachel verschiebt sich 3px nach links und 5px nach unten.  
3. Für drei vertikal gestapelte Displays ohne sichtbaren Zwischenraum sorge dafür, dass `gap_rows` die Indizes enthält, nach denen der spacingY auf 0 gesetzt werden soll (z. B. 5 und 10 im Default).

## Hinweise & Einschränkungen
- Falls der GLSL‑Compiler uniforme Variablen optimiert (Location == -1), meldet das Programm dies in der Konsole. In diesem Branch werden die relevanten Uniforms im Shader verwendet, sodass Locations typischerweise gültig sind.  
- Offsets können zu Überlappungen oder Lücken führen; Lücken werden standardmäßig schwarz gerendert. Falls gewünscht, kann stattdessen eine Hintergrundfarbe oder Füllung implementiert werden.  
- `gap_rows` sind 1‑basiert und müssen im Bereich `1 .. (numTilesPerCol-1)` liegen. Die Array‑Größe ist standardmäßig 8 — bei Bedarf vergrößern.

## Vorgeschlagener Commit & PR‑Meta
- Commit‑Message:
  ```
  Add per-tile output offsets, gap support and runtime rotate/flip controls; enhance loader logging
  ```
- PR‑Titel:
  ```
  feature/auto-resize-v4l2: per-tile offsets + gap handling + runtime rotate/flip
  ```
- PR‑Beschreibung: Zusammenfassung + Key features + How to build & test (oben verwenden).


