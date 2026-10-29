"""Langue de l'interface : français (langue des sources) ou anglais.

La langue est choisie à l'importation, avant que les autres modules ne
construisent leurs textes : $NHHEROEDIT_LANG (fr ou en), sinon la clé
« langue » du fichier de configuration, sinon la locale (LANGUAGE,
LC_ALL, LC_MESSAGES, LANG) : français si elle commence par « fr »,
anglais sinon.

Les textes sont écrits en français dans le code et passent par _() ;
leur traduction est dans nhhero_i18n_en.py (texte absent : laissé en
français). Les noms du jeu, le code C et les textes
écrits dans les sources du jeu ne sont pas traduits.
"""

import configparser
import os

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME")
                          or os.path.expanduser("~/.config"), "nhheroedit")


def _config_lang():
    path = os.environ.get("NHHEROEDIT_CONFIG") or os.path.join(CONFIG_DIR,
                                                               "config")
    cp = configparser.ConfigParser(interpolation=None,
                                   inline_comment_prefixes=(";",))
    try:
        with open(path, encoding="utf-8") as f:
            cp.read_file(f)
        return cp.get("editeur", "langue", fallback="").strip().lower()
    except (OSError, configparser.Error, UnicodeDecodeError):
        return ""


def detect():
    lang = os.environ.get("NHHEROEDIT_LANG", "").lower()
    if lang not in ("fr", "en"):
        lang = _config_lang()
    if lang in ("fr", "en"):
        return lang
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return "fr" if v.lower().startswith("fr") else "en"
    return "en"


LANG = detect()
_CATALOG = {}
if LANG == "en":
    from nhhero_i18n_en import EN as _CATALOG


def _(text):
    """Texte traduit dans la langue de l'interface."""
    return _CATALOG.get(text, text)
