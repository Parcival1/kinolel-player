# KinoLel-Player – Testanleitung

## Installieren

1. `KinoLel-Setup-<Version>-x64.exe` herunterladen und starten.
2. Windows warnt („Der Computer wurde durch Windows geschützt“), weil die Testversion nicht signiert ist:
   **Weitere Informationen → Trotzdem ausführen**. (Die spätere Store-Version kommt ohne Warnung.)
3. Installieren (ohne Administratorrechte möglich), danach startet **KinoLel**.
   Im Startmenü gibt es **KinoLel** (Fenster) und **KinoLel (TV-Modus)** (Vollbild, TV-Oberfläche).

Ohne Installation: `KinoLel-Portable-<Version>-x64.zip` entpacken und `KinoLel.exe` starten.

## Prüfen

| # | Was | Erwartung |
|---|---|---|
| 1 | Start | KinoLel-Logo mit Ladekreis, danach **direkt die Anmeldung** von kinolel.de – keine Serverauswahl |
| 2 | Sprache | Über der Anmeldung **Deutsch / Magyar**. „Magyar“ → Seite lädt auf Ungarisch neu. Anmelden → bleibt Ungarisch. Player schließen und neu starten → weiter Ungarisch. Zurück auf Deutsch genauso |
| 3 | Anmeldung | Mit „Angemeldet bleiben“ → nach Neustart ohne erneute Anmeldung auf der Startseite |
| 4 | **Schauspielerbilder** | Einen Film öffnen → Besetzung zeigt Fotos (fehlten im alten Jellyfin Media Player) |
| 5 | HDR x265 | *The Green Mile* oder *Red Notice* (HDR10, HEVC), *Ready Player One* (Dolby Vision + HDR10): Bild normal hell, Farben nicht ausgewaschen, läuft flüssig. **4K-HDR gibt es im Bestand derzeit nicht** – wer eine 4K-HDR-Datei hat, bitte zusätzlich testen |
| 6 | DTS | *Bűnvadászok* (1977), *Aquaman* oder *2001: Odyssee im Weltraum*: Ton läuft. Mit AV-Receiver: Zahnrad oben → **Client-Einstellungen** → Audio → Durchreichen (Passthrough) für DTS/AC3 einschalten |
| 7 | Ungarische Untertitel | *6 Underground* (eingebettet) und *13 Hours* (extern): Untertitel „Magyar“ wählen → ő, ű, á usw. richtig |
| 8 | Direktwiedergabe | Während 5–7 im Browser unter Dashboard → **Aktivität/Wiedergabe**: „Direktwiedergabe“ statt „Transkodierung“ |
| 9 | Vollbild | **F11** oder **Alt+Enter** schaltet um; im Film Doppelklick |
| 10 | TV-Modus | Startmenü **KinoLel (TV-Modus)**: Vollbild, große TV-Oberfläche, Bedienung mit Pfeiltasten/Enter/Rücktaste oder Gamepad |
| 11 | Medientasten | Wiedergabe/Pause/Weiter auf der Tastatur |

## Wenn es ruckelt oder die Lüfter laufen (Diagnose, ab v0.1.1)

1. In KinoLel **Strg+Umschalt+G** drücken → Diagnoseseite. Oben im lila Kasten steht die Grafik der App:
   - „Software-Rendering: **JA**“ = keine echte Grafikkarte (z. B. in einer VM oder per Remotedesktop) → die CPU rechnet
     jedes Bild selbst. Dann bitte **auf einem PC mit Grafikkarte direkt** testen (nicht per Remotedesktop).
   - „OpenGL: …“ zeigt den Grafiktreiber (z. B. NVIDIA, AMD, Intel).
   - Darunter „Graphics Feature Status“ von Chromium: sollte überwiegend „Hardware accelerated“ zeigen.
   Bildschirmfoto davon an Claude. Nochmal **Strg+Umschalt+G** = zurück.
2. **Task-Manager** (Strg+Umschalt+Esc) → Prozesse → Spalten „CPU“ und „GPU“ (Rechtsklick auf die Kopfzeile → „GPU“):
   KinoLel und QtWebEngineProcess auf der Startseite einige Sekunden beobachten, Werte notieren.

## Wenn etwas nicht geht

- Kurz notieren, was passiert (Film, Schritt, ggf. Bildschirmfoto).
- Logdateien: `%LOCALAPPDATA%\KinoLel\profiles\` → Unterordner → `logs` (Datei `KinoLel.log`).

## Optional: Store-Paket (MSIX) testen

Das spätere Store-Paket lässt sich vorab ausprobieren (braucht einmal Administratorrechte):
1. `KinoLel-Testzertifikat.cer` doppelklicken → Zertifikat installieren → **Lokaler Computer** →
   Speicher **Vertrauenswürdige Personen**.
2. `KinoLel-Test-<Version>.0-x64.msix` doppelklicken → Installieren.
3. Vorher die Setup-Version deinstallieren, damit klar ist, welche läuft. Jeder neue Build hat ein neues Testzertifikat.
