# KinoLel – Windows-Player

Eigener Windows-Player für [KinoLel](https://kinolel.de) (Jellyfin). Er öffnet direkt die Anmeldung von
`https://kinolel.de` – ohne Serverauswahl – und spielt Filme über **mpv** direkt ab (HEVC/x265, 4K, HDR mit
Tonemapping, DTS/TrueHD/AC3, ASS-Untertitel), sodass der Server kaum umwandeln muss.

Grundlage ist **[Jellyfin Desktop](https://github.com/jellyfin/jellyfin-desktop)** 2.x (Qt 6 WebEngine + libmpv),
der Nachfolger des Jellyfin Media Players. Dieses Projekt ist eine Abspaltung davon und steht wie das Original
unter der **GNU General Public License v2.0** (siehe [LICENSE](LICENSE)).

## Was gegenüber Jellyfin Desktop anders ist

| Bereich | KinoLel |
|---|---|
| Name, Server, Version | an **einer** Stelle: [`marke.cmake`](marke.cmake) |
| Start | Startbild mit KinoLel-Logo und Ladekreis, Server fest (`APP_SERVER_URL`), keine Serverauswahl, kein „Server zurücksetzen“ |
| Anmeldung | Anmeldeseite von kinolel.de inkl. Sprachwahl Deutsch/Magyar (kommt von der Weboberfläche, `kl-sprache`) |
| Symbole/Bilder | aus dem KinoLel-Logo, erzeugt mit [`marke/bilder_erzeugen.py`](marke/bilder_erzeugen.py) |
| Installer | Deutsch/Ungarisch, Startmenü „KinoLel“ und „KinoLel (TV-Modus)“ |
| Store | MSIX-Paket (für den Microsoft Store vorbereitet): [`bundle/msix/`](bundle/msix/) |
| Updates | keine Jellyfin-Updateprüfung (später über den Microsoft Store) |
| Build | nur Windows (GitHub Actions, [`.github/workflows/windows.yml`](.github/workflows/windows.yml)) |

Alle Änderungen im Code sind mit `KinoLel` kommentiert (`git grep -n KinoLel`).

## Bauen

Automatisch bei jedem Push auf `main` über GitHub Actions (Windows-Runner). Ergebnis unter
**Actions → windows → letzter Lauf → Artifacts**:

- `windows-x64-installer` – `KinoLel-Setup-<Version>-x64.exe` (Installer)
- `windows-x64-portable` – `KinoLel-Portable-<Version>-x64.zip` (ohne Installation)
- `windows-x64-msix` – `KinoLel-<Version>.0-x64.msix` (für den Store, unsigniert),
  `KinoLel-Test-<Version>.0-x64.msix` + `KinoLel-Testzertifikat.cer` (Test)

Eine Testversion für die Familie: Version in `marke.cmake` erhöhen, committen, Tag setzen:

```bash
git tag v0.1.0 && git push origin main v0.1.0
```

Dann erscheint sie unter **Releases** mit direktem Download-Link (ohne GitHub-Anmeldung).

Bauen von Hand unter Windows: siehe [dev/windows/README.md](dev/windows/README.md) (Visual Studio 2022,
Qt 6.9.3 mit WebEngine, libmpv). Kette: MSVC 2022 x64 → Qt 6.9.3 (`qtwebengine qtwebchannel qtpositioning`) →
libmpv (shinchiro-Build) → MpvQt (Submodul `external/mpvqt`, statisch) → Inno Setup 6 → Windows SDK (`makeappx`).

## Name ändern

1. In `marke.cmake` `APP_NAME` ändern (ggf. `APP_DESCRIPTION`).
2. Bilder neu erzeugen (braucht Pillow):
   `python3 marke/bilder_erzeugen.py . --schrift /pfad/InterDisplay-Bold.otf`
   (für „KinoLel“ stattdessen `--banner banner-light.png` von kinolel.de – dann wird der Original-Schriftzug genommen).
3. Committen und pushen – Installer, Startmenü, Fenstertitel, MSIX und die Anzeige im Jellyfin-Dashboard folgen.

`APP_NAME` ist auch der Datenordner (`%LOCALAPPDATA%\<Name>`): nach der ersten Verteilung nicht mehr ändern,
sonst müssen sich alle neu anmelden. `APP_INSTALLER_GUID` nie ändern.

## Neue Jellyfin-Desktop-Versionen übernehmen

```bash
git remote add upstream https://github.com/jellyfin/jellyfin-desktop.git   # einmalig
git fetch upstream && git merge upstream/master
```

Konflikte entstehen fast nur in den mit `KinoLel` markierten Stellen. Danach Version in `marke.cmake` erhöhen.

## Dateien

Daten (Anmeldung, Einstellungen, Logs) liegen unter `%LOCALAPPDATA%\KinoLel\profiles\<profil>\`.
Eigene mpv-Einstellungen: `mpv.conf` in diesen Ordner legen.

---

Basierend auf Jellyfin Desktop (früher Jellyfin Media Player, ursprünglich Plex Media Player „Konvergo“) – © deren Mitwirkende. Lizenz GPL-2.0.
Testanleitung: [TESTANLEITUNG.md](TESTANLEITUNG.md).
