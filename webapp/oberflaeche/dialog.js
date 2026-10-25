// KinoLel-Dialog: Inhalt kommt vom Hauptprozess (preload „kinolel“), Antwort = gedrückter Knopf
window.kinolel.inhalt(function (d) {
  document.documentElement.lang = d.sprache || 'de';
  document.getElementById('titel').textContent = d.titel || '';
  var inhalt = document.getElementById('inhalt');
  inhalt.textContent = '';
  if (d.punkte && d.punkte.length) {
    var ul = document.createElement('ul');
    d.punkte.forEach(function (p) { var li = document.createElement('li'); li.textContent = p; ul.appendChild(li); });
    inhalt.appendChild(ul);
  }
  if (d.text) { var p = document.createElement('p'); p.textContent = d.text; inhalt.appendChild(p); }
  if (d.vor) { var pre = document.createElement('pre'); pre.textContent = d.vor; inhalt.appendChild(pre); }
  var knoepfe = document.getElementById('knoepfe');
  knoepfe.textContent = '';
  (d.knoepfe || []).forEach(function (k) {
    var b = document.createElement('button');
    b.textContent = k.text;
    b.id = 'kinolel-' + k.id;
    if (k.haupt) b.className = 'haupt';
    b.addEventListener('click', function () { window.kinolel.antwort(k.id); });
    knoepfe.appendChild(b);
  });
  var haupt = knoepfe.querySelector('.haupt') || knoepfe.querySelector('button');
  if (haupt) haupt.focus();
});
window.kinolel.fortschritt(function (anteil) {
  var f = document.getElementById('fortschritt');
  f.style.display = 'block';
  f.firstElementChild.style.width = Math.round(anteil * 100) + '%';
});
document.addEventListener('keydown', function (e) { if (e.key === 'Escape') window.kinolel.antwort('esc'); });
