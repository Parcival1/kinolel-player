// KinoLel: feste Server-Adresse statt Serverauswahl.
// Die Adresse kommt aus marke.cmake (C++ -> jmpInfo.serverUrl). Die Verbindungsprüfung läuft in C++ und
// wiederholt sich von selbst, bis der Server antwortet; danach geht es direkt zur Anmeldeseite von KinoLel.

const FALLBACK_SERVER = 'https://kinolel.de';

// Name aus marke.cmake; die Texte kommen ohne ungarische Endungen am Namen aus (Name kann sich ändern)
const NAME = (window.jmpInfo && window.jmpInfo.appName) || 'KinoLel';

const TEXTE = {
    de: {
        verbinde: `Verbindung zu ${NAME} wird hergestellt …`,
        weg: `${NAME} ist gerade nicht erreichbar.<br>Bitte Internetverbindung prüfen – es wird weiter versucht.`,
        nochmal: 'Erneut versuchen'
    },
    hu: {
        verbinde: `${NAME} – kapcsolódás …`,
        weg: `${NAME} most nem érhető el.<br>Kérjük, ellenőrizd az internetkapcsolatot – tovább próbálkozunk.`,
        nochmal: 'Újra'
    }
};

const sprache = (navigator.language || 'de').slice(0, 2).toLowerCase() === 'hu' ? 'hu' : 'de';
const T = TEXTE[sprache];
document.documentElement.lang = sprache;
document.title = NAME;
document.getElementById('container').setAttribute('aria-label', NAME);
document.querySelector('.name').alt = NAME;

const statusEl = document.getElementById('status');
const knopf = document.getElementById('nochmal');
knopf.textContent = T.nochmal;

let hinweisTimer = null;
let fehlerTimer = null;

function zeigeStatus(html) {
    statusEl.innerHTML = html;
    statusEl.classList.add('sichtbar');
}

function serverAdresse() {
    const info = window.jmpInfo || {};
    return info.serverUrl || FALLBACK_SERVER;
}

async function verbinden() {
    const server = serverAdresse();
    clearTimeout(hinweisTimer);
    clearTimeout(fehlerTimer);
    knopf.hidden = true;
    statusEl.classList.remove('sichtbar');

    // Hinweise nur, wenn es länger dauert (normal ist es nach < 1 s weg)
    hinweisTimer = setTimeout(() => zeigeStatus(T.verbinde), 3000);
    fehlerTimer = setTimeout(() => {
        zeigeStatus(T.weg);
        knopf.hidden = false;
    }, 15000);

    try {
        console.log('KinoLel: verbinde mit', server);
        const ziel = await window.jmpCheckServerConnectivity(server);
        clearTimeout(hinweisTimer);
        clearTimeout(fehlerTimer);
        // Merken (wird von Jellyfin Desktop intern genutzt), dann direkt zur Anmeldung/Startseite
        window.jmpInfo.settings.main.userWebClient = server;
        window.location = ziel;
    } catch (e) {
        // Nur bei Abbruch (Knopf "Erneut versuchen") oder fehlendem WebChannel
        console.warn('KinoLel: Verbindung unterbrochen:', e);
    }
}

knopf.addEventListener('click', () => {
    if (window.jmpCheckServerConnectivity && window.jmpCheckServerConnectivity.abort) {
        window.jmpCheckServerConnectivity.abort();
    }
    if (window.api && window.api.system) {
        window.api.system.cancelServerConnectivity();
    }
    setTimeout(verbinden, 100);
});

(async () => {
    await window.apiPromise;
    verbinden();
})();
