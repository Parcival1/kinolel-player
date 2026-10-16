#!/usr/bin/env python3
"""KinoLel-Player: Test des Auto-Updates auf dem Windows-Runner.

1. Installer dieses Builds still installieren (pro Benutzer).
2. Installierte App mit KINOLEL_TEST_VERSION=0.0.1 starten (gibt sich als alte Version aus).
3. Über das DevTools-Protokoll prüfen, dass der Update-Hinweis erscheint (GitHub-Release gefunden).
4. „Jetzt aktualisieren“ auslösen -> App lädt den Installer des neuesten Releases, startet ihn still und beendet sich.
5. Prüfen: Installer-Datei geladen, App beendet, Installation danach vorhanden.
Aufruf: python update_test.py <Setup.exe> <ausgabe-ordner>
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import psutil
import websocket

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SETUP, AUSGABE = sys.argv[1], sys.argv[2]
os.makedirs(AUSGABE, exist_ok=True)
PORT = 9223
ergebnis = {}


def cdp_seite(frist):
    while time.time() < frist:
        try:
            for z in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3)):
                if z.get('type') == 'page' and 'kinolel.de' in z.get('url', ''):
                    return z
        except Exception:
            pass
        time.sleep(1)
    return None


def js(ws, code, n=[0]):
    n[0] += 1
    ws.send(json.dumps({'id': n[0], 'method': 'Runtime.evaluate',
                        'params': {'expression': code, 'returnByValue': True, 'awaitPromise': True}}))
    while True:
        a = json.loads(ws.recv())
        if a.get('id') == n[0]:
            return a.get('result', {}).get('result', {}).get('value')


# 1. Installieren
r = subprocess.run([SETUP, '/VERYSILENT', '/SP-', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER'], timeout=600)
exe = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'KinoLel', 'KinoLel.exe')
ergebnis['installiert'] = os.path.exists(exe)
print('Installiert:', exe, ergebnis['installiert'])
# Der Installer startet die App im stillen Modus selbst (WizardSilent) -> beenden
time.sleep(8)
for p in psutil.process_iter(['name']):
    if p.info['name'] in ('KinoLel.exe', 'QtWebEngineProcess.exe'):
        p.kill()
time.sleep(3)

# 2. App als „alte Version“ starten
env = dict(os.environ, KINOLEL_TEST_VERSION='0.0.1')
app = subprocess.Popen([exe, '--desktop', '--windowed', f'--remote-debugging-port={PORT}', '--log-level', 'info'], env=env)
ziel = cdp_seite(time.time() + 90)
ergebnis['seite_geladen'] = bool(ziel)
if ziel:
    ws = websocket.create_connection(ziel['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
    # 3. Hinweis abwarten (Dialog von Jellyfin-Web mit unserem Titel)
    gefunden = False
    for _ in range(60):
        text = js(ws, "document.body ? document.body.innerText : ''") or ''
        if 'Update verfügbar' in text or 'Frissítés elérhető' in text:
            gefunden = True
            break
        time.sleep(1)
    ergebnis['hinweis_erschienen'] = gefunden
    print('Hinweis erschienen:', gefunden)
    # 4. „Jetzt aktualisieren“ klicken
    if gefunden:
        geklickt = js(ws, """(function(){var b=[...document.querySelectorAll('button')].find(x=>/Jetzt aktualisieren|Frissítés most/.test(x.textContent));
            if(b){b.click();return true}return false})()""")
        ergebnis['geklickt'] = geklickt
        print('Geklickt:', geklickt)
        # 5. App beendet sich nach dem Laden des Installers
        try:
            app.wait(timeout=240)
            ergebnis['app_beendet'] = True
        except subprocess.TimeoutExpired:
            ergebnis['app_beendet'] = False
        geladen = glob.glob(os.path.join(tempfile.gettempdir(), 'KinoLel-Setup-*.exe'))
        ergebnis['installer_geladen'] = [os.path.basename(g) + f' ({os.path.getsize(g) // 1048576} MB)' for g in geladen]
        print('Installer geladen:', ergebnis['installer_geladen'])
        # Installer läuft still; warten bis fertig
        for _ in range(180):
            if not any(p.info['name'].startswith('KinoLel-Setup') for p in psutil.process_iter(['name'])):
                break
            time.sleep(2)
        ergebnis['nach_update_vorhanden'] = os.path.exists(exe)
for p in psutil.process_iter(['name']):
    if p.info['name'] in ('KinoLel.exe', 'QtWebEngineProcess.exe'):
        p.kill()
logs = glob.glob(os.path.join(os.environ['LOCALAPPDATA'], 'KinoLel', '**', 'KinoLel.log'), recursive=True)
if logs:
    with open(logs[0], encoding='utf-8', errors='replace') as f:
        ergebnis['log_update'] = [z.strip() for z in f if 'KinoLel-Update' in z][-10:]
print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
with open(os.path.join(AUSGABE, 'update-test.json'), 'w', encoding='utf-8') as f:
    json.dump(ergebnis, f, ensure_ascii=False, indent=1)
text = '## KinoLel Auto-Update-Test\n\n' + '\n'.join(f'- **{k}**: {v}' for k, v in ergebnis.items()) + '\n'
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
        f.write(text)
