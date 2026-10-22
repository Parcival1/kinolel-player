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

            // KinoLel (Lel 22.10.2026): einmal nach einem Update zeigen, was neu ist (Texte: native/neuigkeiten.json)
            const neuigkeitenZeigen = (liste) => {
                if (document.getElementById('kl-neuigkeiten')) return;
                const kultur = (document.documentElement.getAttribute('data-culture') || navigator.language || 'de').slice(0, 2).toLowerCase();
                const sp = kultur === 'hu' ? 'hu' : (kultur === 'en' ? 'en' : 'de');
                const version = (window.jmpInfo && window.jmpInfo.version || '').replace(/-.*$/, '');
                const W = {
                    de: { titel: `Neu in ${name} ${version}`, version: (v) => `Version ${v}`, ok: 'Alles klar' },
                    hu: { titel: `Újdonságok – ${name} ${version}`, version: (v) => `${v}. verzió`, ok: 'Rendben' },
                    en: { titel: `New in ${name} ${version}`, version: (v) => `Version ${v}`, ok: 'Got it' }
                }[sp];
                const huelle = document.createElement('div');
                huelle.id = 'kl-neuigkeiten';
                huelle.className = 'kl-neu';
                huelle.style.cssText = 'position:fixed;inset:0;z-index:2147483645;display:flex;align-items:center;justify-content:center;' +
                    'background:rgba(7,10,18,.72);font:16px "Segoe UI",sans-serif';
                const karte = document.createElement('div');
                karte.setAttribute('role', 'dialog');
                karte.setAttribute('aria-modal', 'true');
                karte.style.cssText = 'max-width:560px;width:calc(100% - 48px);max-height:80vh;overflow:auto;background:#151b2a;color:#fff;' +
                    'border:1px solid #9aa4ff;border-radius:14px;padding:22px 26px;box-shadow:0 10px 40px rgba(0,0,0,.6)';
                const h = document.createElement('h2');
                h.textContent = W.titel;
                h.style.cssText = 'margin:0 0 12px;font-size:1.35em;color:#9aa4ff';
                karte.appendChild(h);
                liste.forEach((eintrag) => {
                    if (liste.length > 1) {
                        const v = document.createElement('div');
                        v.textContent = W.version(eintrag.version);
                        v.style.cssText = 'font-weight:600;margin:12px 0 4px;opacity:.85';
                        karte.appendChild(v);
                    }
                    const ul = document.createElement('ul');
                    ul.style.cssText = 'margin:0;padding-left:1.2em;line-height:1.45';
                    (eintrag[sp] || eintrag.de || []).forEach((punkt) => {
                        const li = document.createElement('li');
                        li.textContent = punkt;
                        li.style.margin = '6px 0';
                        ul.appendChild(li);
                    });
                    karte.appendChild(ul);
                });
                const knopf = document.createElement('button');
                knopf.type = 'button';
                knopf.className = 'kl-neu-ok';
                knopf.textContent = W.ok;
                knopf.style.cssText = 'display:block;margin:20px 0 0 auto;border:0;border-radius:999px;padding:10px 26px;' +
                    'background:#9aa4ff;color:#0b0f18;font:600 15px "Segoe UI",sans-serif;cursor:pointer';
                const schliessen = () => {
                    huelle.remove();
                    api.system.kinolelNeuigkeitenGezeigt();
                };
                knopf.addEventListener('click', schliessen);
                huelle.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape' || e.key === 'Enter' || e.key === 'Backspace') { e.preventDefault(); e.stopPropagation(); schliessen(); }
                }, true);
                karte.appendChild(knopf);
                huelle.appendChild(karte);
                document.body.appendChild(huelle);
                knopf.focus();
            };
            // Zuerst die Neuigkeiten (die Update-Prüfung merkt sich ihren Zeitpunkt; davor gilt: noch nie benutzt = Neuinstallation)
            api.system.kinolelNeuigkeiten((liste) => {
                if (liste && liste.length) setTimeout(() => neuigkeitenZeigen(liste), 2500);
                api.system.kinolelUpdatePruefen(false);
            });
        })();
    }
}

window._updatePlugin = updatePlugin;
})();
