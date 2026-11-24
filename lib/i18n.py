"""
Translations of the texts the add-in shows. The English text in the code is the key, t() gives it in the language
of LANGUAGE, texts without a translation stay English.

Only what is shown is translated: dialog labels, tooltips, messages, and the names of sketches and construction
planes (see sketchName). Other names that end up in the design (bodies, timeline features, parameters, the settings
kept in a body's tag) and config files stay English, the add-in finds them again by those names. Dropdown items are
shown translated but kept in English, see item() and key().

The pages of the dialogs have their own dictionary, see lib/ui/html/i18n.js
"""

# 'de' German, 'en' English, 'auto' German when Fusion is set to German, English otherwise
LANGUAGE = 'auto'

_language: str | None = None
# shown text to the English one, for dropdown items and labels kept in English, see key()
_reverse: dict[str, str] = {}


def language() -> str:
    global _language
    if _language is None:
        _language = LANGUAGE
        if LANGUAGE == 'auto':
            try:
                # imported here, the modules kept free of Fusion for their tests import this one too
                import adsk.core
                isGerman = adsk.core.Application.get().preferences.generalPreferences.userLanguage == adsk.core.UserLanguages.GermanLanguage
                _language = 'de' if isGerman else 'en'
            except Exception:
                _language = 'en'
    return _language


def t(text: str, **values) -> str:
    """The text in the add-in's language, {name} placeholders are filled from values"""
    shown = DE.get(text, text) if language() == 'de' else text
    if shown != text:
        _reverse.setdefault(shown, text)
    return shown.format(**values) if values else shown


def pageQuery() -> str:
    """The query that tells a page its language, see lib/ui/html/i18n.js, none for English"""
    return f'?lang={language()}' if language() != 'en' else ''


def item(name: str) -> str:
    """A dropdown item as shown, key() gives its English name back"""
    shown = t(name)
    _reverse[shown] = name
    return shown


def key(shown: str) -> str:
    """The English text of a translated one, for dropdown items and labels the add-in keeps in English"""
    return _reverse.get(shown, shown)


def sketchName(name: str) -> str:
    """Foot sketch shows as Skizze Fuß. Sketches and construction planes are only named for the browser,
    the add-in doesn't look them up by name, so unlike bodies and features they can be translated"""
    return _partName(name, ' sketch', 'Skizze')


def planeName(name: str) -> str:
    """Compartment 2 cavity plane shows as Ebene Fach 2, Hohlraum, see sketchName"""
    return _partName(name, ' plane', 'Ebene')


def _partName(name: str, suffix: str, kind: str) -> str:
    if language() != 'de':
        return name
    base = name[:-len(suffix)] if name.endswith(suffix) else name
    return f'{kind} {partText(base)}'


def partText(text: str) -> str:
    """The generated names are built from the pieces of PARTS_DE, e.g. Lip cutout groove layer 1, the pieces are
    translated one by one, longest first, and joined with commas: Stapelrand-Ausschnitt, Rille Lage 1.
    Numbers and single axis letters stay with the piece before them, unknown words stay English"""
    words = text.split(' ')
    pieces: list[str] = []
    index = 0
    while index < len(words):
        for end in range(len(words), index, -1):
            phrase = ' '.join(words[index:end]).lower()
            if phrase in PARTS_DE:
                pieces.append(PARTS_DE[phrase])
                index = end
                break
        else:
            # numbers, axis letters and unknown words go with the piece before them
            if pieces:
                pieces[-1] += f' {words[index]}'
            else:
                pieces.append(words[index])
            index += 1
    shown = ', '.join(pieces)
    return shown[:1].upper() + shown[1:]


# pieces of the sketch and plane names, lower case
PARTS_DE: dict[str, str] = {
    # bin
    'bin body': 'Boxkörper',
    'foot': 'Fuß',
    'joint origin': 'Gelenkursprung',
    'lip body': 'Stapelrand',
    'lip cutout': 'Stapelrand-Ausschnitt',
    'lip middle cutout': 'Stapelrand-Ausschnitt Mitte',
    'lip top chamfer': 'Stapelrand-Fase oben',
    'lip bottom chamfer': 'Stapelrand-Fase unten',
    'lip notch': 'Stapelrand-Kerbe',
    'lip support': 'Stapelrand-Stütze',
    'lip support inside': 'Stapelrand-Stütze innen',
    'box': 'Quader',
    'cone': 'Kegel',
    'compartment': 'Fach',
    'compartments top clearance': 'Fächer, Freiraum oben',
    'cavity': 'Hohlraum',
    'label tab': 'Beschriftungslasche',
    'label': 'Beschriftung',
    'hollow': 'Aushöhlung',
    'icon': 'Symbol',
    'text': 'Text',
    'front': 'vorne',
    'back opening': 'Öffnung hinten',
    'min x corner opening': 'Ecköffnung min. X',
    'max x corner opening': 'Ecköffnung max. X',
    'min x side opening': 'Seitenöffnung min. X',
    'max x side opening': 'Seitenöffnung max. X',
    'outer clearance trim': 'Außenspiel-Beschnitt',
    'shell interior': 'Schale innen',
    'wall junction pocket': 'Wandecken-Tasche',
    'wall crease': 'Wandfalz',
    'wall crease inside': 'Wandfalz innen',
    'profile': 'Profil',
    'panel': 'Feld',
    # feet and sockets
    'xz mid': 'Mitte XZ',
    'yz mid': 'Mitte YZ',
    'groove': 'Rille',
    'groove layer': 'Rille Lage',
    'magnet socket': 'Magnetaufnahme',
    'magnet tab': 'Klemmnase',
    'screw hole': 'Schraubloch',
    'screw head': 'Schraubenkopf',
    'half width': 'halbe Breite',
    'half length': 'halbe Länge',
    'half corner': 'halbe Ecke',
    # baseplate
    'plate': 'Platte',
    'socket': 'Aufnahme',
    'socket cell': 'Aufnahmezelle',
    'cell': 'Zelle',
    'skeleton cutout': 'Skelett-Ausschnitt',
    'connection hole': 'Verbindungsloch',
    'outline trim': 'Umriss-Beschnitt',
    'pieces cut': 'Teile-Schnitt',
    'padding left': 'Rand links',
    'padding right': 'Rand rechts',
    'padding top': 'Rand oben',
    'padding bottom': 'Rand unten',
}


DE: dict[str, str] = {
    # --- common
    'Info': 'Info',
    'Preview': 'Vorschau',
    'Last preview': 'Letzte Vorschau',
    'None yet': 'Noch keine',
    'failed after {seconds} s': 'fehlgeschlagen nach {seconds} s',
    'Some inputs are invalid, unable to generate preview': 'Einige Eingaben sind ungültig; keine Vorschau möglich',
    'Main dimensions': 'Hauptmaße',
    'Bin xy clearance (mm)': 'XY-Spiel der Box (mm)',
    'Add joint origins': 'Gelenkursprünge setzen',
    'Add screw holes': 'Schraublöcher erzeugen',
    'Screw hole diameter': 'Ø Schraubloch',
    'Magnet cutout diameter': 'Ø Magnetaufnahme',
    'Magnet cutout depth': 'Tiefe Magnetaufnahme',
    'Yes': 'Ja',
    'No': 'Nein',
    'Version {version}': 'Version {version}',
    'An unknown error occurred, please validate your inputs and try again':
        'Ein unbekannter Fehler ist aufgetreten; bitte Eingaben prüfen und erneut versuchen',
    '{name} Error': '{name}: Fehler',
    '{name} failed to initialize': '{name} konnte nicht gestartet werden',
    '{name} Critical error occurred at the start, the command will be unavailable, if the issue persists use <a href="https://github.com/Le0Michine/FusionGridfinityGenerator/issues/new">this link</a> to report it':
        '{name}: Kritischer Fehler beim Start, der Befehl ist nicht verfügbar. Bleibt das Problem bestehen, bitte <a href="https://github.com/Le0Michine/FusionGridfinityGenerator/issues/new">hier melden</a> (englisch)',
    'Design type is unsupported. Projects with disabled design history are unsupported, please enable timeline feature to proceed.':
        'Konstruktionstyp nicht unterstützt. Projekte ohne Konstruktionsverlauf gehen nicht; bitte Zeitachse aktivieren.',
    'See the {palette} panel to copy a report of it': 'Im Fenster „{palette}“ lässt sich ein Fehlerbericht kopieren',
    'Gridfinity error': 'Gridfinity-Fehler',
    'Rebuilding': 'Neuaufbau',
    'Cloned': 'Geklont',
    'Loaded "{fileName}"': '„{fileName}“ geladen',

    # --- bin dialog
    'Gridfinity bin': 'Gridfinity-Box',
    'Creates a gridfinity bin that drops into a baseplate.\n\n'
    'Set its size in base and height units, then pick a hollow, shelled or solid body with a stacking lip, '
    'compartments, a scoop, a label tab and magnet or screw holes in its feet. '
    'A custom shape fills odd spots like a tetris piece.':
        'Erzeugt eine Gridfinity-Box für eine Grundplatte.\n\nGröße in Raster- und Höheneinheiten festlegen, dann hohlen, schalenförmigen oder massiven Körper wählen – mit Stapelrand, Fächern, Griffmulde, Lasche sowie Magnet- oder Schraublöchern. Eine eigene Form füllt Lücken wie ein Tetris-Teil.',
    '<b>Help:</b> Info for inputs can be found <a href="https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options">Here on our GitHub</a>.':
        '<b>Hilfe:</b> Erklärungen zu den Eingaben gibt es '
        '<a href="https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Bin-generator-options">hier auf GitHub</a> (englisch).',
    '<b>Rebuilding {name}</b> in place, features after it in the timeline are kept. Changing only what its parameters hold, like its height or label, sets them instead.':
        '<b>{name} wird an Ort und Stelle neu aufgebaut</b>; spätere Features in der Zeitachse bleiben erhalten. Ändern sich nur Parameterwerte (z. B. Höhe oder Beschriftung), werden nur diese angepasst.',
    'Basic sizes': 'Grundmaße',
    'Base width unit (mm)': 'Rasterbreite (mm)',
    'Base length unit (mm)': 'Rasterlänge (mm)',
    'Bin height unit (mm)': 'Höheneinheit (mm)',
    'Set in base units': 'In Rastereinheiten',
    'Bin width, X (u)': 'Breite X (u)',
    'Bin length, Y (u)': 'Länge Y (u)',
    'In whole or half base units': 'In ganzen oder halben Rastereinheiten',
    'Half grid': 'Halbes Raster',
    'Puts the bin on half size feet, for a half grid baseplate, the bin keeps its size in base units. '
    'Without it a size ending in a half gets whole feet and a row of half feet along the back or right side, halved across the row only. '
    'Half feet have no magnet or screw holes, there is no room for them':
        'Setzt die Box auf halb so große Füße (für Grundplatten mit halbem Raster); die Größe in Rastereinheiten bleibt gleich. Ohne diese Option erhält eine Größe mit ,5 ganze Füße und hinten oder rechts eine Reihe halber Füße (nur quer zur Reihe halbiert). Halbe Füße haben aus Platzgründen keine Magnet- oder Schraublöcher',
    'Bin height, Z (u)': 'Höhe Z (u)',
    'Custom shape': 'Eigene Form',
    'Shows a drawing of the bin cells to leave some of them out, so the bin fills an L or another tetris like spot. Unticking it fills every cell again':
        'Zeigt die Zellen der Box, um einzelne wegzulassen (z. B. für L- oder Tetris-Formen). Abwählen füllt wieder alle Zellen',
    'Actual bin dimensions': 'Tatsächliche Außenmaße der Box',
    'Width': 'Breite',
    'Length': 'Länge',
    'Height': 'Höhe',
    'Width: {value}mm': 'B: {value} mm',
    'Length: {value}mm': 'L: {value} mm',
    'Height: {value}mm': 'H: {value} mm',
    'Bin features': 'Box-Eigenschaften',
    'Generate body': 'Körper erzeugen',
    'Bin type': 'Box-Typ',
    'Hollow': 'Hohl',
    'Shelled': 'Schale',
    'Solid': 'Massiv',
    'Bin wall thickness': 'Wandstärke',
    'Generate lip for stackability': 'Stapelrand erzeugen',
    'Generate lip notches': 'Kerben im Stapelrand',
    'Fold long walls for stiffness': 'Lange Wände falzen',
    'Folds walls of hollow and shelled bins in along shallow creases, origami style, so tall long walls bow less. '
    'Bins from the min height with a wall from the min length get them. Walls are split into even panels up to the max panel length, '
    'walls shorter than a panel of the longest one stay flat. '
    'The scoop wall stays flat, the scoop braces it. A creased bin has a single compartment and a solid label tab':
        'Falzt die Wände hohler und schalenförmiger Boxen leicht nach innen (Origami-Prinzip), damit sich hohe, lange Wände weniger durchbiegen. Gilt ab Mindesthöhe und Mindestwandlänge. Wände werden in gleiche Felder bis zur max. Feldlänge geteilt; kürzere Wände als ein Feld der längsten Wand bleiben glatt. Die Wand mit Griffmulde bleibt glatt, da die Mulde sie versteift. Gefalzte Boxen haben nur ein Fach und eine massive Lasche',
    'Crease depth': 'Falztiefe',
    'Creased wall min length (u)': 'Falz ab Wandlänge (u)',
    'Crease panel max length (u)': 'Max. Feldlänge (u)',
    'Creased bin min height (u)': 'Falz ab Boxhöhe (u)',
    'Bin compartments': 'Fächer',
    'Edit compartment layout': 'Fächer bearbeiten',
    'Shows a drawing of the compartment grid to merge cells into larger compartments and give each its own label and depth. Unticking it resets the compartments to the uniform grid':
        'Zeigt das Fächerraster, um Zellen zu verbinden und ihnen eigene Beschriftungen und Tiefen zu geben. Abwählen setzt das Raster zurück',
    'Scoop': 'Griffmulde',
    'Add scoop (along bin width)': 'Griffmulde (entlang Breite)',
    'Scoop max radius (mm)': 'Max. Muldenradius (mm)',
    'Label tab': 'Beschriftungslasche',
    'Add label tab (along bin width)': 'Lasche (entlang Breite)',
    'Tab length (u)': 'Laschenlänge (u)',
    'Tab width (mm)': 'Laschenbreite (mm)',
    'Tab offset (u)': 'Laschenversatz (u)',
    'Tab overhang angle': 'Überhangwinkel',
    'Tab top angle': 'Neigung Oberseite',
    'Tilts the tab top down towards the front, so the label faces the front of the bin':
        'Neigt die Oberseite der Lasche nach vorne, damit die Beschriftung nach vorne zeigt',
    'Hollow tab': 'Hohle Lasche',
    'Shells the tab with the wall thickness. With a single compartment it is opened through the back wall of the bin, with more compartments it is left closed. On by default for shelled bins':
        'Höhlt die Lasche mit der Wandstärke aus. Bei einem Fach ist sie durch die Rückwand offen, bei mehreren geschlossen. Bei Schalen-Boxen standardmäßig an',
    'Open through side walls': 'Seitlich offen',
    'Also opens a hollow tab through the side walls of the bin where it runs into them, not only through the back wall. Only for a single compartment':
        'Öffnet eine hohle Lasche auch durch die Seitenwände, wo sie auf diese trifft – nicht nur durch die Rückwand. Nur bei einem Fach',
    'Label text': 'Beschriftungstext',
    'Text on every compartment label, compartments in the drawing above can have their own. Each label gets a text parameter to edit it later':
        'Text auf jeder Fachbeschriftung; Fächer oben können eigene erhalten. Jede Beschriftung bekommt einen Textparameter zum späteren Ändern',
    'Label icon': 'Symbol',
    'None': 'Keins',
    'Label style': 'Beschriftungsart',
    'Outline splits the tab face along the label so a slicer can color it, engraved cuts it in, embossed raises it from a lowered tab':
        'Kontur teilt die Laschenfläche entlang der Schrift für den Slicer, graviert schneidet sie ein, erhaben hebt sie aus einer abgesenkten Lasche hervor',
    'Outline': 'Kontur',
    'Engraved': 'Graviert',
    'Embossed': 'Erhaben',
    'Bold label text': 'Fette Schrift',
    # label icons, named after their files in lib/gridfinityUtils/labelIcons, keep in step with i18n.js
    'Button head phillips screw': 'Linsenkopfschraube, Kreuzschlitz',
    'Button head phillips self tapping screw': 'Linsenkopf-Blechschraube, Kreuzschlitz',
    'Button head screw': 'Linsenkopfschraube',
    'Button head self tapping screw': 'Linsenkopf-Blechschraube',
    'Button head slotted screw': 'Linsenkopfschraube, Schlitz',
    'Countersunk phillips screw': 'Senkkopfschraube, Kreuzschlitz',
    'Countersunk phillips self tapping screw': 'Senkkopf-Blechschraube, Kreuzschlitz',
    'Countersunk screw': 'Senkkopfschraube',
    'Countersunk self tapping screw': 'Senkkopf-Blechschraube',
    'Countersunk slotted screw': 'Senkkopfschraube, Schlitz',
    'Grub screw': 'Gewindestift',
    'Socket head screw': 'Zylinderkopfschraube',
    'Hex locknut': 'Sicherungsmutter',
    'Hex nut': 'Sechskantmutter',
    'Square nut': 'Vierkantmutter',
    'Washer': 'Unterlegscheibe',
    'Base interface features': 'Füße',
    'Generate base': 'Füße erzeugen',
    'A joint origin at the bottom center of every foot, to joint the bin into baseplate sockets':
        'Ein Gelenkursprung unten mittig an jedem Fuß, um die Box per Gelenk in Grundplatten-Aufnahmen zu setzen',
    'Add magnet sockets': 'Magnetaufnahmen',
    'Add tabs to magnet sockets': 'Klemmnasen für Magnete',
    'Changes': 'Eingaben',
    'Show auto update preview (slow)': 'Auto-Vorschau (langsam)',
    'Update preview once': 'Vorschau aktualisieren',
    'Compartments, scoop and label tab are not built for custom shapes yet':
        'Fächer, Griffmulde und Lasche werden für eigene Formen noch nicht erzeugt',
    'Pick at least one cell': 'Mindestens eine Zelle auswählen',
    'All cells must form one piece, joined along their sides': 'Alle Zellen müssen über ihre Seiten zusammenhängen',
    'Shapes with holes are not supported yet': 'Formen mit Löchern werden noch nicht unterstützt',
    'The bin was rebuilt. These features after it need a look, ones using a face or an edge of the old bin need them picked again:\n\n':
        'Die Box wurde neu aufgebaut. Nachfolgende Features prüfen; Flächen oder Kanten der alten Box müssen neu gewählt werden:\n\n',
    # settings kept with a body, translated when shown
    'Grid': 'Raster',
    'Compartments': 'Fächeraufteilung',
    'Compartment {index}': 'Fach {index}',
    'Shape': 'Form',
    'Row {index}': 'Reihe {index}',

    # --- baseplate dialog
    'Gridfinity baseplate': 'Gridfinity-Grundplatte',
    'Creates a gridfinity baseplate for bins to sit in.\n\n'
    'Set its size in base units, or fill an area such as a drawer, split into pieces that fit the print bed, '
    'with half cells and padding taking up the rest. Magnet and screw holes and holes to connect the pieces are optional.':
        'Erzeugt eine Gridfinity-Grundplatte für Boxen.\n\nGröße in Rastereinheiten festlegen oder eine Fläche (z. B. Schublade) füllen, passend fürs Druckbett geteilt – mit halben Zellen und Rand als Ausgleich. Magnet-, Schraub- und Verbindungslöcher optional.',
    '<b>Help:</b> Info for inputs can be found <a href="https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Baseplate-generator-options">Here on our GitHub</a>.':
        '<b>Hilfe:</b> Erklärungen zu den Eingaben gibt es '
        '<a href="https://github.com/Le0Michine/FusionGridfinityGenerator/wiki/Baseplate-generator-options">hier auf GitHub</a> (englisch).',
    '<b>Rebuilding {name}</b> in place, features after it in the timeline are kept.':
        '<b>{name} wird an Ort und Stelle neu aufgebaut</b>; spätere Features in der Zeitachse bleiben erhalten.',
    'Basic size': 'Grundeinstellungen',
    'Base width unit, X (mm)': 'Rasterbreite X (mm)',
    'Base length unit, Y (mm)': 'Rasterlänge Y (mm)',
    "Gap on each side between a bin and its cell, the sockets are made larger by it. Keep it the same as the bins' xy clearance. Must be within range [0.1, 0.5]mm":
        'Spalt je Seite zwischen Box und Zelle (Aufnahmen werden entsprechend größer). Sollte dem XY-Spiel der Boxen entsprechen. Bereich: 0,1 bis 0,5 mm',
    'Sizing mode': 'Größenmodus',
    'Fill area generates the grid for a whole area, e.g. a drawer, split into pieces fitting the print bed':
        '„Fläche füllen“ erzeugt das Raster für eine ganze Fläche (z. B. Schublade), aufgeteilt in Teile für das Druckbett',
    'Fill area': 'Fläche füllen',
    'Grid units': 'Rastereinheiten',
    'Plate width, X (u)': 'Plattenbreite X (u)',
    'Plate length, Y (u)': 'Plattenlänge Y (u)',
    'Area width, X': 'Flächenbreite X',
    'Area length, Y': 'Flächenlänge Y',
    'Grid position, X': 'Rasterlage X',
    'Grid position, Y': 'Rasterlage Y',
    'Side the grid is pushed to, the padding fills the rest of the space': 'Seite, an die das Raster geschoben wird; der Rand füllt den restlichen Platz',
    'Left': 'Links',
    'Center': 'Mitte',
    'Right': 'Rechts',
    'Front': 'Vorne',
    'Back': 'Hinten',
    'Fill gaps with half cells': 'Lücken: halbe Zellen',
    'Where the space left past the grid fits a row of half size sockets, adds one instead of solid padding':
        'Reicht der Platz neben dem Raster für eine Reihe halber Aufnahmen, wird diese statt eines massiven Rands eingefügt',
    'Print bed': 'Druckbett',
    'Printer': 'Drucker',
    'Custom': 'Benutzerdefiniert',
    'Bed width, X': 'Bettbreite X',
    'Bed length, Y': 'Bettlänge Y',
    'Bed margin': 'Randabstand',
    'Space kept clear on every side of the bed': 'Freier Abstand an jeder Seite des Druckbetts',
    'Result': 'Ergebnis',
    'Features': 'Merkmale',
    'Baseplate type': 'Plattentyp',
    'Light': 'Leicht',
    'Skeletonized': 'Skelettiert',
    'Full': 'Voll',
    'A joint origin at the bottom center of every socket, to joint bins into it':
        'Ein Gelenkursprung unten mittig in jeder Aufnahme, um Boxen per Gelenk einzusetzen',
    'Magnet cutouts': 'Magnete',
    'Add magnet cutouts': 'Magnetaufnahmen erzeugen',
    'Screw holes': 'Schraublöcher',
    'Screw head cutout diameter': 'Ø Schraubenkopf',
    'Must be greater than screw diameter': 'Muss größer als der Schraubloch-Ø sein',
    'Side padding': 'Seitlicher Rand',
    'Add side padding': 'Seitlichen Rand erzeugen',
    'Padding left': 'Rand links',
    'Padding top': 'Rand oben',
    'Padding right': 'Rand rechts',
    'Padding bottom': 'Rand unten',
    'Must be equal or greater than 0': 'Muss mindestens 0 sein',
    'Advanced plate size options': 'Erweiterte Plattenoptionen',
    'Add connection holes': 'Verbindungslöcher',
    'Connection hole diameter': 'Ø Verbindungsloch',
    'Inputs': 'Eingaben',
    'Show preview (slow)': 'Vorschau (langsam)',
    'The baseplate was rebuilt. These features after it need a look, ones using a face or an edge of the old baseplate need them picked again:\n\n':
        'Die Grundplatte wurde neu aufgebaut. Nachfolgende Features prüfen; Flächen oder Kanten der alten Grundplatte müssen neu gewählt werden:\n\n',
    'Base units must be greater than 0': 'Rastereinheiten müssen größer als 0 sein',
    'Plate size must be at least 1 x 1 u': 'Die Platte muss mindestens 1 x 1 u groß sein',
    'The area is too small to fit a single cell': 'Die Fläche ist zu klein für eine Zelle',
    'The print bed is too small to fit a single cell with the side padding': 'Das Druckbett ist zu klein für eine Zelle samt seitlichem Rand',
    # drawing caption
    '{count} piece': '{count} Teil',
    '{count} pieces': '{count} Teile',
    ', {count} unique': ', {count} verschiedene',
    ', half cells {sides}': ', halbe Zellen {sides}',
    'padding X {x} mm, Y {y} mm': 'Rand X {x} mm, Y {y} mm',
    'padding {sides} mm': 'Rand {sides} mm',
    'no padding': 'kein Rand',
    ', turned 90° on the bed': ', auf dem Bett um 90° gedreht',
    'left': 'links',
    'right': 'rechts',
    'top': 'oben',
    'bottom': 'unten',
    'front': 'vorne',
    'back': 'hinten',

    # --- settings window
    'Gridfinity settings': 'Gridfinity-Einstellungen',
    'Show the settings this bin or baseplate was generated with': 'Zeigt die Einstellungen, mit denen diese Box oder Grundplatte erzeugt wurde',
    'Gridfinity rebuild': 'Gridfinity neu aufbauen',
    'Open the generator dialog with the settings of this bin or baseplate to build it again in its place, keeping the features after it':
        'Öffnet den Generator mit diesen Einstellungen zum Neuaufbau an derselben Stelle; spätere Features bleiben erhalten',
    'Gridfinity clone': 'Gridfinity klonen',
    'Open the generator dialog with the settings of this bin or baseplate to build a new one':
        'Öffnet den Generator mit den Einstellungen dieser Box oder Grundplatte, um eine neue zu erzeugen',
    'Close': 'Schließen',
    'Select a generated bin or baseplate.': 'Erzeugte Box oder Grundplatte auswählen.',
    'Select a generated bin or baseplate to rebuild.': 'Erzeugte Box oder Grundplatte zum Neuaufbau auswählen.',
    'Select a generated bin or baseplate to clone.': 'Erzeugte Box oder Grundplatte zum Klonen auswählen.',
    'Rebuild': 'Neu aufbauen',
    'Open the {title} dialog with these settings to build this {title} again in its place, keeping the features after it':
        'Öffnet den Dialog „{title}“ mit diesen Einstellungen, um diese {title} an derselben Stelle neu aufzubauen; spätere Features bleiben erhalten',
    'Generated with version {version}': 'Erzeugt mit Version {version}',
    'unknown': 'unbekannt',
    'Parameters': 'Parameter',
    'missing, deleted or renamed': 'fehlt, gelöscht oder umbenannt',
    "Settings weren't recorded, this was generated before the generator kept them.":
        'Keine Einstellungen vorhanden; wurde vor Einführung dieser Funktion erzeugt.',
    # parameter labels kept in a baseplate's tag
    'Base width unit': 'Rasterbreite',
    'Base length unit': 'Rasterlänge',
    'Bin height (u)': 'Boxhöhe (u)',
    'Height unit': 'Höheneinheit',
    'Label': 'Beschriftung',
    'Compartment {index} label': 'Beschriftung Fach {index}',

    # --- config buttons
    'bin': 'Box',
    'baseplate': 'Grundplatte',
    'Save to file': 'Speichern',
    'Save these {title} settings to a JSON file': 'Einstellungen ({title}) als JSON-Datei speichern',
    'Load from file': 'Laden',
    'Set the inputs from {title} settings saved to a file': 'Eingaben aus gespeicherter Datei ({title}) laden',
    'Copy': 'Kopieren',
    'Copied': 'Kopiert',
    'Copy these {title} settings to the clipboard as JSON': 'Einstellungen ({title}) als JSON in die Zwischenablage kopieren',
    'Clone into new {title}': 'Als neue {title} klonen',
    'Open the {title} dialog with these settings': 'Öffnet den Dialog „{title}“ mit diesen Einstellungen',
    'Gridfinity config': 'Gridfinity-Konfiguration',
    'Gridfinity config (*.json);;All files (*.*)': 'Gridfinity-Konfiguration (*.json);;Alle Dateien (*.*)',
    'Save Gridfinity config': 'Gridfinity-Konfiguration speichern',
    'Load Gridfinity config': 'Gridfinity-Konfiguration laden',
    "Couldn't save the config to {fileName}:\n{err}": 'Konfiguration konnte nicht nach {fileName} gespeichert werden:\n{err}',
    "Couldn't read {fileName}:\n{err}": '{fileName} konnte nicht gelesen werden:\n{err}',
    "Couldn't copy to the clipboard:\n{err}": 'Kopieren in die Zwischenablage fehlgeschlagen:\n{err}',
    "Couldn't read the config. {err}": 'Konfiguration konnte nicht gelesen werden. {err}',
    '{source} with changes:\n\n{details}': '{source}, mit Änderungen:\n\n{details}',
    'Not recognised, skipped:': 'Unbekannt, übersprungen:',
    'Not in the file, kept the current value:': 'Nicht in Datei, aktueller Wert behalten:',
    'Unknown option, used the default:': 'Unbekannte Option, Standard verwendet:',
    'yes': 'ja',
    'no': 'nein',
    '{count} items': '{count} Einträge',

    # --- rebuild notes
    'needs its inputs picked again': 'Eingaben müssen neu gewählt werden',
    "{name}: couldn't be given the new {title}": '{name}: konnte nicht mit der neuen {title} verknüpft werden',
    "{name}: of the old {title}, Fusion wouldn't delete it, it's suppressed instead":
        '{name}: gehört zur alten {title}. Fusion konnte es nicht löschen; es wurde stattdessen unterdrückt',

    # --- version 2.6
    'Placement': 'Platzierung',
    'Snaps the bin to the free grid spot closest to the origin, next to bins already there, or centers it on the origin': 'Setzt die Box auf den freien Rasterplatz, der dem Ursprung am nächsten ist, neben vorhandene Boxen, oder mittig auf den Ursprung',
    'Snap to free spot': 'Freier Platz',
    'Center on origin': 'Mittig auf Ursprung',
    'Lip type': 'Stapelrand',
    'Light keeps the inside of the lip straight down to the bin top. Full follows the original Gridfinity profile, narrowing to an inner tip with a support under it, and a scoop wall as thick as the tip': 'Leicht: Die Innenseite des Stapelrands geht gerade bis zur Oberkante der Box. Voll: originales Gridfinity-Profil, das sich zu einer inneren Spitze mit Stütze darunter verjüngt, die Greifmulde so dick wie die Spitze',
    'Trim lip top': 'Rand oben kappen',
    'Cuts the top of the lip flat, 0.6mm lower, instead of the sharp edge of the original profile': 'Kappt den Stapelrand oben 0,6 mm tiefer flach statt der scharfen Kante des Originalprofils',
    'Tab top offset (mm)': 'Lasche tiefer (mm)',
    'How far the tab is below the top of the bin, up to 2mm, the label goes down with it. Dividers between compartments are lowered as much': 'Wie weit die Lasche unter der Oberkante der Box liegt, bis 2 mm; die Beschriftung geht mit. Die Trennwände der Fächer werden genauso abgesenkt',
    'Actual dimensions': 'Tatsächliche Maße',
    'Width in inches': 'Breite in Zoll',
    'Length in inches': 'Länge in Zoll',
    'Height in inches': 'Höhe in Zoll',
    'Total bin width: {value}': 'Gesamtbreite Box: {value}',
    'Total bin length: {value}': 'Gesamtlänge Box: {value}',
    'Total bin height: {value}': 'Gesamthöhe Box: {value}',
    'Plate edge clearance (mm)': 'Randspiel Platte (mm)',
    'How far the edge of a plate stops short of the grid line where it meets another, fill pieces or grid units plates glued side by side leave twice it between them. Must be within range [0.025, 0.25]mm': 'Wie weit der Rand einer Platte vor der Rasterlinie endet, an der sie an eine andere stößt. Nebeneinander geklebte Teile haben den doppelten Abstand. Bereich [0,025, 0,25] mm',
    'Bottom padding (mm)': 'Boden zusätzlich (mm)',
    'Solid layer under the sockets of Skeletonized and Full plates, where the magnet sockets and screw holes go. Must be greater than 0': 'Massive Schicht unter den Aufnahmen von skelettierten und vollen Platten, für Magnetaufnahmen und Schraublöcher. Muss größer als 0 sein',
    'Top trim (mm)': 'Oben kappen (mm)',
    'How much is cut off the top of the plate, leaving the ridges between the sockets flat, so a bin sits on its feet in the sockets rather than on the ridges. Must be within range [0, 3]mm': 'Wie viel oben von der Platte abgeschnitten wird, sodass die Stege zwischen den Aufnahmen flach sind und eine Box auf ihren Füßen steht statt auf den Stegen. Bereich [0, 3] mm',
    'Gridfinity export': 'Gridfinity-Export',
    'Export bins and baseplates for printing, 3MF with the label letters in a color of their own, or STL and STEP files': 'Boxen und Grundplatten für den Druck exportieren: 3MF mit eigener Farbe für die Beschriftung, oder STL- und STEP-Dateien',
    'All Gridfinity bodies': 'Alle Gridfinity-Körper',
    'Selects all visible bins and baseplates': 'Wählt alle sichtbaren Boxen und Grundplatten',
    'Bodies': 'Körper',
    'Bins and baseplates': 'Boxen und Grundplatten',
    'Format': 'Format',
    'Export file format': 'Dateiformat des Exports',
    'Folder': 'Ordner',
    'Where the files go, the last folder chosen is kept': 'Zielordner der Dateien; der zuletzt gewählte bleibt erhalten',
    'Choose folder...': 'Ordner wählen …',
    'File name': 'Dateiname',
    'Export file name': 'Name der Exportdatei',
    'Arrange': 'Anordnung',
    'Keep design arrangement or split by print plates': 'Anordnung aus dem Design behalten oder auf Druckplatten verteilen',
    'Packed on print beds': 'Auf Druckplatten verteilt',
    'As placed in the design': 'Wie im Design',
    'The bed size the plates are filled to': 'Bettgröße, bis zu der die Platten gefüllt werden',
    'Spacing (mm)': 'Abstand (mm)',
    'The space between bodies packed on a plate': 'Abstand zwischen den Körpern auf einer Platte',
    'The space kept clear along every edge of the bed': 'Freier Rand an jeder Bettkante',
    'Purge tower': 'Reinigungsturm',
    'Leave room for the purge tower': 'Platz für den Reinigungsturm freihalten',
    'Purge tower area': 'Fläche Reinigungsturm',
    'The side of the square kept free for the purge tower': 'Seitenlänge des Quadrats, das für den Reinigungsturm frei bleibt',
    '3MF files': '3MF-Dateien',
    '1 file for everything or 1 file for each plate': 'Eine Datei für alles oder eine Datei je Platte',
    'One file with all plates': 'Eine Datei mit allen Platten',
    'A file per plate': 'Eine Datei je Platte',
    'Color text': 'Text einfärben',
    'Assign different color to use on text': 'Dem Text eine eigene Farbe zuweisen',
    'Label color index': 'Farbindex Beschriftung',
    'Pick color/extruder index to be used for text on labels': 'Farb- bzw. Extruder-Index für den Beschriftungstext',
    'Writes {count} files, one per plate': 'Schreibt {count} Dateien, eine je Platte',
    'Writes {name}': 'Schreibt {name}',
    'Writes {count} {format} files, one per body': 'Schreibt {count} {format}-Dateien, eine je Körper',
    'Select bodies to export': 'Körper zum Exportieren auswählen',
    'Bodies not found, {error}': 'Körper nicht gefunden: {error}',
    'Nothing to export, select bodies or turn on All Gridfinity bodies.': 'Nichts zu exportieren. Körper auswählen oder „Alle Gridfinity-Körper“ einschalten.',
    '{count} files in {folder}, a plate each': '{count} Dateien in {folder}, je eine Platte',
    'Exported 1 body to {where}.': '1 Körper nach {where} exportiert.',
    'Exported {count} bodies to {where}.': '{count} Körper nach {where} exportiert.',
    'Exported 1 {format} file to {folder}.': '1 {format}-Datei nach {folder} exportiert.',
    'Exported {count} {format} files to {folder}.': '{count} {format}-Dateien nach {folder} exportiert.',
    ' and {count} more': ' und {count} weitere',
    'and {count} more': 'und {count} weitere',
    'Packed on {count} plates.': 'Auf {count} Platten verteilt.',
    'Bigger than the bed, each on a plate of its own: {names}.': 'Größer als das Druckbett, jeweils auf eigener Platte: {names}.',
    'No room to keep the purge tower area or the area the printer keeps free clear on plate {plates}, move the bodies or the tower in the slicer.':
        'Auf Platte {plates} ist kein Platz, um die Fläche des Reinigungsturms oder die vom Drucker freigehaltene Fläche frei zu lassen. Körper oder Turm im Slicer verschieben.',
    'No room to keep the purge tower area or the area the printer keeps free clear on plates {plates}, move the bodies or the tower in the slicer.': 'Auf den Platten {plates} ist kein Platz, um die Fläche des Reinigungsturms oder die vom Drucker freigehaltene Fläche frei zu lassen. Körper oder Turm im Slicer verschieben.',
    'No outline label text to color.': 'Kein Beschriftungstext zum Einfärben.',
    'Label text of the body is assigned color {filament}.': 'Der Beschriftungstext des Körpers hat Farbe {filament}.',
    'Label text of {count} bodies is assigned color {filament}.': 'Der Beschriftungstext von {count} Körpern hat Farbe {filament}.',
    'Replace the existing file in {folder}?': 'Vorhandene Datei in {folder} ersetzen?',
    'Replace {count} existing files in {folder}?': '{count} vorhandene Dateien in {folder} ersetzen?',
    ' and ': ' und ',
    'body': 'Körper',
    'bodies': 'Körper',
    'bins': 'Boxen',
    'baseplates': 'Grundplatten',
    'The bed size has to be more than 0': 'Die Bettgröße muss größer als 0 sein',
    'Kept free by the printer': 'Vom Drucker freigehalten',
    '{count} as placed': '{count} wie im Design',
    '{count} on 1 plate': '{count} auf 1 Platte',
    '{count} on {plates} plates': '{count} auf {plates} Platten',
    ', {margin}mm margin, {spacing}mm apart': ', {margin} mm Rand, {spacing} mm Abstand',
    ', {count} bigger than the bed': ', {count} größer als das Bett',
    ', 1 plate without room to keep an area free': ', 1 Platte ohne Platz für die freie Fläche',
    ', {count} plates without room to keep an area free': ', {count} Platten ohne Platz für die freie Fläche',
}
