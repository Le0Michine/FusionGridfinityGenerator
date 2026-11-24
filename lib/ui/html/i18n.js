// Translates the texts of the pages, as lib/i18n.py does for the dialogs. The English text is the key, text nodes
// and the title and placeholder attributes are replaced as they appear, texts the pages build from values go
// through PATTERNS. Labels the user typed into the drawings are left as they are, see SKIP
const i18n = (() => {
    // the language lib/i18n.py chose, the add-in puts it in the page's address, see pageQuery there
    const LANGUAGE = new URLSearchParams(window.location.search).get('lang') || 'en';

    const DE = {
        // defaults buttons
        'Save as defaults': 'Standard speichern',
        'Save the current inputs as new defaults for this dialog': 'Aktuelle Eingaben als neuen Standard speichern',
        'Reset to defaults': 'Zurücksetzen',
        'Set the inputs back to the saved defaults': 'Eingaben auf gespeicherten Standard zurücksetzen',
        'Clear defaults': 'Standard löschen',
        'Wipe the saved defaults and set the inputs back to the original ones': 'Gespeicherten Standard löschen und ursprüngliche Werte wiederherstellen',
        // error report
        'Copy report': 'Bericht kopieren',
        'Copy and open an issue': 'Kopieren & Issue öffnen',
        'Stack trace': 'Stack-Trace',
        'Config': 'Konfiguration',
        'Config before the rebuild': 'Konfiguration vor Neuaufbau',
        'Copied, the issue has what fit in its link': 'Kopiert; das Issue enthält, was in den Link gepasst hat',
        'Copied, paste it into the issue': 'Kopiert; bitte ins Issue einfügen',
        "Couldn't copy, the report below is selected to copy it": 'Kopieren fehlgeschlagen; Bericht unten ist zum Kopieren markiert',
        // custom shape
        'Fill all': 'Alle füllen',
        'Every cell of the bin': 'Alle Zellen der Box',
        // compartments
        'Reset all': 'Alles zurücksetzen',
        'Back to single cells, without labels or depths': 'Zurück zu einzelnen Zellen, ohne Beschriftung und Tiefe',
        'Drag across cells to merge them into a pocket.': 'Über Zellen ziehen, um sie zu einem Fach zu verbinden.',
        'Click a pocket to set its label and depth.': 'Fach anklicken, um Beschriftung und Tiefe festzulegen.',
        'Label': 'Text',
        'Icon': 'Symbol',
        'Depth': 'Tiefe',
        'label tab text': 'Text der Lasche',
        'Empty takes the text from the label tab section': 'Leer übernimmt den Text aus dem Abschnitt Beschriftungslasche',
        'Turn on the label tab to label pockets': 'Beschriftungslasche aktivieren, um Fächer zu beschriften',
        'From the top of the bin, empty for the full depth': 'Ab Oberkante der Box; leer für volle Tiefe',
        'Split': 'Teilen',
        'Back to single cells': 'Zurück zu einzelnen Zellen',
        'Done': 'Fertig',
        'Finish editing this compartment, changes are already applied': 'Bearbeitung des Fachs beenden (Änderungen sind bereits übernommen)',
        'Cells along the bin width': 'Zellen entlang der Breite',
        'Cells along the bin length': 'Zellen entlang der Länge',
        'Size of one cell inside its walls': 'Innenmaß einer Zelle',
        'Clear': 'Leeren',
        'Back to a single cell': 'Zurück zu einer einzelnen Zelle',
        'Default': 'Standard',
        'None': 'Keins',
        'Other': 'Sonstige',
        'Nuts': 'Muttern',
        'Screws': 'Schrauben',
        'Washers': 'Unterlegscheiben',
        // label icons, keep in step with lib/i18n.py
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
    };

    // texts with values in them, the first match is used
    const PATTERNS_DE = [
        // icon picker entry that follows the label tab icon, e.g. Default (Hex nut)
        [/^Default \((.+)\)$/, (match, name) => `Standard (${translate(name)})`],
        [/^full, (.+)$/, 'voll, $1'],
        [/^cell (.+) mm$/, 'Zelle $1 mm'],
        [/^Cells under (.+) mm are too small for the compartment corner fillets$/, 'Zellen unter $1 mm sind zu klein für die Eckrundungen der Fächer'],
        [/^(\d+) x (\d+) cells, (.+) mm deep$/, '$1 x $2 Zellen, $3 mm tief'],
        [/^(\d+) x (\d+) cells$/, '$1 x $2 Zellen'],
        [/^padding left (.+)$/, 'Rand links $1'],
        [/^padding right (.+)$/, 'Rand rechts $1'],
        [/^padding top (.+)$/, 'Rand oben $1'],
        [/^padding bottom (.+)$/, 'Rand unten $1'],
        [/^Gridfinity bin failed$/, 'Gridfinity-Box fehlgeschlagen'],
        [/^Gridfinity baseplate failed$/, 'Gridfinity-Grundplatte fehlgeschlagen'],
        // export plates drawing
        [/^Plate (\d+)$/, 'Platte $1'],
        [/^Plate (\d+), 1 body$/, 'Platte $1, 1 Körper'],
        [/^Plate (\d+), (\d+) bodies$/, 'Platte $1, $2 Körper'],
        [/^(.+), kept free$/, (match, name) => `${translate(name)}, freigehalten`],
        [/^(.+), ([\d.]+) x ([\d.]+) mm((?:, .+)?)$/, (match, name, width, length, rest) => `${name.replace(/, bin$/, ', Box').replace(/, baseplate$/, ', Grundplatte')}, ${width} x ${length} mm` + rest
            .replace(', turned', ', gedreht')
            .replace(', bigger than the bed', ', größer als das Druckbett')
            .replace(', on an area kept free', ', auf einer freizuhaltenden Fläche')],
    ];

    // user labels drawn in the compartments
    const SKIP = '.pocket-label, textarea, pre, #message';
    const ATTRIBUTES = ['title', 'placeholder'];

    // the translations by language code, as TRANSLATIONS in lib/i18n.py has them: texts by their English one, and
    // the patterns of texts with values in them
    const TRANSLATIONS = {
        de: { texts: DE, patterns: PATTERNS_DE },
    };

    function translate(text) {
        const translation = TRANSLATIONS[LANGUAGE];
        if (!translation || !text) {
            return text;
        }
        const trimmed = text.trim();
        if (Object.prototype.hasOwnProperty.call(translation.texts, trimmed)) {
            return text.replace(trimmed, translation.texts[trimmed]);
        }
        for (const [pattern, replacement] of translation.patterns) {
            if (pattern.test(trimmed)) {
                return text.replace(trimmed, trimmed.replace(pattern, replacement));
            }
        }
        return text;
    }

    function isSkipped(node) {
        const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        return element && element.closest && element.closest(SKIP) !== null;
    }

    function translateNode(node) {
        if (isSkipped(node)) {
            return;
        }
        if (node.nodeType === Node.TEXT_NODE) {
            const shown = translate(node.nodeValue);
            if (shown !== node.nodeValue) {
                node.nodeValue = shown;
            }
            return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return;
        }
        for (const name of ATTRIBUTES) {
            if (node.hasAttribute(name)) {
                const value = node.getAttribute(name);
                const shown = translate(value);
                if (shown !== value) {
                    node.setAttribute(name, shown);
                }
            }
        }
        for (const child of node.childNodes) {
            translateNode(child);
        }
    }

    function start() {
        if (!TRANSLATIONS[LANGUAGE]) {
            return;
        }
        translateNode(document.body);
        // pages build their content from the data they get, translated as it's added
        new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(translateNode);
                } else {
                    translateNode(mutation.target);
                }
            }
        }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTES });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
    return { translate };
})();
