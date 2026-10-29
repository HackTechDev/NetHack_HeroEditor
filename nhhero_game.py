"""Jouer avec un héros : NetHack lancé avec les options du héros (nom,
rôle, race, sexe, alignement, animal, fruit, conduites), en partie
normale, en mode découverte ou en mode wizard.

Mixin de l'éditeur : self.config, self.src, self.hero(), self.game(),
self.msg, self.menu(), self.confirm(), self.message_box() et
self.run_external() sont fournis par nhheroedit.Editor.
"""

import glob
import os
import shlex

import nhhero_data as D
import nhhero_install as I
from nhhero_i18n import _
from nhhero_ui import Cancel

DEFAULT_HACKDIR = os.path.expanduser("~/nh/install/games/lib/nethackdir")


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
        for rel in (I.ROLE_C, I.U_INIT_C):
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
        if mode != "-D" and saved_game(d, h["name"]):
            lines += [_("⚠ Une partie sauvegardée de « %s » existe : le jeu"
                        " la") % h["name"],
                      _("  reprendra, sans tenir compte des options du "
                        "héros."), ""]
        if mode == "-D":
            lines += [_("En mode wizard, le jeu prend le nom « wizard » "
                        "(sysconf WIZARDS)."), ""]
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
