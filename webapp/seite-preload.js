// KinoLel für Windows: vor den Skripten von kinolel.de die Oberfläche wählen – Fenster = Desktop, „KinoLel (TV-Modus)“ = TV
// (jellyfin-web liest „layout“ aus dem localStorage)
const { ipcRenderer } = require('electron');

try {
  const layout = ipcRenderer.sendSync('kinolel-layout');
  if (localStorage.getItem('layout') !== layout) localStorage.setItem('layout', layout);
} catch (_) { /* nie stören */ }
