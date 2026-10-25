// KinoLel für Windows – läuft in kinolel.de vor den Skripten der Seite:
//  1. Oberfläche wählen: Fenster = Desktop, „KinoLel (TV-Modus)“ = TV (jellyfin-web liest „layout“ aus dem localStorage)
//     (Leistungsregeln spielt das Hauptprogramm asynchron ein, siehe main.js)
//  2. dem Hauptprogramm melden, wann das Startbild weg darf: sobald das gleich aussehende Lade-Overlay von kinolel.de
//     gezeichnet ist („overlay“) – ohne Overlay erst, wenn eine Seite fertig ist („fertig“). Nie halb aufgebaut.
const { ipcRenderer } = require('electron');

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
window.addEventListener('DOMContentLoaded', () => { beobachter.disconnect(); pruefen(); fertigBeobachten(); });
