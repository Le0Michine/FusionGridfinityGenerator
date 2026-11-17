"""
Tests for the wiki pages builder: defaults filled from the dialog, links pinned to the commit and the inputs a page
leaves out.
"""

import os
import importlib.util
import pytest


def _load_wiki_pages():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "wiki", "wikiPages.py")
    spec = importlib.util.spec_from_file_location("wikiPages", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wikiPages = _load_wiki_pages()
COMMIT = "abc123"
RAW = f"https://raw.githubusercontent.com/{wikiPages.REPOSITORY}/{COMMIT}"
BLOB = f"https://github.com/{wikiPages.REPOSITORY}/blob/{COMMIT}"


# ---------------------------------------------------------------------------
# fillDefaults
# ---------------------------------------------------------------------------

def test_markers_take_the_dialog_values():
    text = "Default: <!-- default:bin_wall_thickness -->, lip <!--default:bin_lip_type-->"
    filled = wikiPages.fillDefaults(text, {"bin_wall_thickness": "1.2 mm", "bin_lip_type": "Full"})
    assert filled == "Default: 1.2 mm, lip Full"


def test_a_marker_of_an_input_the_dialog_doesnt_have_fails():
    with pytest.raises(KeyError, match="gone_input"):
        wikiPages.fillDefaults("<!-- default:gone_input -->", {}, "Page.md")


def test_other_comments_stay():
    text = "<!-- a note -->"
    assert wikiPages.fillDefaults(text, {}) == text


# ---------------------------------------------------------------------------
# pinLinks
# ---------------------------------------------------------------------------

def test_an_image_points_to_the_file_at_the_commit():
    text = "![bin](../assets/models/solid-bin.png)"
    assert wikiPages.pinLinks(text, COMMIT) == f"![bin]({RAW}/documentation/assets/models/solid-bin.png)"


def test_an_html_image_points_to_the_file_too():
    text = '<img src="../assets/ui/fusion-dialog-bin-generator.png" width="500">'
    assert wikiPages.pinLinks(text, COMMIT) == f'<img src="{RAW}/documentation/assets/ui/fusion-dialog-bin-generator.png" width="500">'


def test_a_picture_source_for_the_dark_theme_points_to_the_file_too():
    text = '<source media="(prefers-color-scheme: dark)" srcset="../assets/gif/bin-lip-dark.gif">'
    assert wikiPages.pinLinks(text, COMMIT) == f'<source media="(prefers-color-scheme: dark)" srcset="{RAW}/documentation/assets/gif/bin-lip-dark.gif">'


def test_a_link_opens_the_file_on_github():
    text = "see [the readme](../../README.md)"
    assert wikiPages.pinLinks(text, COMMIT) == f"see [the readme]({BLOB}/README.md)"


def test_full_urls_and_wiki_links_stay():
    text = "[Bin options](https://github.com/x/y/wiki/Bin) [[Home]] ![](https://example.com/a.png)"
    assert wikiPages.pinLinks(text, COMMIT) == text


# ---------------------------------------------------------------------------
# iconsTable
# ---------------------------------------------------------------------------

def test_icons_are_listed_by_type_with_their_previews():
    table = wikiPages.iconsTable([
        ("Screws", [("Grub screw", "lib/gridfinityUtils/labelIcons/screws/grub-screw"), ("Socket head screw", "lib/gridfinityUtils/labelIcons/screws/socket-head-screw")]),
        ("Nuts", [("Hex nut", "lib/gridfinityUtils/labelIcons/nuts/hex-nut")]),
    ]).splitlines()
    assert table[:2] == ["Type | Icon | Name", ":--- | :---: | :---"]
    assert table[2].startswith("Screws | <picture>") and table[2].endswith("| Grub screw")
    assert table[3].startswith(" | <picture>")
    assert table[4].startswith("Nuts | ")
    assert 'srcset="../../lib/gridfinityUtils/labelIcons/nuts/hex-nut/32x32@2x-dark.png"' in table[4]
    assert 'src="../../lib/gridfinityUtils/labelIcons/nuts/hex-nut/32x32@2x.png"' in table[4]


def test_the_icons_of_the_add_in_have_previews_for_the_table():
    folder = os.path.join(wikiPages.ROOT_DIR, "lib", "gridfinityUtils", "labelIcons")
    icons = [os.path.join(root, name) for (root, _, names) in os.walk(folder) for name in names if name.endswith(".svg")]
    assert icons
    for icon in icons:
        previews = os.path.splitext(icon)[0]
        assert os.path.isfile(os.path.join(previews, "32x32@2x.png")), icon
        assert os.path.isfile(os.path.join(previews, "32x32@2x-dark.png")), icon


# ---------------------------------------------------------------------------
# missingInputs
# ---------------------------------------------------------------------------

def test_names_a_page_mentions_ignoring_case_arent_missing():
    text = "## Lip type\nThe bin wall thickness is ..."
    assert wikiPages.missingInputs(text, ["Lip type", "Bin wall thickness", "Half grid"]) == ["Half grid"]


# ---------------------------------------------------------------------------
# the pages in the repo
# ---------------------------------------------------------------------------

def test_every_page_with_a_dialog_is_in_the_repo():
    assert set(wikiPages.PAGE_COMMANDS) <= set(wikiPages.pages())
