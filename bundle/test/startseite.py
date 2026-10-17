#!/usr/bin/env python3
"""KinoLel-Player: Startseiten-Test auf dem Windows-Runner (ohne GPU, wie Lels VM 123).

Lel 17.10.: „Es flackert konstant auf dem Startbildschirm, es lädt die ganze Zeit alle Elemente neu.“
Der Test startet KinoLel.exe, meldet sich mit dem Hilfskonto an (Passwort nur aus der Umgebung KINOLEL_TEST_PW,
GitHub-Secret, wird nie ausgegeben) und beobachtet die Startseite je Variante BEOBACHTUNG Sekunden:
  - Video des Bildschirms (ffmpeg gdigrab, sonst Einzelbilder der Seite)
  - Netzwerk-Anfragen pro Sekunde (DevTools-Protokoll, nur Pfade ohne Abfrageteil -> keine Zugangsschlüssel)
  - DOM-Mutationen pro Sekunde, neu eingefügte Startseiten-Abschnitte, Karussell-Neuaufbau, Seiten-Neuladen, Hash-Wechsel
  - CPU-Last der App
Varianten ersetzen kinolel.js (Jellyfin-Zusatz von kinolel.de) per Fetch-Abfangen, ohne den Server zu ändern:
so lässt sich eingrenzen, welcher Teil das Neuladen auslöst.

Aufruf: python startseite.py <ordner-mit-KinoLel.exe> <ausgabe-ordner>
Umgebung: KINOLEL_TEST_PW (Pflicht), KINOLEL_TEST_USER (Standard kinolel-hilfe), BEOBACHTUNG (Sekunden, Standard 60),
          VARIANTEN (Komma-Liste der Namen unten, Standard alle)
"""
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

import psutil
import websocket

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
APP_ORDNER, AUSGABE = sys.argv[1], sys.argv[2]
PORT = 9224
BENUTZER = os.environ.get('KINOLEL_TEST_USER', 'kinolel-hilfe')
PASSWORT = (os.environ.get('KINOLEL_TEST_PW') or '').strip('\r\n')
BEOBACHTUNG = int(os.environ.get('BEOBACHTUNG', '60'))

# Varianten: Name -> Änderung an kinolel.js (None = unverändert, 'leer' = gar nicht laden, Liste = (Muster, Ersatz) als Regex)
VARIANTEN = [
    ('original', None),
    ('ohne-kinolel-js', 'leer'),
    ('ohne-karussellNachstarten', [(r'setInterval\(karussellNachstarten, 4000\);', ''), (r'karussellNachstarten\(\);', '')]),
    ('ohne-kopfUeberlauf', [(r'kopfUeberlauf\(\);', '')]),
    ('ohne-spracheNachLogin', [(r'spracheNachLogin\(\);', '')]),
]
if os.environ.get('VARIANTEN'):
    gewuenscht = [v.strip() for v in os.environ['VARIANTEN'].split(',')]
    VARIANTEN = [v for v in VARIANTEN if v[0] in gewuenscht]

# Läuft in jeder geladenen Seite vor allen Seitenskripten (Page.addScriptToEvaluateOnNewDocument)
BEOBACHTER = r"""
(function () {
  if (window.__klBeob) return;
  var B = window.__klBeob = { t0: Date.now(), sek: {}, ziele: {}, zieleAnzahl: 0, abschnitte: 0, abschnitteWeg: 0,
    karussell: 0, bootstrap: 0, verlauf: [], fehler: [] };
  function sekunde() {
    var s = Math.floor((Date.now() - B.t0) / 1000);
    return B.sek[s] || (B.sek[s] = { m: 0, plus: 0, minus: 0, attr: 0, text: 0, abschnitte: 0, abschnitteWeg: 0 });
  }
  function name(e) {
    if (!e || e.nodeType !== 1) return (e && e.nodeName) || '?';
    var n = e.tagName.toLowerCase();
    if (e.id) n += '#' + e.id;
    var k = (typeof e.className === 'string' ? e.className : '').trim().split(/\s+/).filter(Boolean).slice(0, 3);
    if (k.length) n += '.' + k.join('.');
    return n.slice(0, 90);
  }
  function pfad(e) {
    var a = e && e.parentElement, id = '';
    while (a && !id) { if (a.id) id = a.tagName.toLowerCase() + '#' + a.id; a = a.parentElement; }
    return (id ? id + ' > ' : '') + name(e);
  }
  function zaehle(k) {
    if (!(k in B.ziele)) { if (B.zieleAnzahl > 4000) k = '(weitere)'; else B.zieleAnzahl++; }
    B.ziele[k] = (B.ziele[k] || 0) + 1;
  }
  var ABSCHNITT = '.verticalSection, .homeSection, [class*="homeSection"], .section0, .section1, .section2, .section3, .section4, .section5, .section6, .section7, .section8, .section9';
  function istAbschnitt(n) { try { return n.nodeType === 1 && n.matches(ABSCHNITT) && !!n.closest('#indexPage'); } catch (e) { return false; } }
  new MutationObserver(function (liste) {
    var s = sekunde();
    for (var i = 0; i < liste.length; i++) {
      var r = liste[i], j, n;
      s.m++;
      if (r.type === 'childList') {
        s.plus += r.addedNodes.length; s.minus += r.removedNodes.length;
        zaehle('kind ' + pfad(r.target));
        for (j = 0; j < r.addedNodes.length; j++) {
          n = r.addedNodes[j];
          if (istAbschnitt(n)) { s.abschnitte++; B.abschnitte++; }
          if (n.nodeType === 1 && (n.id === 'slides-container' || (n.querySelector && n.querySelector('#slides-container')))) B.karussell++;
        }
        for (j = 0; j < r.removedNodes.length; j++) {
          n = r.removedNodes[j];
          if (n.nodeType === 1 && n.matches) { try { if (n.matches(ABSCHNITT)) { s.abschnitteWeg++; B.abschnitteWeg++; } } catch (e) { /* egal */ } }
        }
      } else if (r.type === 'attributes') {
        s.attr++;
        zaehle('attr ' + r.attributeName + ' ' + pfad(r.target));
      } else {
        s.text++;
      }
    }
  }).observe(document, { childList: true, subtree: true, attributes: true, characterData: true });
  function zeit() { return Date.now() - B.t0; }
  ['pushState', 'replaceState'].forEach(function (f) {
    var o = history[f];
    history[f] = function () { B.verlauf.push([zeit(), f, String(arguments[2] || '').slice(0, 120)]); return o.apply(this, arguments); };
  });
  addEventListener('hashchange', function () { B.verlauf.push([zeit(), 'hashchange', location.hash.slice(0, 120)]); });
  addEventListener('beforeunload', function () { B.verlauf.push([zeit(), 'beforeunload', '']); });
  addEventListener('error', function (e) { if (B.fehler.length < 50) B.fehler.push([zeit(), String(e.message || (e.target && e.target.src) || e.type).slice(0, 200)]); }, true);
  // Media Bar: Aufrufe von slideshowPure.bootstrap() zählen
  var t = setInterval(function () {
    var sp = window.slideshowPure;
    if (sp && typeof sp.bootstrap === 'function' && !sp.bootstrap.__kl) {
      var o = sp.bootstrap;
      sp.bootstrap = function () { B.bootstrap++; B.verlauf.push([zeit(), 'slideshowPure.bootstrap', '']); return o.apply(this, arguments); };
      sp.bootstrap.__kl = true;
    }
  }, 300);
})();
"""

ZUSTAND = r"""
(function () {
  var B = window.__klBeob;
  if (!B) return null;
  var sp = window.slideshowPure, st = sp && sp.STATE && sp.STATE.slideshow;
  return { t0: B.t0, sek: B.sek, abschnitte: B.abschnitte, abschnitteWeg: B.abschnitteWeg, karussell: B.karussell,
    bootstrap: B.bootstrap, verlauf: B.verlauf, fehler: B.fehler, hash: location.hash.slice(0, 120),
    karussellDa: !!document.getElementById('slides-container'),
    karussellZustand: st ? { hasInitialized: st.hasInitialized, isBootstrapping: st.isBootstrapping, isLoading: st.isLoading,
      totalItems: st.totalItems, firstSlideShown: st.firstSlideShown } : null,
    abschnitteJetzt: document.querySelectorAll('#indexPage:not(.hide) .verticalSection').length,
    fenster: [innerWidth, innerHeight, devicePixelRatio], sprache: document.documentElement.lang,
    culture: document.documentElement.getAttribute('data-culture') };
})()
"""

ZIELE = "(function(){var B=window.__klBeob;if(!B)return null;return Object.keys(B.ziele).map(function(k){return [k,B.ziele[k]]}).sort(function(a,b){return b[1]-a[1]}).slice(0,40)})()"

GEHEIM = [
    (re.compile(r'(api_key|ApiKey|apikey|X-Emby-Token|X-MediaBrowser-Token|access_?token|Token)(["\']?\s*[=:]\s*["\']?)[A-Za-z0-9\-_.]{12,}', re.I), r'\1\2***'),
    (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?)[^"\'\r\n]+', re.I), r'\1***'),
]


def schwaerzen(text):
    text = str(text)
    for muster, ersatz in GEHEIM:
        text = muster.sub(ersatz, text)
    if PASSWORT and len(PASSWORT) >= 4:
        text = text.replace(PASSWORT, '***')
    return text


def pfad_ohne_abfrage(url):
    url = url.split('#', 1)[0]
    teile = url.split('?', 1)
    basis = re.sub(r'^https?://', '', teile[0])
    basis = re.sub(r'/[0-9a-f]{32}(?=/|$)', '/{id}', basis)  # Element-IDs zusammenfassen
    return basis[:160]


class Cdp:
    """DevTools-Verbindung mit Lese-Thread (Ereignisse + Antworten)."""

    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
        self.n = 0
        self.sperre = threading.Lock()
        self.antworten = {}
        self.warte = {}
        self.ereignis_rueckrufe = []
        self.offen = True
        threading.Thread(target=self._lesen, daemon=True).start()

    def _lesen(self):
        while self.offen:
            try:
                nachricht = json.loads(self.ws.recv())
            except Exception:  # noqa: BLE001
                self.offen = False
                for e in self.warte.values():
                    e.set()
                return
            if 'id' in nachricht:
                self.antworten[nachricht['id']] = nachricht
                e = self.warte.get(nachricht['id'])
                if e:
                    e.set()
            else:
                for r in list(self.ereignis_rueckrufe):
                    try:
                        r(nachricht.get('method'), nachricht.get('params', {}))
                    except Exception as fehler:  # noqa: BLE001
                        print('Rückruf-Fehler', repr(fehler))

    def senden(self, methode, **params):
        with self.sperre:
            self.n += 1
            nr = self.n
            self.ws.send(json.dumps({'id': nr, 'method': methode, 'params': params}))
        return nr

    def rufe(self, methode, zeit=60, **params):
        with self.sperre:
            self.n += 1
            nr = self.n
            e = self.warte[nr] = threading.Event()
            self.ws.send(json.dumps({'id': nr, 'method': methode, 'params': params}))
        e.wait(zeit)
        self.warte.pop(nr, None)
        antwort = self.antworten.pop(nr, {})
        return antwort.get('result', {})

    def js(self, code, zeit=60):
        r = self.rufe('Runtime.evaluate', zeit=zeit, expression=code, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')


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


def seite_finden(frist, port):
    while time.time() < frist:
        try:
            for z in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=3)):
                if z.get('type') == 'page' and 'kinolel.de' in z.get('url', ''):
                    return z
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return None


def ffmpeg_pfad():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


class Aufnahme:
    """Bildschirmvideo per ffmpeg gdigrab (ganzer Bildschirm = echtes App-Fenster inkl. Qt-Darstellung)."""

    def __init__(self, ziel):
        self.ziel = ziel
        self.proc = None
        exe = ffmpeg_pfad()
        if not exe:
            return
        self.proc = subprocess.Popen([exe, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'gdigrab', '-framerate', '10',
                                      '-draw_mouse', '0', '-i', 'desktop', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                                      '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-pix_fmt', 'yuv420p', ziel],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def stop(self):
        if not self.proc:
            return None
        try:
            self.proc.communicate(b'q', timeout=30)
        except Exception:  # noqa: BLE001
            self.proc.kill()
        fehler = (self.proc.stderr.read().decode(errors='replace') if self.proc.stderr and not self.proc.stderr.closed else '')
        return os.path.exists(self.ziel) and os.path.getsize(self.ziel) > 1000, fehler[-400:]


def warten(cdp, ausdruck, frist, pause=0.5):
    while time.time() < frist:
        try:
            if cdp.js(ausdruck, zeit=10):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(pause)
    return False


STARTSEITE_BEREIT = ("(function(){return /^#\\/home/.test(location.hash) && "
                     "document.querySelectorAll('#indexPage:not(.hide) .verticalSection, #indexPage:not(.hide) .homeSection').length > 0})()")


def anmelden(cdp, ergebnis, teil):
    if not warten(cdp, "!!document.querySelector('#loginPage:not(.hide), #indexPage:not(.hide)')", time.time() + 90):
        ergebnis['fehler_' + teil] = 'weder Anmeldung noch Startseite nach 90 s'
        return False
    if cdp.js("!!document.querySelector('#indexPage:not(.hide)')"):
        return True  # schon angemeldet
    if not PASSWORT:
        time.sleep(10)
        ergebnis['fehler_' + teil] = 'Trockenlauf: Secret KINOLEL_TEST_PW fehlt, nur Anmeldeseite geladen'
        return False
    time.sleep(3)
    cdp.js("(function(){var f=document.querySelector('#loginPage .manualLoginForm');"
           "if(f&&f.classList.contains('hide')){var b=document.querySelector('#loginPage .btnManual');if(b)b.click();}return true})()")
    time.sleep(1)
    cdp.js("(function(){var n=document.querySelector('#txtManualName');n.focus();n.value=%s;"
           "n.dispatchEvent(new Event('input',{bubbles:true}));n.dispatchEvent(new Event('change',{bubbles:true}));"
           "var p=document.querySelector('#txtManualPassword');p.value='';p.focus();return true})()" % json.dumps(BENUTZER))
    cdp.rufe('Input.insertText', text=PASSWORT)  # Passwort nur als Tastatureingabe, nie als Skripttext
    time.sleep(0.5)
    if not cdp.js("document.querySelector('#txtManualPassword').value.length > 0"):
        feld = cdp.rufe('Runtime.evaluate', expression="document.querySelector('#txtManualPassword')").get('result', {})
        cdp.rufe('Runtime.callFunctionOn', objectId=feld.get('objectId'), arguments=[{'value': PASSWORT}],
                 functionDeclaration="function(w){this.value=w;this.dispatchEvent(new Event('input',{bubbles:true}));}")
    cdp.js("(function(){var b=document.querySelector('#loginPage .manualLoginForm button[type=submit]');"
           "if(b){b.click();return true}var f=document.querySelector('#loginPage .manualLoginForm');"
           "f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));return true})()")
    if warten(cdp, "/^#\\/home/.test(location.hash)", time.time() + 45):
        return True
    toast = cdp.js("Array.from(document.querySelectorAll('.toast')).map(function(t){return t.textContent}).join(' | ')")
    ergebnis['fehler_' + teil] = 'Anmeldung fehlgeschlagen: ' + schwaerzen(toast or '(kein Hinweis)')[:300]
    return False


def beobachten(cdp, proc, nr, name, aenderung, ereignisse):
    """Eine Variante: kinolel.js-Ersatz setzen, Seite neu laden, BEOBACHTUNG s aufnehmen und zählen."""
    v = {'variante': name}
    ereignisse['aenderung'] = aenderung
    ereignisse['anfragen'] = []
    ereignisse['navigation'] = []
    ereignisse['konsole'] = []
    ereignisse['kinolel_js'] = 0
    cdp.rufe('Page.reload', ignoreCache=True)
    t_reload = time.time()
    bereit = warten(cdp, STARTSEITE_BEREIT, time.time() + 60)
    v['startseite_nach_s'] = round(time.time() - t_reload, 1) if bereit else None
    if not bereit:
        v['fehler'] = 'Startseite nach Neuladen nicht bereit (60 s)'
    time.sleep(2)
    video = os.path.join(AUSGABE, f'{nr}-{name}.mp4')
    aufnahme = Aufnahme(video)
    ereignisse['anfragen'] = []  # nur der Beobachtungszeitraum zählt
    ereignisse['navigation'] = []
    nav_vorher = len(ereignisse['navigation'])
    start_js = cdp.js('Date.now()')
    c0, t0 = cpu_sekunden(proc.pid), time.time()
    bilder = []
    while time.time() - t0 < BEOBACHTUNG:
        time.sleep(1)
        s = int(time.time() - t0)
        if s % 10 == 0 and s not in bilder:
            bilder.append(s)
            daten = cdp.rufe('Page.captureScreenshot', zeit=20, format='jpeg', quality=60).get('data')
            if daten:
                with open(os.path.join(AUSGABE, f'{nr}-{name}-{s:02d}s.jpg'), 'wb') as f:
                    f.write(base64.b64decode(daten))
    dauer = time.time() - t0
    v['cpu_prozent'] = round((cpu_sekunden(proc.pid) - c0) / dauer * 100, 1)
    a = aufnahme.stop()
    if a:
        v['video'] = os.path.basename(video) if a[0] else None
        if a[1]:
            v['video_fehler'] = a[1]
    zustand = cdp.js(ZUSTAND) or {}
    ziele = cdp.js(ZIELE) or []
    # Mutationen nur im Beobachtungszeitraum (ab start_js)
    sek = zustand.get('sek') or {}
    t0_seite = zustand.get('t0') or 0
    ab = int(((start_js or 0) - t0_seite) / 1000) if start_js and t0_seite else 0
    reihen = [(int(k), w) for k, w in sek.items() if int(k) >= ab]
    def summe(feld):
        return sum(w.get(feld, 0) for _, w in reihen)
    v['dom_mutationen'] = summe('m')
    v['dom_mutationen_pro_s'] = round(summe('m') / dauer, 1)
    v['knoten_eingefuegt_pro_s'] = round(summe('plus') / dauer, 1)
    v['knoten_entfernt_pro_s'] = round(summe('minus') / dauer, 1)
    v['attribut_aenderungen_pro_s'] = round(summe('attr') / dauer, 1)
    v['abschnitte_neu'] = summe('abschnitte')
    v['abschnitte_entfernt'] = summe('abschnitteWeg')
    v['karussell_neu_aufgebaut_gesamt'] = zustand.get('karussell')
    v['bootstrap_aufrufe_gesamt'] = zustand.get('bootstrap')
    v['abschnitte_jetzt'] = zustand.get('abschnitteJetzt')
    v['karussell_da'] = zustand.get('karussellDa')
    v['karussell_zustand'] = zustand.get('karussellZustand')
    v['fenster'] = zustand.get('fenster')
    v['sprache'] = [zustand.get('sprache'), zustand.get('culture')]
    v['hash'] = zustand.get('hash')
    v['verlauf'] = [x for x in (zustand.get('verlauf') or [])][-40:]
    v['fehler_seite'] = (zustand.get('fehler') or [])[:20]
    v['mutationen_je_sekunde'] = [[k - ab, w.get('m', 0), w.get('plus', 0), w.get('minus', 0), w.get('abschnitte', 0)] for k, w in sorted(reihen)]
    v['top_mutationsziele'] = ziele[:30]
    anfragen = ereignisse['anfragen']
    v['anfragen'] = len(anfragen)
    v['anfragen_pro_s'] = round(len(anfragen) / dauer, 2)
    je_s = {}
    je_pfad = {}
    for t, methode, typ, pfad in anfragen:
        je_s[int(t - t0)] = je_s.get(int(t - t0), 0) + 1
        k = f'{methode} {typ} {pfad}'
        je_pfad[k] = je_pfad.get(k, 0) + 1
    v['anfragen_max_pro_s'] = max(je_s.values()) if je_s else 0
    v['anfragen_je_sekunde'] = [je_s.get(i, 0) for i in range(int(dauer) + 1)]
    v['top_anfragen'] = sorted(je_pfad.items(), key=lambda x: -x[1])[:30]
    v['seiten_neu_geladen'] = len([n for n in ereignisse['navigation'][nav_vorher:] if n[1] == 'frameNavigated'])
    v['navigation'] = ereignisse['navigation'][nav_vorher:][:40]
    v['kinolel_js_ersetzt'] = ereignisse['kinolel_js']
    v['konsole'] = ereignisse['konsole'][:60]
    return v


def sitzung(teil, befehl, cwd, port, varianten, ergebnis):
    """Programm (KinoLel-App oder Chrome als Vergleich) starten, anmelden, Varianten beobachten, abmelden."""
    proc = subprocess.Popen(befehl, cwd=cwd)
    cdp = None
    try:
        ziel = seite_finden(time.time() + 90, port)
        if not ziel:
            ergebnis['fehler_' + teil] = 'kinolel.de nicht geladen (90 s)'
            return
        cdp = Cdp(ziel['webSocketDebuggerUrl'])
        ereignisse = {'anfragen': [], 'navigation': [], 'konsole': [], 'aenderung': None, 'kinolel_js': 0}

        def bei_ereignis(methode, p):
            if methode == 'Network.requestWillBeSent':
                r = p.get('request', {})
                ereignisse['anfragen'].append((time.time(), r.get('method', ''), p.get('type', ''), pfad_ohne_abfrage(r.get('url', ''))))
            elif methode == 'Network.webSocketCreated':
                ereignisse['anfragen'].append((time.time(), 'WS', 'WebSocket', pfad_ohne_abfrage(p.get('url', ''))))
            elif methode == 'Page.frameNavigated' and not p.get('frame', {}).get('parentId'):
                ereignisse['navigation'].append((round(time.time(), 1), 'frameNavigated', pfad_ohne_abfrage(p['frame'].get('url', ''))))
            elif methode == 'Page.navigatedWithinDocument':
                ereignisse['navigation'].append((round(time.time(), 1), 'imDokument', schwaerzen(p.get('url', '').split('#', 1)[-1][:120])))
            elif methode == 'Runtime.consoleAPICalled':
                if len(ereignisse['konsole']) < 200:
                    text = ' '.join(str(a.get('value', a.get('description', '')))[:200] for a in p.get('args', []))
                    ereignisse['konsole'].append((p.get('type'), schwaerzen(text)[:300]))
            elif methode == 'Fetch.requestPaused':
                threading.Thread(target=abfangen, args=(p,), daemon=True).start()

        def abfangen(p):
            rid = p['requestId']
            aenderung = ereignisse['aenderung']
            if aenderung is None:
                cdp.senden('Fetch.continueRequest', requestId=rid)
                return
            koerper = cdp.rufe('Fetch.getResponseBody', requestId=rid)
            text = koerper.get('body', '')
            if koerper.get('base64Encoded'):
                text = base64.b64decode(text).decode('utf-8', errors='replace')
            if aenderung == 'leer':
                text = '/* KinoLel-Test: kinolel.js abgeschaltet */'
            else:
                for muster, ersatz in aenderung:
                    text, n = re.subn(muster, ersatz, text)
                    if n == 0:
                        print(f'Hinweis: Muster nicht gefunden: {muster}')
            ereignisse['kinolel_js'] += 1
            cdp.senden('Fetch.fulfillRequest', requestId=rid, responseCode=200,
                       responseHeaders=[{'name': 'Content-Type', 'value': 'application/javascript; charset=utf-8'},
                                        {'name': 'Cache-Control', 'value': 'no-store'}],
                       body=base64.b64encode(text.encode('utf-8')).decode())

        cdp.ereignis_rueckrufe.append(bei_ereignis)
        for d in ('Network.enable', 'Page.enable', 'Runtime.enable'):
            cdp.rufe(d)
        cdp.rufe('Network.setCacheDisabled', cacheDisabled=False)
        cdp.rufe('Page.addScriptToEvaluateOnNewDocument', source=BEOBACHTER)
        cdp.rufe('Fetch.enable', patterns=[{'urlPattern': '*/kinolel/kinolel.js*', 'requestStage': 'Response'}])

        # Anmelden (Bildschirmvideo der Anmeldung + ersten Startseite)
        aufnahme = Aufnahme(os.path.join(AUSGABE, f'{teil}-0-anmeldung.mp4'))
        t_anm = time.time()
        ok = anmelden(cdp, ergebnis, teil)
        if ok:
            ergebnis['startseite_bereit_' + teil] = warten(cdp, STARTSEITE_BEREIT, time.time() + 60)
            ergebnis['anmeldung_bis_startseite_s_' + teil] = round(time.time() - t_anm, 1)
            time.sleep(min(BEOBACHTUNG, 30))  # erste Startseite nach der Anmeldung (wie bei Lel) mit aufnehmen
        aufnahme.stop()
        daten = cdp.rufe('Page.captureScreenshot', format='jpeg', quality=60).get('data')
        if daten:
            with open(os.path.join(AUSGABE, f'{teil}-0-nach-anmeldung.jpg'), 'wb') as f:
                f.write(base64.b64decode(daten))
        if not ok:
            return
        for nr, (name, aenderung) in enumerate(varianten, 1):
            v = beobachten(cdp, proc, f'{teil}-{nr}', name, aenderung, ereignisse)
            v['teil'] = teil
            kurz = {k: v.get(k) for k in ('variante', 'anfragen_pro_s', 'anfragen_max_pro_s', 'dom_mutationen_pro_s', 'knoten_eingefuegt_pro_s',
                                          'abschnitte_neu', 'seiten_neu_geladen', 'bootstrap_aufrufe_gesamt', 'cpu_prozent', 'fehler')}
            print(json.dumps(kurz, ensure_ascii=False))
            ergebnis['varianten'].append(v)
    except Exception as e:  # noqa: BLE001
        ergebnis['fehler_' + teil] = schwaerzen(repr(e))
    finally:
        if cdp and cdp.offen:
            try:  # Sitzung des Hilfskontos beenden (Zugangsschlüssel wird damit ungültig)
                ergebnis['abgemeldet_' + teil] = cdp.js("(function(){var a=window.ApiClient;if(!a||!a.logout)return false;"
                                                "return a.logout().then(function(){return true},function(){return false})})()", zeit=20)
            except Exception:  # noqa: BLE001
                pass
        for p in reversed(prozesse(proc.pid)):
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        time.sleep(3)


def main():
    os.makedirs(AUSGABE, exist_ok=True)
    ergebnis = {'benutzer': BENUTZER, 'beobachtung_s': BEOBACHTUNG, 'kerne': psutil.cpu_count(), 'varianten': []}
    if not PASSWORT:
        print('KINOLEL_TEST_PW fehlt (GitHub-Secret) - nur Trockenlauf bis zur Anmeldeseite')
    exe = os.path.join(APP_ORDNER, 'KinoLel.exe')
    sitzung('app', [exe, '--desktop', '--windowed', f'--remote-debugging-port={PORT}', '--log-level', 'debug'], APP_ORDNER, PORT,
            VARIANTEN, ergebnis)
    for wurzel, _, dateien in os.walk(APP_ORDNER):
        if 'KinoLel.log' in dateien:
            with open(os.path.join(wurzel, 'KinoLel.log'), encoding='utf-8', errors='replace') as f:
                text = f.read()
            with open(os.path.join(AUSGABE, 'KinoLel.log'), 'w', encoding='utf-8') as f:
                f.write(schwaerzen(text))
            break
    # Vergleich: Google Chrome auf demselben Runner (Lel: „im Browser flüssig“)
    chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    if os.environ.get('CHROME_VERGLEICH', '1') == '1' and os.path.exists(chrome):
        profil = os.path.join(os.environ.get('RUNNER_TEMP', AUSGABE), 'chrome-profil')
        sitzung('chrome', [chrome, f'--remote-debugging-port={PORT + 1}', f'--user-data-dir={profil}', '--no-first-run',
                           '--no-default-browser-check', '--start-maximized', 'https://kinolel.de/web/'], None, PORT + 1,
                VARIANTEN[:1], ergebnis)
    bericht(ergebnis)


def bericht(ergebnis):
    with open(os.path.join(AUSGABE, 'startseite.json'), 'w', encoding='utf-8') as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=1)
    z = ['## KinoLel-Startseiten-Test (Runner ohne GPU)', '',
         f"Konto {ergebnis.get('benutzer')}, je Variante {ergebnis.get('beobachtung_s')} s beobachtet. "
         f"Anmeldung bis Startseite: App {ergebnis.get('anmeldung_bis_startseite_s_app', '–')} s, "
         f"Chrome {ergebnis.get('anmeldung_bis_startseite_s_chrome', '–')} s. "
         f"Fehler: {'; '.join(f'{k}: {w}' for k, w in ergebnis.items() if k.startswith('fehler')) or 'keine'}", '',
         '| Programm | Variante | Anfragen/s (max) | DOM-Mutationen/s | Knoten neu/s | Abschnitte neu | Seiten neu geladen | bootstrap() | CPU % | Fehler |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for v in ergebnis['varianten']:
        z.append(f"| {v.get('teil')} | {v['variante']} | {v.get('anfragen_pro_s')} ({v.get('anfragen_max_pro_s')}) | {v.get('dom_mutationen_pro_s')} | "
                 f"{v.get('knoten_eingefuegt_pro_s')} | {v.get('abschnitte_neu')} | {v.get('seiten_neu_geladen')} | "
                 f"{v.get('bootstrap_aufrufe_gesamt')} | {v.get('cpu_prozent')} | {v.get('fehler', '')} |")
    for v in ergebnis['varianten'][:1]:
        z += ['', f"Häufigste Anfragen ({v['variante']}):", '']
        z += [f'- {n}× {k}' for k, n in v.get('top_anfragen', [])[:12]]
        z += ['', f"Häufigste DOM-Änderungen ({v['variante']}):", '']
        z += [f'- {n}× {k}' for k, n in v.get('top_mutationsziele', [])[:12]]
    text = '\n'.join(z) + '\n'
    print(text)
    with open(os.path.join(AUSGABE, 'startseite.md'), 'w', encoding='utf-8') as f:
        f.write(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(text)


if __name__ == '__main__':
    main()
