#!/usr/bin/env python3
"""KinoLel Windows als Web-App (Lel 25.10.2026), Auftrag Abschnitt 1 – Vorprüfung mit Electron (eigenes Chromium):
  1. Welche Video-/Tonformate spielt dieses Chromium unter Windows direkt (MediaSource/canPlayType/mediaCapabilities,
     dazu die GPU-Dekoder laut SystemInfo)?
  2. Läuft kinolel.de (jellyfin-web 12.3, kinolel.js, Lade-Overlay, Media Bar, Home Screen Sections, Jellyfin Enhanced,
     Custom Tabs) fehlerfrei? JavaScript-Fehler, Merkmale, Bildschirmfotos, CPU im Leerlauf.
Anmeldung mit dem Hilfskonto einmal (Passwort nur aus KINOLEL_TEST_PW, nie getippt/ausgegeben), am Ende abmelden.
Aufruf: python pruefung_webapp.py <electron.exe> <app-ordner> <ausgabe-ordner>"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bundle', 'test'))
from startseite import Cdp, anmelden, anmeldefelder_leeren, cpu_je_art, cpu_sekunden, schwaerzen, seite_finden, warten, STARTSEITE_BEREIT  # noqa: E402

EXE, APP, AUS = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(AUS, exist_ok=True)
PORT = 9227
ergebnis = {'fehler_js': [], 'konsole': []}

FORMATE = r"""(async function(){
  var v = document.createElement('video');
  var mse = function(t){ try { return window.MediaSource ? MediaSource.isTypeSupported(t) : null } catch(e) { return 'Fehler' } };
  var typen = {
    'H.264 (MP4)': 'video/mp4; codecs="avc1.640028"',
    'HEVC hvc1 (MP4)': 'video/mp4; codecs="hvc1.1.6.L120.90"',
    'HEVC Main10 hvc1': 'video/mp4; codecs="hvc1.2.4.L120.90"',
    'HEVC hev1 (MP4)': 'video/mp4; codecs="hev1.1.6.L120.90"',
    'AV1 (MP4)': 'video/mp4; codecs="av01.0.08M.08"',
    'VP9 (WebM)': 'video/webm; codecs="vp9"',
    'AAC': 'audio/mp4; codecs="mp4a.40.2"',
    'AC3 (Dolby Digital)': 'audio/mp4; codecs="ac-3"',
    'E-AC3 (Dolby Digital Plus)': 'audio/mp4; codecs="ec-3"',
    'DTS': 'audio/mp4; codecs="dtsc"',
    'Opus': 'audio/webm; codecs="opus"',
    'FLAC (MP4)': 'audio/mp4; codecs="flac"',
    'MP3': 'audio/mpeg',
    'MKV (Matroska)': 'video/x-matroska; codecs="avc1.640028"'
  };
  var aus = {};
  for (var k in typen) aus[k] = {mse: mse(typen[k]), canPlay: v.canPlayType(typen[k])};
  var faehig = async function(ct){
    try {
      var r = await navigator.mediaCapabilities.decodingInfo({type: 'media-source', video: {contentType: ct, width: 1920, height: 1080, bitrate: 8000000, framerate: 24}});
      return {unterstuetzt: r.supported, fluessig: r.smooth, sparsam_hardware: r.powerEfficient};
    } catch (e) { return String(e) }
  };
  aus['_decodingInfo'] = {
    'H.264 1080p': await faehig('video/mp4; codecs="avc1.640028"'),
    'HEVC 1080p': await faehig('video/mp4; codecs="hvc1.1.6.L120.90"'),
    'HEVC Main10 1080p': await faehig('video/mp4; codecs="hvc1.2.4.L120.90"'),
    'AV1 1080p': await faehig('video/mp4; codecs="av01.0.08M.08"')
  };
  return aus;
})()"""

MERKMALE = r"""(function(){
  var n = function(s){ try { return document.querySelectorAll(s).length } catch(e) { return 'Fehler' } };
  return {
    ua: navigator.userAgent,
    kinolel_js: !!document.querySelector('script[src*="kinolel/kinolel.js"]'),
    lade_overlay_weg: !document.getElementById('kinolel-lade'),
    ladezeit_ms: window.kinolelLadezeit || null,
    startseiten_abschnitte: n('#indexPage:not(.hide) .verticalSection, #indexPage:not(.hide) .homeSection'),
    karten: n('#indexPage:not(.hide) .card'),
    media_bar: n('#slides-container, .slide, [id*="mediaBar" i], [class*="slideshow" i]'),
    jellyfin_enhanced: typeof window.JellyfinEnhanced !== 'undefined' || n('[class*="jellyfin-enhanced" i], [id*="jellyfin-enhanced" i]') > 0,
    reiter_kopfleiste: n('.headerTabs .emby-tab-button, .headerTabs .tabButton'),
    bilder_kaputt: Array.from(document.images).filter(function(i){ return i.complete && i.naturalWidth === 0 && i.src }).length
  };
})()"""


def bild(cdp, name):
    daten = cdp.rufe('Page.captureScreenshot', zeit=30, format='png').get('data')
    if daten:
        with open(os.path.join(AUS, name + '.png'), 'wb') as f:
            f.write(base64.b64decode(daten))


def ereignis(methode, p):
    if methode == 'Runtime.exceptionThrown':
        d = p.get('exceptionDetails', {})
        text = (d.get('exception') or {}).get('description') or d.get('text', '')
        ergebnis['fehler_js'].append(schwaerzen(f"{d.get('url', '')}:{d.get('lineNumber')} {text}")[:400])
    elif methode == 'Runtime.consoleAPICalled' and p.get('type') in ('error', 'assert'):
        teile = [str(a.get('value', a.get('description', ''))) for a in p.get('args', [])]
        ergebnis['konsole'].append(schwaerzen(p.get('type') + ': ' + ' '.join(teile))[:300])
    elif methode == 'Log.entryAdded' and p.get('entry', {}).get('level') == 'error':
        e = p['entry']
        ergebnis['konsole'].append(schwaerzen(f"log: {e.get('url', '')} {e.get('text', '')}")[:300])


def main():
    env = dict(os.environ, KINOLEL_DEVTOOLS_PORT=str(PORT))
    env.pop('KINOLEL_TEST_PW', None)  # die App selbst braucht das Passwort nicht
    proc = subprocess.Popen([EXE, APP], env=env)
    try:
        z = seite_finden(time.time() + 90, PORT)
        if not z:
            ergebnis['fehler'] = 'keine kinolel.de-Seite über DevTools'
            return
        # GPU / Video-Dekoder (Browser-Ebene)
        try:
            browser_ws = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5))['webSocketDebuggerUrl']
            b = Cdp(browser_ws)
            info = b.rufe('SystemInfo.getInfo', zeit=30)
            gpu = info.get('gpu', {})
            ergebnis['gpu_geraete'] = [f"{g.get('vendorString', '')} {g.get('deviceString', '')}".strip() for g in gpu.get('devices', [])]
            ergebnis['gpu_funktionen'] = {k: v for k, v in (gpu.get('featureStatus') or {}).items()
                                          if k in ('gpu_compositing', 'video_decode', 'webgl', 'rasterization', 'skia_graphite')}
            ergebnis['gpu_videodekoder'] = sorted({d.get('profile', '') for d in gpu.get('videoDecoding', [])})
            ergebnis['chromium'] = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5)).get('Browser')
        except Exception as e:  # noqa: BLE001
            ergebnis['gpu_fehler'] = repr(e)[:200]
        cdp = Cdp(z['webSocketDebuggerUrl'])
        cdp.ereignis_rueckrufe.append(ereignis)
        for d in ('Runtime.enable', 'Log.enable', 'Page.enable'):
            cdp.rufe(d)
        time.sleep(5)
        ergebnis['formate'] = cdp.js(FORMATE, zeit=60)
        bild(cdp, '01-anmeldeseite')
        if not anmelden(cdp, ergebnis, 'webapp'):
            anmeldefelder_leeren(cdp)
            bild(cdp, '01b-anmeldung-fehlgeschlagen')
            return
        ergebnis['startseite_bereit'] = warten(cdp, STARTSEITE_BEREIT + " && !document.getElementById('kinolel-lade')", time.time() + 90)
        time.sleep(8)
        ergebnis['merkmale'] = cdp.js(MERKMALE)
        bild(cdp, '02-startseite')
        # Leerlauf: CPU-Sekunden in 30 s (alle Electron-Prozesse)
        vorher, je_vorher = cpu_sekunden(proc.pid), cpu_je_art(proc.pid)
        time.sleep(30)
        ergebnis['cpu_leerlauf_prozent'] = round((cpu_sekunden(proc.pid) - vorher) / 30 * 100, 1)
        je_nachher = cpu_je_art(proc.pid)
        ergebnis['cpu_leerlauf_je_art'] = {k: round((je_nachher.get(k, 0) - je_vorher.get(k, 0)) / 30 * 100, 1) for k in je_nachher}
        # eine Detailseite (Film aus „Kürzlich hinzugefügt“), dann zurück
        cdp.js("(function(){var k=document.querySelector('#indexPage:not(.hide) .card[data-type=\"Movie\"] a, #indexPage:not(.hide) .card[data-type=\"Movie\"] button');if(k)k.click();return !!k})()")
        warten(cdp, "/^#\\/details/.test(location.hash)", time.time() + 30)
        time.sleep(6)
        bild(cdp, '03-details')
        ergebnis['details_hash'] = (cdp.js('location.hash') or '')[:60]
    finally:
        try:
            print('Abmelden:', cdp.js("(function(){try{var c=JSON.parse(localStorage.getItem('jellyfin_credentials'));var s=c.Servers[0];"
                                      "if(!s.AccessToken)return 'keine Sitzung';return fetch('/Sessions/Logout',{method:'POST',headers:{'Authorization':"
                                      "'MediaBrowser Token=\"'+s.AccessToken+'\"'}}).then(function(r){return 'HTTP '+r.status})}catch(e){return 'Fehler '+e}})()"))
        except Exception as e:  # noqa: BLE001
            print('Abmelden fehlgeschlagen:', type(e).__name__)
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:  # noqa: BLE001
            proc.kill()
        with open(os.path.join(AUS, 'ergebnis.json'), 'w', encoding='utf-8') as f:
            json.dump(ergebnis, f, ensure_ascii=False, indent=1)
        print(json.dumps(ergebnis, ensure_ascii=False, indent=1)[:12000])


cdp = None
main()
