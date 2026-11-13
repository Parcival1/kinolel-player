// KinoLel für Windows – läuft in kinolel.de vor den Skripten der Seite:
//  1. Oberfläche wählen: Fenster = Desktop, „KinoLel (TV-Modus)“ = TV (jellyfin-web liest „layout“ aus dem localStorage)
//     (Leistungsregeln spielt das Hauptprogramm asynchron ein, siehe main.js)
//  2. dem Hauptprogramm melden, wann das Startbild weg darf: sobald das gleich aussehende Lade-Overlay von kinolel.de
//     gezeichnet ist („overlay“) – ohne Overlay erst, wenn eine Seite fertig ist („fertig“). Nie halb aufgebaut.
//  3. HDR nur melden, wenn der Bildschirm HDR kann (siehe hdrSchutz)
const { ipcRenderer, contextBridge, webFrame } = require('electron');

// 3. Lel 13.11.2026 („The Crown“ in der App viel zu dunkel): jellyfin-web hält Chrome auf dem Desktop immer für
//    HDR10-fähig und schreibt das in das Geräteprofil jeder Abspiel-Anfrage (PlaybackInfo). Auf einem Bildschirm ohne HDR
//    rechnet dann Chromium das HDR-Bild selbst um – viel zu dunkel. Ohne HDR-Bildschirm bleibt in den
//    VideoRangeType-Bedingungen nur SDR stehen; der Server rechnet HDR dann selbst um (Tonemapping mit Grafikkarte).
//    Geprüft wird bei jeder Anfrage – das Fenster kann auf einen HDR-Bildschirm wandern oder HDR wird eingeschaltet.
//    Läuft in der Seite selbst (Hauptwelt), vor allen Skripten von kinolel.de.
function hdrSchutz() {
  const hdr = () => { try { return matchMedia('(dynamic-range: high)').matches; } catch (_) { return true; } };
  const anpassen = (text) => {
    if (typeof text !== 'string' || text.indexOf('VideoRangeType') < 0 || hdr()) return text;
    try {
      const d = JSON.parse(text);
      const p = d && d.DeviceProfile;
      if (!p || !Array.isArray(p.CodecProfiles)) return text;
      let geaendert = false;
      for (const cp of p.CodecProfiles) {
        for (const c of (cp && cp.Conditions) || []) {
          if (c && c.Property === 'VideoRangeType' && typeof c.Value === 'string') {
            const neu = c.Value.split('|').filter((v) => v === 'SDR' || v === 'DOVIWithSDR').join('|') || 'SDR';
            if (neu !== c.Value) { c.Value = neu; geaendert = true; }
          }
        }
      }
      return geaendert ? JSON.stringify(d) : text;
    } catch (_) { return text; }
  };
  const abspielInfo = (url) => /\/Items\/[^/?#]+\/PlaybackInfo/i.test(String(url || ''));
  const X = XMLHttpRequest.prototype;
  const oeffnen = X.open;
  const senden = X.send;
  X.open = function (methode) {
    this.kinolelAbspielInfo = String(methode).toUpperCase() === 'POST' && abspielInfo(arguments[1]);
    return oeffnen.apply(this, arguments);
  };
  X.send = function (koerper) { return senden.call(this, this.kinolelAbspielInfo ? anpassen(koerper) : koerper); };
  const holen = window.fetch;
  if (holen) {
    window.fetch = function (eingabe, init) {
      try {
        const url = typeof eingabe === 'string' ? eingabe : (eingabe && eingabe.url);
        if (init && typeof init.body === 'string' && abspielInfo(url)) init = Object.assign({}, init, { body: anpassen(init.body) });
      } catch (_) { /* nie stören */ }
      return holen.call(this, eingabe, init);
    };
  }
  // für den Test (webapp_test.py): Stand ablesen und die Anpassung prüfen
  Object.defineProperty(window, 'kinolelHdr', { value: Object.freeze({ bildschirm: hdr, anpassen }) });
}
try {
  if (contextBridge && contextBridge.executeInMainWorld) contextBridge.executeInMainWorld({ func: hdrSchutz });
  else webFrame.executeJavaScript(`(${hdrSchutz.toString()})()`);
} catch (_) { /* nie stören */ }

try {
  // Fenster = Desktop, „KinoLel (TV-Modus)“ = TV – kommt als Startargument (kein Warten auf das Hauptprogramm)
  const arg = (process.argv || []).find((a) => a.startsWith('--kinolel-layout='));
  const layout = arg ? arg.split('=')[1] : 'desktop';
  if (localStorage.getItem('layout') !== layout) localStorage.setItem('layout', layout);
} catch (_) { /* nie stören */ }

let gemeldet = false;
function melden(stand) {
  if (gemeldet) return;
  gemeldet = true;
  ipcRenderer.send('kinolel-seite-stand', stand, document.visibilityState);
}
function fertig() {
  if (!document.querySelector('.page:not(.hide)')) return false;
  if (/^#\/home/.test(location.hash) || location.hash === '' || location.hash === '#/') {
    return document.querySelectorAll('#indexPage:not(.hide) .verticalSection, #indexPage:not(.hide) .homeSection').length > 0;
  }
  return true;
}
// Für die Startzeiten: wann ist kinolel.de wirklich fertig (Overlay weg, Seite steht)?
let fertigGemeldet = false;
function fertigBeobachten() {
  if (fertigGemeldet) return;
  if (!document.getElementById('kinolel-lade') && fertig()) {
    fertigGemeldet = true;
    ipcRenderer.send('kinolel-seite-stand', 'startseite');
    return;
  }
  setTimeout(fertigBeobachten, 100);
}

function pruefen() {
  if (gemeldet) return;
  if (document.getElementById('kinolel-lade')) {
    // sofort melden – nicht auf Animationsbilder warten: die verdeckte Seite bekommt (mit Grafikkarte) keine, bis das
    // Startbild weg ist (25.10.: Startbild hing so bis zur Notbremse). Gleiche Farbe/Gestaltung, der Tausch fällt nicht auf.
    melden('overlay');
    return;
  }
  if (fertig()) melden('fertig');
  else setTimeout(pruefen, 150);
}
// Das Lade-Overlay steht ganz oben in index.html: schon beim Einlesen bemerken (nicht erst, wenn alle Skripte geladen sind)
const beobachter = new MutationObserver(() => {
  if (document.getElementById('kinolel-lade')) {
    beobachter.disconnect();
    pruefen();
  }
});
beobachter.observe(document, { childList: true, subtree: true });
window.addEventListener('DOMContentLoaded', () => { beobachter.disconnect(); pruefen(); fertigBeobachten(); spracheMelden(); });

// Sprache, die kinolel.de anzeigt (<html lang>), für die Texte der App melden – auch wenn sie wechselt
function spracheMelden() {
  const melden = () => { if (document.documentElement.lang) ipcRenderer.send('kinolel-sprache', document.documentElement.lang); };
  melden();
  new MutationObserver(melden).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
}
