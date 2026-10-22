#!/usr/bin/env python3
"""KinoLel-Player: Test der Meldung „Neu in …“ (Lel 22.10.2026) auf dem Windows-Runner.

1. App starten, als wäre zuletzt 0.1.3 gesehen (KINOLEL_TEST_NEUIGKEITEN_SEIT) -> Meldung muss erscheinen (Bildschirmfoto),
   „Alles klar“ anklicken.
2. App erneut starten (ohne Testvorgabe) -> Meldung darf nicht mehr erscheinen.
Aufruf: python neuigkeiten_test.py <ordner-mit-KinoLel.exe> <ausgabe-ordner>
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import psutil
import websocket

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ORDNER, AUSGABE = sys.argv[1], sys.argv[2]
os.makedirs(AUSGABE, exist_ok=True)
PORT = 9226
ergebnis = {}


def seite(frist):
    while time.time() < frist:
        try:
            for z in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3)):
                if z.get('type') == 'page' and 'kinolel.de' in z.get('url', ''):
                    return z
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return None


def js(ws, code, n=[0]):
    n[0] += 1
    ws.send(json.dumps({'id': n[0], 'method': 'Runtime.evaluate', 'params': {'expression': code, 'returnByValue': True}}))
    while True:
        a = json.loads(ws.recv())
        if a.get('id') == n[0]:
            return a.get('result', {}).get('result', {}).get('value')


def lauf(name, env_zusatz, klicken):
    env = dict(os.environ)
    env.update(env_zusatz)
    proc = subprocess.Popen([os.path.join(ORDNER, 'KinoLel.exe'), '--desktop', '--windowed', f'--remote-debugging-port={PORT}'], cwd=ORDNER, env=env)
    gefunden = None
    try:
        z = seite(time.time() + 90)
        if not z:
            return 'kinolel.de nicht geladen'
        ws = websocket.create_connection(z['webSocketDebuggerUrl'], timeout=30, suppress_origin=True)
        ende = time.time() + 45
        while time.time() < ende:
            gefunden = js(ws, "(function(){var d=document.getElementById('kl-neuigkeiten');return d?d.innerText:null})()")
            if gefunden:
                break
            time.sleep(1)
        n = [100]
        ws.send(json.dumps({'id': 999, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
        while True:
            a = json.loads(ws.recv())
            if a.get('id') == 999:
                daten = a.get('result', {}).get('data')
                if daten:
                    with open(os.path.join(AUSGABE, f'neuigkeiten-{name}.png'), 'wb') as f:
                        f.write(base64.b64decode(daten))
                break
        if gefunden and klicken:
            js(ws, "document.querySelector('#kl-neuigkeiten .kl-neu-ok').click();true")
            time.sleep(2)
        return gefunden
    finally:
        for p in reversed([psutil.Process(proc.pid)] + psutil.Process(proc.pid).children(recursive=True)):
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        time.sleep(3)


t1 = lauf('nach-update', {'KINOLEL_TEST_NEUIGKEITEN_SEIT': '0.1.3'}, True)
ergebnis['nach_update_gezeigt'] = bool(t1) and t1 != 'kinolel.de nicht geladen'
ergebnis['text'] = (t1 or '')[:600]
t2 = lauf('zweiter-start', {}, False)
ergebnis['zweiter_start_ohne_meldung'] = not t2
ok = ergebnis['nach_update_gezeigt'] and ergebnis['zweiter_start_ohne_meldung']
ergebnis['ok'] = ok
print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
with open(os.path.join(AUSGABE, 'neuigkeiten.json'), 'w', encoding='utf-8') as f:
    json.dump(ergebnis, f, ensure_ascii=False, indent=1)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
        f.write(f"\n## Meldung „Neu in …“\n\n- nach Update gezeigt: {ergebnis['nach_update_gezeigt']}\n- zweiter Start ohne Meldung: {ergebnis['zweiter_start_ohne_meldung']}\n")
