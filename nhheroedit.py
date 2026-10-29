#!/usr/bin/env python3
"""nhheroedit — éditeur de héros pour NetHack 5.0 (thème Night City), en
mode terminal.

Usage : python3 nhheroedit.py [projet.json] [--src DOSSIER_DES_SOURCES]

Un héros, c'est un nom, un rôle, une race, un sexe, un alignement, un
animal… : « j » lance le jeu avec lui. Les règles de départ de son rôle
(inventaire, or, intrinsèques, attributs, PV, titres de rang, dieux,
races permises, tuile) se modifient aussi : « I » les intègre aux
sources du jeu, « m » compile, « U » met à jour le jeu installé.
Appuyez sur « ? » pour l'aide.
"""

import copy
import curses
import json
import os
import re
import subprocess
import sys
import time

import nhhero_config as C
import nhhero_data as D
from nhhero_i18n import _
import nhhero_install as I
import nhhero_game as G
from nhhero_game import Game
import nhhero_project as P
import nhhero_templates as T
from nhhero_ui import (Cancel, Colors, ESC, Mouse, Popups, box, centered,
                       enable_mouse, get_key, is_enter, put, wheel)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT = os.path.join(HERE, "heros.json")
DEFAULT_SRC = os.path.normpath(os.path.join(HERE, "..", "NetHack-5.0.0"))
BACKUP_DIR = os.path.join(HERE, "sauvegardes")

GOD_LABEL = [_("Dieu loyal"), _("Dieu neutre"), _("Dieu chaotique")]
RANK_VARIANTS = [
    ("ranks_en", 0, _("anglais, masculin"), _("nom interne (role.c)")),
    ("ranks_en", 1, _("anglais, féminin"), _("facultatif : vide = le titre "
                                            "masculin sert aux deux")),
    ("ranks_fr", 0, _("français, masculin"), "po/fr.po"),
    ("ranks_fr", 1, _("français, féminin"), "po/fr.po"),
    ("ranks_cyber", 0, _("Night City, masculin"), "po/themes/fr@cyber.po"),
    ("ranks_cyber", 1, _("Night City, féminin"), "po/themes/fr@cyber.po"),
]

HELP = [
    _("nhheroedit — éditeur de héros pour NetHack 5.0 (Night City)"),
    "",
    _("Deux zones : la liste des héros du projet (à gauche) et la fiche du"),
    _("héros choisi. Tab passe de l'une à l'autre."),
    "",
    _("La fiche a deux parties :"),
    _("  ▸ Héros : nom, rôle, race, sexe, alignement, animal, fruit,"),
    _("    conduites, biographie. Rien à intégrer : j lance le jeu avec."),
    _("  ▸ Rôle : règles de départ du rôle (titres, dieux, races permises,"),
    _("    attributs, PV, énergie, or, intrinsèques, inventaire, tuiles)."),
    _("    Elles changent le jeu pour TOUS les héros de ce rôle, et"),
    _("    demandent d'intégrer (I), compiler (m) et mettre à jour (U)."),
    _("    Un champ modifié est marqué ● ; Suppr rend la valeur du jeu."),
    "",
    _("Dans la fiche :"),
    _("  ↑ ↓          champ précédent / suivant"),
    _("  ← →          changer une valeur (choix, nombre)"),
    _("  Entrée       modifier le champ"),
    _("  Suppr        vider le champ, ou rendre la valeur du jeu"),
    "",
    _("Héros :"),
    _("  n            nouveau héros d'après un archétype de Night City"),
    _("  d            dupliquer le héros"),
    _("  N            nom de Night City au hasard pour le héros"),
    _("  Suppr / X    supprimer le héros (dans la liste)"),
    _("  < >          déplacer le héros dans la liste"),
    _("  /            aller à un héros (tapez une partie de son nom)"),
    _("  k            inventaire de départ du rôle"),
    _("  t            dessiner la tuile du rôle (sexe du héros)"),
    _("  T            noms affichés : Night City, français, anglais"),
    "",
    _("Contrôle :"),
    _("  v            vérifier tous les héros et rôles"),
    _("  c            voir les options du héros et le code du rôle"),
    _("  x            écrire le .nethackrc du héros"),
    "",
    _("Sources du jeu :"),
    _("  I            intégrer les rôles modifiés (aperçu, confirmation ;"),
    _("               copie des fichiers dans sauvegardes/)"),
    _("  R            retirer les modifications, ou rétablir une"),
    _("               sauvegarde"),
    _("  m            compiler (make)"),
    _("  U            mettre à jour le jeu installé (make update)"),
    _("  j            jouer avec le héros (normal, découverte, wizard)"),
    _("  h            historique des parties du héros (xlogfile du jeu)"),
    "",
    _("Projet :"),
    _("  p            fusionner un projet, exporter ou importer un héros,"),
    _("               rendre au rôle ses valeurs du jeu"),
    _("  s            enregistrer        u  annuler   Ctrl-R  rétablir"),
    _("  ?            cette aide         q  quitter"),
    "",
    _("Souris : un clic choisit un héros ou un champ, un double clic"),
    _("modifie ; la molette fait défiler (Maj + clic pour sélectionner du"),
    _("texte, NHHEROEDIT_MOUSE=0 coupe la souris)."),
]


def frame_top(title, w):
    head = "┌─ %s " % title
    return head + "─" * max(0, w - len(head) - 1) + "┐"


def detect_theme(config):
    """Thème des noms : configuration, sinon l'option language du
    ~/.nethackrc (fr@cyber, fr), sinon cyber."""
    if config.get("theme") in D.THEMES:
        return config["theme"]
    try:
        with open(os.path.expanduser("~/.nethackrc"), encoding="utf-8",
                  errors="replace") as f:
            rc = f.read()
    except OSError:
        return "cyber"
    langs = re.findall(r"^\s*OPTIONS\s*=.*\blanguage:([\w@]+)", rc, re.M)
    if langs:
        return "cyber" if langs[-1].endswith("@cyber") else \
            "fr" if langs[-1].startswith("fr") else "en"
    return "cyber"


def qty_text(o):
    return str(o["qmin"]) if o["qmin"] == o["qmax"] else \
        "%d-%d" % (o["qmin"], o["qmax"])


def parse_qty(s):
    mo = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$", s)
    if not mo:
        return None
    a = int(mo.group(1))
    b = int(mo.group(2)) if mo.group(2) else a
    return (a, b) if 1 <= a <= b <= 127 else None


class Editor(Popups, Game):
    def __init__(self, stdscr, project, src, config=None, config_errs=()):
        self.stdscr = stdscr
        self.config = config or {}
        self.colors = Colors()
        self.project = project
        self.src = src
        self.heroes = []
        self.roles = {}         # clé du rôle -> modifications
        self.cur = 0
        self.field = 1
        self.focus = "list"
        self.modified = False
        self.undo_stack = []
        self.redo_stack = []
        self.autosave_delay = self.config.get("autosave", P.AUTOSAVE_DELAY)
        self.autosave_time = time.time()
        self.theme = detect_theme(self.config)
        self.msg = ""
        self.form_top = 0
        self.list_top = 0
        self.areas = {}
        self._game = None
        self._state = (None, None)
        self.load()
        if config_errs:
            self.msg = _("Configuration : %s") % "; ".join(config_errs)

    # --- données ----------------------------------------------------------

    def load(self):
        if os.path.isfile(self.project):
            try:
                self.heroes, self.roles = P.read_project(self.project)
            except P.ProjectError as e:
                sys.exit(str(e))
            self.msg = _("Projet ouvert : %s (%d héros)") % (
                self.project, len(self.heroes))
        else:
            self.msg = _("Nouveau projet : %s — « n » pour créer un "
                         "héros") % self.project

    def save(self):
        P.write_project(self.project, self.heroes, self.roles)
        P.drop_autosave(self.project)
        self.modified = False
        self.msg = _("Enregistré : %s") % self.project

    def game(self):
        """Données du jeu (sources d'origine), lues une fois."""
        if self._game is None:
            self._game = I.GameData(self.src)
        return self._game

    def reload_game(self):
        self._game = None
        self._state = (None, None)

    def hero(self):
        return self.heroes[self.cur] if self.heroes else None

    def role_of(self, h):
        return self.game().role(h["role"]) if h else None

    def race_of(self, h):
        return self.game().race(h["race"]) if h else None

    def mod(self, key):
        return self.roles.get(key, {})

    def set_mod(self, key, field, value, default):
        """Modification d'un champ du rôle ; la valeur du jeu la retire."""
        m = dict(self.roles.get(key, {}))
        if value is None or value == default:
            m.pop(field, None)
        else:
            m[field] = value
        if m:
            self.roles[key] = m
        else:
            self.roles.pop(key, None)

    def checkpoint(self):
        self.undo_stack.append((copy.deepcopy(self.heroes),
                                copy.deepcopy(self.roles), self.cur))
        del self.undo_stack[:-100]
        self.redo_stack = []
        self.modified = True

    def undo(self, redo=False):
        src, dst = (self.redo_stack, self.undo_stack) if redo else \
            (self.undo_stack, self.redo_stack)
        if not src:
            self.msg = _("Rien à rétablir") if redo else _("Rien à annuler")
            return
        dst.append((self.heroes, self.roles, self.cur))
        self.heroes, self.roles, self.cur = src.pop()
        self.cur = min(self.cur, max(0, len(self.heroes) - 1))
        self.modified = True
        self.msg = _("Rétabli") if redo else _("Annulé")

    # --- noms ----------------------------------------------------------------

    def role_name(self, role, gender="male", theme=None):
        theme = theme or self.theme
        n = self.game().names.role(role, gender, theme)
        return n if theme == "en" else "%s (%s)" % (n, role["name"][0])

    def race_name(self, race, gender="male"):
        return self.game().names.race(race, gender, self.theme)

    def obj_name(self, o):
        """Libellé d'un objet de l'inventaire."""
        g = self.game()
        if o["otyp"] == D.UNDEF_TYP:
            return _("%s au hasard") % D.CLASS_FR.get(o["cls"], o["cls"])
        ob = g.by_sn.get(o["otyp"])
        if not ob:
            return o["otyp"]
        name = g.names.obj(ob, self.theme)
        if ob["cls"] in ("RING_CLASS", "WAND_CLASS", "POTION_CLASS",
                         "SCROLL_CLASS", "SPBOOK_CLASS"):
            name = "%s : %s" % (D.CLASS_FR[ob["cls"]], name)
        return name

    def item_text(self, o):
        s = qty_text(o) + " × " + self.obj_name(o) if (
            o["qmin"], o["qmax"]) != (1, 1) else self.obj_name(o)
        if o["spe"] is not None:
            if o["cls"] in ("WEAPON_CLASS", "ARMOR_CLASS"):
                s += " %+d" % o["spe"]
            elif o["spe"]:
                s += _(" (charges %d)") % o["spe"]
        if o["bless"] == 1:
            s += _(" (béni)")
        return s

    def god_text(self, g):
        if not g:
            return _("au hasard (panthéon d'un autre rôle)")
        return _("%s (déesse)") % g[1:] if g.startswith("_") else g

    # --- état des sources ----------------------------------------------------

    def source_state(self):
        """(sources à jour pour le projet ?, rôles modifiés dans les
        sources, rôles des autres projets) ; calcul mis en cache tant que
        ni le projet ni les fichiers ne changent."""
        mt = []
        for rel in I.ALL_FILES:
            try:
                mt.append(os.path.getmtime(os.path.join(self.src, rel)))
            except OSError:
                mt.append(0)
        key = (json.dumps(self.roles, sort_keys=True), tuple(mt))
        if self._state[0] != key:
            others = self.other_projects()
            try:
                mods, origins = self.merged_roles(others)
                files = I.plan(self.src, mods, self.game(), origins)
                ok = not I.changed_files(self.src, files)
            except (I.InstallError, OSError, ValueError):
                ok = False
            try:
                present = I.installed_roles(self.src, self.game())
            except (OSError, ValueError):
                present = set()
            self._state = (key, (ok, present, others))
        return self._state[1]

    def other_projects(self):
        """Rôles modifiés dans les sources par d'autres projets : {clé:
        (chemin du projet, modifications)} ; chemin None quand le projet
        n'est pas connu, modifications None quand il est illisible."""
        try:
            origins = I.installed_projects(self.src)
            roles = I.installed_roles(self.src, self.game())
        except (OSError, ValueError):
            return {}
        out, read = {}, {}
        for k in sorted(set(origins) | roles):
            path = origins.get(k)
            if path and os.path.abspath(path) == self.project:
                continue
            if not path and self.mod(k):
                continue        # intégré avant que les projets soient notés
            mod = None
            if path:
                if path not in read:
                    try:
                        read[path] = P.read_project(path)[1]
                    except P.ProjectError:
                        read[path] = {}
                mod = read[path].get(k)
            out[k] = (path, mod)
        return out

    def merged_roles(self, others, keep=True):
        """(modifications, projets) à intégrer : les rôles du projet, et
        ceux que d'autres projets ont intégrés (keep) s'il n'y touche pas."""
        mods = {k: v for k, v in self.roles.items() if v}
        origins = {k: self.project for k in mods}
        for k, (path, mod) in others.items() if keep else ():
            if k not in mods and mod:
                mods[k], origins[k] = mod, path
        return mods, origins

    def role_label(self, key):
        role = self.game().role(key)
        return self.game().names.role(role, "male", self.theme) if role \
            else key

    def role_status(self, key):
        """(texte, attribut) de l'état du rôle dans les sources."""
        ok, installed, others = self.source_state()
        present = key in installed
        other = others.get(key, (None, None))[0]
        if other and not self.mod(key):
            return _("intégré par le projet %s") % os.path.basename(other), \
                self.colors.fg(curses.COLOR_CYAN, True)
        if other and not ok:
            return _("intégré par le projet %s (I le remplacera)") % \
                os.path.basename(other), \
                self.colors.fg(curses.COLOR_YELLOW, True)
        if not self.mod(key):
            if present:
                return _("modifié dans les sources (R pour retirer)"), \
                    self.colors.fg(curses.COLOR_YELLOW, True)
            return _("rôle d'origine"), curses.A_DIM
        if ok:
            return _("intégré"), self.colors.fg(curses.COLOR_GREEN, True)
        if present:
            return _("intégré, modifié depuis"), \
                self.colors.fg(curses.COLOR_YELLOW, True)
        return _("modifié, non intégré (I)"), \
            self.colors.fg(curses.COLOR_YELLOW, True)

    def problems(self, h):
        g = self.game()
        return D.validate(h, self.role_of(h), self.race_of(h),
                          self.mod(h["role"]), g.objects,
                          [o for o in self.heroes if o is not h]) + \
            self.rank_problems(h["role"])

    def rank_problems(self, key):
        """Avertissements sur les titres de rang du rôle key."""
        try:
            res = I.rank_conflicts(self.game(), self.roles, self.theme)
        except (OSError, ValueError):
            return []
        return [("attention", m) for m in res.get(key, [])]

    # --- champs ------------------------------------------------------------

    def fields(self, h=None):
        """Champs de la fiche : (type, clé, libellé, aide)."""
        h = h or self.hero()
        role = self.role_of(h)
        out = [
            ("section", None, _("Héros"), ""),
            ("text", "name", _("Nom"), _("nom du personnage (option name) "
             "; sert aussi au fichier de sauvegarde")),
            ("role", "role", _("Rôle"), _("la profession ; ← → pour "
             "changer, Entrée pour choisir")),
            ("race", "race", _("Race"), _("✖ : race que le rôle n'accepte "
             "pas")),
            ("gender", "gender", _("Sexe"), _("masculin ou féminin")),
            ("align", "align", _("Alignement"), _("loyal, neutre ou "
             "chaotique ; donne le dieu du héros")),
            ("pet", "pet", _("Animal"), _("animal de départ (option "
             "pettype)")),
            ("text", "petname", _("Nom de l'animal"), _("options dogname, "
             "catname ou horsename")),
            ("text", "fruit", _("Fruit préféré"), _("nom du fruit "
             "personnalisé (option fruit)")),
            ("conducts", "conducts", _("Conduites"), _("défis choisis avant "
             "la partie : sans le sou, nudiste, aveugle…")),
            ("longtext", "story", _("Biographie"), _("l'histoire du héros "
             "(pour vous ; non intégrée au jeu)")),
            ("longtext", "notes", _("Notes"), _("vos notes")),
        ]
        if not role:
            return out
        out.append(("section", None, _("Rôle « %s » — commun à tous ses "
                    "héros, à intégrer (I)") % self.game().names.role(
                        role, h["gender"], self.theme), ""))
        for i in range(9):
            out.append(("rank", i, _("Rang %d (niv. %s)") % (
                i + 1, D.RANK_LEVELS[i]), _("titre affiché selon le niveau "
                "d'expérience ; Entrée : anglais, français, Night City")))
        for i in range(3):
            out.append(("god", i, GOD_LABEL[i], _("nom du dieu ; un « _ » "
                        "devant le nom en fait une déesse")))
        out += [
            ("allow", "races", _("Races permises"), _("races que le rôle "
             "accepte (la race doit aussi accepter le sexe et "
             "l'alignement)")),
            ("allow", "genders", _("Sexes permis"), _("sexes que le rôle "
             "accepte")),
            ("allow", "aligns", _("Alignements permis"), _("alignements que "
             "le rôle accepte")),
        ]
        for i, a in enumerate(D.ATTRS):
            out.append(("attr", i, D.ATTR_FR[a], _("base : minimum au "
                        "départ ; poids : part des points restants (total "
                        "des poids : 100) ; ← → change la base")))
        out += [
            ("adv", "hp", _("PV de départ"), _("PV du rôle : fixe + 1 à N au "
             "hasard (la race en ajoute)")),
            ("adv", "en", _("Énergie de départ"), _("énergie du rôle : fixe "
             "+ 1 à N au hasard (la race en ajoute)")),
            ("gold", "gold", _("Or de départ"), _("pièces d'or au départ ; "
             "vide = celui du jeu")),
            ("intrinsics", "intrinsics", _("Intrinsèques"), _("capacités "
             "données dès le départ, en plus de celles du rôle")),
        ]
        kits = self.game().kit_names(role)
        for n in kits:
            out.append(("kit", n, _("Inventaire") if len(kits) == 1 else
                        _("Inventaire %s") % n.split("_")[-1],
                        _("objets de départ (k) ; le jeu tire l'une des deux "
                          "variantes au hasard") if len(kits) > 1 else
                        _("objets de départ (k ou Entrée)")))
        out += [("tile", g, _("Tuile (%s)") % D.GENDER_FR[g],
                 _("image des versions graphiques (Qt, X11) ; Entrée : "
                   "dessiner, Suppr : tuile du jeu")) for g in D.GENDERS]
        return out

    def is_role_field(self, f):
        return f[0] in ("rank", "god", "allow", "attr", "adv", "gold",
                        "intrinsics", "kit", "tile")

    def field_modified(self, h, f):
        mod = self.mod(h["role"])
        kind, key = f[0], f[1]
        if kind == "rank":
            return any(k in mod and mod[k][key] != self.rank_defaults(
                self.role_of(h))[k][key] for k in
                ("ranks_en", "ranks_fr", "ranks_cyber"))
        if kind == "god":
            return "gods" in mod and mod["gods"][key] != \
                self.role_of(h)["gods"][key]
        if kind == "allow":
            if "allow" not in mod:
                return False
            bits = self.allow_bits(key)
            return {b for b in mod["allow"] if b in bits} != \
                {b for b in self.role_of(h)["allow"] if b in bits}
        if kind == "attr":
            role = self.role_of(h)
            return any(k in mod and mod[k][key] != role[k][key]
                       for k in ("attrbase", "attrdist"))
        if kind == "adv":
            return key in mod
        if kind in ("gold", "intrinsics"):
            return key in mod
        if kind == "kit":
            return key in mod.get("kits", {})
        if kind == "tile":
            return ("tile_" + key) in mod
        return False

    def rank_defaults(self, role):
        tab = D.ranks_table(role, self.game().names)
        return {"ranks_en": [r[:2] for r in tab],
                "ranks_fr": [r[2:4] for r in tab],
                "ranks_cyber": [r[4:6] for r in tab]}

    def ranks(self, role, which):
        return copy.deepcopy(self.mod(D.role_key(role)).get(
            which, self.rank_defaults(role)[which]))

    def allow_bits(self, key):
        return {"races": D.RACE_BITS,
                "genders": [D.GENDER_BIT[g] for g in D.GENDERS],
                "aligns": [D.ALIGN_BIT[a] for a in D.ALIGNS]}[key]

    def eff(self, h):
        return D.effective(self.role_of(h), self.mod(h["role"]))

    def kit(self, h, name):
        return copy.deepcopy(self.mod(h["role"]).get("kits", {}).get(
            name, self.game().kits.get(name, [])))

    def tile(self, h, gender):
        t = self.mod(h["role"]).get("tile_" + gender)
        return t or self.game().tile(self.role_of(h), gender) or \
            D.blank_tile()

    def field_value(self, h, f):
        kind, key = f[0], f[1]
        g = self.game()
        role, race = self.role_of(h), self.race_of(h)
        red = self.colors.fg(curses.COLOR_RED, True)
        if kind == "text":
            v = h[key]
            if key == "petname" and h["pet"] == "none":
                return _("(pas d'animal)"), curses.A_DIM
            return (v, 0) if v else ("—", curses.A_DIM)
        if kind == "longtext":
            s = " ".join(h[key].split())
            return (s, 0) if s else ("—", curses.A_DIM)
        if kind == "role":
            if not role:
                return "%s ?" % h["role"], red
            return self.role_name(role, h["gender"]), \
                self.colors.fg(curses.COLOR_MAGENTA, True)
        if kind == "race":
            if not race:
                return "%s ?" % h["race"], red
            ok = role and D.allowed(self.eff(h)["allow"], race)
            return "%s%s" % (self.race_name(race, h["gender"]),
                             "" if ok else _("  ✖ interdit")), \
                0 if ok else red
        if kind == "gender":
            ok = role and race and D.allowed(self.eff(h)["allow"], race,
                                             h["gender"])
            return D.GENDER_FR[h["gender"]] + ("" if ok else
                                               _("  ✖ interdit")), \
                0 if ok else red
        if kind == "align":
            ok = role and race and D.allowed(self.eff(h)["allow"], race,
                                             None, h["align"])
            god = self.eff(h)["gods"][D.ALIGN_GOD[h["align"]]] if role \
                else None
            return "%s — %s%s" % (D.ALIGN_FR[h["align"]],
                                  _("dieu : ") + self.god_text(god),
                                  "" if ok else _("  ✖ interdit")), \
                0 if ok else red
        if kind == "pet":
            if h["pet"]:
                return dict(D.PETS)[h["pet"]], 0
            if role and role["petnum"] in D.PET_OF_PM:
                mon = D.PET_MONSTER[D.PET_OF_PM[role["petnum"]]]
                return _("imposé par le rôle : %s") % g.names.monster(
                    mon, self.theme), curses.A_DIM
            return _("au hasard : %s ou %s") % (
                g.names.monster("kitten", self.theme),
                g.names.monster("little dog", self.theme)), curses.A_DIM
        if kind == "conducts":
            return (", ".join(c.lstrip("!") for c in h[key]), 0) if h[key] \
                else (_("aucune"), curses.A_DIM)
        if kind == "rank":
            names = self.ranks(role, "ranks_" + ("en" if self.theme == "en"
                                                 else self.theme))[key]
            en = self.ranks(role, "ranks_en")[key]
            m, fe = names
            s = m if not fe or fe == m else "%s / %s" % (m, fe)
            if self.theme != "en":
                s += "  (%s)" % en[0]
            return s, 0
        if kind == "god":
            return self.god_text(self.eff(h)["gods"][key]), 0
        if kind == "allow":
            allow = self.eff(h)["allow"]
            if key == "races":
                v = [self.race_name(r) for r in g.races
                     if r["self"] & allow]
            elif key == "genders":
                v = [D.GENDER_FR[x] for x in D.GENDERS
                     if D.GENDER_BIT[x] in allow]
            else:
                v = [D.ALIGN_FR[x] for x in D.ALIGNS
                     if D.ALIGN_BIT[x] in allow]
            return (", ".join(v), 0) if v else (_("aucun ✖"), red)
        if kind == "attr":
            e = self.eff(h)
            base, dist = e["attrbase"][key], e["attrdist"][key]
            s = _("base %2d   poids %2d") % (base, dist)
            if race:
                lo, hi = D.attr_range((base,), (race["attrmin"][key],
                                                race["attrmax"][key]))
                s += _("   → de %s à %s") % (D.attr_text(lo, key),
                                            D.attr_text(hi, key))
            return s, 0
        if kind == "adv":
            fix, rnd = self.eff(h)[key]
            s = "%d" % fix + (" + 1d%d" % rnd if rnd else "")
            if race:
                lo, hi = (D.start_hp if key == "hp" else D.start_en)(
                    [fix, rnd], race)
                s += _("   (avec la race : %d à %d)") % (lo, hi) if \
                    lo != hi else _("   (avec la race : %d)") % lo
            return s, 0
        if kind == "gold":
            v = self.eff(h)["gold"]
            if v is None:
                gg = D.GAME_GOLD.get(role["mnum"])
                return (_("celui du jeu : %s") % gg if gg else
                        _("celui du jeu : aucun")), curses.A_DIM
            return str(v), 0
        if kind == "intrinsics":
            v = self.eff(h)["intrinsics"]
            return (", ".join(D.INTRINSIC_FR[x] for x in v), 0) if v else \
                (_("ceux du rôle seulement"), curses.A_DIM)
        if kind == "kit":
            items = self.kit(h, key)
            return "%d : %s" % (len(items), ", ".join(
                self.item_text(o) for o in items)), 0
        if kind == "tile":
            return (_("dessinée (Entrée : modifier)"), 0) \
                if ("tile_" + key) in self.mod(h["role"]) else \
                (_("celle du jeu (Entrée : dessiner)"), curses.A_DIM)
        return "?", 0

    # --- dessin -----------------------------------------------------------

    def redraw(self):
        self.draw()

    def draw(self):
        scr = self.stdscr
        scr.erase()
        H, W = scr.getmaxyx()
        if H < 20 or W < 70:
            put(scr, 0, 0, _("Terminal trop petit (70x20 minimum)"))
            scr.refresh()
            return
        title = _(" nhheroedit ▸ héros de Night City ")
        proj = " %s · %s%s " % (D.THEME_FR[self.theme],
                                os.path.basename(self.project),
                                _(" [modifié]") if self.modified else "")
        bar = self.colors.pair(curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        put(scr, 0, 0, " " * W, bar)
        put(scr, 0, 0, title, bar | curses.A_BOLD)
        put(scr, 0, max(len(title) + 1, W - len(proj) - 1), proj, bar)
        lw = 26
        rw = 42 if W >= 120 else 0
        fw = W - lw - rw
        self.areas = {"list": (1, 0, H - 3, lw), "form": (1, lw, H - 3, fw)}
        self.draw_list(1, 0, H - 3, lw)
        self.draw_form(1, lw, H - 3, fw)
        if rw:
            self.draw_side(1, lw + fw, H - 3, rw)
        h = self.hero()
        hint = ""
        if self.focus == "form" and h:
            fs = self.fields()
            self.field = min(self.field, len(fs) - 1)
            hint = fs[self.field][3]
        put(scr, H - 2, 0, (" " + hint).ljust(W),
            self.colors.fg(curses.COLOR_CYAN))
        keys = _(" n:nouveau d:dupl. k:inventaire t:tuile T:thème v:vérif "
                 "c:code I:intégrer m:make U:update j:jouer s:enreg. ?:aide "
                 "q:quitter")
        put(scr, H - 1, 0, (" " + self.msg).ljust(W) if self.msg else
            keys.ljust(W), self.colors.pair(curses.COLOR_BLACK,
                                            curses.COLOR_CYAN))
        scr.refresh()

    def frame(self, y, x, h, w, title, attr):
        scr = self.stdscr
        put(scr, y, x, frame_top(title, w), attr)
        for i in range(1, h - 1):
            put(scr, y + i, x, "│", attr)
            put(scr, y + i, x + w - 1, "│", attr)
        put(scr, y + h - 1, x, "└" + "─" * (w - 2) + "┘", attr)

    def draw_list(self, y, x, h, w):
        scr = self.stdscr
        act = self.focus == "list"
        self.frame(y, x, h, w, _("Héros"),
                   self.colors.fg(curses.COLOR_MAGENTA, act))
        if not self.heroes:
            put(scr, y + 2, x + 2, _("(aucun héros)"), curses.A_DIM)
            put(scr, y + 3, x + 2, _("n : nouveau héros"), curses.A_DIM)
            return
        rows = h - 2
        top = max(0, min(self.cur - rows // 2, len(self.heroes) - rows))
        self.list_top = top
        for r, hero in enumerate(self.heroes[top:top + rows]):
            i = top + r
            sel = i == self.cur
            a = curses.A_REVERSE if sel and act else \
                (curses.A_BOLD if sel else 0)
            put(scr, y + 1 + r, x + 1, " " * (w - 2), a)
            put(scr, y + 1 + r, x + 2, "@", self.colors.fg(
                curses.COLOR_CYAN if hero["gender"] == "male"
                else curses.COLOR_MAGENTA, True) | (a & curses.A_REVERSE))
            put(scr, y + 1 + r, x + 4, hero["name"] or _("(sans nom)"), a,
                w - 8)
            errs = any(g == "erreur" for g, _m in self.problems(hero))
            mark = "✖" if errs else ("◆" if self.mod(hero["role"]) else "")
            put(scr, y + 1 + r, x + w - 3, mark,
                self.colors.fg(curses.COLOR_RED, True) if errs else
                self.colors.fg(curses.COLOR_YELLOW, True))

    def draw_form(self, y, x, h, w):
        scr = self.stdscr
        hero = self.hero()
        act = self.focus == "form"
        self.frame(y, x, h, w, _("Fiche"),
                   self.colors.fg(curses.COLOR_CYAN, act))
        if not hero:
            return
        fs = self.fields()
        self.field = max(1, min(self.field, len(fs) - 1))
        if fs[self.field][0] == "section":
            self.move_field(1)
        rows = h - 2
        if self.field < self.form_top + 1:
            self.form_top = max(0, self.field - 1)
        if self.field >= self.form_top + rows:
            self.form_top = self.field - rows + 1
        lw = 20
        for r, f in enumerate(fs[self.form_top:self.form_top + rows]):
            i = self.form_top + r
            yy = y + 1 + r
            if f[0] == "section":
                put(scr, yy, x + 2, "▸ " + f[2],
                    self.colors.fg(curses.COLOR_MAGENTA, True), w - 4)
                continue
            sel = i == self.field
            la = curses.A_REVERSE if sel and act else \
                (curses.A_BOLD if sel else 0)
            if self.is_role_field(f) and self.field_modified(hero, f):
                put(scr, yy, x + 1, "●",
                    self.colors.fg(curses.COLOR_YELLOW, True))
            put(scr, yy, x + 2, f[2].ljust(lw), la, lw)
            val, va = self.field_value(hero, f)
            put(scr, yy, x + 3 + lw, val, va, w - lw - 5)

    def draw_side(self, y, x, h, w):
        scr = self.stdscr
        hero = self.hero()
        self.frame(y, x, h, w, _("Aperçu"),
                   self.colors.fg(curses.COLOR_BLUE, True))
        if not hero:
            return
        g = self.game()
        role, race = self.role_of(hero), self.race_of(hero)
        cw = w - 4
        yy = y + 1
        S = D.TILE_SIZE
        bottom = y + h - 1
        show_tile = h >= 24 and role
        if show_tile:
            bottom -= S // 2 + 1
        put(scr, yy, x + 2, "@", self.colors.fg(curses.COLOR_WHITE, True))
        put(scr, yy, x + 4, hero["name"] or "?", curses.A_BOLD, cw - 2)
        yy += 1
        if role and race:
            title = g.names.rank(
                {"name": role["name"],
                 "ranks": self.ranks(role, "ranks_en")}, 0,
                hero["gender"], "en")
            loc = self.ranks(role, "ranks_" + ("en" if self.theme == "en"
                                               else self.theme))[0]
            title = (loc[1] if hero["gender"] == "female" and loc[1]
                     else loc[0]) or title
            put(scr, yy, x + 4, title, self.colors.fg(curses.COLOR_CYAN,
                                                      True), cw - 2)
            yy += 1
            put(scr, yy, x + 4, "%s %s, %s" % (
                g.names.role(role, hero["gender"], self.theme),
                self.race_name(race, hero["gender"]),
                D.ALIGN_FR[hero["align"]]), 0, cw - 2)
            yy += 2
            e = self.eff(hero)
            for i, a in enumerate(D.ATTRS):
                lo, hi = D.attr_range((e["attrbase"][i],),
                                      (race["attrmin"][i],
                                       race["attrmax"][i]))
                col = i % 2
                put(scr, yy + i // 2, x + 2 + col * 19, "%s %s-%s" % (
                    D.ATTR_SHORT[a], D.attr_text(lo, i), D.attr_text(hi, i)),
                    0, 18)
            yy += 3
            hp = D.start_hp(e["hp"], race)
            en = D.start_en(e["en"], race)
            put(scr, yy, x + 2, _("PV %d-%d   Énergie %d-%d") % (
                hp + en), 0, cw)
            yy += 1
            god = e["gods"][D.ALIGN_GOD[hero["align"]]]
            put(scr, yy, x + 2, _("Dieu : %s") % self.god_text(god), 0, cw)
            yy += 1
            st, sa = self.role_status(hero["role"])
            put(scr, yy, x + 2, _("Rôle : "), curses.A_DIM)
            put(scr, yy, x + 9, st, sa, cw - 7)
            yy += 1
            games = self.games(hero["name"])
            if games:
                s = G.games_summary(games)
                put(scr, yy, x + 2, _("Parties : %d, record %s (h)") % (
                    s["count"], "—" if s["best"] is None else s["best"]),
                    curses.A_DIM, cw)
                yy += 1
            yy += 1
            for n in g.kit_names(role):
                for o in self.kit(hero, n):
                    if yy >= bottom - 3:
                        break
                    put(scr, yy, x + 2, "· " + self.item_text(o), 0, cw)
                    yy += 1
                if len(g.kit_names(role)) > 1:
                    put(scr, yy, x + 2, _("  (ou l'autre variante)"),
                        curses.A_DIM)
                    yy += 1
                    break
            gold = e["gold"]
            if gold:
                put(scr, yy, x + 2, _("· %d pièces d'or") % gold, 0, cw)
                yy += 1
            yy += 1
        res = self.problems(hero)
        if not res:
            put(scr, yy, x + 2, _("✔ aucun problème"),
                self.colors.fg(curses.COLOR_GREEN, True))
        for gr, msg in res:
            if yy >= bottom:
                break
            a = self.colors.fg(curses.COLOR_RED, True) if gr == "erreur" \
                else self.colors.fg(curses.COLOR_YELLOW, True)
            words, line, first = msg.split(), "", True
            for wd in words:
                if len(line) + len(wd) + 1 > cw - 2:
                    put(scr, yy, x + 2, ("✖ " if gr == "erreur" else "⚠ ")
                        + line if first else "  " + line, a)
                    yy, line, first = yy + 1, wd, False
                    if yy >= bottom:
                        break
                else:
                    line = (line + " " + wd).strip()
            if yy < bottom and line:
                put(scr, yy, x + 2, (("✖ " if gr == "erreur" else "⚠ ")
                                     if first else "  ") + line, a)
                yy += 1
        if show_tile:
            tile = self.tile(hero, hero["gender"])
            put(scr, bottom, x + 2, _("Tuile (t)"), curses.A_DIM)
            tx = x + w - 2 - S
            for j in range(0, S, 2):
                for i in range(S):
                    put(scr, bottom + 1 + j // 2, tx + i, "▀",
                        self.colors.halfblock(tile[j][i], tile[j + 1][i]))

    # --- édition --------------------------------------------------------------

    def move_field(self, delta):
        fs = self.fields()
        i = self.field
        while True:
            i += delta
            if i < 0 or i >= len(fs):
                return
            if fs[i][0] != "section":
                self.field = i
                return

    def fix_combo(self, h):
        """Après un changement de rôle, de race ou de sexe : race, sexe
        et alignement ramenés à une combinaison permise."""
        role = self.role_of(h)
        if not role:
            return
        allow = self.eff(h)["allow"]
        cs = D.combos(allow, self.game().races)
        if not cs or (h["race"], h["gender"], h["align"]) in cs:
            return
        old = (h["race"], h["gender"], h["align"])
        # garder le plus possible : race, puis sexe, puis alignement
        for keep in ((0, 1), (0,), (1,), ()):
            best = [c for c in cs if all(c[k] == old[k] for k in keep)]
            if best:
                h["race"], h["gender"], h["align"] = best[0]
                break
        changed = [n for n, a, b in zip(
            (_("race"), _("sexe"), _("alignement")), old,
            (h["race"], h["gender"], h["align"])) if a != b]
        self.msg = _("Ajusté pour une combinaison permise : %s") % \
            ", ".join(changed)

    def choices(self, kind, h):
        g = self.game()
        if kind == "role":
            return [(D.role_key(r), self.role_name(r, h["gender"]))
                    for r in g.roles]
        allow = self.eff(h)["allow"] if self.role_of(h) else set()
        if kind == "race":
            return [(r["noun"], self.race_name(r, h["gender"]) + (
                "" if D.allowed(allow, r) else _("  ✖ interdit")))
                for r in g.races]
        race = self.race_of(h)
        if kind == "gender":
            return [(x, D.GENDER_FR[x] + ("" if race and D.allowed(
                allow, race, x) else _("  ✖ interdit"))) for x in D.GENDERS]
        if kind == "align":
            return [(x, D.ALIGN_FR[x] + ("" if race and D.allowed(
                allow, race, None, x) else _("  ✖ interdit")))
                for x in D.ALIGNS]
        if kind == "pet":
            return list(D.PETS)
        return []

    def adjust(self, delta):
        h = self.hero()
        f = self.fields()[self.field]
        kind, key = f[0], f[1]
        if kind in ("role", "race", "gender", "align", "pet"):
            ch = [c for c, _d in self.choices(kind, h)]
            i = ch.index(h[key]) if h[key] in ch else 0
            self.checkpoint()
            h[key] = ch[(i + delta) % len(ch)]
            if kind == "role":
                self.fix_combo(h)
        elif kind == "attr":
            role = self.role_of(h)
            v = self.eff(h)["attrbase"]
            v[key] = max(3, min(18, v[key] + delta))
            self.checkpoint()
            self.set_mod(h["role"], "attrbase", v, role["attrbase"])
        elif kind == "adv":
            role = self.role_of(h)
            v = self.eff(h)[key]
            v[0] = max(0, min(99, v[0] + delta))
            self.checkpoint()
            self.set_mod(h["role"], key, v, (role["hpadv"] if key == "hp"
                                             else role["enadv"])[:2])
        elif kind == "gold":
            v = self.eff(h)["gold"] or 0
            self.checkpoint()
            self.set_mod(h["role"], "gold", max(0, v + 50 * delta), None)

    def clear_field(self):
        h = self.hero()
        f = self.fields()[self.field]
        kind, key = f[0], f[1]
        if kind in ("text", "longtext") and key != "name" and h[key]:
            self.checkpoint()
            h[key] = ""
        elif kind == "conducts" and h[key]:
            self.checkpoint()
            h[key] = []
        elif kind == "pet" and h[key]:
            self.checkpoint()
            h[key] = ""
        elif self.is_role_field(f) and self.field_modified(h, f):
            self.checkpoint()
            self.reset_role_field(h, f)
            self.msg = _("Valeur du jeu rétablie")

    def reset_role_field(self, h, f):
        role = self.role_of(h)
        rk = h["role"]
        kind, key = f[0], f[1]
        mod = self.mod(rk)
        if kind == "rank":
            for k in ("ranks_en", "ranks_fr", "ranks_cyber"):
                if k in mod:
                    v = self.ranks(role, k)
                    v[key] = self.rank_defaults(role)[k][key]
                    self.set_mod(rk, k, v, self.rank_defaults(role)[k])
        elif kind == "god":
            v = self.eff(h)["gods"]
            v[key] = role["gods"][key]
            self.set_mod(rk, "gods", v, role["gods"])
        elif kind == "allow":
            bits = self.allow_bits(key)
            v = {b for b in self.eff(h)["allow"] if b not in bits} | \
                {b for b in role["allow"] if b in bits}
            self.set_mod(rk, "allow", sorted(v), sorted(role["allow"]))
        elif kind == "attr":
            for k in ("attrbase", "attrdist"):
                v = self.eff(h)[k]
                v[key] = role[k][key]
                self.set_mod(rk, k, v, role[k])
        elif kind in ("adv", "gold", "intrinsics"):
            self.set_mod(rk, key, None, None)
        elif kind == "kit":
            kits = dict(mod.get("kits", {}))
            kits.pop(key, None)
            self.set_mod(rk, "kits", kits, {})
        elif kind == "tile":
            self.set_mod(rk, "tile_" + key, None, None)

    def edit_field(self):
        h = self.hero()
        f = self.fields()[self.field]
        kind, key, label = f[0], f[1], f[2].strip()
        role = self.role_of(h)
        try:
            if kind == "text":
                v = self.input_line(label, h[key], f[3]).strip()
                if v != h[key]:
                    self.checkpoint()
                    h[key] = v
            elif kind == "longtext":
                v = self.text_area(label, h[key])
                if v != h[key]:
                    self.checkpoint()
                    h[key] = v
            elif kind in ("role", "race", "gender", "align", "pet"):
                ch = self.choices(kind, h)
                names = [c for c, _d in ch]
                i = self.menu(label, [(d, "") for _c, d in ch],
                              names.index(h[key]) if h[key] in names else 0,
                              filterable=len(ch) > 6)
                if ch[i][0] != h[key]:
                    self.checkpoint()
                    h[key] = ch[i][0]
                    if kind == "role":
                        self.fix_combo(h)
            elif kind == "conducts":
                v = self.checklist(label, D.CONDUCTS, h[key])
                if v != h[key]:
                    self.checkpoint()
                    h[key] = v
            elif kind == "rank":
                self.edit_rank(h, key)
            elif kind == "god":
                v = self.input_line(label, self.eff(h)["gods"][key] or "",
                                    _("vide = nom du jeu ; « _ » devant : "
                                      "déesse")).strip()
                gods = self.eff(h)["gods"]
                gods[key] = v or role["gods"][key]
                self.checkpoint()
                self.set_mod(h["role"], "gods", gods, role["gods"])
            elif kind == "allow":
                bits = self.allow_bits(key)
                g = self.game()
                labels = {**{r["noun"]: self.race_name(r) for r in g.races},
                          **D.GENDER_FR, **D.ALIGN_FR}
                ids = {"races": [r["noun"] for r in g.races],
                       "genders": D.GENDERS, "aligns": D.ALIGNS}[key]
                allow = self.eff(h)["allow"]
                cur = [i for i, b in zip(ids, bits) if b in allow]
                v = self.checklist(label, [(i, labels[i]) for i in ids], cur)
                new = {b for b in allow if b not in bits} | \
                    {b for i, b in zip(ids, bits) if i in v}
                self.checkpoint()
                self.set_mod(h["role"], "allow", sorted(new),
                             sorted(role["allow"]))
            elif kind == "attr":
                e = self.eff(h)
                s = self.input_line(label, "%d %d" % (
                    e["attrbase"][key], e["attrdist"][key]),
                    _("base (3 à 18) puis poids (0 à 100), par exemple "
                      "« 10 30 »"))
                mo = re.match(r"^\s*(\d+)\s+(\d+)\s*$", s)
                if not mo or not 3 <= int(mo.group(1)) <= 18 or \
                        int(mo.group(2)) > 100:
                    self.msg = _("Valeur invalide : base de 3 à 18, poids "
                                 "de 0 à 100")
                    return
                self.checkpoint()
                for k, v in (("attrbase", int(mo.group(1))),
                             ("attrdist", int(mo.group(2)))):
                    lst = e[k]
                    lst[key] = v
                    self.set_mod(h["role"], k, lst, role[k])
            elif kind == "adv":
                fix, rnd = self.eff(h)[key]
                s = self.input_line(label, "%d %d" % (fix, rnd),
                                    _("fixe puis dé (0 : aucun), par exemple "
                                      "« 14 2 »"))
                mo = re.match(r"^\s*(\d+)\s+(\d+)\s*$", s)
                if not mo or int(mo.group(1)) > 99 or int(mo.group(2)) > 99:
                    self.msg = _("Valeur invalide : deux nombres de 0 à 99")
                    return
                self.checkpoint()
                self.set_mod(h["role"], key, [int(mo.group(1)),
                                              int(mo.group(2))],
                             (role["hpadv"] if key == "hp"
                              else role["enadv"])[:2])
            elif kind == "gold":
                v = self.eff(h)["gold"]
                s = self.input_line(label, "" if v is None else str(v),
                                    _("0 à 100000 ; vide = celui du jeu"))
                s = s.strip()
                if s and (not s.isdigit() or int(s) > 100000):
                    self.msg = _("Valeur invalide : 0 à 100000")
                    return
                self.checkpoint()
                self.set_mod(h["role"], "gold", int(s) if s else None, None)
            elif kind == "intrinsics":
                v = self.checklist(label, D.INTRINSICS,
                                   self.eff(h)["intrinsics"])
                self.checkpoint()
                self.set_mod(h["role"], "intrinsics", v, [])
            elif kind == "kit":
                self.edit_kit(h, key)
            elif kind == "tile":
                self.edit_tile(key)
        except Cancel:
            pass

    def edit_rank(self, h, i):
        role = self.role_of(h)
        sel = 0
        while True:
            items = []
            for which, j, label, where in RANK_VARIANTS:
                v = self.ranks(role, which)[i][j]
                items.append((label, (v or "—") + "   " + where))
            try:
                sel = self.menu(_("Rang %d (niveaux %s)") % (
                    i + 1, D.RANK_LEVELS[i]), items, sel, filterable=False)
            except Cancel:
                return
            which, j, label, _w = RANK_VARIANTS[sel]
            tab = self.ranks(role, which)
            try:
                v = self.input_line(_("Rang %d : %s") % (i + 1, label),
                                    tab[i][j], _("vide = titre du jeu")
                                    if which != "ranks_en" or j == 0 else
                                    _("vide = pas de titre féminin propre"))
            except Cancel:
                continue
            v = v.strip()
            if not v and not (which == "ranks_en" and j == 1):
                v = self.rank_defaults(role)[which][i][j]
            if v == tab[i][j]:
                continue
            self.checkpoint()
            tab[i][j] = v
            self.set_mod(h["role"], which, tab,
                         self.rank_defaults(role)[which])
            warn = self.rank_problems(h["role"])
            if warn:
                self.msg = "⚠ " + warn[0][1]

    # --- inventaire ----------------------------------------------------------

    def choose_object(self, o=None):
        """Menu des objets du jeu ; renvoie (sn, classe) ou lève Cancel."""
        g = self.game()
        items = [(_("(au hasard) %s") % s, "") for _c, s, _p in D.CLASSES]
        keys = [(D.UNDEF_TYP, c) for c, _s, _p in D.CLASSES]
        for ob in g.objects:
            name = g.names.obj(ob, self.theme)
            items.append(("%s : %s" % (D.CLASS_FR[ob["cls"]], name),
                          ob["name"] if name != ob["name"] else ""))
            keys.append((ob["sn"], ob["cls"]))
        cur = keys.index((o["otyp"], o["cls"])) if o and \
            (o["otyp"], o["cls"]) in keys else 0
        i = self.menu(_("Objet (%d) — tapez pour filtrer") % len(g.objects),
                      items, cur)
        return keys[i]

    def edit_item(self, o):
        """Objet, quantité, enchantement, bénédiction ; lève Cancel."""
        sn, cls = self.choose_object(o)
        o = dict(o or {"qmin": 1, "qmax": 1, "spe": 0, "bless": None})
        o["otyp"], o["cls"] = sn, cls
        hint = _("1 ou un intervalle : 10-20 (le jeu tire au hasard)")
        while True:
            q = parse_qty(self.input_line(_("Quantité"), qty_text(o), hint))
            if q:
                break
            hint = _("⚠ invalide : 1 à 127, ou min-max")
        o["qmin"], o["qmax"] = q
        hint = _("+2 arme ou armure, charges d'une baguette ; vide = au "
                 "hasard")
        while True:
            s = self.input_line(_("Enchantement / charges"),
                                "" if o["spe"] is None else str(o["spe"]),
                                hint).strip()
            if not s:
                o["spe"] = None
                break
            try:
                o["spe"] = int(s)
                if -127 <= o["spe"] <= 127:
                    break
            except ValueError:
                pass
            hint = _("⚠ invalide : un entier de -127 à 127, ou vide")
        b = self.menu(_("État"), [
            (_("au hasard (le jeu ne maudit pas l'équipement de départ)"),
             ""), (_("non maudit"), ""), (_("béni"), "")],
            {None: 0, 0: 1, 1: 2}[o["bless"]], filterable=False)
        o["bless"] = [None, 0, 1][b]
        return D.normalize_item(o)

    def edit_kit(self, h, name):
        """Éditeur de l'inventaire de départ name du rôle du héros."""
        role = self.role_of(h)
        items = self.kit(h, name)
        orig = self.game().kits.get(name, [])
        sel, top = 0, 0
        H, W = self.stdscr.getmaxyx()
        win = centered(self.stdscr, H - 2, min(W - 2, 90))
        wh, ww = win.getmaxyx()
        title = _("Inventaire de départ : %s — %s") % (
            self.game().names.role(role, h["gender"], self.theme), name)
        try:
            while True:
                rows = wh - 6
                sel = max(0, min(sel, len(items) - 1)) if items else 0
                if sel < top:
                    top = sel
                if sel >= top + rows:
                    top = sel - rows + 1
                win.erase()
                box(win, title, self.accent())
                put(win, 1, 2, _("Entrée : modifier  a : ajouter  Suppr : "
                                 "retirer  < > : déplacer  o : inventaire "
                                 "du jeu  Échap : terminer"), curses.A_DIM,
                    ww - 4)
                for r, o in enumerate(items[top:top + rows]):
                    i = top + r
                    a = curses.A_REVERSE if i == sel else 0
                    put(win, 3 + r, 2, ("%2d  %-15s %s" % (
                        i + 1, D.CLASS_FR.get(o["cls"], o["cls"]),
                        self.item_text(o))).ljust(ww - 4), a, ww - 4)
                if not items:
                    put(win, 3, 4, _("(aucun objet : a pour ajouter)"),
                        curses.A_DIM)
                same = items == orig
                put(win, wh - 2, 2, _("inventaire du jeu") if same else
                    _("● modifié (%d objets ; jeu : %d)") % (len(items),
                                                             len(orig)),
                    curses.A_DIM if same else
                    self.colors.fg(curses.COLOR_YELLOW, True))
                win.refresh()
                k = get_key(win)
                if k == ESC or k == "q":
                    break
                if isinstance(k, Mouse):
                    pos = k.inside(win)
                    if wheel(k):
                        sel += 3 * wheel(k)
                    elif pos and 3 <= pos[0] < 3 + rows and \
                            top + pos[0] - 3 < len(items):
                        if sel == top + pos[0] - 3 or k.kind == "double":
                            k = "\n"
                        else:
                            sel = top + pos[0] - 3
                            continue
                    else:
                        continue
                if k == curses.KEY_UP:
                    sel -= 1
                elif k == curses.KEY_DOWN:
                    sel += 1
                elif is_enter(k) and items:
                    try:
                        items[sel] = self.edit_item(items[sel])
                    except Cancel:
                        pass
                elif k in ("a", "+", curses.KEY_IC):
                    if len(items) >= D.MAX_KIT:
                        continue
                    try:
                        o = self.edit_item(None)
                    except Cancel:
                        continue
                    items.insert(sel + 1 if items else 0, o)
                    sel = sel + 1 if len(items) > 1 else 0
                elif k in (curses.KEY_DC, "x", "X") and items:
                    del items[sel]
                elif k == "<" and sel > 0:
                    items[sel - 1], items[sel] = items[sel], items[sel - 1]
                    sel -= 1
                elif k == ">" and sel < len(items) - 1:
                    items[sel + 1], items[sel] = items[sel], items[sel + 1]
                    sel += 1
                elif k == "o":
                    items = copy.deepcopy(orig)
        finally:
            self.redraw()
        kits = dict(self.mod(h["role"]).get("kits", {}))
        if items == kits.get(name, orig):
            return
        self.checkpoint()
        if items == orig:
            kits.pop(name, None)
        else:
            kits[name] = items
        self.set_mod(h["role"], "kits", kits, {})
        self.msg = _("Inventaire modifié — I pour l'intégrer au jeu")

    def kit_key(self):
        """k : premier inventaire du rôle (ou celui du champ choisi)."""
        h = self.hero()
        if not h or not self.role_of(h):
            return
        f = self.fields()[self.field]
        if self.focus == "form" and f[0] == "kit":
            self.edit_kit(h, f[1])
            return
        names = self.game().kit_names(self.role_of(h))
        if len(names) > 1:
            try:
                i = self.menu(_("Quel inventaire ?"),
                              [(n, "") for n in names], filterable=False)
            except Cancel:
                return
            self.edit_kit(h, names[i])
        elif names:
            self.edit_kit(h, names[0])

    # --- tuiles ----------------------------------------------------------------

    def import_tile(self):
        """Tuile d'un monstre du jeu (menu filtrable), ou None."""
        g = self.game()
        tiles = g.monster_tiles()
        items = [("%s (%s)" % (g.names.monster(n, self.theme),
                               D.GENDER_FR[s]), n) for n, s in tiles]
        try:
            i = self.menu(_("Importer la tuile d'un monstre (%d)")
                          % len(items), items)
        except Cancel:
            return None
        return I.find_tile(g.tiles_text, *tiles[i])

    def edit_tile(self, gender=None):
        h = self.hero()
        role = self.role_of(h)
        if not role:
            return
        gender = gender or h["gender"]
        old = self.tile(h, gender)
        orig = self.game().tile(role, gender)
        new = self.tile_editor(old, "%s, %s" % (
            self.game().names.role(role, gender, self.theme),
            D.GENDER_FR[gender]), self.import_tile, orig)
        if new != old:
            self.checkpoint()
            self.set_mod(h["role"], "tile_" + gender, new, orig)
            self.msg = _("Tuile modifiée — commune à tous les héros %s ; I "
                         "pour l'intégrer") % self.game().names.role(
                             role, gender, self.theme)

    # --- héros ------------------------------------------------------------------

    def add_hero(self, h):
        self.checkpoint()
        self.heroes.insert(self.cur + 1 if self.heroes else 0, h)
        self.cur = self.cur + 1 if len(self.heroes) > 1 else 0
        self.focus = "form"
        self.field = 1

    def unique_name(self, h):
        names = {o["name"] for o in self.heroes}
        base, n = h["name"], 1
        while h["name"] in names:
            n += 1
            h["name"] = "%s%d" % (base, n)
        return h

    def new_hero(self):
        items = T.template_list()
        try:
            i = self.menu(_("Nouveau héros : archétype"), items)
            if i == T.RANDOM:
                g = self.game()
                h = T.random_hero(g.roles, g.races, lambda r: D.effective(
                    r, self.mod(D.role_key(r)))["allow"])
                if not h:
                    self.msg = _("Aucun rôle n'a de combinaison permise")
                    return
                h = self.unique_name(h)
            else:
                h = T.from_template(i)
            name = self.input_line(_("Nom du héros"), h["name"],
                                   _("sans - , : = / (31 caractères au "
                                     "plus)"))
        except Cancel:
            return
        old, h["name"] = h["name"], name.strip() or h["name"]
        if old and i == T.RANDOM and h["story"].startswith(old + " "):
            h["story"] = h["name"] + h["story"][len(old):]
        self.add_hero(self.unique_name(h))
        self.fix_combo(h)
        self.msg = _("Héros créé : %s") % h["name"]

    def random_name(self):
        """N : nom de Night City au hasard pour le héros choisi."""
        h = self.hero()
        if not h:
            return
        names = {o["name"] for o in self.heroes if o is not h}
        for _i in range(50):
            name = T.random_name(gender=h["gender"])
            if name not in names:
                break
        self.checkpoint()
        old, h["name"] = h["name"], name
        if h["story"].startswith(old + " ") and old:
            h["story"] = name + h["story"][len(old):]
        self.msg = _("Nouveau nom : %s (u pour annuler)") % name

    def duplicate(self):
        h = self.hero()
        if h:
            self.add_hero(self.unique_name(copy.deepcopy(h)))
            self.msg = _("Copie créée : %s") % self.hero()["name"]

    def delete(self):
        h = self.hero()
        if not h or not self.confirm(_("Supprimer « %s » du projet ?\n(les "
                                       "modifications de son rôle restent)")
                                     % (h["name"] or "?")):
            return
        self.checkpoint()
        del self.heroes[self.cur]
        self.cur = max(0, min(self.cur, len(self.heroes) - 1))
        self.msg = _("Supprimé")

    def goto_hero(self):
        if not self.heroes:
            return
        g = self.game()
        items = [(h["name"] or "?", self.role_name(g.role(h["role"]),
                                                   h["gender"])
                  if g.role(h["role"]) else h["role"]) for h in self.heroes]
        try:
            self.cur = self.menu(_("Aller au héros (%d)") % len(items),
                                 items, self.cur)
        except Cancel:
            return
        self.focus = "list"

    def move_hero(self, delta):
        j = self.cur + delta
        if not self.heroes or not 0 <= j < len(self.heroes):
            return
        self.checkpoint()
        hs = self.heroes
        hs[self.cur], hs[j] = hs[j], hs[self.cur]
        self.cur = j

    def cycle_theme(self):
        self.theme = D.THEMES[(D.THEMES.index(self.theme) + 1) %
                              len(D.THEMES)]
        self.msg = _("Noms affichés : %s") % D.THEME_FR[self.theme]

    # --- sauvegarde de secours ----------------------------------------------

    def autosave(self):
        now = time.time()
        if not self.modified or self.autosave_delay <= 0 or \
                now - self.autosave_time < self.autosave_delay:
            return
        self.autosave_time = now
        try:
            P.write_project(P.autosave_path(self.project), self.heroes,
                            self.roles)
        except OSError:
            pass

    def offer_autosave(self):
        auto = P.pending_autosave(self.project)
        if not auto:
            return
        when = time.strftime("%d/%m/%Y %H:%M",
                             time.localtime(os.path.getmtime(auto)))
        if not self.confirm(_("Sauvegarde de secours du %s trouvée\n"
                              "(session interrompue). La récupérer ?") % when,
                            _("Sauvegarde de secours")):
            P.drop_autosave(self.project)
            return
        try:
            heroes, roles = P.read_project(auto)
        except P.ProjectError as e:
            self.msg = _("Sauvegarde de secours illisible : %s") % e
            return
        self.checkpoint()
        self.heroes, self.roles, self.cur = heroes, roles, 0
        self.msg = _("Sauvegarde de secours récupérée (%d héros) — s pour "
                     "enregistrer") % len(heroes)

    # --- projet -------------------------------------------------------------

    def project_menu(self):
        actions = [
            (_("Fusionner un autre projet…"),
             _("ajoute ses héros et ses rôles modifiés"), self.merge),
            (_("Exporter le héros…"),
             _("fichier .nhhero.json, avec les changements de son rôle"),
             self.export_hero),
            (_("Importer un héros exporté…"), _("fichier .nhhero.json"),
             self.import_hero),
            (_("Rendre au rôle toutes ses valeurs du jeu"),
             _("efface les modifications du rôle du héros"),
             self.reset_role),
        ]
        try:
            i = self.menu(_("Projet"), [(a, b) for a, b, _f in actions],
                          filterable=False)
        except Cancel:
            return
        actions[i][2]()

    def choose_file(self, title, suffix):
        dirs = [os.path.dirname(self.project), HERE, os.getcwd()]
        files = [(n, d) for n, d in P.json_files(dirs, suffix)
                 if os.path.realpath(os.path.join(d, n)) !=
                 os.path.realpath(self.project)]
        items = [(n, d) for n, d in files] + [(_("Autre fichier…"), "")]
        i = self.menu(title, items)
        if i < len(files):
            return os.path.join(files[i][1], files[i][0])
        return os.path.expanduser(self.input_line(_("Fichier"), "",
                                                  _("chemin du fichier")))

    def add_from(self, heroes, roles):
        """Ajoute des héros et des rôles modifiés (un rôle déjà modifié
        dans le projet est gardé tel quel)."""
        self.checkpoint()
        kept = []
        for k, v in roles.items():
            if k in self.roles and not P.same(self.roles[k], v):
                kept.append(k)
            elif v:
                self.roles[k] = v
        n = 0
        for h in heroes:
            if not any(P.same(h, o) for o in self.heroes):
                self.heroes.append(self.unique_name(h))
                n += 1
        self.msg = _("%d héros ajouté(s)") % n + (
            _(" ; rôles déjà modifiés ici, gardés : %s") % ", ".join(kept)
            if kept else "")

    def merge(self):
        try:
            path = self.choose_file(_("Fusionner un projet"), ".json")
            heroes, roles = P.read_project(path)
        except Cancel:
            return
        except P.ProjectError as e:
            self.msg = str(e)
            return
        self.add_from(heroes, roles)

    def export_hero(self):
        h = self.hero()
        if not h:
            return
        path = P.export_path(os.path.dirname(self.project), h)
        try:
            path = os.path.expanduser(self.input_line(
                _("Exporter vers"), path, _("fichier .nhhero.json")))
        except Cancel:
            return
        if os.path.exists(path) and not self.confirm(
                _("Remplacer %s ?") % path):
            return
        P.write_hero(path, h, self.mod(h["role"]))
        self.msg = _("Héros exporté : %s") % path

    def import_hero(self):
        try:
            path = self.choose_file(_("Importer un héros"), P.HERO_SUFFIX)
            heroes, roles = P.read_project(path)
        except Cancel:
            return
        except P.ProjectError as e:
            self.msg = str(e)
            return
        self.add_from(heroes, roles)

    def reset_role(self):
        h = self.hero()
        if not h or not self.mod(h["role"]):
            self.msg = _("Le rôle n'est pas modifié")
            return
        if not self.confirm(_("Effacer toutes les modifications du rôle "
                              "%s ?") % h["role"]):
            return
        self.checkpoint()
        self.roles.pop(h["role"], None)
        self.msg = _("Rôle rendu à ses valeurs du jeu — I pour l'appliquer "
                     "aux sources")

    # --- contrôle -----------------------------------------------------------

    def show_validation(self):
        lines = []
        for h in self.heroes:
            res = self.problems(h)
            lines.append(("%s%s" % (h["name"] or "?",
                                    "" if res else _("  ✔")),
                          curses.A_BOLD))
            for g, m in res:
                lines.append(("  %s %s" % ("✖" if g == "erreur" else "⚠",
                                           m),
                              self.colors.fg(curses.COLOR_RED, True)
                              if g == "erreur" else
                              self.colors.fg(curses.COLOR_YELLOW, True)))
        g = self.game()
        for k in sorted(self.roles):
            role = g.role(k)
            if role and not any(h["role"] == k for h in self.heroes):
                res = D.role_problems(role, g.races[0], self.roles[k],
                                      g.objects) + self.rank_problems(k)
                lines.append((_("Rôle %s (sans héros)") % role["name"][0],
                              curses.A_BOLD))
                lines += [("  %s %s" % ("✖" if gr == "erreur" else "⚠", m),
                           0) for gr, m in res]
        self.viewer(_("Vérification"), lines or [_("Aucun héros")])

    def show_code(self):
        h = self.hero()
        if not h or not self.role_of(h):
            return
        g = self.game()
        role, race = self.role_of(h), self.race_of(h)
        lines = [(_("Options du héros (.nethackrc) :"), curses.A_BOLD)]
        if race:
            lines += [(l, self.cyan()) for l in
                      D.nethackrc(h, role, race, g.names,
                                  self.theme).splitlines()]
        lines += ["", (_("Changements du rôle dans les sources :"),
                       curses.A_BOLD)]
        mod = self.mod(h["role"])
        if not mod:
            lines.append(_("  (aucun : rôle d'origine)"))
        else:
            try:
                files = I.plan(self.src, {h["role"]: mod}, g)
                for rel, new in files.items():
                    old = I.clean_text(self.src, rel)
                    if old == new:
                        continue
                    for l in I.difflib.unified_diff(
                            old.splitlines(), new.splitlines(),
                            "a/" + rel, "b/" + rel, n=1, lineterm=""):
                        lines.append((l, self.diff_attr(l)))
            except (I.InstallError, OSError, ValueError) as e:
                lines.append(("✖ %s" % e,
                              self.colors.fg(curses.COLOR_RED, True)))
        self.viewer(_("Code — %s") % (h["name"] or "?"), lines)

    def diff_attr(self, l):
        if l.startswith("+"):
            return self.colors.fg(curses.COLOR_GREEN)
        if l.startswith("-"):
            return self.colors.fg(curses.COLOR_RED)
        if l.startswith("@@"):
            return self.cyan()
        return 0

    def export_rc(self):
        """x : écrit <nom>.nethackrc à côté du projet."""
        h = self.hero()
        if not h:
            return
        g = self.game()
        role, race = self.role_of(h), self.race_of(h)
        if not role or not race:
            return
        base = P.export_path(os.path.dirname(self.project), h)
        path = base[:-len(P.HERO_SUFFIX)] + ".nethackrc"
        try:
            path = os.path.expanduser(self.input_line(
                _("Écrire les options du héros dans"), path,
                _("à recopier dans ~/.nethackrc, ou NETHACKOPTIONS=@fichier")))
        except Cancel:
            return
        if os.path.exists(path) and not self.confirm(
                _("Remplacer %s ?") % path):
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(D.nethackrc(h, role, race, g.names, self.theme))
        self.msg = _("Options écrites : %s") % path

    # --- sources ------------------------------------------------------------

    def check_src(self):
        err = I.check_tree(self.src)
        if err:
            self.message_box(_("Sources introuvables"), [
                err, _("Indiquez-les avec --src ou NHHEROEDIT_SRC.")])
            return False
        return True

    def integrate(self):
        if not self.check_src():
            return
        g = self.game()
        others = self.other_projects()
        kept = [k for k, (_p, m) in others.items()
                if m and not self.mod(k)]
        keep = True
        if kept:
            try:
                keep = self.menu(
                    _("Rôles intégrés par d'autres projets"), [
                        (_("Les garder"), ", ".join(
                            "%s (%s)" % (self.role_label(k), os.path.basename(
                                others[k][0])) for k in kept)),
                        (_("Les retirer des sources"),
                         _("seuls les rôles de ce projet restent"))],
                    filterable=False) == 0
            except Cancel:
                return
        mods, origins = self.merged_roles(others, keep)
        errs = []
        for k, mod in sorted(mods.items()):
            role = g.role(k)
            if role:
                errs += ["%s : %s" % (role["name"][0], m)
                         for gr, m in D.role_problems(role, g.races[0], mod,
                                                      g.objects)
                         if gr == "erreur"]
        if errs:
            self.message_box(_("Intégration impossible"), [
                _("Erreurs à corriger dans les rôles :")] +
                ["  ✖ " + e for e in errs[:15]])
            return
        try:
            files = I.plan(self.src, mods, g, origins)
        except (I.InstallError, ValueError) as e:
            self.message_box(_("Intégration impossible"), [str(e)])
            return
        if not I.changed_files(self.src, files):
            self.msg = _("Les sources sont déjà à jour")
            return
        err = I.check_po(self.src, files)
        if err:
            self.message_box(_("Traductions refusées par msgfmt"),
                             err.split("\n")[-12:])
            return
        self.viewer(_("Changements prévus (q pour continuer)"),
                    [(l, self.diff_attr(l))
                     for l in I.diff(self.src, files).split("\n")])
        names = ", ".join(self.role_label(k) for k in sorted(self.roles)
                          if self.roles[k] and g.role(k)) or \
            _("aucun (retour au jeu d'origine)")
        notes = []
        for label, ks in (
                (_("Gardés (autres projets) : %s"),
                 [k for k in mods if k not in self.roles or
                  not self.roles[k]]),
                (_("Remplacés par ce projet : %s"),
                 [k for k in others if self.mod(k)]),
                (_("Retirés des sources : %s"),
                 [k for k in others if k not in mods])):
            if ks:
                notes.append(label % ", ".join(self.role_label(k)
                                               for k in sorted(ks)))
        if not self.confirm(_("Écrire dans les sources (%s) ?\n\nRôles "
                              "modifiés : %s\n%s\nLes fichiers sont d'abord "
                              "copiés dans sauvegardes/.") % (
                                  self.src, names, "".join(
                                      n + "\n" for n in notes))):
            return
        ch, _bk = I.apply(self.src, files, BACKUP_DIR)
        self._state = (None, None)
        if self.modified:
            self.save()
        self.msg = _("Intégré : %d fichier(s) — m pour compiler") % len(ch)
        names, _d = G.build_interfaces(self.src)
        if names and not set(names) & set(G.GRAPHIC) and \
                any(I.TILES == rel for rel in ch):
            self.msg += _(" (tuiles : le jeu compilé n'a ni X11 ni Qt, "
                          "qui seuls les affichent)")
        self.offer_commit(ch, I.commit_message(g, mods))

    def offer_commit(self, changed, message):
        if not changed or not I.is_git_repo(self.src):
            return
        try:
            message = self.input_line(
                _("Commit dans les sources ? (Échap : non)"), message,
                _("message du commit des %d fichier(s) modifié(s)")
                % len(changed)).strip()
        except Cancel:
            return
        if not message:
            return
        ok, out = I.git_commit(self.src, changed, message)
        if ok:
            self.msg = _("Commit créé dans les sources : %s") % \
                out.split("\n")[0]
        else:
            self.message_box(_("Commit impossible"), out.split("\n")[-12:])

    def sources_menu(self):
        try:
            i = self.menu(_("Retirer des sources"), [
                (_("Retirer les modifications de l'éditeur"),
                 _("rend les fichiers d'origine")),
                (_("Rétablir une sauvegarde…"),
                 _("fichiers de sauvegardes/"))], filterable=False)
        except Cancel:
            return
        if i == 0:
            self.remove()
        else:
            self.restore_backup()

    def remove(self):
        if not self.check_src():
            return
        g = self.game()
        others = {k: v for k, v in self.other_projects().items() if v[1]}
        mods, origins = {}, {}
        if others:
            try:
                if self.menu(_("Rôles intégrés par d'autres projets"), [
                        (_("Retirer seulement ceux de ce projet"),
                         _("garder : %s") % ", ".join(
                             self.role_label(k) for k in others)),
                        (_("Tout retirer"), _("rend les fichiers d'origine"))],
                        filterable=False) == 0:
                    mods = {k: m for k, (_p, m) in others.items()}
                    origins = {k: p for k, (p, _m) in others.items()}
            except Cancel:
                return
        try:
            files = I.plan(self.src, mods, g, origins)
        except (I.InstallError, ValueError) as e:
            self.message_box(_("Retrait impossible"), [str(e)])
            return
        if not I.changed_files(self.src, files):
            self.msg = _("Aucune modification de l'éditeur dans les "
                         "sources")
            return
        gone = sorted(I.installed_roles(self.src, g) - set(mods))
        if not self.confirm(_("Retirer des sources les modifications de "
                              "l'éditeur ?\n%s") % (", ".join(
                                  self.role_label(k) for k in gone) or
                                  _("(textes de l'éditeur seulement)"))):
            return
        ch, _bk = I.apply(self.src, files, BACKUP_DIR)
        self._state = (None, None)
        self.msg = _("Retiré de %d fichier(s)") % len(ch)
        self.offer_commit(ch, I.commit_message(g, mods))

    def restore_backup(self):
        if not self.check_src():
            return
        backups = I.list_backups(BACKUP_DIR)
        if not backups:
            self.msg = _("Aucune sauvegarde dans %s") % BACKUP_DIR
            return
        items = []
        for d, files in backups:
            n = os.path.basename(d)
            when = "%s/%s/%s %s:%s:%s" % (n[6:8], n[4:6], n[:4], n[9:11],
                                          n[11:13], n[13:15]) \
                if re.match(r"\d{8}-\d{6}$", n) else n
            items.append((when, _("%d fichier(s)") % len(files)))
        try:
            i = self.menu(_("Rétablir une sauvegarde"), items,
                          filterable=False)
        except Cancel:
            return
        files = I.restore_plan(self.src, backups[i][0])
        if not files:
            self.msg = _("Les sources sont déjà dans cet état")
            return
        self.viewer(_("Changements du rétablissement (q pour continuer)"),
                    [(l, self.diff_attr(l))
                     for l in I.diff(self.src, files).split("\n")])
        if not self.confirm(_("Rétablir dans les sources ?\n\n%s\n\nL'état "
                              "actuel est d'abord copié dans sauvegardes/.")
                            % "\n".join("  " + r for r in files)):
            return
        ch, _bk = I.apply(self.src, files, BACKUP_DIR)
        self.reload_game()
        self.msg = _("Sauvegarde du %s rétablie : %d fichier(s)") % (
            items[i][0], len(ch))

    def run_external(self, title, cmd, cwd):
        """Lance une commande hors de curses, la sortie dans le terminal."""
        curses.def_prog_mode()
        curses.endwin()
        print("\033[1;35m== nhheroedit : %s ==\033[0m" % title)
        print("$ %s\n" % cmd)
        t = time.time()
        try:
            rc = subprocess.call(cmd, shell=True, cwd=cwd)
        except KeyboardInterrupt:
            rc = -1
        color = "32" if rc == 0 else "31"
        print(_("\n\033[1;%sm== terminé (code %d, %.0f s) ==\033[0m")
              % (color, rc, time.time() - t))
        try:
            input(_("Entrée pour revenir à l'éditeur… "))
        except (EOFError, KeyboardInterrupt):
            pass
        curses.reset_prog_mode()
        self.stdscr.clear()
        curses.curs_set(0)
        enable_mouse()
        return rc

    def make(self):
        if not self.check_src():
            return
        if not os.path.isfile(os.path.join(self.src, "Makefile")):
            self.message_box(_("Sources non configurées"), [
                _("Pas de Makefile : configurez d'abord les sources :"),
                "  cd sys/unix && sh setup.sh hints/linux.500"])
            return
        rc = self.run_external(_("compilation"), G.make_command(
            self.src, "", self.config.get("make", "")), self.src)
        self.msg = _("Compilation réussie — U pour mettre à jour le jeu") \
            if rc == 0 else _("La compilation a échoué (code %d)") % rc

    def make_update(self):
        if not self.check_src():
            return
        if not self.confirm(
                _("Mettre à jour le jeu installé (make update) ?\n\n"
                  "sysconf, scores et dossier save sont conservés ;\n"
                  "le jeu précédent est gardé en nethack.old.")):
            return
        rc = self.run_external(_("mise à jour du jeu"), G.make_command(
            self.src, "update", self.config.get("make", "")), self.src)
        self.msg = _("Jeu mis à jour — j pour jouer") if rc == 0 \
            else _("make update a échoué (code %d)") % rc

    # --- souris et boucle -----------------------------------------------------

    def mouse(self, ev):
        for zone, (y, x, h, w) in self.areas.items():
            if y < ev.y < y + h - 1 and x < ev.x < x + w - 1:
                break
        else:
            return
        if not self.heroes:
            return
        row = ev.y - y - 1
        if zone == "list":
            self.focus = "list"
            if wheel(ev):
                self.cur = max(0, min(len(self.heroes) - 1,
                                      self.cur + 3 * wheel(ev)))
            elif ev.kind in ("click", "double") and \
                    self.list_top + row < len(self.heroes):
                self.cur = self.list_top + row
                if ev.kind == "double":
                    self.focus = "form"
        else:
            self.focus = "form"
            fs = self.fields()
            if wheel(ev):
                for _i in range(3):
                    self.move_field(wheel(ev))
            elif ev.kind in ("click", "double"):
                i = self.form_top + row
                if i < len(fs) and fs[i][0] != "section":
                    self.field = i
                    if ev.kind == "double":
                        self.edit_field()

    def quit(self):
        if not self.modified:
            return True
        try:
            i = self.menu(_("Projet modifié"), [
                (_("Enregistrer et quitter"), ""),
                (_("Quitter sans enregistrer"), ""),
                (_("Annuler"), "")], filterable=False)
        except Cancel:
            return False
        if i == 0:
            self.save()
            return True
        return i == 1

    def run(self):
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(5000)
        enable_mouse()
        if self.check_src():
            try:
                self.game()
            except (OSError, ValueError) as e:
                self.message_box(_("Sources illisibles"), [str(e)])
                return
        else:
            return
        self.draw()
        self.offer_autosave()
        actions = {
            "?": lambda: self.viewer(_("Aide"), HELP),
            "s": self.save, "u": self.undo,
            "\x12": lambda: self.undo(redo=True),
            "\x19": lambda: self.undo(redo=True),
            "n": self.new_hero, "d": self.duplicate, "/": self.goto_hero,
            "N": self.random_name,
            "k": self.kit_key, "t": lambda: self.hero() and self.edit_tile(),
            "T": self.cycle_theme, "p": self.project_menu,
            "v": self.show_validation, "c": self.show_code,
            "x": self.export_rc, "I": self.integrate,
            "R": self.sources_menu, "m": self.make, "U": self.make_update,
            "j": self.play, "h": self.show_history,
        }
        while True:
            self.autosave()
            self.draw()
            k = get_key(self.stdscr, idle=True)
            if k is None or k == curses.KEY_RESIZE:
                continue
            self.msg = ""
            if isinstance(k, Mouse):
                self.mouse(k)
            elif k == "q":
                if self.quit():
                    P.drop_autosave(self.project)
                    return
            elif k in actions:
                actions[k]()
            elif k == "\t":
                if self.heroes:
                    self.focus = "form" if self.focus == "list" else "list"
            elif self.focus == "list":
                self.key_list(k)
            else:
                self.key_form(k)

    def key_list(self, k):
        n = len(self.heroes)
        if not n:
            return
        if k == curses.KEY_UP:
            self.cur = max(0, self.cur - 1)
        elif k == curses.KEY_DOWN:
            self.cur = min(n - 1, self.cur + 1)
        elif k == curses.KEY_HOME:
            self.cur = 0
        elif k == curses.KEY_END:
            self.cur = n - 1
        elif is_enter(k) or k == curses.KEY_RIGHT:
            self.focus = "form"
        elif k in (curses.KEY_DC, "X"):
            self.delete()
        elif k == "<":
            self.move_hero(-1)
        elif k == ">":
            self.move_hero(1)

    def key_form(self, k):
        if not self.heroes:
            return
        if k == curses.KEY_UP:
            self.move_field(-1)
        elif k == curses.KEY_DOWN:
            self.move_field(1)
        elif k == curses.KEY_PPAGE:
            for _i in range(10):
                self.move_field(-1)
        elif k == curses.KEY_NPAGE:
            for _i in range(10):
                self.move_field(1)
        elif k == curses.KEY_HOME:
            self.field = 1
        elif k == curses.KEY_END:
            self.field = len(self.fields()) - 1
        elif k in (curses.KEY_LEFT, "-"):
            self.adjust(-1)
        elif k in (curses.KEY_RIGHT, "+", "="):
            self.adjust(1)
        elif is_enter(k) or k == " ":
            self.edit_field()
        elif k in (curses.KEY_DC, curses.KEY_BACKSPACE, "\x7f"):
            self.clear_field()
        elif k == ESC:
            self.focus = "list"


def parse_args(argv, config=None):
    """(projet, sources) : ligne de commande, puis NHHEROEDIT_SRC, puis
    la configuration, puis les valeurs par défaut."""
    config = config or {}
    project = config.get("project", DEFAULT_PROJECT)
    src = os.environ.get("NHHEROEDIT_SRC") or config.get("src", DEFAULT_SRC)
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in ("-h", "--help"):
            print(_(__doc__.strip()))
            sys.exit(0)
        elif a == "--src" and args:
            src = args.pop(0)
        elif a.startswith("--src="):
            src = a.split("=", 1)[1]
        elif a.startswith("-"):
            sys.exit(_("Option inconnue : %s (voir --help)") % a)
        else:
            project = a
    return os.path.abspath(project), os.path.abspath(src)


def main(argv=None):
    config, errs = C.load(C.default_path())
    project, src = parse_args(sys.argv[1:] if argv is None else argv,
                              config)
    os.environ.setdefault("ESCDELAY", "25")
    if "mouse" in config:
        os.environ.setdefault("NHHEROEDIT_MOUSE", "1" if config["mouse"]
                              else "0")
    import locale
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(lambda scr: Editor(scr, project, src, config,
                                      errs).run())


if __name__ == "__main__":
    main()
