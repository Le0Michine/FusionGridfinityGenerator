"""
The GitHub wiki's pages, kept in documentation/wiki and published by .github/workflows/wiki.yml, the wiki itself isn't
edited. A page is copied as it is, but for:

- `<!-- default:<input id> -->`, replaced with the input's value as the dialog opens with its original defaults, so
  a page follows changes to them. The id is the one the dialog saves its defaults by, see
  tools/screenshots/dialogRecorder.py
- `<!-- label-icons -->`, replaced with a table of the label icons the add-in has, as the dialog lists them
- links to files in the repo by a relative path, `![](../assets/...)`, `src="../assets/..."` or a `srcset`, which point
  to the file at the published commit, the wiki is a repo of its own

`check` lists the inputs of each dialog a page doesn't mention by name, to see what it leaves out.

    python3 tools/wiki/wikiPages.py build <folder>
    python3 tools/wiki/wikiPages.py check
"""

import os
import posixpath
import re
import subprocess
import sys

WIKI_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(WIKI_DIR))
PAGES_DIR = os.path.join(ROOT_DIR, 'documentation', 'wiki')
# the pages' folder in the repo, links are relative to it
PAGES_PATH = 'documentation/wiki'
REPOSITORY = 'Le0Michine/FusionGridfinityGenerator'
# the dialog each page tells about, its defaults fill the page's markers
PAGE_COMMANDS = {
    'Bin-generator-options.md': 'bin',
    'Baseplate-generator-options.md': 'baseplate',
}

DEFAULT_MARKER = re.compile(r'<!--\s*default:([\w-]+)\s*-->')
LABEL_ICONS_MARKER = re.compile(r'<!--\s*label-icons\s*-->')
# a markdown link or image, or an html src, srcset or href, to a relative path
RELATIVE_LINK = re.compile(r'(\]\(|(?:src|srcset|href)=")((?:\.\./|\./)[^)"\s]+)')


def fillDefaults(text: str, defaults: dict[str, str], page: str = '') -> str:
    """The markers replaced with the inputs' values, an unknown input fails the page"""
    def value(match: re.Match) -> str:
        inputId = match.group(1)
        if inputId not in defaults:
            raise KeyError(f'{page} has a default of "{inputId}", which its dialog has no input of')
        return defaults[inputId]
    return DEFAULT_MARKER.sub(value, text)


def iconsTable(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    """
    Icons by type, each a name and the folder of its dropdown previews from the add-in folder, shown in the reader's
    theme, see tools/labelIcons.py
    """
    rows = ['Type | Icon | Name', ':--- | :---: | :---']
    for (groupName, icons) in groups:
        for (index, (name, folder)) in enumerate(icons):
            path = f'../../{folder}'
            picture = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{path}/32x32@2x-dark.png">'
                       f'<img src="{path}/32x32@2x.png" alt="{name}" width="32"></picture>')
            rows.append(f'{groupName if index == 0 else ""} | {picture} | {name}')
    return '\n'.join(rows)


def labelIcons() -> list[tuple[str, list[tuple[str, str]]]]:
    """The add-in's label icons by type, as the bin dialog lists them, with their preview folders"""
    # the label module needs the fake API in place of Fusion's, the dialog brings it
    _session('bin')
    labelGenerator = next(module for (name, module) in sys.modules.items() if name.endswith('gridfinityUtils.labelGenerator'))
    groups = []
    for group in labelGenerator.listIconGroups():
        folder = os.path.dirname(group[0].path)
        groupName = 'Other' if folder == labelGenerator.LABEL_ICONS_FOLDER else os.path.basename(folder).capitalize()
        groups.append((groupName, [(icon.name, os.path.relpath(icon.previewFolder, ROOT_DIR).replace(os.sep, '/')) for icon in group]))
    return groups


def pinLinks(text: str, commit: str) -> str:
    """Relative links pointing to the files in the repo at the commit, images shown as they are, others on GitHub"""
    def pinned(match: re.Match) -> str:
        path = posixpath.normpath(posixpath.join(PAGES_PATH, match.group(2)))
        isImage = match.group(1) in ('src="', 'srcset="') or (match.group(1) == '](' and _isImageLink(text, match.start()))
        url = f'https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}' if isImage else f'https://github.com/{REPOSITORY}/blob/{commit}/{path}'
        return match.group(1) + url
    return RELATIVE_LINK.sub(pinned, text)


def _isImageLink(text: str, linkStart: int) -> bool:
    """Whether the markdown link ending its text at linkStart is an image, ![...](...)"""
    opening = text.rfind('[', 0, linkStart)
    return opening > 0 and text[opening - 1] == '!'


def missingInputs(text: str, names: list[str]) -> list[str]:
    """The input names the page doesn't mention, ignoring case"""
    lowered = text.lower()
    return [name for name in names if name.lower() not in lowered]


def _commit() -> str:
    if os.environ.get('GITHUB_SHA'):
        return os.environ['GITHUB_SHA']
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()


def _session(command: str):
    sys.path.insert(0, os.path.join(ROOT_DIR, 'tools', 'screenshots'))
    import dialogRecorder
    return dialogRecorder.DialogSession(command)


def _inputs(session) -> list:
    """Every input of the dialog, those in groups and tables too"""
    found = []
    def walk(inputs):
        for input in inputs:
            found.append(input)
            nested = getattr(input, 'children', None)
            if nested is not None:
                walk(nested)
    walk(session.inputs)
    return found


def dialogDefaults(command: str) -> dict[str, str]:
    """
    Each input's value as the dialog opens, as it shows it. Values the dialog keeps for its pages, as the compartment
    grid size, by their id too when they're whole numbers or text
    """
    # first, it puts the fake API in place of Fusion's
    session = _session(command)
    import adsk.core
    defaults = {}
    for input in _inputs(session):
        if isinstance(input, (adsk.core.ValueCommandInput, adsk.core.FloatSpinnerCommandInput, adsk.core.IntegerSpinnerCommandInput)):
            defaults[input.id] = input.expression
        elif isinstance(input, adsk.core.BoolValueCommandInput) and input.isCheckBox:
            defaults[input.id] = 'on' if input.value else 'off'
        elif isinstance(input, adsk.core.DropDownCommandInput) and input.selectedItem is not None:
            defaults[input.id] = input.selectedItem.name
        elif isinstance(input, adsk.core.StringValueCommandInput):
            defaults[input.id] = input.value
    import dialogRecorder
    if dialogRecorder._has(session.module, dialogRecorder.UI_STATE_NAMES):
        state = dialogRecorder._find(session.module, dialogRecorder.UI_STATE_NAMES)
        for inputId in state.inputState:
            value = state.getState(inputId)
            if inputId not in defaults and isinstance(value, (int, str)) and not isinstance(value, bool):
                defaults[inputId] = str(value)
    return defaults


def dialogNames(command: str) -> list[str]:
    """The names the dialog shows its inputs by, groups too, those without a name left out"""
    names = []
    for input in _inputs(_session(command)):
        if input.name and input.isVisible and input.name not in names:
            names.append(input.name)
    return names


def pages() -> list[str]:
    return sorted(name for name in os.listdir(PAGES_DIR) if name.endswith('.md'))


def build(outDir: str):
    """The pages ready for the wiki in the folder, files of the same name replaced"""
    os.makedirs(outDir, exist_ok=True)
    commit = _commit()
    for page in pages():
        with open(os.path.join(PAGES_DIR, page), encoding='utf-8') as file:
            text = file.read()
        if DEFAULT_MARKER.search(text):
            text = fillDefaults(text, dialogDefaults(PAGE_COMMANDS[page]), page)
        if LABEL_ICONS_MARKER.search(text):
            table = iconsTable(labelIcons())
            text = LABEL_ICONS_MARKER.sub(lambda _: table, text)
        with open(os.path.join(outDir, page), 'w', encoding='utf-8') as file:
            file.write(pinLinks(text, commit))


def check() -> int:
    """Prints what each page leaves out of its dialog, how many inputs that is"""
    total = 0
    for (page, command) in PAGE_COMMANDS.items():
        with open(os.path.join(PAGES_DIR, page), encoding='utf-8') as file:
            missing = missingInputs(file.read(), dialogNames(command))
        total += len(missing)
        print(f'{page}: {len(missing)} of the {command} dialog\'s inputs not mentioned')
        for name in missing:
            print(f'  {name}')
    return total


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'build':
        build(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == 'check':
        check()
    else:
        print(__doc__)
        sys.exit(2)
