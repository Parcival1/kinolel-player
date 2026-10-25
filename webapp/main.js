// KinoLel für Windows (Lel 25.10.2026: „… eine web app … basiere unseres bitte auf Chrome“) – Vorprüfung:
// kleinste Hülle um https://kinolel.de mit dem Chromium von Electron. DevTools-Port nur für Tests (KINOLEL_DEVTOOLS_PORT).
const { app, BrowserWindow, shell } = require('electron');

const SERVER = 'https://kinolel.de';
const port = process.env.KINOLEL_DEVTOOLS_PORT;
if (port) app.commandLine.appendSwitch('remote-debugging-port', port);
app.setName('KinoLel');

app.whenReady().then(() => {
  const fenster = new BrowserWindow({
    width: 1600,
    height: 1000,
    backgroundColor: '#0B0F18',
    title: 'KinoLel',
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, sandbox: true },
  });
  // fremde Links im normalen Browser
  fenster.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(SERVER)) shell.openExternal(url);
    return { action: url.startsWith(SERVER) ? 'allow' : 'deny' };
  });
  fenster.loadURL(SERVER + '/web/');
});

app.on('window-all-closed', () => app.quit());
