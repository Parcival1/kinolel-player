// KinoLel für Windows – läuft in kinolel.de vor den Skripten der Seite:
//  1. Oberfläche wählen: Fenster = Desktop, „KinoLel (TV-Modus)“ = TV (jellyfin-web liest „layout“ aus dem localStorage)
//  2. dem Hauptprogramm melden, wann das Startbild weg darf: sobald das gleich aussehende Lade-Overlay von kinolel.de
//     gezeichnet ist („overlay“) – ohne Overlay erst, wenn eine Seite fertig ist („fertig“). Nie halb aufgebaut.
const { ipcRenderer } = require('electron');

try {
  const layout = ipcRenderer.sendSync('kinolel-layout');
  if (localStorage.getItem('layout') !== layout) localStorage.setItem('layout', layout);
} catch (_) { /* nie stören */ }

let gemeldet = false;
function melden(stand) {
  if (gemeldet) return;
  gemeldet = true;
  ipcRenderer.send('kinolel-seite-stand', stand);
}
function fertig() {
  if (!document.querySelector('.page:not(.hide)')) return false;
  if (/^#\/home/.test(location.hash) || location.hash === '' || location.hash === '#/') {
    return document.querySelectorAll('#indexPage:not(.hide) .verticalSection, #indexPage:not(.hide) .homeSection').length > 0;
  }
  return true;
}
function pruefen() {
  if (gemeldet) return;
  if (document.getElementById('kinolel-lade')) {
    // zwei Bilder abwarten, damit das Overlay sicher gezeichnet ist
    requestAnimationFrame(() => requestAnimationFrame(() => melden('overlay')));
    return;
  }
  if (fertig()) melden('fertig');
  else setTimeout(pruefen, 150);
}
window.addEventListener('DOMContentLoaded', pruefen);
