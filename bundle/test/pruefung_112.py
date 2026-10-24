#!/usr/bin/env python3
"""KinoLel Windows-Neubau (Lel 24.10.2026), Auftrag Abschnitt 2: Trägt jellyfin-desktop v1.12.0 die heutige kinolel.de-Seite?

Startet die offizielle JellyfinMediaPlayer.exe 1.12.0 (Qt 5.15 / QtWebEngine) mit DevTools-Port, öffnet kinolel.de,
meldet sich mit dem Hilfskonto an (Passwort nur aus KINOLEL_TEST_PW, nie ausgegeben) und sammelt:
  - Browser-Version (Chromium) und welche CSS-/JS-Funktionen fehlen
  - JavaScript-Fehler (Seite, kinolel.js, Plugins) beim Anmelden, auf der Startseite und der Detailseite
  - Schauspielerbilder auf der Detailseite des Testfilms: Anzahl, Größe, Bild gesetzt, und welche CSS-Regel ihre Höhe macht
  - Bildschirmfotos
Aufruf: python pruefung_112.py <JellyfinMediaPlayer.exe> <ausgabe-ordner>"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from startseite import Cdp, anmelden, schwaerzen, warten, STARTSEITE_BEREIT  # noqa: E402

EXE, AUS = sys.argv[1], sys.argv[2]
os.makedirs(AUS, exist_ok=True)
PORT = 9226
TESTFILM = "Zurück in die Zukunft II"
ergebnis = {"fehler_js": [], "konsole": []}


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
    elif methode == 'Runtime.consoleAPICalled' and p.get('type') in ('error', 'warning', 'assert'):
        teile = [str(a.get('value', a.get('description', ''))) for a in p.get('args', [])]
        ergebnis['konsole'].append(schwaerzen(p.get('type') + ': ' + ' '.join(teile))[:300])
    elif methode == 'Log.entryAdded' and p.get('entry', {}).get('level') == 'error':
        e = p['entry']
        ergebnis['konsole'].append(schwaerzen(f"log: {e.get('url', '')} {e.get('text', '')}")[:300])


FUNKTIONEN = r"""(function(){
  var c = function(e){ try { return CSS.supports(e) } catch(x) { return 'Fehler' } };
  var js = function(f){ try { return !!f() } catch(x) { return false } };
  return {
    ua: navigator.userAgent,
    css_aspect_ratio: c('aspect-ratio: 1'), css_flex_gap: c('gap: 1px'), css_inset: c('inset: 0'),
    css_is: c('selector(:is(a))'), css_where: c('selector(:where(a))'), css_has: c('selector(:has(a))'),
    css_nesting: c('selector(&)'), css_container: c('container-type: inline-size'), css_backdrop: c('backdrop-filter: blur(2px)'),
    css_clamp: c('width: clamp(1px, 2px, 3px)'), css_dvh: c('height: 100dvh'), css_color_mix: c('color: color-mix(in srgb, red, blue)'),
    js_optional_chaining: js(function(){ return new Function('return ({a:1})?.a')() === 1 }),
    js_replaceAll: js(function(){ return 'aa'.replaceAll('a','b') === 'bb' }),
    js_at: js(function(){ return [1,2].at(-1) === 2 }),
    js_structuredClone: typeof structuredClone === 'function',
    js_resizeObserver: typeof ResizeObserver === 'function',
    js_intersectionObserver: typeof IntersectionObserver === 'function'
  };
})()"""

SCHAUSPIELER = r"""(function(){
  var s = document.querySelector('.page:not(.hide) #castContent, .page:not(.hide) .peopleSection, .page:not(.hide) [class*="cast"]');
  var karten = document.querySelectorAll('.page:not(.hide) #castContent .card, .page:not(.hide) .personCard, .page:not(.hide) .peopleSection .card');
  var aus = {abschnitt: !!s, karten: karten.length, beispiele: []};
  for (var i = 0; i < Math.min(karten.length, 3); i++) {
    var k = karten[i], b = k.querySelector('.cardImageContainer, .cardImage, img'), box = k.querySelector('.cardBox, .cardScalable') || k;
    var r = (b || k).getBoundingClientRect(), cs = b ? getComputedStyle(b) : null, sc = k.querySelector('.cardScalable');
    var pad = k.querySelector('.cardPadder, [class*="cardPadder"]');
    aus.beispiele.push({
      klasse: k.className.slice(0, 80), bild_klasse: b ? b.className.slice(0, 80) : null,
      breite: Math.round(r.width), hoehe: Math.round(r.height),
      hintergrund: cs ? cs.backgroundImage.slice(0, 90) : null,
      scalable_hoehe: sc ? Math.round(sc.getBoundingClientRect().height) : null,
      scalable_aspect: sc ? getComputedStyle(sc).aspectRatio : null,
      padder: pad ? (pad.className + ' h=' + Math.round(pad.getBoundingClientRect().height) + ' pb=' + getComputedStyle(pad).paddingBottom) : 'kein cardPadder'
    });
  }
  // Welche Regeln mit aspect-ratio betreffen Karten?
  var regeln = [];
  for (var j = 0; j < document.styleSheets.length; j++) {
    var sh = document.styleSheets[j], rs;
    try { rs = sh.cssRules } catch (e) { continue }
    if (!rs) continue;
    for (var n = 0; n < rs.length; n++) {
      var t = rs[n].cssText || '';
      if (/aspect-ratio/.test(t) && /card|person|cast/i.test(t)) regeln.push(((sh.href || (sh.ownerNode && sh.ownerNode.id) || 'inline') + '').slice(-60) + ' :: ' + t.slice(0, 160));
    }
  }
  aus.aspect_regeln = regeln.slice(0, 12);
  return aus;
})()"""


def main():
    env = dict(os.environ, QTWEBENGINE_REMOTE_DEBUGGING=str(PORT))
    proc = subprocess.Popen([EXE], env=env)
    seiten = []
    ende = time.time() + 120
    while time.time() < ende and not seiten:
        try:
            seiten = [z for z in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3))
                      if z.get('type') == 'page']
        except Exception:  # noqa: BLE001
            pass
        if not seiten:
            time.sleep(2)
    time.sleep(8)  # Oberfläche fertig laden lassen, dann Liste neu lesen
    try:
        seiten = [z for z in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=3)) if z.get('type') == 'page']
    except Exception:  # noqa: BLE001
        pass
    ergebnis['seiten'] = [{k: z.get(k) for k in ('title', 'url', 'type')} for z in seiten]
    if not seiten:
        ergebnis['fehler'] = 'keine DevTools-Seite nach 120 s'
        return proc
    # die Seite nehmen, die auf „1+1“ antwortet (bei Qt gibt es teils mehrere Seiten)
    cdp = None
    for z in seiten:
        try:
            versuch = Cdp(z['webSocketDebuggerUrl'])
            if versuch.js('1+1', zeit=10) == 2:
                cdp, seite = versuch, z
                break
            ergebnis.setdefault('seiten_ohne_antwort', []).append(z.get('url'))
        except Exception as e:  # noqa: BLE001
            ergebnis.setdefault('seiten_fehler', []).append(f"{z.get('url')}: {e!r}"[:200])
    if not cdp:
        ergebnis['fehler'] = 'keine Seite antwortet über DevTools'
        return proc
    ergebnis['gewaehlte_seite'] = seite.get('url')
    try:
        version = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5))
        ergebnis['browser'] = {k: version.get(k) for k in ('Browser', 'User-Agent', 'Protocol-Version')}
    except Exception as e:  # noqa: BLE001
        ergebnis['browser'] = repr(e)
    cdp.ereignis_rueckrufe.append(ereignis)
    for d in ('Runtime.enable', 'Log.enable', 'Page.enable', 'Network.enable'):
        cdp.rufe(d)
    time.sleep(5)
    bild(cdp, '00-start-1.12.0')
    ergebnis['startseite_url'] = cdp.js('location.href')

    cdp.rufe('Page.navigate', url='https://kinolel.de/web/index.html')
    time.sleep(8)
    ergebnis['funktionen'] = cdp.js(FUNKTIONEN)
    bild(cdp, '01-anmeldeseite')
    if not anmelden(cdp, ergebnis, 'v112'):
        bild(cdp, '01b-anmeldung-fehlgeschlagen')
        return proc
    ok = warten(cdp, STARTSEITE_BEREIT + " && !document.getElementById('kinolel-lade')", time.time() + 90)
    ergebnis['startseite_bereit'] = ok
    ergebnis['ladezeit_overlay_ms'] = cdp.js('window.kinolelLadezeit || null')
    ergebnis['ladeprotokoll'] = cdp.js('JSON.stringify(window.kinolelLadeProtokoll || [])')
    time.sleep(8)
    bild(cdp, '02-startseite')
    ergebnis['startzeilen'] = cdp.js("[].map.call(document.querySelectorAll('.page:not(.hide) .sectionTitle'),function(e){return e.textContent.trim()}).slice(0,6)")
    ergebnis['karussell'] = cdp.js("!!document.querySelector('#slides-container .slide.active')")

    # Detailseite des Testfilms mit Besetzung
    film = cdp.js("ApiClient.getItems(ApiClient.getCurrentUserId(), {searchTerm: %s, IncludeItemTypes: 'Movie', Recursive: true, Limit: 5})"
                  ".then(function(r){var i=r.Items.filter(function(x){return x.Name===%s})[0]; return i ? i.Id : null})"
                  % (json.dumps(TESTFILM), json.dumps(TESTFILM)))
    ergebnis['testfilm'] = film
    if film:
        cdp.js("location.hash = '#/details?id=%s'; true" % film)
        warten(cdp, "!!document.querySelector('.page:not(.hide) #castContent .card, .page:not(.hide) .peopleSection .card')", time.time() + 30)
        time.sleep(6)
        cdp.js("var c=document.querySelector('.page:not(.hide) #castContent, .page:not(.hide) .peopleSection'); if(c) c.scrollIntoView(); true")
        time.sleep(4)
        bild(cdp, '03-details-besetzung')
        ergebnis['schauspieler'] = cdp.js(SCHAUSPIELER)

    # Abmelden (nur einmal angemeldet – fail2ban)
    cdp.js("ApiClient.logout().then(function(){return true},function(){return false})")
    return proc


proc = None
try:
    proc = main()
except Exception as e:  # noqa: BLE001
    ergebnis['fehler'] = repr(e)
finally:
    with open(os.path.join(AUS, 'pruefung.json'), 'w', encoding='utf-8') as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in ergebnis.items() if k not in ('konsole',)}, ensure_ascii=False, indent=1)[:12000])
    print('Konsole (Auszug):')
    for z in ergebnis['konsole'][:40]:
        print('  ', z)
    if proc:
        proc.kill()
