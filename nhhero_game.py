"""Jouer avec un héros : NetHack lancé avec les options du héros (nom,
rôle, race, sexe, alignement, animal, fruit, conduites), en partie
normale, en mode découverte ou en mode wizard, dans un panneau tmux à
côté de l'éditeur quand c'est possible ; historique de ses parties
(xlogfile du jeu).

Mixin de l'éditeur : self.config, self.src, self.hero(), self.game(),
self.msg, self.menu(), self.confirm(), self.message_box() et
self.run_external() sont fournis par nhheroedit.Editor.
"""

import glob
import os
import pwd
import re
import shlex
import shutil
import subprocess
import time

import curses

import nhhero_data as D
import nhhero_install as I
from nhhero_i18n import _
from nhhero_ui import Cancel

DEFAULT_HACKDIR = os.path.expanduser("~/nh/install/games/lib/nethackdir")
# parties sauvegardées mises de côté : parties/<nom>/<date>/<fichier>
ASIDE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "parties")
# extensions possibles d'une sauvegarde compressée (COMPRESS_EXTENSION)
SAVE_EXTENSIONS = ("", ".gz", ".Z", ".bz2", ".xz", ".zst")

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


def tmux(*args):
    """Commande tmux ; sa sortie, ou None en cas d'échec."""
    try:
        r = subprocess.run(["tmux"] + list(args), capture_output=True,
                           text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


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


def user_rc():
    """(chemin, texte, options en plus) de la configuration du joueur :
    le fichier désigné par NETHACKOPTIONS (« @… », « /… »), sinon
    ~/.nethackrc et les options de NETHACKOPTIONS."""
    env = os.environ.get("NETHACKOPTIONS", "")
    extra = ""
    if env.startswith("@"):
        path = env[1:]
    elif env.startswith("/"):
        path = env
    else:
        path, extra = os.path.expanduser("~/.nethackrc"), env
    try:
        with open(os.path.expanduser(path), encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
    except OSError:
        text = ""
    return path, text, extra


def write_full_rc(path, h, role, race, names, theme="cyber"):
    """Écrit le fichier d'options complet du héros dans path."""
    src, text, extra = user_rc()
    home = os.path.expanduser("~")
    src = "~" + src[len(home):] if src.startswith(home + os.sep) else src
    data = D.full_rc(text, h, role, race, names, theme, extra, src)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def play_rc_path(name):
    """Fichier d'options complet écrit pour j (dossier temporaire)."""
    import tempfile
    return os.path.join(tempfile.gettempdir(), "nhheroedit-%d-%s.nethackrc"
                        % (os.getuid(), re.sub(r"[^A-Za-z0-9_]", "_", name)))


def game_command(hackdir, h, role, race, mode="", rc=None):
    """Commande shell qui lance le jeu avec le héros. mode : "" (partie
    normale), "-X" (découverte) ou "-D" (wizard). rc : fichier d'options
    complet (NETHACKOPTIONS=@rc) ; sans lui, les options du héros
    s'ajoutent à NETHACKOPTIONS."""
    if rc:
        env, full = {"HACKDIR": hackdir, "NETHACKOPTIONS": "@" + rc}, True
    else:
        env, full = game_env(hackdir, D.hero_options(h, role, race) +
                             D.display_options(h))
    args = ["-u", h["name"]] if mode != "-D" else []
    if h["windowtype"]:
        args.insert(0, "-w" + h["windowtype"])
    if not full:
        args += ["-p", role["filecode"], "-r", race["filecode"]]
    if mode:
        args.append(mode)
    return "cd %s && %s %s %s" % (
        shlex.quote(hackdir),
        " ".join("%s=%s" % (k, shlex.quote(v)) for k, v in env.items()),
        shlex.quote(os.path.join(hackdir, "nethack")),
        " ".join(shlex.quote(a) for a in args))


FALLBACK_SYMSETS = ["DECgraphics", "IBMgraphics", "curses", "Enhanced1",
                    "plain"]


def symsets(hackdir):
    """Jeux de symboles du fichier symbols du jeu (sans ceux du niveau
    de Rogue)."""
    try:
        with open(os.path.join(hackdir or "", "symbols"), encoding="utf-8",
                  errors="replace") as f:
            names = re.findall(r"^start:\s*(\S+)", f.read(), re.M)
    except OSError:
        return FALLBACK_SYMSETS
    return [n for n in names if not n.startswith("Rogue") and
            n != "Blank"] or FALLBACK_SYMSETS


def save_base(name):
    """Nom du fichier de sauvegarde : uid puis nom, « . », « / » et
    espaces changés en « _ » (regularize() du jeu)."""
    return "%d%s" % (os.getuid(), re.sub(r"[./ ]", "_", name))


def saved_game(hackdir, name):
    """Fichier de partie sauvegardée du héros, ou None."""
    for ext in SAVE_EXTENSIONS:
        p = os.path.join(hackdir, "save", save_base(name) + ext)
        if os.path.isfile(p):
            return p
    return None


def set_aside(path, name, root=ASIDE_DIR):
    """Range la sauvegarde path dans root/<nom>/<date>/ ; renvoie le
    nouveau chemin."""
    d = os.path.join(root, save_base(name), time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, os.path.basename(path))
    shutil.move(path, dest)
    return dest


def aside_games(name, root=ASIDE_DIR):
    """Parties mises de côté du héros, la plus récente d'abord :
    [(date « AAAAMMJJ-HHMMSS », chemin)]."""
    base = os.path.join(root, save_base(name))
    out = []
    for stamp in sorted(os.listdir(base) if os.path.isdir(base) else [],
                        reverse=True):
        for f in sorted(glob.glob(os.path.join(glob.escape(base), stamp,
                                               "*"))):
            out.append((stamp, f))
    return out


def put_back(path, hackdir):
    """Remet une partie mise de côté dans save/ du jeu (sans écraser une
    sauvegarde) ; renvoie le chemin, ou None si la place est prise."""
    dest = os.path.join(hackdir, "save", os.path.basename(path))
    if os.path.exists(dest):
        return None
    shutil.move(path, dest)
    for empty in (os.path.dirname(path), os.path.dirname(
            os.path.dirname(path))):
        try:
            os.rmdir(empty)
        except OSError:
            break
    return dest


def stamp_text(stamp):
    """« 20261029-191510 » → « 2026-10-29 19:15 »."""
    mo = re.match(r"^(\d{4})(\d\d)(\d\d)-(\d\d)(\d\d)", stamp)
    return "%s-%s-%s %s:%s" % mo.groups() if mo else stamp


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
    game_pane = None
    game_where = ""

    def use_tmux(self):
        """Lancer le jeu dans tmux ? (l'éditeur tourne dans tmux, et la
        configuration ne dit pas non)"""
        return bool(os.environ.get("TMUX")) and bool(shutil.which("tmux")) \
            and self.config.get("tmux", True)

    def game_alive(self):
        """Le panneau du jeu existe-t-il encore ? (il se ferme avec le
        jeu)"""
        if not self.game_pane:
            return False
        if tmux("display-message", "-p", "-t", self.game_pane,
                "#{pane_id}") is None:
            self.game_pane = None
        return bool(self.game_pane)

    def start_in_tmux(self, cmd, name):
        """Lance cmd dans un panneau tmux à droite de l'éditeur (fenêtre
        assez large), sinon dans une fenêtre tmux à part ; le jeu prend la
        main. Renvoie le lieu (texte), ou None en cas d'échec."""
        here = os.environ.get("TMUX_PANE", "")
        width = int(tmux("display-message", "-p", "-t", here,
                         "#{window_width}") or 0)
        if width >= 170:
            pane = tmux("split-window", "-h", "-l", "82", "-t", here, "-P",
                        "-F", "#{pane_id}", cmd)
            where = _("panneau tmux à droite")
        else:
            pane = tmux("new-window", "-n", "nethack-" + name[:12], "-P",
                        "-F", "#{pane_id}", cmd)
            where = _("fenêtre tmux « nethack-%s »") % name[:12]
        if not pane:
            return None
        self.game_pane, self.game_where = pane, where
        return where
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

    def choose_save(self, d, name):
        """Partie sauvegardée de name : la reprendre, la mettre de côté
        ou la supprimer ; sans sauvegarde, en remettre une mise de côté.
        Renvoie True si le jeu reprendra une partie ; lève Cancel."""
        path = saved_game(d, name)
        if path:
            i = self.menu(_("Partie sauvegardée de « %s »") % name, [
                (_("La reprendre"), _("le jeu ignore alors les options "
                                      "du héros")),
                (_("La mettre de côté, nouvelle partie"),
                 _("rangée dans parties/ de l'éditeur, à remettre plus "
                   "tard")),
                (_("La supprimer, nouvelle partie"), _("définitif"))],
                filterable=False)
            if i == 0:
                return True
            if i == 1:
                try:
                    set_aside(path, name)
                except OSError as e:
                    self.message_box(_("Impossible de ranger la partie"),
                                     [str(e)])
                    raise Cancel()
                return False
            if not self.confirm(_("Supprimer définitivement la partie "
                                  "sauvegardée de « %s » ?\n\n%s") % (
                                      name, path), _("Supprimer")):
                raise Cancel()
            os.remove(path)
            return False
        aside = aside_games(name)
        if not aside:
            return False
        i = self.menu(_("Parties de « %s » mises de côté") % name,
                      [(_("Nouvelle partie"), "")] +
                      [(_("Reprendre celle du %s") % stamp_text(s),
                        os.path.basename(p)) for s, p in aside[:9]],
                      filterable=False)
        if i == 0:
            return False
        if not put_back(aside[i - 1][1], d):
            self.message_box(_("Impossible de remettre la partie"), [
                _("Une sauvegarde occupe déjà sa place dans save/.")])
            raise Cancel()
        return True

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
        tmuxed = self.use_tmux()
        if tmuxed and self.game_alive():
            self.msg = _("Une partie est déjà ouverte (%s).") % \
                self.game_where
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
        try:
            resume = self.choose_save(d, save_name)
        except Cancel:
            return
        if resume:
            lines += [_("Le jeu reprend la partie sauvegardée de « %s » :")
                      % save_name,
                      _("  les options du héros ne servent qu'à une "
                        "nouvelle partie."), ""]
        if mode == "-D":
            lines += [_("En mode wizard, le jeu nomme toujours le héros "
                        "« wizard » :"),
                      _("sa partie reste ainsi à part de celle de « %s ». "
                        "Rôle, race,") % h["name"],
                      _("sexe, alignement et règles du rôle sont bien ceux "
                        "du héros."), ""]
        _env, full = game_env(d, [])
        if not full and not rc:
            lines += [_("NETHACKOPTIONS désigne un fichier : seuls le nom, "
                        "le rôle"),
                      _("et la race sont transmis (ligne de commande)."), ""]
        try:
            rc = write_full_rc(play_rc_path(h["name"]), h, role, race,
                               g.names, self.theme)
        except OSError:
            rc = None
        lines += ["  " + o for o in D.hero_options(h, role, race)]
        disp = D.display_options(h)
        if h["windowtype"] or disp:
            lines += ["  " + _("affichage : %s") % ", ".join(
                ([h["windowtype"]] if h["windowtype"] else []) +
                [o for o in disp if not o.startswith("hilite_status")] +
                ([_("%d règles de couleur") % len(D.NIGHTCITY_HILITES)]
                 if h["colors"] else []))]
        if rc:
            lines += ["", _("Options : %s") % rc,
                      _("  (votre configuration, puis celles du héros)")]
        if tmuxed:
            lines += ["", _("Le jeu s'ouvrira dans tmux, à côté de "
                            "l'éditeur.")]
        lines += ["", _("Lancer NetHack maintenant ?")]
        if not self.confirm("\n".join(lines), _("Jouer")):
            return
        cmd = game_command(d, h, role, race, mode, rc)
        if tmuxed:
            where = self.start_in_tmux(cmd, h["name"])
            if where:
                self.msg = _("NetHack lancé (%s) ; l'historique se met à "
                             "jour à la fin de la partie.") % where
                return
        rc = self.run_external(_("NetHack — %s") % h["name"], cmd, d)
        self.msg = _("Retour de NetHack (code %d)") % rc
