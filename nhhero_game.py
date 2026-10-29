"""Jouer avec un héros : NetHack lancé avec les options du héros (nom,
rôle, race, sexe, alignement, animal, fruit, conduites), en partie
normale, en mode découverte ou en mode wizard ; historique de ses
parties (xlogfile du jeu).

Mixin de l'éditeur : self.config, self.src, self.hero(), self.game(),
self.msg, self.menu(), self.confirm(), self.message_box() et
self.run_external() sont fournis par nhheroedit.Editor.
"""

import glob
import os
import pwd
import re
import shlex

import curses

import nhhero_data as D
import nhhero_install as I
from nhhero_i18n import _
from nhhero_ui import Cancel

DEFAULT_HACKDIR = os.path.expanduser("~/nh/install/games/lib/nethackdir")

# interfaces du jeu : (nom, variable WANT_WIN_<…> de make, objet compilé)
INTERFACES = [("tty", "TTY", "wintty.o"), ("curses", "CURSES", "cursmain.o"),
              ("X11", "X11", "winX.o"), ("Qt", "QT", "qt_main.o")]
GRAPHIC = ("X11", "Qt")          # les seules qui affichent les tuiles


def build_interfaces(src):
    """(interfaces, interface par défaut) du dernier build des sources,
    d'après dat/options (écrit par makedefs à chaque compilation), sinon
    d'après les fichiers objets ; ([], None) si rien n'est compilé."""
    try:
        with open(os.path.join(src, "dat", "options"),
                  encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    mo = re.search(r"Supported windowing systems?:\n\s*\n(.*?)\n\s*\n", text,
                   re.S)
    if mo:
        quoted = re.findall(r'"([^"]+)"', mo.group(1))
        names = [n for n, _w, _o in INTERFACES if n in quoted]
        dm = re.search(r'default of "([^"]+)"', mo.group(1))
        if names:
            return names, dm.group(1) if dm else names[0]
    names = [n for n, _w, o in INTERFACES
             if os.path.isfile(os.path.join(src, "src", o))]
    return names, names[0] if names else None


def make_flags(src):
    """Variables de make qui refont le jeu avec les mêmes interfaces que
    le dernier build : sans elles, « make » ne fait qu'un jeu tty, sans
    les tuiles des versions X11 et Qt."""
    names, default = build_interfaces(src)
    flags = ["WANT_WIN_%s=1" % w for n, w, _o in INTERFACES if n in names]
    if names and default != names[0]:
        flags.append("WANT_DEFAULT=%s" % default)
    return flags


def make_command(src, target="", opts=""):
    """Commande make : opts (configuration) ou -jN, plus les interfaces
    du dernier build si opts n'en choisit pas. Pour « update », seules
    les variables WANT_… sont gardées (pas de compilation parallèle)."""
    if target == "update":
        opts = " ".join(o for o in opts.split() if o.startswith("WANT_"))
    else:
        opts = opts or "-j%d" % (os.cpu_count() or 2)
    if "WANT_" not in opts:
        opts = " ".join([opts] + make_flags(src))
    return " ".join(x for x in ("make", target, opts.strip()) if x)


def game_env(hackdir, options):
    """Variables d'environnement du jeu. Une valeur de NETHACKOPTIONS
    qui désigne un fichier (« @… », « /… ») remplace le .nethackrc : elle
    est gardée, et les options du héros passent alors par la ligne de
    commande seulement. Renvoie (env, options passées)."""
    env = {"HACKDIR": hackdir}
    old = os.environ.get("NETHACKOPTIONS", "")
    if old.startswith(("/", "@")):
        return env, False
    env["NETHACKOPTIONS"] = ",".join(([old] if old else []) + options)
    return env, True


def game_command(hackdir, h, role, race, mode=""):
    """Commande shell qui lance le jeu avec le héros. mode : "" (partie
    normale), "-X" (découverte) ou "-D" (wizard)."""
    env, full = game_env(hackdir, D.hero_options(h, role, race))
    args = ["-u", h["name"]] if mode != "-D" else []
    if not full:
        args += ["-p", role["filecode"], "-r", race["filecode"]]
    if mode:
        args.append(mode)
    return "cd %s && %s %s %s" % (
        shlex.quote(hackdir),
        " ".join("%s=%s" % (k, shlex.quote(v)) for k, v in env.items()),
        shlex.quote(os.path.join(hackdir, "nethack")),
        " ".join(shlex.quote(a) for a in args))


def saved_game(hackdir, name):
    """Fichier de partie sauvegardée du héros, ou None."""
    pat = os.path.join(hackdir, "save", "%d%s*" % (os.getuid(),
                                                    glob.escape(name)))
    found = glob.glob(pat)
    return found[0] if found else None


def sysconf(hackdir):
    """{CLÉ: valeur} du sysconf du jeu ({} s'il n'y en a pas)."""
    out = {}
    try:
        with open(os.path.join(hackdir, "sysconf"), encoding="utf-8",
                  errors="replace") as f:
            for line in f:
                mo = re.match(r"^\s*([A-Z_]+)\s*=\s*(.*?)\s*$", line)
                if mo:
                    out[mo.group(1)] = mo.group(2)
    except OSError:
        pass
    return out


def mode_allowed(hackdir, mode, name):
    """(permis ?, liste du sysconf) pour le mode -D (WIZARDS) ou -X
    (EXPLORERS), comme check_user_string() du jeu : « * » pour tous,
    sinon le compte Unix, ou le nom du héros avec CHECK_PLNAME=1. permis
    vaut None quand le jeu n'a pas de sysconf."""
    conf = sysconf(hackdir)
    if not conf:
        return None, ""
    who = conf.get({"-D": "WIZARDS", "-X": "EXPLORERS"}[mode], "")
    if who.startswith("*"):
        return True, who
    if conf.get("CHECK_PLNAME") == "1":
        user = name
    else:
        try:
            user = pwd.getpwuid(os.getuid()).pw_name
        except KeyError:
            return None, who
    return user in who.split(), who


# --- historique des parties (xlogfile) ------------------------------------

# conduites tenues (champ conductX)
CONDUCT_NAMES = {
    "foodless": _("sans manger"), "vegan": _("végétalien"),
    "vegetarian": _("végétarien"), "atheist": _("athée"),
    "weaponless": _("sans arme"), "pacifist": _("pacifiste"),
    "illiterate": _("illettré"), "polyless": _("sans polymorphie d'objet"),
    "polyselfless": _("sans se polymorpher"), "wishless": _("sans vœu"),
    "artiwishless": _("sans vœu d'artefact"),
    "genocideless": _("sans génocide"), "elberethless": _("sans Elbereth"),
    "sokoban": _("Sokoban sans tricher"), "blind": _("aveugle"),
    "nudist": _("nudiste"), "bonesless": _("sans bones"),
    "petless": _("sans animal"), "unrerolled": _("sans relance"),
}
# fins sans tueur : (masculin, féminin)
SIMPLE_ENDS = {
    "quit": (_("a abandonné"), _("a abandonné")),
    "escaped": (_("s'est échappé"), _("s'est échappée")),
    "ascended": (_("est monté au ciel"), _("est montée au ciel")),
}


def read_xlog(hackdir):
    """Parties terminées du jeu, dans l'ordre : liste de dicts (champs du
    xlogfile, « points » et « flags » en entiers)."""
    try:
        with open(os.path.join(hackdir, "xlogfile"), encoding="utf-8",
                  errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        rec = dict(c.split("=", 1) for c in line.split("\t") if "=" in c)
        try:
            rec["points"] = int(rec["points"])
            rec["flags"] = int(rec.get("flags", "0"), 0)
        except (KeyError, ValueError):
            continue
        out.append(rec)
    return out


def hero_games(records, name, uid=None):
    """Parties du héros name (même compte Unix)."""
    uid = str(os.getuid() if uid is None else uid)
    return [r for r in records
            if r.get("name") == name and r.get("uid", uid) == uid]


def game_mode(rec):
    """"" pour une partie normale, sinon « wizard » ou « découverte »."""
    return "wizard" if rec["flags"] & 1 else \
        _("découverte") if rec["flags"] & 2 else ""


def _int(rec, key):
    try:
        return int(rec.get(key, ""))
    except ValueError:
        return None


def games_summary(games):
    """Résumé : nombre, record (parties normales), profondeur maximale,
    victoires."""
    normal = [g for g in games if not game_mode(g)]
    return {"count": len(games),
            "best": max([g["points"] for g in normal], default=None),
            "maxlvl": max([_int(g, "maxlvl") or 0 for g in games],
                          default=0),
            "ascended": sum(g.get("death") == "ascended" for g in games)}


def _tr(names, theme, msgid, *ctxs):
    """Traduction de msgid (premier contexte qui en a une), ou None."""
    for ctx in ctxs:
        for table in ((names.cyber, names.fr) if theme == "cyber"
                      else (names.fr,)):
            v = table.get((ctx, msgid))
            if v and v not in ("m", "f"):
                return v
    return None


def killer_text(names, theme, killer):
    """« a kobold » → « un kobold » avec le catalogue du jeu."""
    v = _tr(names, theme, killer, "killer")
    if v:
        return v
    mo = re.match(r"^(a|an|the) (.+)$", killer)
    if not mo:
        return _tr(names, theme, killer, "monster") or killer
    art, noun = mo.groups()
    mon = _tr(names, theme, noun, "monster")
    if not mon:
        return killer
    gender = [t.get(("gender", noun)) for t in
              ((names.cyber, names.fr) if theme == "cyber" else (names.fr,))]
    fem = next((x for x in gender if x), None) == "f"
    if art != "the":
        return ("une " if fem else "un ") + mon
    if mon[:1].lower() in "aâàeéèêiîïoôuûyh":
        return "l'" + mon
    return ("la " if fem else "le ") + mon


def death_text(rec, names, theme="cyber"):
    """Fin de la partie, dans la langue du jeu (« tuée par un kobold »)."""
    death = rec.get("death", "?")
    if theme == "en":
        return death
    fem = rec.get("gender") == "Fem"
    if death in SIMPLE_ENDS:
        return SIMPLE_ENDS[death][fem]
    v = _tr(names, theme, death, *(("feminine", None) if fem else (None,)))
    if v:
        return v
    prefixes = sorted({m for c, m in names.fr if c == "killed by"},
                      key=len, reverse=True)
    for p in prefixes:
        if death.startswith(p):
            head = _tr(names, theme, p, *(("feminine killed by",
                                           "killed by") if fem
                                          else ("killed by",)))
            return (head or p) + killer_text(names, theme, death[len(p):])
    return death


class Game:
    def hackdir(self):
        """Dossier du jeu installé : NHHEROEDIT_HACKDIR, configuration,
        ~/nh/install/…, puis playground des sources."""
        for d in (os.environ.get("NHHEROEDIT_HACKDIR", ""),
                  self.config.get("hackdir", ""), DEFAULT_HACKDIR,
                  os.path.join(self.src, "playground")):
            if d and os.access(os.path.join(d, "nethack"), os.X_OK):
                return d
        return None

    def games(self, name):
        """Parties du héros name (xlogfile relu quand il change)."""
        d = self.hackdir()
        if not d:
            return []
        try:
            mt = os.path.getmtime(os.path.join(d, "xlogfile"))
        except OSError:
            return []
        cache = getattr(self, "_xlog", None)
        if not cache or cache[0] != (d, mt):
            self._xlog = cache = ((d, mt), read_xlog(d))
        return hero_games(cache[1], name)

    def show_history(self):
        """h : historique des parties du héros."""
        h = self.hero()
        if not h:
            return
        games = self.games(h["name"])
        if not games:
            self.message_box(_("Historique de %s") % h["name"], [
                _("Aucune partie terminée sous ce nom dans le xlogfile du "
                  "jeu."), _("(les parties sauvegardées n'y sont pas)")])
            return
        s = games_summary(games)
        names = self.game().names
        lines = [(_("%d partie(s) — record %s — niveau le plus profond %d"
                    " — victoires %d") % (
                        s["count"], s["best"] if s["best"] is not None
                        else "—", s["maxlvl"], s["ascended"]),
                  curses.A_BOLD), ""]
        for g in reversed(games):
            date = g.get("deathdate", "")
            date = "%s-%s-%s" % (date[:4], date[4:6], date[6:]) \
                if len(date) == 8 else date or "?"
            mode = game_mode(g)
            lines.append(("%s  %7d pts  niv. %-2s  %s%s" % (
                date, g["points"], g.get("deathlev", "?"),
                death_text(g, names, self.theme),
                "  [%s]" % mode if mode else ""),
                curses.A_DIM if mode else 0))
            details = [_("%s tours") % g.get("turns", "?"),
                       _("profondeur max %s") % g.get("maxlvl", "?")]
            kept = [CONDUCT_NAMES.get(c, c)
                    for c in g.get("conductX", "").split(",") if c]
            if kept:
                details.append(_("conduites : %s") % ", ".join(kept))
            lines.append(("            " + " · ".join(details),
                          curses.A_DIM))
        self.viewer(_("Historique de %s") % h["name"], lines)

    def outdated_game(self, hackdir):
        """Le jeu installé est-il plus ancien que les sources touchées ?"""
        exe = os.path.getmtime(os.path.join(hackdir, "nethack"))
        for rel in I.ALL_FILES:
            p = os.path.join(self.src, rel)
            if os.path.isfile(p) and os.path.getmtime(p) > exe:
                return True
        return False

    def play(self):
        """j : jouer avec le héros choisi."""
        h = self.hero()
        if not h:
            return
        d = self.hackdir()
        if not d:
            self.message_box(_("Jeu introuvable"), [
                _("Pas d'exécutable nethack installé. Compilez (m) puis"),
                _("mettez à jour le jeu (U), ou indiquez son dossier avec"),
                "NHHEROEDIT_HACKDIR."])
            return
        g = self.game()
        role, race = g.role(h["role"]), g.race(h["race"])
        errs = [m for gr, m in D.validate(h, role, race, {}, g.objects)
                if gr == "erreur"]
        if errs:
            self.message_box(_("Héros incomplet"), [_("À corriger avant "
                             "de jouer :")] + ["  ✖ " + e for e in errs])
            return
        try:
            mode = ["", "-X", "-D"][self.menu(
                _("Jouer avec %s") % h["name"], [
                    (_("Partie normale"), _("scores et sauvegarde")),
                    (_("Mode découverte"), _("-X : sans mourir, sans "
                                             "score")),
                    (_("Mode wizard"), _("-D : commandes de test (^W "
                                         "souhait, ^F carte…)"))],
                filterable=False)]
        except Cancel:
            return
        lines = []
        if self.outdated_game(d):
            lines += [_("⚠ Le jeu installé est plus ancien que les sources"
                        " :"),
                      _("  intégrez (I), compilez (m) et mettez à jour (U)"
                        " pour"),
                      _("  jouer avec les rôles modifiés."), ""]
        if mode:
            ok, who = mode_allowed(d, mode, h["name"])
            if ok is False and mode == "-D":
                lines += [_("⚠ sysconf réserve le mode wizard à : %s") %
                          (who or _("personne")),
                          _("  le jeu passera en mode découverte (ajoutez "
                            "votre compte à WIZARDS)."), ""]
            elif ok is False:
                lines += [_("⚠ sysconf réserve le mode découverte à : %s")
                          % (who or _("personne")),
                          _("  le jeu partira en partie normale."), ""]
        save_name = "wizard" if mode == "-D" else h["name"]
        if saved_game(d, save_name):
            lines += [_("⚠ Une partie sauvegardée de « %s » existe : le jeu"
                        " la") % save_name,
                      _("  reprendra, sans tenir compte des options du "
                        "héros."), ""]
        if mode == "-D":
            lines += [_("En mode wizard, le jeu nomme toujours le héros "
                        "« wizard » :"),
                      _("sa partie reste ainsi à part de celle de « %s ». "
                        "Rôle, race,") % h["name"],
                      _("sexe, alignement et règles du rôle sont bien ceux "
                        "du héros."), ""]
        _env, full = game_env(d, [])
        if not full:
            lines += [_("NETHACKOPTIONS désigne un fichier : seuls le nom, "
                        "le rôle"),
                      _("et la race sont transmis (ligne de commande)."), ""]
        lines += ["  " + o for o in D.hero_options(h, role, race)]
        lines += ["", _("Lancer NetHack maintenant ?")]
        if not self.confirm("\n".join(lines), _("Jouer")):
            return
        rc = self.run_external(_("NetHack — %s") % h["name"],
                               game_command(d, h, role, race, mode), d)
        self.msg = _("Retour de NetHack (code %d)") % rc
