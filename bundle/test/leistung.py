#!/usr/bin/env python3
"""KinoLel-Player: Leistungstest auf dem Windows-Runner (GitHub Actions).

Startet KinoLel.exe in mehreren Varianten, wartet auf die Anmeldeseite von kinolel.de und misst über das
DevTools-Protokoll (--remote-debugging-port) und psutil:
  - CPU-Last der App (KinoLel.exe + QtWebEngineProcess.exe) im Leerlauf (Anmeldeseite)
  - CPU-Last und Bildrate (requestAnimationFrame) mit einer nachgebauten KinoLel-Startseite:
    Hintergrund mit Ken-Burns-Zoom, Fortschrittsbalken (width-Animation), 24 Kacheln mit backdrop-filter: blur
Der Runner hat KEINE GPU (wie eine VM ohne Grafikkarte) – die Werte zeigen den Software-Pfad.

Aufruf: python leistung.py <ordner-mit-KinoLel.exe> <ausgabe-ordner>
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

APP_ORDNER, AUSGABE = sys.argv[1], sys.argv[2]
EXE = os.path.join(APP_ORDNER, 'KinoLel.exe')
PORT = 9222
MESSDAUER = 15

VARIANTEN = [
    ('v0.1.1 Standard', {}),
    ('alt: Web-Bildschicht an (wie v0.1.0)', {'KINOLEL_WEB_LAYER': '1'}),
    ('Chromium --disable-gpu', {'QTWEBENGINE_CHROMIUM_FLAGS': '--disable-gpu'}),
    ('Qt-Render-Thread erzwungen', {'QSG_RENDER_LOOP': 'threaded'}),
]

STARTSEITE_NACHBAU = r"""
(function () {
  var s = document.createElement('style');
  s.textContent = '@keyframes klkb{from{transform:scale(1)}to{transform:scale(1.18)}}' +
    '@keyframes klpr{from{width:0}to{width:100%}}' +
    '#kltest{position:fixed;inset:0;z-index:2147483600;overflow:hidden;background:#0b0f18}' +
    '#kltest .bg{position:absolute;inset:-5%;background:radial-gradient(circle at 30% 30%,#9aa4ff,#151b2a 40%,#0b0f18),' +
    'repeating-linear-gradient(45deg,#223 0 20px,#334 20px 40px);animation:klkb 12s linear infinite alternate}' +
    '#kltest .pr{position:absolute;left:0;bottom:0;height:4px;background:#9aa4ff;animation:klpr 12s linear infinite}' +
    '#kltest .gr{position:absolute;inset:10% 5% 5% 5%;display:grid;grid-template-columns:repeat(6,1fr);gap:16px}' +
    '#kltest .k{height:150px;border-radius:12px;background:rgba(21,27,42,.35);backdrop-filter:blur(20px);' +
    '-webkit-backdrop-filter:blur(20px);border:1px solid rgba(154,164,255,.25)}';
  document.head.appendChild(s);
  var d = document.createElement('div'); d.id = 'kltest';
  var h = '<div class="bg"></div><div class="gr">';
  for (var i = 0; i < 24; i++) h += '<div class="k"></div>';
  d.innerHTML = h + '</div><div class="pr"></div>';
  document.body.appendChild(d);
  return true;
})()
"""

RAF_START = "window.__klf=0;window.__kla=true;(function f(){if(!window.__kla)return;window.__klf++;requestAnimationFrame(f)})();true"
RAF_STOP = "window.__kla=false;window.__klf"


def prozesse(wurzel):
    try:
        p = psutil.Process(wurzel)
        return [p] + p.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def cpu_sekunden(wurzel):
    summe = 0.0
    for p in prozesse(wurzel):
        try:
            t = p.cpu_times()
            summe += t.user + t.system
        except psutil.NoSuchProcess:
            pass
    return summe


def speicher_mb(wurzel):
    summe = 0
    for p in prozesse(wurzel):
        try:
            summe += p.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return round(summe / 1048576)


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.n = 0

    def rufe(self, methode, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': methode, 'params': params}))
        while True:
            antwort = json.loads(self.ws.recv())
            if antwort.get('id') == self.n:
                return antwort.get('result', {})

    def js(self, code):
        r = self.rufe('Runtime.evaluate', expression=code, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')


def seite_finden(frist):
    while time.time() < frist:
        try:
            ziele = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3))
            for z in ziele:
                if z.get('type') == 'page' and 'kinolel.de' in z.get('url', ''):
                    return z
        except Exception:
            pass
        time.sleep(1)
    return None


def messen(name, env_zusatz, nr):
    ergebnis = {'variante': name, 'env': env_zusatz}
    env = dict(os.environ)
    env.update(env_zusatz)
    proc = subprocess.Popen([EXE, '--desktop', '--windowed', f'--remote-debugging-port={PORT}', '--log-level', 'info'],
                            cwd=APP_ORDNER, env=env)
    try:
        ziel = seite_finden(time.time() + 90)
        if not ziel:
            ergebnis['fehler'] = 'kinolel.de nicht geladen (90 s)'
            ergebnis['laeuft'] = proc.poll() is None
            return ergebnis
        cdp = Cdp(ziel['webSocketDebuggerUrl'])
        for _ in range(60):
            if cdp.js("document.readyState==='complete' && !!document.querySelector('.manualLoginForm, #loginPage')"):
                break
            time.sleep(1)
        time.sleep(8)  # Lade-Overlay verschwindet, Seite ruhig

        # Leerlauf (Anmeldeseite)
        c0, t0 = cpu_sekunden(proc.pid), time.time()
        time.sleep(MESSDAUER)
        ergebnis['leerlauf_cpu_prozent'] = round((cpu_sekunden(proc.pid) - c0) / (time.time() - t0) * 100, 1)

        # Nachgebaute Startseite mit Dauer-Animationen + Blur
        cdp.js(STARTSEITE_NACHBAU)
        time.sleep(3)
        cdp.js(RAF_START)
        c0, t0 = cpu_sekunden(proc.pid), time.time()
        time.sleep(MESSDAUER)
        bilder = cdp.js(RAF_STOP) or 0
        dauer = time.time() - t0
        ergebnis['animation_cpu_prozent'] = round((cpu_sekunden(proc.pid) - c0) / dauer * 100, 1)
        ergebnis['animation_fps'] = round(bilder / dauer, 1)
        ergebnis['speicher_mb'] = speicher_mb(proc.pid)
        bild = cdp.rufe('Page.captureScreenshot', format='png').get('data')
        if bild:
            with open(os.path.join(AUSGABE, f'{nr}-bild.png'), 'wb') as f:
                f.write(base64.b64decode(bild))
        ergebnis['laeuft'] = proc.poll() is None
        return ergebnis
    except Exception as e:  # noqa: BLE001 – Test soll weiterlaufen
        ergebnis['fehler'] = repr(e)
        return ergebnis
    finally:
        for p in reversed(prozesse(proc.pid)):
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        time.sleep(4)
        # Log dieser Variante sichern (portabler Modus: Daten liegen im App-Ordner)
        for wurzel, _, dateien in os.walk(APP_ORDNER):
            if 'KinoLel.log' in dateien:
                quelle = os.path.join(wurzel, 'KinoLel.log')
                with open(quelle, encoding='utf-8', errors='replace') as f:
                    text = f.read()
                with open(os.path.join(AUSGABE, f'{nr}-KinoLel.log'), 'w', encoding='utf-8') as f:
                    f.write(text)
                ergebnis['grafik'] = [z.split('KinoLel-Grafik:', 1)[1].strip() for z in text.splitlines() if 'KinoLel-Grafik:' in z]
                break


def main():
    os.makedirs(AUSGABE, exist_ok=True)
    print('Kerne:', psutil.cpu_count(), '| CPU-Prozent = Summe aller App-Prozesse, 100 % = ein voller Kern')
    alle = []
    for nr, (name, env) in enumerate(VARIANTEN, 1):
        e = messen(name, env, nr)
        print(json.dumps(e, ensure_ascii=False))
        alle.append(e)
    with open(os.path.join(AUSGABE, 'leistung.json'), 'w', encoding='utf-8') as f:
        json.dump({'kerne': psutil.cpu_count(), 'messdauer_s': MESSDAUER, 'ergebnisse': alle}, f, ensure_ascii=False, indent=1)
    zeilen = ['## KinoLel-Leistungstest (Runner ohne GPU)', '',
              '| Variante | Leerlauf CPU % | Animation CPU % | Animation Bilder/s | Speicher MB | Fehler |',
              '|---|---|---|---|---|---|']
    for e in alle:
        zeilen.append(f"| {e['variante']} | {e.get('leerlauf_cpu_prozent', '–')} | {e.get('animation_cpu_prozent', '–')} | "
                      f"{e.get('animation_fps', '–')} | {e.get('speicher_mb', '–')} | {e.get('fehler', '')} |")
    text = '\n'.join(zeilen) + '\n'
    print(text)
    with open(os.path.join(AUSGABE, 'leistung.md'), 'w', encoding='utf-8') as f:
        f.write(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(text)


if __name__ == '__main__':
    main()
