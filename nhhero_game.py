"""Jouer avec un héros : NetHack lancé avec les options du héros (nom,
rôle, race, sexe, alignement, animal, fruit, conduites), en partie
normale, en mode découverte ou en mode wizard.

Mixin de l'éditeur : self.config, self.src, self.hero(), self.game(),
self.msg, self.menu(), self.confirm(), self.message_box() et
self.run_external() sont fournis par nhheroedit.Editor.
"""

import glob
import os
import pwd
import re
import shlex

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
