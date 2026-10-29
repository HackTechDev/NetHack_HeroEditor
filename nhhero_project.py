"""Fichiers de l'éditeur : projets (héros et rôles modifiés en JSON),
fusion de projets, héros exportés un par un (*.nhhero.json, avec les
modifications de leur rôle), sauvegarde de secours
(projet.json.nhheroedit-autosave)."""

import json
import os

import nhhero_data as D
from nhhero_i18n import _

PROJECT_FORMAT = "nhheroedit"
HERO_FORMAT = "nhheroedit-heros"
HERO_SUFFIX = ".nhhero.json"
AUTOSAVE_SUFFIX = ".nhheroedit-autosave"
AUTOSAVE_DELAY = 60         # secondes


class ProjectError(Exception):
    pass


def write_json(path, data):
    """Écrit le JSON par un fichier temporaire (pas de fichier à moitié
    écrit si l'écriture échoue)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def write_project(path, heroes, roles):
    write_json(path, {"format": PROJECT_FORMAT, "version": 1,
                      "heroes": heroes,
                      "roles": {k: v for k, v in sorted(roles.items())
                                if v}})


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise ProjectError(_("%s illisible : %s") % (path, e))


def read_project(path):
    """(héros, rôles modifiés) d'un projet ou d'un héros exporté."""
    data = _load(path)
    fmt = data.get("format") if isinstance(data, dict) else None
    if fmt == HERO_FORMAT and isinstance(data.get("hero"), dict):
        h = D.normalize(data["hero"])
        mod = D.normalize_mod(data.get("role_changes"))
        return [h], ({h["role"]: mod} if mod else {})
    if fmt != PROJECT_FORMAT:
        raise ProjectError(_("%s n'est pas un projet nhheroedit") % path)
    roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
    return ([D.normalize(h) for h in data.get("heroes", [])],
            {k: D.normalize_mod(v) for k, v in roles.items()
             if D.normalize_mod(v)})


def export_path(directory, h):
    base = "".join(c if c.isalnum() or c in "-_" else "_"
                   for c in (h["name"] or "heros").lower())
    return os.path.join(directory, base + HERO_SUFFIX)


def write_hero(path, h, mod):
    data = {"format": HERO_FORMAT, "version": 1, "hero": h}
    if mod:
        data["role_changes"] = mod
    write_json(path, data)


def autosave_path(project):
    return project + AUTOSAVE_SUFFIX


def pending_autosave(project):
    """Sauvegarde de secours plus récente que le projet (session
    interrompue), ou None ; une sauvegarde périmée est effacée."""
    auto = autosave_path(project)
    if not os.path.isfile(auto):
        return None
    if os.path.isfile(project) and \
            os.path.getmtime(auto) <= os.path.getmtime(project):
        drop_autosave(project)
        return None
    return auto


def drop_autosave(project):
    try:
        os.remove(autosave_path(project))
    except OSError:
        pass


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def json_files(dirs, suffix=".json"):
    """[(nom, dossier)] des fichiers *suffix des dossiers donnés."""
    out, seen = [], set()
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.realpath(os.path.join(d, n))
            if n.endswith(suffix) and os.path.isfile(p) and p not in seen:
                seen.add(p)
                out.append((n, d))
    return out
