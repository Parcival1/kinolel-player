// KinoLel: Auto-Update-Hinweis (ersetzt die Jellyfin-Desktop-Updateprüfung).
// Die App (SystemKinoLelUpdate.cpp) prüft die GitHub-Releases; ist eine neuere Version da, fragt dieser Dialog nach.
// „Jetzt aktualisieren“ lädt den Installer, installiert still und startet KinoLel neu.
(function() {
class updatePlugin {
    constructor({ confirm }) {
        this.name = 'Update Plugin';
        this.type = 'input';
        this.id = 'updatePlugin';

        (async () => {
            const api = await window.apiPromise;
            const hu = ((document.documentElement.getAttribute('data-culture') || navigator.language || '')
                .slice(0, 2).toLowerCase() === 'hu');
            const name = (window.jmpInfo && window.jmpInfo.appName) || 'KinoLel';
            const T = hu ? {
                titel: 'Frissítés elérhető',
                text: (v, k) => `A(z) ${name} ${v} verziója elérhető.` + (k ? ' Most frissítsünk? (Kb. 1 perc, utána újraindul.)' : ''),
                jetzt: 'Frissítés most', seite: 'Letöltési oldal', spaeter: 'Később',
                laedt: 'Frissítés letöltése …', fehler: 'A frissítés nem sikerült: '
            } : {
                titel: 'Update verfügbar',
                text: (v, k) => `${name} ${v} ist verfügbar.` + (k ? ' Jetzt aktualisieren? (Dauert etwa 1 Minute, danach startet die App neu.)' : ''),
                jetzt: 'Jetzt aktualisieren', seite: 'Download-Seite', spaeter: 'Später',
                laedt: 'Update wird geladen …', fehler: 'Update fehlgeschlagen: '
            };

            let anzeige = null;
            const zeige = (text) => {
                if (!anzeige) {
                    anzeige = document.createElement('div');
                    anzeige.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2147483646;' +
                        'background:#151b2a;color:#fff;border:1px solid #9aa4ff;border-radius:8px;padding:12px 20px;' +
                        'font:15px "Segoe UI",sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.5)';
                    document.body.appendChild(anzeige);
                }
                anzeige.textContent = text;
            };

            api.system.kinolelUpdateVerfuegbar.connect(async (version, url, seite, einKlick) => {
                try {
                    // kurz warten, damit die Startseite fertig ist
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    await confirm({
                        title: T.titel,
                        text: T.text(version, einKlick),
                        cancelText: T.spaeter,
                        confirmText: einKlick ? T.jetzt : T.seite
                    });
                    if (einKlick) {
                        zeige(T.laedt);
                        api.system.kinolelUpdateInstallieren(url, version);
                    } else {
                        api.system.openExternalUrl(seite);
                    }
                } catch (e) {
                    // „Später“
                }
            });
            api.system.kinolelUpdateFortschritt.connect((prozent) => zeige(`${T.laedt} ${prozent} %`));
            api.system.kinolelUpdateFehler.connect((text) => {
                zeige(T.fehler + text);
                setTimeout(() => { if (anzeige) { anzeige.remove(); anzeige = null; } }, 8000);
            });
            api.system.kinolelUpdatePruefen(false);
        })();
    }
}

window._updatePlugin = updatePlugin;
})();
