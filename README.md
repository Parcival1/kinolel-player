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

## Name und Bilder

Der Name ist endgültig **KinoLel** (Lel, 15.10.2026); Logo und Schriftzug wie auf kinolel.de.
Bilder neu erzeugen (z. B. nach Logo-Änderung, braucht Pillow):
`python3 marke/bilder_erzeugen.py . --banner banner-light.png` (Banner von kinolel.de).
`APP_NAME` (= Datenordner) und `APP_INSTALLER_GUID` nicht ändern.

## Neue Jellyfin-Desktop-Versionen übernehmen

```bash
git remote add upstream https://github.com/jellyfin/jellyfin-desktop.git   # einmalig
git fetch upstream && git merge upstream/master
```

Konflikte entstehen fast nur in den mit `KinoLel` markierten Stellen. Danach Version in `marke.cmake` erhöhen.

## Dateien

Daten (Anmeldung, Einstellungen, Logs) liegen unter `%LOCALAPPDATA%\KinoLel\profiles\<profil>\`.
Eigene mpv-Einstellungen: `mpv.conf` in diesen Ordner legen.

## Code signing policy

Windows releases of KinoLel are prepared for code signing via the SignPath Foundation:
**Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).**
Until the project is approved, release binaries are unsigned.

- Only binaries built from this repository by GitHub Actions on GitHub-hosted runners are signed
  (`KinoLel.exe` and the installer `KinoLel-Setup-*.exe`); bundled third-party libraries (Qt, libmpv) are not signed by us.
- Every signing request is approved manually in SignPath.
- **Team roles:** Committers and reviewers: [Parcival1](https://github.com/Parcival1) · Approvers: [Parcival1](https://github.com/Parcival1).
  Parts of the code are written with an AI coding assistant; all changes are pushed and released by the maintainer.
- **Privacy:** This program will not transfer any information to other networked systems unless specifically requested by the
  user or the person installing or operating it. It only connects to the KinoLel media server (`https://kinolel.de`,
  set in `marke.cmake`), which the user signs in to; there is no telemetry and no update check.

## What KinoLel does

KinoLel is a desktop client for the KinoLel media server (Jellyfin). It shows the server's web interface and plays movies
and series locally with mpv (direct play of HEVC/4K/HDR, DTS/TrueHD audio). Downloads: [Releases](../../releases).

---

Basierend auf Jellyfin Desktop (früher Jellyfin Media Player, ursprünglich Plex Media Player „Konvergo“) – © deren Mitwirkende. Lizenz GPL-2.0.
Testanleitung: [TESTANLEITUNG.md](TESTANLEITUNG.md).
