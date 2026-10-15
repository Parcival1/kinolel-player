# =====================================================================================================
#  KinoLel-Player – Marke. EINZIGE Stelle für Name, Server, Version und Store-Daten.
#
#  Name ändern (z. B. FilmLel, CineLel, MoziKino): nur APP_NAME hier anpassen und die Bilder neu
#  erzeugen (marke/README.md). Alles andere – Fenstertitel, Programmdatei, Startmenü, Installer,
#  MSIX-Paket, Anzeige im Jellyfin-Dashboard – wird beim Bauen daraus abgeleitet.
#
#  Achtung: APP_NAME ist auch der Datenordner (%LOCALAPPDATA%\<APP_NAME>). Nach der ersten Verteilung
#  an die Familie den Namen nicht mehr ändern, sonst müssen sich alle neu anmelden.
# =====================================================================================================

# Anzeigename (Fenster, Startmenü, Programmdatei <APP_NAME>.exe, Datenordner, Client-Name in Jellyfin)
set(APP_NAME "KinoLel")

# Kurzbeschreibung (Installer, Store-Paket)
set(APP_DESCRIPTION "Filme und Serien von KinoLel")

# Fester Server – es gibt keine Serverauswahl, der Player öffnet direkt die Anmeldung.
set(APP_SERVER_URL "https://kinolel.de")

# Herausgeber (Installer, Paket) und Webseite
set(APP_PUBLISHER "Lel")
set(APP_URL "https://kinolel.de")

# Version des Players (drei Zahlen; das MSIX-Paket hängt ".0" an). Bei jeder Verteilung erhöhen.
set(APP_VERSION "0.1.0")

# Technische Kennung ohne Leerzeichen/Umlaute (Dateinamen der Pakete, User-Agent)
set(APP_ID "KinoLelPlayer")

# Inno-Setup-Kennung – NIE ändern (sonst erkennt Windows Updates nicht als dieselbe App)
set(APP_INSTALLER_GUID "35069221-331e-4793-bed0-a842d0e01949")

# Microsoft Store (MSIX). Die echten Werte stehen später im Partner Center unter
# „Produktidentität“ – dann hier eintragen. Bis dahin Testwerte (Testzertifikat aus dem Build).
set(STORE_IDENTITY_NAME "KinoLel.Player")
set(STORE_PUBLISHER "CN=KinoLel Test")
set(STORE_PUBLISHER_DISPLAY_NAME "Lel")

# Farben (Logo weiß; Akzent Lavendel, Grund dunkel – wie kinolel.de)
set(APP_COLOR_ACCENT "#9aa4ff")
set(APP_COLOR_BACKGROUND "#0b0f18")
