# KinoLel für Windows – Testanleitung

**Neu ab 0.3.0:** KinoLel läuft jetzt mit **Chromium** (wie Google Chrome) statt der bisherigen Technik – kein Flackern mehr,
flüssig auch ohne Grafikkarte. Abgespielt wird im Player von kinolel.de.

## Installieren / Update

- **KinoLel ist schon installiert (0.1.x):** Die App meldet „Neue Version“ → **Jetzt aktualisieren**. Danach startet die neue
  KinoLel von selbst, die Anmeldung bleibt, einmal erscheint „Neu in KinoLel 0.3.0“.
- **Neu:** `KinoLel-Setup-<Version>-x64.exe` herunterladen und starten (ohne Administratorrechte). Windows warnt, weil die
  Testversion nicht signiert ist: **Weitere Informationen → Trotzdem ausführen**.
- Startmenü: **KinoLel** (Fenster) und **KinoLel (TV-Modus)** (Vollbild, TV-Oberfläche für Fernbedienung/Gamepad).
- Ohne Installation: `KinoLel-Portable-<Version>-x64.zip` entpacken, `KinoLel.exe` starten (Updates dann von Hand).

## Prüfen

| # | Was | Erwartung |
|---|---|---|
| 1 | Öffnen | KinoLel-Startbild mit Ladekreis, bis die Startseite fertig ist – keine halb aufgebauten Menüs |
| 2 | Startseite | 1–2 Minuten stehen lassen: **kein Flackern**, nichts lädt dauernd neu |
| 3 | Fenster | Titelleiste dunkel (`#0B0F18`) mit „KinoLel“; Minimieren/Maximieren/Schließen wie gewohnt, Andocken mit Win+Pfeiltasten, Snap-Layouts beim Überfahren von „Maximieren“ |
| 4 | Abspielen | Film starten, mit der Maus über die Zeitleiste → **Vorschaubilder**, Ton/Untertitel umschalten, Intro überspringen, nächste Folge |
| 5 | Vollbild | **F11**; im Film Doppelklick |
| 6 | TV-Modus | Startmenü **KinoLel (TV-Modus)**: Vollbild, große TV-Oberfläche, Pfeiltasten/Enter/Rücktaste |
| 7 | Links | „Wünsche“ und andere fremde Seiten öffnen sich im normalen Browser |
| 8 | Updates | KinoLel sucht beim Start und alle 3 Stunden; „Später“ fragt erst nach 4 Stunden wieder |

## Formate („direkt abspielen“)

- **Direkt:** Bild H.264, AV1, VP9; Ton AAC, MP3, Opus, FLAC.
- **HEVC (H.265):** direkt mit einer Grafikkarte, die HEVC kann (etwa ab 2016: NVIDIA ab GTX 950, Intel ab 6. Generation,
  AMD ab RX 400; 10 Bit ab GTX 10xx bzw. Intel 7. Generation). Ohne passende Karte wandelt der Server das Bild um.
- **Dolby Digital (AC3), Dolby Digital Plus (E-AC3), DTS:** kann Chromium nicht – der Server wandelt nur den Ton um, das
  Bild bleibt unverändert.

## Wenn etwas nicht stimmt

**Strg+Umschalt+G** zeigt die Grafik-Info (Grafikkarte, Hardware-Dekoder, z. B. ob HEVC dabei ist) – „Kopieren“ und an Claude
schicken. Protokoll: `%LOCALAPPDATA%\KinoLel\App\kinolel.log`.
