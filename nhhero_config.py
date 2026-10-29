"""Fichier de configuration de l'éditeur (~/.config/nhheroedit/config,
ou $NHHEROEDIT_CONFIG).

Format INI ; toutes les clés sont facultatives. Voir config.exemple.
Ordre de priorité : ligne de commande, puis variables d'environnement,
puis ce fichier, puis les valeurs par défaut.
"""

import configparser
import os

from nhhero_i18n import CONFIG_DIR, _

YES = {"oui": True, "o": True, "yes": True, "y": True, "1": True,
       "vrai": True, "true": True, "non": False, "n": False, "no": False,
       "0": False, "faux": False, "false": False}


def default_path():
    return os.environ.get("NHHEROEDIT_CONFIG") or os.path.join(CONFIG_DIR,
                                                               "config")


def load(path):
    """Lit le fichier. Renvoie (réglages, erreurs) ; réglages ne contient
    que les clés présentes et valides."""
    cfg, errs = {}, []
    if not os.path.isfile(path):
        return cfg, errs
    cp = configparser.ConfigParser(interpolation=None,
                                   inline_comment_prefixes=(";",))
    try:
        with open(path, encoding="utf-8") as f:
            cp.read_file(f)
    except (OSError, configparser.Error, UnicodeDecodeError) as e:
        return cfg, ["%s : %s" % (path, e)]

    def bad(section, key, why):
        errs.append("[%s] %s : %s" % (section, key, why))

    for key, val in cp.items("jeu") if cp.has_section("jeu") else []:
        val = val.strip()
        if key == "sources":
            cfg["src"] = os.path.expanduser(val)
        elif key in ("repertoire", "répertoire", "hackdir"):
            cfg["hackdir"] = os.path.expanduser(val)
        elif key == "make":
            # options de make (« -j8 WANT_WIN_ALL=1 ») ; défaut : -jN
            cfg["make"] = val
        elif key == "tmux":
            # j dans un panneau tmux à côté de l'éditeur (dans tmux)
            if val.lower() not in YES:
                bad("jeu", key, _("oui ou non attendu"))
            else:
                cfg["tmux"] = YES[val.lower()]
        else:
            bad("jeu", key, _("clé inconnue"))
    for key, val in (cp.items("editeur") if cp.has_section("editeur")
                     else []):
        low = val.strip().lower()
        if key == "projet":
            cfg["project"] = os.path.expanduser(val.strip())
        elif key == "langue":
            if low not in ("fr", "en", "auto"):
                bad("editeur", key, _("fr, en ou auto attendu"))
        elif key in ("theme", "thème"):
            if low not in ("cyber", "fr", "en", "auto"):
                bad("editeur", key, _("cyber, fr, en ou auto attendu"))
            elif low != "auto":
                cfg["theme"] = low
        elif key == "souris":
            if low not in YES:
                bad("editeur", key, _("oui ou non attendu"))
            else:
                cfg["mouse"] = YES[low]
        elif key == "sauvegarde":
            try:
                cfg["autosave"] = max(0, int(low))
            except ValueError:
                bad("editeur", key, _("nombre de secondes attendu (0 : "
                                      "désactivée)"))
        else:
            bad("editeur", key, _("clé inconnue"))
    for s in cp.sections():
        if s not in ("jeu", "editeur"):
            errs.append(_("[%s] : section inconnue") % s)
    return cfg, errs
