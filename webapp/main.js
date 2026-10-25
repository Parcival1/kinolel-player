'use strict';
// KinoLel für Windows (Lel 25.10.2026: „Die Windows app ist immer noch des todes schlecht, es flackert etc. Können wir
// nicht einfach eine web app daraus machen? … basiere unseres bitte auf Chrome.“) – schlanke Hülle um https://kinolel.de
// mit dem eigenen Chromium von Electron. Auftrag: CT 103 /dokumentation/kinolel-player/AUFTRAG-WINDOWS-WEBAPP.md
//
// Aufbau des Fensters (WebContentsViews übereinander):
//   titel  – Titelleiste #0B0F18 (Verschieben/Andocken), rechts die echten Windows-Knöpfe (titleBarOverlay)
//   seite  – kinolel.de
//   start  – Startbild wie das Lade-Overlay von kinolel.de, bis die Seite fertig aufgebaut ist
//   dialog – KinoLel-Dialoge (Update, Was ist neu, Grafik-Info), nur solange einer offen ist
const { app, BrowserWindow, WebContentsView, Menu, ipcMain, net, shell, clipboard } = require('electron');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

// Startzeiten (Lel 25.10.: „lädt aber seeeeeehr lange“): Millisekunden ab Prozessstart, im Protokoll als „Startzeiten“
const PROZESS_START = Date.now() - Math.round(process.uptime() * 1000);
const zeiten = {};
function zeit(name) {
  if (!(name in zeiten)) zeiten[name] = Date.now() - PROZESS_START;
}

const MARKE = require('./marke.json');
const NEUIGKEITEN = require('./neuigkeiten.json');

const SERVER = MARKE.server;
const TITEL_HOEHE = 36;
const TV = process.argv.includes('--tv');
const DEVTOOLS_PORT = process.env.KINOLEL_DEVTOOLS_PORT;                 // nur Tests
const TEST_VERSION = process.env.KINOLEL_TEST_VERSION;                   // nur Test: gibt eine ältere Version vor
const TEST_NEUIGKEITEN_SEIT = process.env.KINOLEL_TEST_NEUIGKEITEN_SEIT; // nur Test: „zuletzt gesehen“
const TEST_APPS_LISTE = process.env.KINOLEL_TEST_APPS_LISTE;             // nur Test: andere Versionsliste
const PRUEF_ABSTAND_MS = 3 * 60 * 60 * 1000;   // Update-Suche alle 3 h, solange offen
const SPAETER_MS = 4 * 60 * 60 * 1000;          // „Später“ unterdrückt dieselbe Version 4 h
const START_NOTBREMSE_MS = 8000;                // Startbild spätestens dann weg (darunter liegt das gleiche Overlay der Seite)

// Daten wie bisher unter %LOCALAPPDATA%\KinoLel (die Deinstallation fragt dort, ob gelöscht werden soll)
const DATEN = path.join(process.env.LOCALAPPDATA || app.getPath('appData'), MARKE.name);
const ALTE_APP_DATEN = fs.existsSync(DATEN) && !fs.existsSync(path.join(DATEN, 'App'));
app.setPath('userData', path.join(DATEN, 'App'));
app.setName(MARKE.name);
app.setAppUserModelId(MARKE.appUserModelId);
if (DEVTOOLS_PORT) app.commandLine.appendSwitch('remote-debugging-port', DEVTOOLS_PORT);
// Abspielen ohne vorherigen Klick: Fernsteuerung vom Server, nächste Folge, TV-Modus mit Fernbedienung
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
// wie Chrome, mit „KinoLel/<Version>“, ohne „Electron“
app.userAgentFallback = app.userAgentFallback.replace(/\s*Electron\/\S+/i, '');
Menu.setApplicationMenu(null);

// ---------------------------------------------------------------------------------------------------------------
// Protokoll (%LOCALAPPDATA%\KinoLel\App\kinolel.log, höchstens ca. 1 MB)
const LOGDATEI = path.join(app.getPath('userData'), 'kinolel.log');
function log(...teile) {
  const zeile = `${new Date().toISOString()} ${teile.map(String).join(' ')}\n`;
  try {
    fs.mkdirSync(path.dirname(LOGDATEI), { recursive: true });
    if (fs.existsSync(LOGDATEI) && fs.statSync(LOGDATEI).size > 1_000_000) fs.renameSync(LOGDATEI, LOGDATEI + '.alt');
    fs.appendFileSync(LOGDATEI, zeile);
  } catch (_) { /* Protokoll darf nie stören */ }
}

// Einstellungen der App (Fenster, „Später“, zuletzt gesehene Version)
const EINSTELLUNGEN = path.join(app.getPath('userData'), 'kinolel-einstellungen.json');
let einst = {};
try { einst = JSON.parse(fs.readFileSync(EINSTELLUNGEN, 'utf8')); } catch (_) { einst = {}; }
function speichern() {
  try {
    fs.mkdirSync(path.dirname(EINSTELLUNGEN), { recursive: true });
    fs.writeFileSync(EINSTELLUNGEN, JSON.stringify(einst, null, 1));
  } catch (e) { log('Einstellungen nicht gespeichert:', e.message); }
}

// ---------------------------------------------------------------------------------------------------------------
// Sprache der App-Texte (Lel 25.10.: wie in KinoLel gewählt): die Sprache, die kinolel.de anzeigt (KinoLel-Wahl
// Deutsch/Magyar bzw. Jellyfins Anzeigesprache, gemeldet über <html lang>); noch nicht bekannt: Windows-Sprache, sonst Englisch
const SPRACHEN = ['de', 'hu', 'en'];
function systemSprache() {
  const s = (app.getPreferredSystemLanguages()[0] || app.getLocale() || 'en').slice(0, 2).toLowerCase();
  return ['de', 'hu'].includes(s) ? s : 'en';
}
function sprache() {
  return SPRACHEN.includes(einst.seiteSprache) ? einst.seiteSprache : systemSprache();
}
const spracheWartende = [];
ipcMain.on('kinolel-sprache', (e, lang) => {
  if (!ansichten.seite || e.sender !== ansichten.seite.webContents) return;
  const s = String(lang || '').slice(0, 2).toLowerCase();
  if (!SPRACHEN.includes(s)) return;
  if (einst.seiteSprache !== s) { einst.seiteSprache = s; speichern(); log('Sprache von kinolel.de:', s); }
  spracheWartende.splice(0).forEach((r) => r());
});
function aufSpracheWarten(frist) {
  if (SPRACHEN.includes(einst.seiteSprache)) return Promise.resolve();
  return new Promise((fertig) => { spracheWartende.push(fertig); setTimeout(fertig, frist); });
}
const TEXTE = {
  de: {
    updateTitel: 'Neue Version', updateText: 'KinoLel %1 ist da (installiert: %2). Jetzt aktualisieren?',
    jetzt: 'Jetzt aktualisieren', spaeter: 'Später', laedt: 'KinoLel %1 wird geladen …',
    fehler: 'Das Update konnte nicht geladen werden. Bitte später noch einmal versuchen.',
    aktuell: 'KinoLel ist auf dem neuesten Stand.', ok: 'OK', portabel: 'Diese KinoLel-Version wurde ohne Installation gestartet. Die neue Version gibt es auf der Download-Seite.',
    downloadSeite: 'Download-Seite', neuTitel: 'Neu in KinoLel %1', verstanden: 'Verstanden',
    grafikTitel: 'Grafik-Info', kopieren: 'Kopieren', schliessen: 'Schließen',
  },
  hu: {
    updateTitel: 'Új verzió', updateText: 'Elérhető a KinoLel %1 (telepítve: %2). Frissítsünk most?',
    jetzt: 'Frissítés most', spaeter: 'Később', laedt: 'A KinoLel %1 letöltése folyamatban …',
    fehler: 'A frissítést nem sikerült letölteni. Kérjük, próbáld újra később.',
    aktuell: 'A KinoLel naprakész.', ok: 'OK', portabel: 'Ez a KinoLel-verzió telepítés nélkül fut. Az új verzió a letöltési oldalon érhető el.',
    downloadSeite: 'Letöltési oldal', neuTitel: 'Újdonságok a KinoLel %1-ban', verstanden: 'Értem',
    grafikTitel: 'Grafikai információ', kopieren: 'Másolás', schliessen: 'Bezárás',
  },
  en: {
    updateTitel: 'New version', updateText: 'KinoLel %1 is available (installed: %2). Update now?',
    jetzt: 'Update now', spaeter: 'Later', laedt: 'Downloading KinoLel %1 …',
    fehler: 'The update could not be downloaded. Please try again later.',
    aktuell: 'KinoLel is up to date.', ok: 'OK', portabel: 'This KinoLel version runs without installation. Get the new version from the download page.',
    downloadSeite: 'Download page', neuTitel: 'New in KinoLel %1', verstanden: 'Got it',
    grafikTitel: 'Graphics info', kopieren: 'Copy', schliessen: 'Close',
  },
};
function t(schluessel, ...werte) {
  let s = (TEXTE[sprache()] || TEXTE.de)[schluessel] || schluessel;
  werte.forEach((w, i) => { s = s.replace(`%${i + 1}`, w); });
  return s;
}

// ---------------------------------------------------------------------------------------------------------------
// Anmeldung aus der bisherigen KinoLel-App (Qt) übernehmen: deren „Local Storage“ (Chromium-Format) einmal kopieren
function anmeldungUebernehmen() {
  const ziel = path.join(app.getPath('userData'), 'Local Storage');
  if (fs.existsSync(ziel)) return;
  const quelle = suchen(DATEN, 'Local Storage', 7);
  if (!quelle) return;
  try {
    fs.mkdirSync(app.getPath('userData'), { recursive: true });
    fs.cpSync(quelle, ziel, { recursive: true });
    log('Anmeldung der bisherigen App übernommen aus', quelle);
  } catch (e) { log('Anmeldung nicht übernommen:', e.message); }
}
function suchen(ordner, name, tiefe) {
  if (tiefe < 0) return null;
  let eintraege;
  try { eintraege = fs.readdirSync(ordner, { withFileTypes: true }); } catch (_) { return null; }
  for (const e of eintraege) {
    if (!e.isDirectory()) continue;
    const voll = path.join(ordner, e.name);
    if (voll === app.getPath('userData')) continue;
    if (e.name === name && fs.existsSync(path.join(voll, 'leveldb'))) return voll;
  }
  for (const e of eintraege) {
    if (!e.isDirectory() || path.join(ordner, e.name) === app.getPath('userData')) continue;
    const r = suchen(path.join(ordner, e.name), name, tiefe - 1);
    if (r) return r;
  }
  return null;
}

// ---------------------------------------------------------------------------------------------------------------
let fenster = null;
let ansichten = {};
let startWeg = false;

function eigene(url) {
  return url === SERVER || url.startsWith(SERVER + '/');
}

function anordnen() {
  if (!fenster) return;
  const { width: b, height: h } = fenster.getContentBounds();
  const oben = (TV || fenster.isFullScreen()) ? 0 : TITEL_HOEHE;
  ansichten.titel?.setBounds({ x: 0, y: 0, width: b, height: oben });
  ansichten.seite?.setBounds({ x: 0, y: oben, width: b, height: h - oben });
  ansichten.start?.setBounds({ x: 0, y: oben, width: b, height: h - oben });
  ansichten.dialog?.setBounds({ x: 0, y: 0, width: b, height: h });
}

function fensterOeffnen() {
  const f = einst.fenster || {};
  fenster = new BrowserWindow({
    width: f.breite || 1440, height: f.hoehe || 900, x: f.x, y: f.y, minWidth: 900, minHeight: 600,
    backgroundColor: MARKE.farbeHintergrund, title: MARKE.name, show: false,
    icon: path.join(__dirname, 'app.ico'),
    titleBarStyle: TV ? 'default' : 'hidden',
    titleBarOverlay: TV ? false : { color: MARKE.farbeHintergrund, symbolColor: MARKE.farbeSymbole, height: TITEL_HOEHE },
    fullscreen: TV,
  });
  if (f.maximiert && !TV) fenster.maximize();

  const sicher = { sandbox: true, contextIsolation: true, nodeIntegration: false };
  ansichten.titel = new WebContentsView({ webPreferences: sicher });
  // backgroundThrottling aus: Solange das Startbild die Seite verdeckt, hielt Chromium (mit Grafikkarte) deren Bilder an –
  // das Fertig-Signal kam nie, erst die Notbremse nach 20 s gab frei (Lel 25.10.: „auf Windows dauert es 20 sek“)
  ansichten.seite = new WebContentsView({ webPreferences: { ...sicher, backgroundThrottling: false,
    preload: path.join(__dirname, 'seite-preload.js'), additionalArguments: [`--kinolel-layout=${TV ? 'tv' : 'desktop'}`] } });
  ansichten.start = new WebContentsView({ webPreferences: sicher });
  for (const v of [ansichten.titel, ansichten.seite, ansichten.start]) v.setBackgroundColor(MARKE.farbeHintergrund);
  fenster.contentView.addChildView(ansichten.titel);
  fenster.contentView.addChildView(ansichten.seite);
  fenster.contentView.addChildView(ansichten.start);
  anordnen();
  for (const e of ['resize', 'maximize', 'unmaximize', 'enter-full-screen', 'leave-full-screen']) fenster.on(e, anordnen);
  fenster.on('focus', () => ansichten.titel.webContents.executeJavaScript("document.body.classList.remove('inaktiv')").catch(() => {}));
  fenster.on('blur', () => ansichten.titel.webContents.executeJavaScript("document.body.classList.add('inaktiv')").catch(() => {}));
  fenster.on('close', () => {
    if (TV) return;
    const g = fenster.getNormalBounds();
    einst.fenster = { x: g.x, y: g.y, breite: g.width, hoehe: g.height, maximiert: fenster.isMaximized() };
    speichern();
  });
  fenster.on('closed', () => { fenster = null; ansichten = {}; });

  ansichten.titel.webContents.loadFile(path.join(__dirname, 'oberflaeche', 'titel.html'));
  ansichten.start.webContents.loadFile(path.join(__dirname, 'oberflaeche', 'start.html'));
  ansichten.start.webContents.once('did-finish-load', () => { zeit('fenster_sichtbar'); fenster?.show(); });
  setTimeout(() => fenster && !fenster.isVisible() && fenster.show(), 3000);

  const seite = ansichten.seite.webContents;
  // fremde Links (Wünsche, Hilfe-Seiten anderer Anbieter, …) im normalen Browser
  seite.setWindowOpenHandler(({ url }) => {
    if (eigene(url)) return { action: 'allow' };
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  seite.on('will-navigate', (e, url) => {
    if (!eigene(url)) { e.preventDefault(); if (/^https?:/i.test(url)) shell.openExternal(url); }
  });
  for (const v of [ansichten.titel, ansichten.seite, ansichten.start]) v.webContents.on('before-input-event', tastenkuerzel);
  // Vollbild aus der Seite (Doppelklick im Film, Vollbild-Knopf des Players) = ganzes Fenster im Vollbild
  seite.on('enter-html-full-screen', () => fenster?.setFullScreen(true));
  seite.on('leave-html-full-screen', () => { if (!TV) fenster?.setFullScreen(false); });
  seite.on('render-process-gone', (_e, d) => { log('Seite abgestürzt:', d.reason); seite.reload(); });
  seite.on('did-fail-load', (_e, code, text, url, haupt) => { if (haupt) log('Laden fehlgeschlagen:', code, text, url); });
  seite.on('did-start-loading', () => { zeit('laden_beginnt'); if (startWeg) return; startUeberwachen(); });
  seite.on('did-navigate', () => zeit('erste_antwort'));
  seite.on('dom-ready', () => { zeit('dom_bereit'); leistungsregeln(seite); });
  seite.on('did-finish-load', () => zeit('seite_geladen'));
  zeit('kinolel_de_aufrufen');
  seite.loadURL(SERVER + '/web/');
}

// Startbild erst weg, wenn kinolel.de sein eigenes (gleich aussehendes) Lade-Overlay zeigt oder fertig ist –
// nie ein halb aufgebauter Bildschirm (Lel 25.10.). Die Seite meldet das selbst (seite-preload.js); Notbremse 20 s.
let startBeginn = 0;
let notbremse = null;
function startUeberwachen() {
  if (notbremse) return;
  startBeginn = Date.now();
  notbremse = setTimeout(() => { log('Startbild nach Notbremse entfernt'); startEntfernen(true); }, START_NOTBREMSE_MS);
}
ipcMain.on('kinolel-seite-stand', (e, stand, sichtbarkeit) => {
  if (!ansichten.seite || e.sender !== ansichten.seite.webContents) return;
  if (stand === 'startseite') {
    // kinolel.de fertig (Lade-Overlay weg, erste Seite steht): Zeiten einmal protokollieren
    zeit('startseite_fertig');
    if (!zeiten._protokolliert) {
      zeiten._protokolliert = true;
      log('Startzeiten (ms ab Prozessstart):', Object.entries(zeiten).filter(([k]) => !k.startsWith('_')).map(([k, v]) => `${k}=${v}`).join(' '));
    }
    return;
  }
  if (startWeg) return;
  zeit('startbild_weg');
  clearTimeout(notbremse);
  log('Startbild weg nach', Date.now() - startBeginn, 'ms:', stand, `(Seite ${sichtbarkeit || '?'})`);
  startEntfernen(stand !== 'overlay');
});
// Strg+Umschalt+G = Grafik-Info, F11 = Vollbild (gilt in jeder Ansicht des Fensters)
function tastenkuerzel(e, ein) {
  if (ein.type !== 'keyDown' && ein.type !== 'rawKeyDown') return;
  if (DEVTOOLS_PORT && ein.control && ein.shift) log('Taste (Test):', ein.type, ein.code, ein.key);
  if (ein.control && ein.shift && (ein.code === 'KeyG' || String(ein.key).toLowerCase() === 'g')) { e.preventDefault(); grafikInfo(); }
  if (ein.code === 'F11' && !TV && fenster) { e.preventDefault(); fenster.setFullScreen(!fenster.isFullScreen()); }
}

function startEntfernen(sanft) {
  if (startWeg || !ansichten.start) return;
  startWeg = true;
  const v = ansichten.start;
  const weg = () => {
    try { fenster?.contentView.removeChildView(v); v.webContents.close(); } catch (_) {}
    ansichten.start = null;
    ansichten.seite?.webContents.focus();
  };
  if (!sanft) return weg();
  v.webContents.executeJavaScript("document.getElementById('kinolel-lade').classList.add('kinolel-weg')").catch(() => {});
  setTimeout(weg, 480);
}

// ---------------------------------------------------------------------------------------------------------------
// KinoLel-Dialoge (eigene Ansicht über allem; eine Antwort je Dialog)
let dialogWarteschlange = Promise.resolve();
const offeneDialoge = new Map();
function dialogBeenden(v, id) {
  const h = offeneDialoge.get(v);
  if (h) h({ sender: v.webContents }, id);
}
function dialogZeigen(inhalt) {
  const lauf = dialogWarteschlange.then(() => new Promise((fertig) => {
    if (!fenster) return fertig('esc');
    const v = new WebContentsView({ webPreferences: { sandbox: true, contextIsolation: true, preload: path.join(__dirname, 'dialog-preload.js') } });
    v.setBackgroundColor('#00000000');
    ansichten.dialog = v;
    fenster.contentView.addChildView(v);
    anordnen();
    const antwort = (_e, id) => {
      if (_e.sender !== v.webContents) return;
      ipcMain.removeListener('kinolel-antwort', antwort);
      offeneDialoge.delete(v);
      try { fenster?.contentView.removeChildView(v); v.webContents.close(); } catch (_) {}
      if (ansichten.dialog === v) ansichten.dialog = null;
      ansichten.seite?.webContents.focus();
      fertig(id);
    };
    ipcMain.on('kinolel-antwort', antwort);
    offeneDialoge.set(v, antwort);
    v.webContents.loadFile(path.join(__dirname, 'oberflaeche', 'dialog.html'));
    v.webContents.once('did-finish-load', () => {
      v.webContents.send('kinolel-dialog', { sprache: sprache(), ...inhalt });
      v.webContents.focus();
    });
    inhalt.beiOffen?.(v);
  }));
  dialogWarteschlange = lauf.catch(() => {});
  return lauf;
}

// ---------------------------------------------------------------------------------------------------------------
// „Was ist neu“: einmal nach einem Update (frisch installiert: nichts; Umstieg von der bisherigen App: zeigen)
function versionsTeile(v) { return String(v).replace(/^v/i, '').split('.').map((x) => parseInt(x, 10) || 0); }
function neuer(a, b) {
  const x = versionsTeile(a), y = versionsTeile(b);
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  return false;
}
async function neuigkeitenZeigen() {
  const aktuell = app.getVersion();
  let gesehen = TEST_NEUIGKEITEN_SEIT || einst.gesehen;
  if (!gesehen && !ALTE_APP_DATEN && !TEST_NEUIGKEITEN_SEIT) { einst.gesehen = aktuell; speichern(); return; }
  if (gesehen && !neuer(aktuell, gesehen)) return;
  einst.gesehen = aktuell;
  speichern();
  // in der Sprache von kinolel.de zeigen – nach einem Update erst darauf warten (höchstens 15 s)
  await aufSpracheWarten(15000);
  const eintraege = NEUIGKEITEN.versionen.filter((e) => (!gesehen || neuer(e.version, gesehen)) && !neuer(e.version, aktuell));
  if (!eintraege.length) return;
  const punkte = eintraege.flatMap((e) => e[sprache()] || e.de);
  log('Was ist neu gezeigt:', eintraege.map((e) => e.version).join(', '));
  await dialogZeigen({ titel: t('neuTitel', aktuell), punkte, knoepfe: [{ id: 'ok', text: t('verstanden'), haupt: true }] });
}

// ---------------------------------------------------------------------------------------------------------------
// Update-Suche über https://kinolel.de/web/kinolel/apps.json (Schlüssel „windows“): beim Start und alle 3 h
let letztePruefung = 0;
async function jsonHolen(url) {
  const antwort = await net.fetch(url, { cache: 'no-store' });
  if (!antwort.ok) throw new Error('HTTP ' + antwort.status);
  return antwort.json();
}
function portabel() {
  return !fs.existsSync(path.join(path.dirname(process.execPath), 'unins000.exe'));
}
async function updatePruefen(vonHand = false) {
  if (!vonHand && Date.now() - letztePruefung < 60_000) return;
  letztePruefung = Date.now();
  let eintrag;
  try {
    eintrag = (await jsonHolen(TEST_APPS_LISTE || MARKE.appsListe))[MARKE.updateSchluessel];
  } catch (e) {
    log('Versionsliste nicht erreichbar:', e.message);
    return;
  }
  if (!eintrag?.version || !eintrag?.url) return;
  const neu = String(eintrag.version).replace(/^v/i, '');
  const aktuell = TEST_VERSION || app.getVersion();
  log('Update-Suche:', aktuell, '->', neu);
  if (!neuer(neu, aktuell)) {
    if (vonHand) await dialogZeigen({ titel: MARKE.name, text: t('aktuell'), knoepfe: [{ id: 'ok', text: t('ok'), haupt: true }] });
    return;
  }
  if (!vonHand && einst.spaeter?.version === neu && Date.now() < einst.spaeter.bis) return;
  if (portabel() && !process.env.KINOLEL_TEST_INSTALLIERT) {
    const a = await dialogZeigen({ titel: t('updateTitel'), text: t('updateText', neu, aktuell) + '\n\n' + t('portabel'),
      knoepfe: [{ id: 'spaeter', text: t('spaeter') }, { id: 'seite', text: t('downloadSeite'), haupt: true }] });
    if (a === 'seite') shell.openExternal(eintrag.seite || MARKE.releaseSeite);
    else { einst.spaeter = { version: neu, bis: Date.now() + SPAETER_MS }; speichern(); }
    return;
  }
  const a = await dialogZeigen({ titel: t('updateTitel'), text: t('updateText', neu, aktuell),
    knoepfe: [{ id: 'spaeter', text: t('spaeter') }, { id: 'jetzt', text: t('jetzt'), haupt: true }] });
  if (a !== 'jetzt') { einst.spaeter = { version: neu, bis: Date.now() + SPAETER_MS }; speichern(); return; }
  await installieren(eintrag, neu);
}

async function installieren(eintrag, neu) {
  const ziel = path.join(os.tmpdir(), eintrag.datei || `KinoLel-Setup-${neu}-x64.exe`);
  let dialogAnsicht = null;
  const fortschrittDialog = dialogZeigen({ titel: t('updateTitel'), text: t('laedt', neu), knoepfe: [], beiOffen: (v) => { dialogAnsicht = v; } });
  try {
    const antwort = await net.fetch(eintrag.url);
    if (!antwort.ok) throw new Error('HTTP ' + antwort.status);
    const gesamt = Number(antwort.headers.get('content-length')) || 0;
    const datei = fs.createWriteStream(ziel);
    let geladen = 0;
    const leser = antwort.body.getReader();
    for (;;) {
      const { done, value } = await leser.read();
      if (done) break;
      datei.write(Buffer.from(value));
      geladen += value.length;
      if (gesamt) dialogAnsicht?.webContents.send('kinolel-fortschritt', geladen / gesamt);
    }
    await new Promise((r) => datei.end(r));
    log('Update geladen:', ziel, geladen, 'Bytes');
    // still installieren wie bisher (Inno Setup); der Installer startet KinoLel danach wieder
    const protokoll = path.join(os.tmpdir(), 'KinoLel-Update.log');
    const setup = spawn(ziel, ['/SILENT', '/SP-', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', `/LOG=${protokoll}`],
      { detached: true, stdio: 'ignore' });
    await new Promise((gestartet, fehler) => { setup.once('spawn', gestartet); setup.once('error', fehler); });
    setup.unref();
    log('Setup gestartet (Protokoll', protokoll + ')');
    setTimeout(() => app.quit(), 1500);
  } catch (e) {
    log('Update fehlgeschlagen:', e.message);
    if (dialogAnsicht) dialogBeenden(dialogAnsicht, 'fehler');
    await fortschrittDialog;
    await dialogZeigen({ titel: t('updateTitel'), text: t('fehler'), knoepfe: [{ id: 'ok', text: t('ok'), haupt: true }] });
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Grafik-Diagnose (Strg+Umschalt+G): GPU, Video-Dekoder (HEVC?), Funktionsstatus – auch ins Protokoll
async function grafikInfo() {
  log('Grafik-Info angefordert');
  let text = '';
  try {
    // „complete“ kann ohne Grafikkarte lange hängen -> höchstens 4 s, sonst „basic“
    const info = await Promise.race([
      app.getGPUInfo('complete'),
      new Promise((r) => setTimeout(() => r(null), 4000)),
    ]) || await app.getGPUInfo('basic');
    const geraete = (info.gpuDevice || []).map((g) => `${g.vendorId?.toString(16)}:${g.deviceId?.toString(16)} ${g.driverVendor || ''} ${g.driverVersion || ''} ${g.active ? '(aktiv)' : ''}`.trim());
    const dekoder = [...new Set((info.videoDecoding || info.videoDecodeAcceleratorSupportedProfile || []).map((d) => d.profile ?? d.codec ?? JSON.stringify(d)))];
    text = [
      `KinoLel ${app.getVersion()} · Chromium ${process.versions.chrome}`,
      `Windows ${os.release()} · ${os.cpus()[0]?.model || ''}`,
      '', 'Grafikkarte(n):', ...geraete.map((g) => '  ' + g),
      '', 'Funktionen:', ...Object.entries(app.getGPUFeatureStatus()).map(([k, v]) => `  ${k}: ${v}`),
      '', 'Video-Dekoder (Hardware):', ...(dekoder.length ? dekoder.map((d) => '  ' + d) : ['  keine']),
    ].join('\n');
  } catch (e) { text = 'GPU-Info nicht lesbar: ' + e.message; }
  log('Grafik-Info\n' + text);
  const a = await dialogZeigen({ titel: t('grafikTitel'), vor: text,
    knoepfe: [{ id: 'kopieren', text: t('kopieren') }, { id: 'zu', text: t('schliessen'), haupt: true }] });
  if (a === 'kopieren') clipboard.writeText(text);
}

// ---------------------------------------------------------------------------------------------------------------
// Leistungsregeln (gemessen mit startseite.py, Windows ohne GPU): ohne Grafikkarte zeichnet Chromium jedes Bild in Software
// – die Weichzeichner und die laufende Fortschrittsleiste des Karussells lassen die Seite dann dauernd neu zeichnen
// (82 % statt 6 % CPU). Ken-Burns-Zoom bleibt an (Lel 25.10.: „das Zoomen im Karussell fehlt“; KINOLEL_KENBURNS=0 nur
// für den Vergleich im Test). Asynchron eingespielt, damit nichts den Seitenaufbau aufhält. KINOLEL_LEISTUNG=0 = aus.
let ohneGpu = null;
async function gpuBekannt() {
  if (ohneGpu !== null) return ohneGpu;
  try { await Promise.race([app.getGPUInfo('basic'), new Promise((r) => setTimeout(r, 3000))]); } catch (_) {}
  const g = app.getGPUFeatureStatus();
  ohneGpu = /disabled|unavailable/.test(g.gpu_compositing || '');
  return ohneGpu;
}
async function leistungsregeln(wc) {
  if (process.env.KINOLEL_LEISTUNG === '0') return;
  let stil = process.env.KINOLEL_KENBURNS === '0' ? '.backdrop.high-quality{animation:none!important}' : '';
  if (await gpuBekannt()) {
    stil += '*{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}';
    stil += '.spec-rail,.spec-progress{display:none!important}';
  }
  if (stil && !wc.isDestroyed()) wc.insertCSS(stil, { cssOrigin: 'author' }).catch(() => {});
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!fenster) return;
    if (fenster.isMinimized()) fenster.restore();
    fenster.focus();
  });
  anmeldungUebernehmen();
  app.whenReady().then(async () => {
    zeit('electron_bereit');
    log(`Start KinoLel ${app.getVersion()} (Chromium ${process.versions.chrome})`, TV ? 'TV-Modus' : '',
      'GPU:', JSON.stringify(app.getGPUFeatureStatus()));
    fensterOeffnen();
    await neuigkeitenZeigen();
    setTimeout(() => updatePruefen(), 8000);
    setInterval(() => updatePruefen(), PRUEF_ABSTAND_MS);
  });
  app.on('window-all-closed', () => app.quit());
}
