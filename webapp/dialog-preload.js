// KinoLel-Dialog: schmale Brücke zum Hauptprozess (nur diese drei Funktionen)
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kinolel', {
  inhalt: (rueckruf) => ipcRenderer.on('kinolel-dialog', (_e, d) => rueckruf(d)),
  fortschritt: (rueckruf) => ipcRenderer.on('kinolel-fortschritt', (_e, anteil) => rueckruf(anteil)),
  antwort: (id) => ipcRenderer.send('kinolel-antwort', id),
});
