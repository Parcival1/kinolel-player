#!/usr/bin/env python3
"""KinoLel-Player: Programmsymbol, Installer- und Store-Bilder aus dem KinoLel-Logo erzeugen.

Logo = Leinwand + Play-Symbol (weiß) wie auf kinolel.de; Akzent Lavendel, Grund dunkel (siehe marke.cmake).

Aufruf (braucht Pillow; z. B. auf CT 103):
    python3 bilder_erzeugen.py <repo-ordner> [--banner banner-light.png] [--schrift InterDisplay-Bold.otf]

Name/Farben werden aus <repo>/marke.cmake gelesen. Heißt der Player "KinoLel" und ist --banner angegeben,
wird der Schriftzug aus dem Banner von kinolel.de übernommen; sonst wird der Name mit --schrift gesetzt.
Erzeugt:
    resources/images/icon.png          Fenster-/Infobereich-Symbol (256 px)
    resources/images/icon.svg          dasselbe als Vektor
    native/schriftzug.png      Schriftzug für das Startbild (Ladekreis)
    bundle/win/app.ico                 Programmsymbol (16–256 px)
    bundle/win/wizard-image.png        Installer, große Seitenleiste
    bundle/win/wizard-small-image.png  Installer, kleines Bild oben rechts
    bundle/msix/Assets/*.png           Bilder für das MSIX-/Store-Paket
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

# Logo-Geometrie (aus dem SVG-Pfad des Lade-Overlays, viewBox 0 0 677 433)
LOGO_W, LOGO_H = 677, 433
SS = 4  # Überabtastung für glatte Kanten


def marke_lesen(repo):
    werte = {}
    with open(os.path.join(repo, 'marke.cmake'), encoding='utf-8') as f:
        for zeile in f:
            m = re.match(r'\s*set\((\w+)\s+"([^"]*)"\)', zeile)
            if m:
                werte[m.group(1)] = m.group(2)
    return werte


def farbe(hexwert, alpha=255):
    h = hexwert.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def logo_maske(breite, dick=False):
    """Maske (L) des Logos in der gewünschten Breite; Dreieck = Loch (eigene Maske für Akzentfarbe).
    dick=True: kräftigere Variante für sehr kleine Symbole (16–32 px), sonst verschwinden Rahmen und Kreis."""
    s = breite * SS / LOGO_W
    w, h = round(LOGO_W * s), round(LOGO_H * s)
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    rand, r, k = (88, 112, 1.12) if dick else (50, 97, 1.0)  # Rahmenstärke, Kreisradius, Dreieck-Faktor
    d.rounded_rectangle((0, 0, LOGO_W * s, LOGO_H * s), radius=22 * s, fill=255)
    d.rounded_rectangle((rand * s, (rand - 5) * s, (677 - rand) * s, (433 - rand + 5) * s), radius=14 * s, fill=0)
    d.ellipse(((338 - r) * s, (216 - r) * s, (338 + r) * s, (216 + r) * s), fill=255)
    dreieck = [((354.5 + (308 - 354.5) * k) * s, (216 + (156 - 216) * k) * s),
               ((354.5 + (401 - 354.5) * k) * s, 216 * s),
               ((354.5 + (308 - 354.5) * k) * s, (216 + (279 - 216) * k) * s)]
    d.polygon(dreieck, fill=0)
    t = Image.new('L', (w, h), 0)
    ImageDraw.Draw(t).polygon(dreieck, fill=255)
    zu = (round(w / SS), round(h / SS))
    return m.resize(zu, Image.LANCZOS), t.resize(zu, Image.LANCZOS)


def logo_bild(breite, weiss=(255, 255, 255, 255), akzent=None, dick=False):
    m, t = logo_maske(breite, dick)
    bild = Image.new('RGBA', m.size, (0, 0, 0, 0))
    bild.paste(Image.new('RGBA', m.size, weiss), (0, 0), m)
    if akzent:
        bild.paste(Image.new('RGBA', m.size, akzent), (0, 0), t)
    return bild


def hintergrund(w, h, grund, rund=0.0):
    """Dunkler Verlauf wie das Lade-Overlay (Mitte etwas heller), optional abgerundete Ecken."""
    g = farbe(grund)
    hell = (21, 27, 42, 255)  # #151b2a
    bild = Image.new('RGBA', (w, h), g)
    verlauf = Image.radial_gradient('L').resize((w, h), Image.BICUBIC)  # 0 = Mitte, 255 = Rand
    oben = Image.new('RGBA', (w, h), hell)
    maske = verlauf.point(lambda v: max(0, 255 - int(v * 1.6)))
    bild.paste(oben, (0, 0), maske)
    if rund:
        r = round(min(w, h) * rund)
        mk = Image.new('L', (w * SS, h * SS), 0)
        ImageDraw.Draw(mk).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=255)
        mk = mk.resize((w, h), Image.LANCZOS)
        leer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        leer.paste(bild, (0, 0), mk)
        bild = leer
    return bild


def logo_frei(breite, marke, dick=False):
    """Logo OHNE Hintergrundplatte (transparent, Lel 16.10.): weißer Rahmen, dunkle Leinwand innen, weißer Kreis mit
    Play-Dreieck in Lavendel und feine dunkle Kontur außen – so auf hellem und dunklem Grund sichtbar."""
    from PIL import ImageFilter
    s = breite * SS / LOGO_W
    w, h = round(LOGO_W * s), round(LOGO_H * s)
    rand, r, k = (88, 112, 1.12) if dick else (50, 97, 1.0)
    rand_px = max(2, round(breite * SS * (0.035 if dick else 0.022)))  # Konturbreite
    def maske(zeichnen):
        m = Image.new('L', (w + 2 * rand_px, h + 2 * rand_px), 0)
        zeichnen(ImageDraw.Draw(m), rand_px)
        return m
    aussen = maske(lambda d, o: d.rounded_rectangle((o, o, o + LOGO_W * s, o + LOGO_H * s), radius=22 * s, fill=255))
    innen = maske(lambda d, o: d.rounded_rectangle((o + rand * s, o + (rand - 5) * s, o + (677 - rand) * s,
                                                    o + (433 - rand + 5) * s), radius=14 * s, fill=255))
    kreis = maske(lambda d, o: d.ellipse((o + (338 - r) * s, o + (216 - r) * s, o + (338 + r) * s, o + (216 + r) * s), fill=255))
    def dreieck_zeichnen(d, o):
        d.polygon([(o + (354.5 + (308 - 354.5) * k) * s, o + (216 + (156 - 216) * k) * s),
                   (o + (354.5 + (401 - 354.5) * k) * s, o + 216 * s),
                   (o + (354.5 + (308 - 354.5) * k) * s, o + (216 + (279 - 216) * k) * s)], fill=255)
    dreieck = maske(dreieck_zeichnen)
    kontur = aussen.filter(ImageFilter.MaxFilter(rand_px * 2 + 1))
    bild = Image.new('RGBA', aussen.size, (0, 0, 0, 0))
    bild.paste(Image.new('RGBA', aussen.size, farbe(marke['APP_COLOR_BACKGROUND'], 150)), (0, 0), kontur)
    leinwand = hintergrund(aussen.width, aussen.height, marke['APP_COLOR_BACKGROUND'])
    bild.paste(leinwand, (0, 0), innen)
    rahmen = ImageChops.subtract(aussen, innen)
    weiss = Image.new('RGBA', aussen.size, (255, 255, 255, 255))
    bild.paste(weiss, (0, 0), rahmen)
    bild.paste(weiss, (0, 0), kreis)
    bild.paste(Image.new('RGBA', aussen.size, farbe(marke['APP_COLOR_ACCENT'])), (0, 0), dreieck)
    zu = (round(bild.width / SS), round(bild.height / SS))
    return bild.resize(zu, Image.LANCZOS)


def symbol_frei(groesse, marke):
    """Quadratisches Programmsymbol mit transparentem Hintergrund (Logo zentriert, volle Breite)."""
    bild = Image.new('RGBA', (groesse, groesse), (0, 0, 0, 0))
    return mittig(bild, logo_frei(max(8, round(groesse * 0.94)), marke, dick=groesse <= 32))


def mittig(grund, teil, dy=0):
    x = (grund.width - teil.width) // 2
    y = (grund.height - teil.height) // 2 + dy
    grund.alpha_composite(teil, (x, y))
    return grund


def symbol(groesse, marke, platte=True):
    """Programmsymbol: dunkle, abgerundete Platte + weißes Logo, Play-Dreieck in Lavendel."""
    akzent = farbe(marke['APP_COLOR_ACCENT'])
    if platte:
        bild = hintergrund(groesse, groesse, marke['APP_COLOR_BACKGROUND'], rund=0.22)
        anteil = 0.72 if groesse >= 32 else 0.80
    else:
        bild = Image.new('RGBA', (groesse, groesse), (0, 0, 0, 0))
        anteil = 0.92
    return mittig(bild, logo_bild(max(8, round(groesse * anteil)), akzent=akzent, dick=groesse <= 32))


def schriftzug(marke, hoehe, banner=None, schrift=None):
    """Weißer Schriftzug mit dem Namen (transparent)."""
    name = marke['APP_NAME']
    if banner and name == 'KinoLel':
        b = Image.open(banner).convert('RGBA')
        alpha = b.split()[3]
        w, h = b.size
        spalten = [x for x in range(w) if alpha.crop((x, 0, x + 1, h)).getbbox()]
        # erste Lücke > 20 px trennt Logo und Schrift
        start = next(spalten[i] for i in range(1, len(spalten)) if spalten[i] - spalten[i - 1] > 20)
        teil = b.crop((start, 0, w, h))
        teil = teil.crop(teil.getbbox())
        return teil.resize((round(teil.width * hoehe / teil.height), hoehe), Image.LANCZOS)
    if not schrift:
        sys.exit('Für einen anderen Namen als KinoLel bitte --schrift <Schriftdatei.otf> angeben.')
    f = ImageFont.truetype(schrift, hoehe * SS)
    links, oben, rechts, unten = f.getbbox(name)
    bild = Image.new('RGBA', (rechts - links + 4 * SS, unten - oben + 4 * SS), (0, 0, 0, 0))
    ImageDraw.Draw(bild).text((2 * SS - links, 2 * SS - oben), name, font=f, fill=(255, 255, 255, 255))
    bild = bild.crop(bild.getbbox())
    return bild.resize((round(bild.width / bild.height * hoehe), hoehe), Image.LANCZOS)


def logo_mit_name(marke, breite, hoehe, banner, schrift, grund=True, anteil=0.36):
    bild = hintergrund(breite, hoehe, marke['APP_COLOR_BACKGROUND']) if grund else \
        Image.new('RGBA', (breite, hoehe), (0, 0, 0, 0))
    lh = round(hoehe * anteil)
    logo = logo_bild(round(lh * LOGO_W / LOGO_H), akzent=farbe(marke['APP_COLOR_ACCENT']))
    name = schriftzug(marke, round(lh * 0.62), banner, schrift)
    abstand = round(lh * 0.28)
    gesamt = logo.width + abstand + name.width
    if gesamt > breite * 0.86:  # zu breit -> verkleinern
        f = breite * 0.86 / gesamt
        logo = logo.resize((round(logo.width * f), round(logo.height * f)), Image.LANCZOS)
        name = name.resize((round(name.width * f), round(name.height * f)), Image.LANCZOS)
        abstand = round(abstand * f)
        gesamt = logo.width + abstand + name.width
    x = (breite - gesamt) // 2
    bild.alpha_composite(logo, (x, (hoehe - logo.height) // 2))
    bild.alpha_composite(name, (x + logo.width + abstand, (hoehe - name.height) // 2))
    return bild


def svg_symbol(marke):
    g = marke['APP_COLOR_BACKGROUND']
    a = marke['APP_COLOR_ACCENT']
    # 256er-Raster, Logo 72 % breit
    s = 256 * 0.72 / LOGO_W
    tx, ty = (256 - LOGO_W * s) / 2, (256 - LOGO_H * s) / 2
    pfad = ('M22,0H655A22,22 0 0 1 677,22V411A22,22 0 0 1 655,433H22A22,22 0 0 1 0,411V22A22,22 0 0 1 22,0Z'
            'M64,45H613A14,14 0 0 1 627,59V374A14,14 0 0 1 613,388H64A14,14 0 0 1 50,374V59A14,14 0 0 1 64,45Z'
            'M241,216A97,97 0 1 0 435,216A97,97 0 1 0 241,216ZM308,156L401,216L308,279Z')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs><radialGradient id="g" cx="50%" cy="50%" r="70%"><stop offset="0" stop-color="#151b2a"/><stop offset="0.6" stop-color="{g}"/></radialGradient></defs>
  <rect width="256" height="256" rx="56" fill="url(#g)"/>
  <g transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">
    <path d="M308,156L401,216L308,279Z" fill="{a}"/>
    <path fill="#fff" fill-rule="evenodd" d="{pfad}"/>
  </g>
</svg>
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('repo')
    ap.add_argument('--banner', help='banner-light.png von kinolel.de (Schriftzug KinoLel)')
    ap.add_argument('--schrift', help='Schriftdatei für andere Namen, z. B. InterDisplay-Bold.otf')
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    marke = marke_lesen(repo)

    def pfad(*teile):
        p = os.path.join(repo, *teile)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    # Fenster-/Infobereich-Symbol + Vektor – transparent (Lel 16.10.)
    symbol_frei(256, marke).save(pfad('resources', 'images', 'icon.png'))
    with open(pfad('resources', 'images', 'icon.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_symbol(marke))

    # Schriftzug fürs Startbild (Ladekreis): 84 x 21 angezeigt -> 4-fach für hohe Bildschirmauflösung
    sz = schriftzug(marke, 84, a.banner, a.schrift)
    sz.save(pfad('native', 'schriftzug.png'))

    # Windows-Programmsymbol (mehrere Größen)
    groessen = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    bilder = [symbol_frei(g, marke) for g in groessen]
    bilder[-1].save(pfad('bundle', 'win', 'app.ico'), sizes=[(g, g) for g in groessen], append_images=bilder[:-1])

    # Installer-Bilder (Inno Setup, 200 %: 328 x 628 und 110 x 110)
    gross = hintergrund(328, 628, marke['APP_COLOR_BACKGROUND'])
    mittig(gross, logo_bild(220, akzent=farbe(marke['APP_COLOR_ACCENT'])), dy=-60)
    name = schriftzug(marke, 52, a.banner, a.schrift)
    if name.width > 280:
        name = name.resize((280, round(name.height * 280 / name.width)), Image.LANCZOS)
    gross.alpha_composite(name, ((328 - name.width) // 2, 628 // 2 + 40))
    gross.convert('RGB').save(pfad('bundle', 'win', 'wizard-image.png'))
    symbol_frei(110, marke).save(pfad('bundle', 'win', 'wizard-small-image.png'))

    # MSIX-/Store-Bilder
    assets = ('bundle', 'msix', 'Assets')
    # Transparent (Lel 16.10.); die dunkle Leinwand + Kontur halten das Logo auf hellem Grund sichtbar.
    # altform-unplated: Windows legt dann keine Farbplatte hinter das Symbol (Taskleiste, Startmenü).
    symbol_frei(50, marke).save(pfad(*assets, 'StoreLogo.png'))
    symbol_frei(150, marke).save(pfad(*assets, 'Square150x150Logo.png'))
    symbol_frei(44, marke).save(pfad(*assets, 'Square44x44Logo.png'))
    for g in (16, 24, 32, 48, 256):
        symbol_frei(g, marke).save(pfad(*assets, f'Square44x44Logo.targetsize-{g}.png'))
        symbol_frei(g, marke).save(pfad(*assets, f'Square44x44Logo.targetsize-{g}_altform-unplated.png'))
    logo_mit_name(marke, 310, 150, a.banner, a.schrift).save(pfad(*assets, 'Wide310x150Logo.png'))
    logo_mit_name(marke, 620, 300, a.banner, a.schrift).save(pfad(*assets, 'SplashScreen.png'))
    # Vorschau für die Doku
    logo_mit_name(marke, 1200, 300, a.banner, a.schrift).convert('RGB').save(pfad('marke', 'vorschau-logo.png'))
    print('fertig:', marke['APP_NAME'])


if __name__ == '__main__':
    main()
