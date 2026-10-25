# KinoLel für Windows

Windows-App für [KinoLel](https://kinolel.de): ein eigenes Fenster mit **https://kinolel.de**, angetrieben von
**Chromium** (über [Electron](https://www.electronjs.org/)) – dieselbe Technik wie Google Chrome, unabhängig davon, ob Chrome
installiert ist. Seit **v0.3.0** (25.10.2026, Lel: „… eine web app … basiere unseres bitte auf Chrome“).

Die bisherige App (Abspaltung von Jellyfin Desktop, Qt WebEngine + mpv, bis v0.1.6) liegt unverändert unter dem Tag
**`qt-0.1.6`** bzw. dem Zweig **`alt-qt`**.

## Aufbau (`webapp/`)

| Datei | Zweck |
|---|---|
| [`main.js`](webapp/main.js) | Fenster mit Titelleiste `#0B0F18` und echten Windows-Knöpfen (Andocken, Snap-Layouts), kinolel.de, Startbild, TV-Modus (`--tv`), fremde Links im Browser, Update-Suche, „Was ist neu“, Grafik-Info (Strg+Umschalt+G), Protokoll, Übernahme der Anmeldung aus der Qt-App |
| [`seite-preload.js`](webapp/seite-preload.js) | wählt Desktop-/TV-Oberfläche von kinolel.de, meldet, wann das Startbild weg darf |
| [`oberflaeche/`](webapp/oberflaeche/) | Startbild (wie das Lade-Overlay von kinolel.de), Titelleiste, Dialoge im KinoLel-Design |
| [`marke.json`](webapp/marke.json), [`neuigkeiten.json`](webapp/neuigkeiten.json) | Name/Server/Versionsliste, „Was ist neu“ (de/hu/en) |
| [`installer/KinoLel.iss`](webapp/installer/KinoLel.iss) | Inno Setup – **gleiche AppId wie die bisherige App**, ersetzt sie beim Update |
| [`test/webapp_test.py`](webapp/test/webapp_test.py) | Test auf dem Windows-Runner (siehe unten) |

Version: `webapp/package.json`. Neue Version = dort erhöhen, in `neuigkeiten.json` oben einen Eintrag ergänzen, Tag `v<Version>`.

## Bauen und testen

GitHub Actions [`webapp.yml`](.github/workflows/webapp.yml) (Windows-Runner ohne Grafikkarte): Electron paketieren, Setup und
Portable-ZIP, dann der Test – Umstieg von der echten v0.1.6 (eine Anmeldung je Lauf, Passwort aus dem Secret
`KINOLEL_TEST_PW`, wird nie getippt oder ausgegeben), Startseite (Flackern im Bildschirmvideo, Neuladen, CPU), Abspielen
(Trickplay, Tonspur, Fortschritt), TV-Modus, Auto-Update. Ein Tag `v*` veröffentlicht Setup und ZIP unter „Releases“;
`https://kinolel.de/web/kinolel/apps.json` übernimmt die neue Version (Host-Cron alle 15 Min.).

## Lizenz

GPL-2.0 (siehe [LICENSE](LICENSE)). Electron/Chromium unter ihren eigenen Lizenzen.
