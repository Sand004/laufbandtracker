# Schnellstart-Anleitung 🚀

## Voraussetzungen

1. **Python 3.8+** installiert
2. **Bluetooth** aktiviert (für Laufband-Verbindung)
3. **Supabase Account** (kostenlos auf [supabase.com](https://supabase.com))

## Installation in 5 Minuten

### 1. Repository klonen
```bash
git clone https://github.com/Sand004/laufbandtracker.git
cd laufbandtracker
```

### 2. Setup-Skript ausführen
```bash
python setup.py
```

Das Setup-Skript:
- ✅ Prüft Python-Version
- ✅ Installiert alle Abhängigkeiten
- ✅ Prüft Konfiguration
- ✅ Testet Supabase-Verbindung
- ✅ Migriert bestehende Daten

### 3. Supabase einrichten

1. Projekt auf [supabase.com](https://supabase.com) erstellen
2. SQL Editor öffnen
3. Inhalt von `supabase_schema.sql` ausführen
4. Project URL und Anon Key kopieren

### 4. Konfiguration

`.env` Datei erstellen (oder `.env.example` kopieren):
```env
SUPABASE_URL=deine_projekt_url
SUPABASE_KEY=dein_anon_key
```

### 5. App starten
```bash
python treadmill_app_modern.py
```

Oder per Doppelklick auf `start_treadmill_ui.bat`

## ESP32 Klimmzug-Sensor

### Hardware anschließen
- **TRIG_PIN**: GPIO 5
- **ECHO_PIN**: GPIO 18
- HC-SR04 Sensor über der Klimmzugstange montieren

### Code anpassen
Im ESP32 Code nur WLAN-Daten ändern:
```cpp
const char* WIFI_SSID = "DeinWLAN";
const char* WIFI_PASS = "DeinPasswort";
```

Supabase Credentials sind bereits konfiguriert!

## Verwendung

### Laufband-Training
1. **"Connect Device"** klicken
2. Loslaufen - Training startet automatisch
3. Anhalten - Training wird nach 2 Sek. gespeichert

### Manuelle Eingabe
1. **"📝 Log Manual Workout"** klicken
2. Distanz, Schritte und Zeit eingeben
3. Speichern

### Statistiken
- **Zeitraum** oben rechts auswählen
- **Tabs** für verschiedene Ansichten
- **Klimmzüge** werden automatisch aktualisiert

## Problembehebung

### Bluetooth funktioniert nicht?
- Bluetooth am PC aktiviert?
- Laufband eingeschaltet?
- Richtige Adresse in `.env`?

### Supabase Fehler?
- Credentials korrekt?
- Internet-Verbindung?
- Schema in Supabase ausgeführt?

### ESP32 sendet keine Daten?
- WLAN verbunden? (Serial Monitor prüfen)
- Sensor richtig verkabelt?
- Abstand zur Stange korrekt?

## Tipps

- 🔄 Daten werden alle 30 Sekunden aktualisiert
- 📊 Verschiedene Zeiträume für bessere Übersicht
- 💾 Alle Daten in der Cloud gesichert
- 🏃‍♂️ Mindestens 50 Schritte für Speicherung

## Support

Bei Problemen:
1. `setup.py` erneut ausführen
2. Logs in der App prüfen
3. Issue auf GitHub erstellen

Viel Spaß beim Training! 💪
