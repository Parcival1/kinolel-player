#!/usr/bin/env python3
"""KinoLel für Windows als Web-App (Electron, Lel 25.10.2026) – Test auf dem Windows-Runner (ohne GPU).

Reihenfolge (nur EINE Anmeldung je Lauf, fail2ban: > 6 Fehler in 10 Min. = Sperre):
 1. Umstieg: echte v0.1.6 (Qt) installieren, dort mit dem Hilfskonto anmelden (Passwort nur aus KINOLEL_TEST_PW, nie
    getippt/ausgegeben), schließen; dann das neue Setup so starten wie das Auto-Update der v0.1.6 (/SILENT …)
 2. Neue App: startet von selbst, Anmeldung übernommen, „Was ist neu“ einmal, Startbild bis die Seite steht,
    Name „KinoLel“ (Prozess, Fenster, kein „Electron“), eine Installation, Startmenü-Einträge
 3. Grafik-Info (Strg+Umschalt+G)
 4. Startseite beobachten (startseite.py: Flackern im Bildschirmvideo, Anfragen/DOM, CPU) – ohne neue Anmeldung
 5. Abspielen eines Testfilms (Start, Vorschaubild beim Spulen, Tonspur wechseln, Fortschritt beim Server)
 6. TV-Modus (Vollbild, TV-Oberfläche)
 7. Auto-Update: Versionsliste mit höherer Version (lokal) -> Hinweis -> „Jetzt aktualisieren“ -> Setup läuft still,
    KinoLel startet wieder
 8. Abmelden
Aufruf: python webapp_test.py <KinoLel-Setup.exe> <ausgabe-ordner>"""
import base64
import ctypes
import ctypes.wintypes as wt
import glob
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bundle', 'test'))
import startseite  # noqa: E402
from startseite import (Cdp, anmelden, anmeldefelder_leeren, cpu_je_art, cpu_sekunden, prozesse, schwaerzen,  # noqa: E402
                        seite_finden, warten, STARTSEITE_BEREIT)
import psutil  # noqa: E402

SETUP, AUS = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(AUS, exist_ok=True)
startseite.AUSGABE = AUS
PORT, PORT_ALT = 9231, 9232
ALT = 'v0.1.6'
LOCAL = os.environ['LOCALAPPDATA']
ORDNER = os.path.join(LOCAL, 'Programs', 'KinoLel')
EXE = os.path.join(ORDNER, 'KinoLel.exe')
LOG = os.path.join(LOCAL, 'KinoLel', 'App', 'kinolel.log')
TESTFILM = 'Zurück in die Zukunft II'
ergebnis = {}


def merke(name, ok, info=''):
    ergebnis[name] = {'ok': bool(ok), 'info': info}
    print(('OK     ' if ok else 'FEHLER ') + name + (f' – {info}' if info else ''), flush=True)
    return ok


def umgebung(**zusatz):
    u = dict(os.environ)
    u.pop('KINOLEL_TEST_PW', None)  # Programme brauchen das Passwort nicht
    u.update({k: str(v) for k, v in zusatz.items()})
    return u


def kinolel_prozesse():
    return [p for p in psutil.process_iter(['name', 'exe']) if (p.info['name'] or '').lower() == 'kinolel.exe']


def beenden(sanft=True, frist=25):
    """App schließen – zuerst wie ein Klick aufs X (speichert Anmeldung), notfalls hart."""
    if sanft:
        subprocess.run(['taskkill', '/IM', 'KinoLel.exe'], capture_output=True)
        ende = time.time() + frist
        while time.time() < ende and kinolel_prozesse():
            time.sleep(1)
    for p in kinolel_prozesse():
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    time.sleep(2)


def setup_still(pfad, name, env=None):
    """Wie das Auto-Update der App: Setup mit /SILENT … (startet die App danach selbst)."""
    r = subprocess.run([pfad, '/SILENT', '/SP-', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS',
                        f'/LOG={os.path.join(AUS, name + "-setup.log")}'], env=env, timeout=900)
    return r.returncode


def ziele(port):
    try:
        return json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=3))
    except Exception:  # noqa: BLE001
        return []


def dialog_finden(port, frist):
    ende = time.time() + frist
    while time.time() < ende:
        for z in ziele(port):
            if z.get('type') == 'page' and z.get('url', '').endswith('dialog.html'):
                return Cdp(z['webSocketDebuggerUrl'])
        time.sleep(0.5)
    return None


def dialog_text(d):
    return d.js("(document.getElementById('titel').textContent||'')+' | '+(document.getElementById('inhalt').textContent||'')") or ''


def bild(cdp, name):
    try:
        daten = cdp.rufe('Page.captureScreenshot', zeit=30, format='png').get('data')
        if daten:
            with open(os.path.join(AUS, name + '.png'), 'wb') as f:
                f.write(base64.b64decode(daten))
    except Exception:  # noqa: BLE001
        pass


def fenster_von(pids):
    """(Titel, Rechteck) der sichtbaren Fenster der Prozesse"""
    user32 = ctypes.windll.user32
    aus = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def je(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            puffer = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, puffer, n + 1)
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if puffer.value:
                aus.append((puffer.value, (r.left, r.top, r.right, r.bottom)))
        return True
    user32.EnumWindows(je, 0)
    return aus


def nach_vorne_und_tasten(*tasten):
    """KinoLel-Fenster nach vorne holen und echte Tasten drücken (wie ein Mensch, nicht über DevTools)"""
    user32 = ctypes.windll.user32
    ziel = []
    pids = {p.pid for p in kinolel_prozesse()}

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def je(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd):
            ziel.append(hwnd)
        return True
    user32.EnumWindows(je, 0)
    if not ziel:
        return False
    user32.keybd_event(0x12, 0, 0, 0)  # Alt: Windows erlaubt dann das Vorholen
    user32.SetForegroundWindow(ziel[0])
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.5)
    # einmal in die Seite klicken (links oben in der Kopfleiste von kinolel.de, unter der Titelleiste): die
    # Tastatur geht dann an kinolel.de – wie bei einem Menschen, der das Fenster benutzt
    r = wt.RECT()
    user32.GetWindowRect(ziel[0], ctypes.byref(r))
    user32.SetCursorPos(r.left + 30, r.top + 36 + 45)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(1)
    for vk in tasten:
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
    for vk in reversed(tasten):
        user32.keybd_event(vk, 0, 2, 0)
    return True


def app_starten(*args, **env):
    beenden()
    proc = subprocess.Popen([EXE, *args], cwd=ORDNER, env=umgebung(KINOLEL_DEVTOOLS_PORT=PORT, **env))
    z = seite_finden(time.time() + 90, PORT)
    return proc, (Cdp(z['webSocketDebuggerUrl']) if z else None)


def log_text():
    try:
        with open(LOG, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


# ---------------------------------------------------------------------------------------------------------------
def umstieg():
    """1.–2. Umstieg von der echten v0.1.6 mit Anmeldung"""
    alt_setup = os.path.join(os.environ.get('RUNNER_TEMP', AUS), f'KinoLel-Setup-{ALT[1:]}-x64.exe')
    urllib.request.urlretrieve(f'https://github.com/Parcival1/kinolel-player/releases/download/{ALT}/KinoLel-Setup-{ALT[1:]}-x64.exe', alt_setup)
    rc = setup_still(alt_setup, 'alt', env=umgebung(QTWEBENGINE_REMOTE_DEBUGGING=PORT_ALT, QTWEBENGINE_DISABLE_SANDBOX=1))
    merke(f'Alte App {ALT} installiert', rc == 0 and os.path.exists(os.path.join(ORDNER, 'Qt6Core.dll')), f'Setup {rc}')
    z = seite_finden(time.time() + 120, PORT_ALT)
    if not z:  # startete nicht von selbst -> von Hand
        subprocess.Popen([EXE, '--desktop', '--windowed', f'--remote-debugging-port={PORT_ALT}'], cwd=ORDNER,
                         env=umgebung(QTWEBENGINE_DISABLE_SANDBOX=1))
        z = seite_finden(time.time() + 120, PORT_ALT)
    if not merke('Alte App zeigt kinolel.de', z):
        return False
    cdp = Cdp(z['webSocketDebuggerUrl'])
    for d in ('Runtime.enable', 'Page.enable'):
        cdp.rufe(d)
    angemeldet = anmelden(cdp, ergebnis, 'alt')  # die EINE Anmeldung dieses Laufs
    if not angemeldet:
        anmeldefelder_leeren(cdp)
    merke('Anmeldung in der alten App', angemeldet, ergebnis.get('fehler_alt', ''))
    warten(cdp, STARTSEITE_BEREIT, time.time() + 60)
    time.sleep(5)
    beenden(sanft=True)
    if not angemeldet:
        return False
    # Neues Setup wie das Auto-Update der v0.1.6
    t0 = time.time()
    rc = setup_still(SETUP, 'neu', env=umgebung(KINOLEL_DEVTOOLS_PORT=PORT))
    merke('Neues Setup über die alte App (wie deren Auto-Update)', rc == 0, f'{round(time.time() - t0)} s')
    reste = [n for n in ('Qt6Core.dll', 'Qt6WebEngineCore.dll', 'libmpv-2.dll') if os.path.exists(os.path.join(ORDNER, n))]
    merke('Alte Programmdateien entfernt, neue da', not reste and os.path.exists(os.path.join(ORDNER, 'resources', 'app.asar')),
          ', '.join(reste))
    import winreg
    eintraege = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall') as k:
        for i in range(winreg.QueryInfoKey(k)[0]):
            name = winreg.EnumKey(k, i)
            try:
                with winreg.OpenKey(k, name) as u:
                    if 'KinoLel' in str(winreg.QueryValueEx(u, 'DisplayName')[0]):
                        eintraege.append(f"{name}: {winreg.QueryValueEx(u, 'DisplayVersion')[0]}")
            except OSError:
                pass
    merke('Genau eine KinoLel-Installation (Programme und Features)', len(eintraege) == 1, '; '.join(eintraege))
    startmenue = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs')
    links = sorted(os.path.basename(p) for p in glob.glob(os.path.join(startmenue, 'KinoLel*.lnk')))
    merke('Startmenü: KinoLel und KinoLel (TV-Modus)', len(links) == 2, ', '.join(links))
    # die neue App startet nach dem stillen Setup von selbst
    z = seite_finden(time.time() + 90, PORT)
    if not merke('Neue App startet nach dem Update von selbst', z):
        return False
    cdp = Cdp(z['webSocketDebuggerUrl'])
    for d in ('Runtime.enable', 'Page.enable'):
        cdp.rufe(d)
    d = dialog_finden(PORT, 20)
    text = dialog_text(d) if d else ''
    merke('„Was ist neu“ nach dem Umstieg', d and '0.3.0' in text, text[:160])
    if d:
        d.js("document.getElementById('kinolel-ok').click()")
    ok = warten(cdp, STARTSEITE_BEREIT, time.time() + 60)
    nie_anmelden = not cdp.js("/^#\\/login/.test(location.hash)")
    bild(cdp, '02-neue-app-startseite')
    merke('Anmeldung aus der alten App übernommen (Startseite ohne Anmelden)', ok and nie_anmelden,
          'Protokoll: ' + ('übernommen' if 'Anmeldung der bisherigen App übernommen' in log_text() else 'nichts übernommen'))
    ua = cdp.js('navigator.userAgent') or ''
    pids = {p.pid for p in kinolel_prozesse()}
    titel = [t for t, _ in fenster_von(pids)]
    merke('Name „KinoLel“: Prozess KinoLel.exe, Fenstertitel, kein „Electron“',
          pids and titel and all('Electron' not in t for t in titel) and 'Electron' not in ua and any('KinoLel' in t for t in titel),
          f'Fenster {titel}; UA …{ua[-60:]}')
    zeile = [z for z in log_text().splitlines() if 'Startbild weg nach' in z]
    merke('Startbild bis kinolel.de übernimmt (Lade-Overlay oder fertige Seite)', zeile and 'Notbremse' not in zeile[-1],
          zeile[-1].split(' ', 1)[-1] if zeile else 'keine Protokollzeile')
    # 3. Grafik-Info
    # über DevTools wie eine Tastatureingabe in der Seite; falls nicht angekommen, echte Tasten
    cdp.rufe('Input.dispatchKeyEvent', type='rawKeyDown', modifiers=10, key='G', code='KeyG', windowsVirtualKeyCode=71)
    cdp.rufe('Input.dispatchKeyEvent', type='keyUp', modifiers=10, key='G', code='KeyG', windowsVirtualKeyCode=71)
    d = dialog_finden(PORT, 12)
    if not d:
        nach_vorne_und_tasten(0x11, 0x10, 0x47)  # Strg, Umschalt, G
        d = dialog_finden(PORT, 12)
    text = d.js("document.querySelector('pre') ? document.querySelector('pre').textContent : ''") if d else ''
    with open(os.path.join(AUS, '03-grafik-info.txt'), 'w', encoding='utf-8') as f:
        f.write(text or '')
    merke('Grafik-Info (Strg+Umschalt+G)', d and 'Chromium' in (text or ''), (text or '').splitlines()[0] if text else '')
    if d:
        d.js("document.getElementById('kinolel-zu').click()")
    beenden(sanft=True)
    # „Was ist neu“ nur einmal
    proc, cdp = app_starten()
    time.sleep(6)
    merke('„Was ist neu“ beim zweiten Start nicht mehr', cdp and not dialog_finden(PORT, 3))
    beenden(sanft=True)
    return True


def startseite_beobachten():
    """4. startseite.py: Flackern (Video), Anfragen, DOM, CPU – angemeldet ist die App schon"""
    teil = {'varianten': []}
    startseite.sitzung('webapp', [EXE], ORDNER, PORT, startseite.VARIANTEN[:1], teil,
                       env={'KINOLEL_DEVTOOLS_PORT': str(PORT)}, abmelden=False)
    with open(os.path.join(AUS, 'startseite.json'), 'w', encoding='utf-8') as f:
        json.dump(teil, f, ensure_ascii=False, indent=1)
    v = (teil.get('varianten') or [{}])[0]
    fl = teil.get('flackern_anmeldung_webapp') or {}
    # Vergleich ohne Leistungsregeln (Auftrag: nur behalten, wenn sie messbar helfen)
    beenden(sanft=True)
    ohne = {'varianten': []}
    startseite.sitzung('webapp-ohne-leistungsregeln', [EXE], ORDNER, PORT, startseite.VARIANTEN[:1], ohne,
                       env={'KINOLEL_DEVTOOLS_PORT': str(PORT), 'KINOLEL_LEISTUNG': '0'}, abmelden=False)
    with open(os.path.join(AUS, 'startseite-ohne-leistungsregeln.json'), 'w', encoding='utf-8') as f:
        json.dump(ohne, f, ensure_ascii=False, indent=1)
    vo = (ohne.get('varianten') or [{}])[0]
    merke('Leistungsregeln (ohne GPU) messbar', True, f"CPU mit {v.get('cpu_prozent')} % / ohne {vo.get('cpu_prozent')} %, "
          f"GPU-Prozess {(v.get('cpu_je_prozess') or {}).get('gpu-process')} / {(vo.get('cpu_je_prozess') or {}).get('gpu-process')} %, "
          f"Layout/s {(v.get('hauptthread') or {}).get('LayoutCount_pro_s')} / {(vo.get('hauptthread') or {}).get('LayoutCount_pro_s')}")
    merke('Startseite: keine Neulade-Schleife', v and not v.get('seiten_neu_geladen') and not v.get('abschnitte_neu'),
          f"Seiten neu {v.get('seiten_neu_geladen')}, Abschnitte neu {v.get('abschnitte_neu')}")
    merke('Startseite: kein Flackern im Bildschirmvideo', isinstance(fl, dict) and not fl.get('blitzer'), json.dumps(fl)[:200])
    merke('Startseite: CPU im Leerlauf', v and (v.get('cpu_prozent') or 999) < 35, f"{v.get('cpu_prozent')} % (Runner ohne GPU, 4 Kerne)")
    beenden(sanft=True)


def abspielen():
    """5. Testfilm abspielen: Start, Vorschaubild beim Spulen, Tonspur wechseln, Fortschritt beim Server"""
    proc, cdp = app_starten()
    if not merke('App für den Abspieltest', cdp):
        return
    anfragen = []
    cdp.ereignis_rueckrufe.append(lambda m, p: anfragen.append(p.get('request', {}).get('url', '')) if m == 'Network.requestWillBeSent' else None)
    for d in ('Runtime.enable', 'Page.enable', 'Network.enable'):
        cdp.rufe(d)
    warten(cdp, STARTSEITE_BEREIT, time.time() + 60)
    film = cdp.js("ApiClient.getItems(ApiClient.getCurrentUserId(),{searchTerm:%s,IncludeItemTypes:'Movie',Recursive:true,Limit:5})"
                  ".then(function(r){var i=r.Items.filter(function(x){return x.Name===%s})[0];return i?i.Id:null})" % (json.dumps(TESTFILM), json.dumps(TESTFILM)), zeit=30)
    if not merke('Testfilm gefunden', film, TESTFILM):
        return
    cdp.js(f"location.hash='#/details?id={film}'")
    warten(cdp, "!!document.querySelector('.page:not(.hide) .btnPlay, .page:not(.hide) .btnResume')", time.time() + 30)
    time.sleep(2)
    cdp.js("(document.querySelector('.page:not(.hide) .btnResume:not(.hide)')||document.querySelector('.page:not(.hide) .btnPlay')).click()")
    laeuft = warten(cdp, "(function(){var v=document.querySelector('video');return !!v&&v.currentTime>2&&!v.paused})()", time.time() + 90)
    zustand = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){var p=(s[0]||{}).PlayState||{};"
                     "return {methode:p.PlayMethod,ton:p.AudioStreamIndex,pos:p.PositionTicks}})", zeit=20) or {}
    bild(cdp, '05-abspielen')
    merke('Abspielen: Film läuft im eingebauten Player', laeuft, f"{zustand.get('methode')}")
    if not laeuft:
        return
    # Vorschaubild beim Spulen: Maus über die Zeitleiste
    cdp.rufe('Input.dispatchMouseEvent', type='mouseMoved', x=600, y=400)
    time.sleep(1)
    r = cdp.js("(function(){var s=document.querySelector('.osdPositionSlider');if(!s)return null;var b=s.getBoundingClientRect();"
               "return [b.left,b.top,b.width,b.height]})()")
    vorschau = False
    if r:
        for anteil in (0.3, 0.5, 0.7):
            cdp.rufe('Input.dispatchMouseEvent', type='mouseMoved', x=r[0] + r[2] * anteil, y=r[1] + r[3] / 2)
            time.sleep(1.2)
        vorschau = any('/Trickplay/' in u for u in anfragen) or cdp.js(
            "(function(){var b=document.querySelector('.sliderBubble');return !!b&&!b.classList.contains('hide')&&/Trickplay/.test(b.innerHTML)})()")
        bild(cdp, '05b-vorschaubild')
    merke('Spulen: Vorschaubild (Trickplay) über der Zeitleiste', vorschau)
    # Spulen (+30 s)
    vorher = cdp.js("document.querySelector('video').currentTime") or 0
    for _ in range(3):
        cdp.rufe('Input.dispatchKeyEvent', type='rawKeyDown', key='ArrowRight', code='ArrowRight', windowsVirtualKeyCode=39)
        cdp.rufe('Input.dispatchKeyEvent', type='keyUp', key='ArrowRight', code='ArrowRight', windowsVirtualKeyCode=39)
        time.sleep(0.6)
    time.sleep(6)
    pos = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){return ((s[0]||{}).PlayState||{}).PositionTicks||0})", zeit=20) or 0
    merke('Spulen mit der Tastatur', pos / 1e7 > (vorher or 0) + 15, f'{vorher:.0f} s -> {pos / 1e7:.0f} s (Server)')
    # Tonspur wechseln über das Menü der Leiste: Ziel = eine andere Tonspur des Films als die gerade laufende
    ton_vorher = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){return ((s[0]||{}).PlayState||{}).AudioStreamIndex})", zeit=20)
    ziel = cdp.js("ApiClient.getItem(ApiClient.getCurrentUserId(),%s).then(function(i){var s=((i.MediaSources||[])[0]||{}).MediaStreams||[];"
                  "var a=s.filter(function(x){return x.Type==='Audio'&&x.Index!==%s});return a.length?(a[0].DisplayTitle||a[0].Language||''):null})"
                  % (json.dumps(film), json.dumps(ton_vorher)), zeit=20)
    cdp.rufe('Input.dispatchMouseEvent', type='mouseMoved', x=700, y=500)
    time.sleep(1)
    cdp.js("(function(){var b=document.querySelector('.btnAudio');if(b)b.click();return !!b})()")
    time.sleep(1.5)
    gewaehlt = cdp.js("(function(z){var e=[].slice.call(document.querySelectorAll('.actionSheetMenuItem'));"
                      "var k=e.filter(function(x){return z&&x.textContent.indexOf(z.slice(0,12))>=0})[0];if(k){k.click();return k.textContent.trim()}"
                      "return null})(%s)" % json.dumps(ziel))
    ton_nachher = ton_vorher
    ende = time.time() + 40
    while time.time() < ende and ton_nachher == ton_vorher:
        time.sleep(2)
        ton_nachher = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){return ((s[0]||{}).PlayState||{}).AudioStreamIndex})", zeit=20)
    merke('Tonspur wechseln (Menü der Leiste)', gewaehlt and ton_nachher != ton_vorher, f'{ton_vorher} -> {ton_nachher} ({gewaehlt})')
    # Fortschritt kommt an: Position beim Server läuft weiter
    p1 = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){return ((s[0]||{}).PlayState||{}).PositionTicks||0})", zeit=20) or 0
    time.sleep(12)
    p2 = cdp.js("ApiClient.getSessions({DeviceId:ApiClient.deviceId()}).then(function(s){return ((s[0]||{}).PlayState||{}).PositionTicks||0})", zeit=20) or 0
    merke('Fortschritt beim Server', p2 > p1, f'{p1 / 1e7:.0f} s -> {p2 / 1e7:.0f} s')
    # Vollbild aus dem Player (wie Doppelklick) = ganzes Fenster im Vollbild, danach zurück
    cdp.rufe('Runtime.evaluate', expression="document.documentElement.requestFullscreen().then(function(){return true},function(e){return String(e)})",
             userGesture=True, awaitPromise=True, returnByValue=True)
    time.sleep(2)
    user32 = ctypes.windll.user32
    breite, hoehe = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    rechtecke = [r for _, r in fenster_von({p.pid for p in kinolel_prozesse()})]
    merke('Vollbild aus dem Player: ganzes Fenster', any(r[2] - r[0] >= breite and r[3] - r[1] >= hoehe for r in rechtecke), f'{rechtecke}')
    cdp.rufe('Runtime.evaluate', expression="document.exitFullscreen().then(function(){return true},function(){return false})",
             userGesture=True, awaitPromise=True, returnByValue=True)
    time.sleep(2)
    cdp.js("(function(){var b=document.querySelector('.btnStop');if(b)b.click();else history.back();return true})()")
    time.sleep(3)
    beenden(sanft=True)


def tv_modus():
    """6. TV-Modus: Vollbild und TV-Oberfläche"""
    proc, cdp = app_starten('--tv')
    if not merke('TV-Modus startet', cdp):
        return
    tv = warten(cdp, "document.documentElement.classList.contains('layout-tv')", time.time() + 60)
    time.sleep(3)
    bild(cdp, '06-tv-modus')
    user32 = ctypes.windll.user32
    breite, hoehe = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    rechtecke = [r for _, r in fenster_von({p.pid for p in kinolel_prozesse()})]
    voll = any(r[2] - r[0] >= breite and r[3] - r[1] >= hoehe for r in rechtecke)
    merke('TV-Modus: Vollbild mit TV-Oberfläche', tv and voll, f'{rechtecke} bei {breite}x{hoehe}')
    beenden(sanft=True)
    # danach wieder Desktop-Oberfläche
    proc, cdp = app_starten()
    desktop = cdp and warten(cdp, "document.documentElement.classList.contains('layout-desktop')", time.time() + 60)
    merke('Normaler Start: wieder Desktop-Oberfläche', desktop)
    beenden(sanft=True)


def auto_update():
    """7. Versionsliste (lokal) mit 0.3.99 -> Hinweis -> Jetzt aktualisieren -> Setup still -> KinoLel wieder da"""
    ordner = os.path.join(os.environ.get('RUNNER_TEMP', AUS), 'update-server')
    os.makedirs(ordner, exist_ok=True)
    shutil.copy(SETUP, os.path.join(ordner, 'KinoLel-Setup-0.3.99-x64.exe'))
    with open(os.path.join(ordner, 'apps.json'), 'w', encoding='utf-8') as f:
        json.dump({'windows': {'version': 'v0.3.99', 'url': 'http://127.0.0.1:8766/KinoLel-Setup-0.3.99-x64.exe',
                               'datei': 'KinoLel-Setup-0.3.99-x64.exe', 'seite': 'https://kinolel.de'}}, f)

    class Leise(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=ordner, **k)

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8766), Leise)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        proc, cdp = app_starten(KINOLEL_TEST_APPS_LISTE='http://127.0.0.1:8766/apps.json')
        d = dialog_finden(PORT, 40)
        text = dialog_text(d) if d else ''
        merke('Update-Hinweis (Versionsliste mit 0.3.99)', d and '0.3.99' in text, text[:140])
        if not d:
            return
        alt_pid = proc.pid
        d.js("document.getElementById('kinolel-jetzt').click()")
        ende = time.time() + 180
        while time.time() < ende and psutil.pid_exists(alt_pid):
            time.sleep(1)
        merke('Update: App beendet sich für die Installation', not psutil.pid_exists(alt_pid))
        neu = None
        ende = time.time() + 300
        while time.time() < ende and not neu:
            neu = [p for p in kinolel_prozesse() if p.pid != alt_pid]
            time.sleep(2)
        merke('Update: Setup lief still, KinoLel startet wieder', bool(neu))
        merke('Update: KinoLel danach vollständig installiert', os.path.exists(EXE) and os.path.exists(os.path.join(ORDNER, 'resources', 'app.asar')))
    finally:
        for quelle in glob.glob(os.path.join(os.environ.get('TEMP', ''), 'KinoLel-Update.log')):
            shutil.copy(quelle, os.path.join(AUS, 'update-setup.log'))
        server.shutdown()
        beenden(sanft=True)


def abmelden():
    """8. Sitzung des Hilfskontos beenden"""
    proc, cdp = app_starten()
    ok = cdp and warten(cdp, "!!window.ApiClient && !!ApiClient.accessToken()", time.time() + 60) and cdp.js(
        "ApiClient.logout().then(function(){return true},function(){return false})", zeit=30)
    merke('Abgemeldet', ok)
    beenden(sanft=True)


def main():
    if not os.environ.get('KINOLEL_TEST_PW'):
        print('KINOLEL_TEST_PW fehlt – nur Installation geprüft')
    try:
        if umstieg():
            startseite_beobachten()
            abspielen()
            tv_modus()
            auto_update()
    except Exception as e:  # noqa: BLE001
        merke('Ablauf', False, schwaerzen(f'{type(e).__name__}: {e}')[:300])
    finally:
        try:
            abmelden()
        except Exception as e:  # noqa: BLE001
            print('Abmelden:', type(e).__name__)
        beenden(sanft=False)
        try:
            shutil.copy(LOG, os.path.join(AUS, 'kinolel.log'))
        except OSError:
            pass
        with open(os.path.join(AUS, 'ergebnis.json'), 'w', encoding='utf-8') as f:
            json.dump(ergebnis, f, ensure_ascii=False, indent=1)
        fehler = [k for k, v in ergebnis.items() if not v['ok']]
        zeilen = [f"## KinoLel Windows (Web-App) – {len(ergebnis) - len(fehler)} von {len(ergebnis)} OK", '']
        zeilen += [f"- {'✅' if v['ok'] else '❌'} {k}" + (f" – {v['info']}" if v['info'] else '') for k, v in ergebnis.items()]
        zusammenfassung = os.environ.get('GITHUB_STEP_SUMMARY')
        if zusammenfassung:
            with open(zusammenfassung, 'a', encoding='utf-8') as f:
                f.write('\n'.join(zeilen) + '\n')
        print('\n'.join(zeilen))


main()
