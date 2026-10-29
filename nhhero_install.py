"""Intégration des rôles modifiés dans les sources de NetHack.

Les héros eux-mêmes ne touchent pas aux sources : ce sont des options
(nom, rôle, race, sexe, alignement, animal…). Ce qui change le jeu, ce
sont les modifications des rôles : départ, titres, dieux, tuiles.

Chaque modification est repérable (« nhheroedit ») et garde le texte
d'origine à côté d'elle : une nouvelle intégration rend d'abord les
fichiers d'origine, et « retirer » les rétablit à l'identique.

Fichiers touchés (chemins relatifs aux sources) :
  src/role.c                entrée du rôle dans roles[] (titres, dieux,
                            races, sexes et alignements permis,
                            attributs, PV et énergie de départ) ;
                            l'entrée d'origine reste dans un « #if 0 » ;
                            un commentaire avant roles[] donne le
                            projet de chaque rôle intégré
  src/u_init.c              inventaires de départ (tableaux trobj, avec
                            l'original en « #if 0 »), or et intrinsèques
                            de départ (bloc ajouté après u_init_race())
  win/share/monsters.txt    tuiles mâle et femelle du rôle (l'original
                            en commentaire sous la tuile)
  src/allmain.c             biographie du héros au début d'une nouvelle
                            partie (texte de NHHEROEDIT_STORY, que
                            l'éditeur passe au jeu)
  src/insight.c             titre de rang au féminin dans ^X et dans la
                            liste des rangs atteints (quand des titres
                            de rang sont changés)
  po/fr.po, po/themes/fr@cyber.po, po/nethack.pot
                            titres de rang en français et du thème
                            Night City (traduction d'origine gardée dans
                            un commentaire « # nhheroedit:orig »)
"""

import difflib
import os
import re
import shutil
import subprocess
import time

import nhhero_data as D
from nhhero_i18n import _

TAG = "nhheroedit"
ROLE_C = "src/role.c"
U_INIT_C = "src/u_init.c"
INSIGHT_C = "src/insight.c"
ALLMAIN_C = "src/allmain.c"
MONSTERS_H = "include/monsters.h"
OBJECTS_H = "include/objects.h"
TILES = "win/share/monsters.txt"
PO_FR = "po/fr.po"
PO_CYBER = "po/themes/fr@cyber.po"
POT = "po/nethack.pot"
ALL_FILES = [ROLE_C, U_INIT_C, INSIGHT_C, ALLMAIN_C, TILES, PO_FR,
             PO_CYBER, POT]
START_KEY = "start"
PROJECTS_KEY = "projects"
STORY_KEY = "story"
STORY_ENV = "NHHEROEDIT_STORY"
FEMININE_KEY = "feminine-rank"


class InstallError(Exception):
    pass


def _read(src, rel):
    with open(os.path.join(src, rel), encoding="utf-8") as f:
        return f.read()


def _write(src, rel, text):
    path = os.path.join(src, rel)
    tmp = path + ".nhheroedit-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def check_tree(src):
    """Message d'erreur si src n'est pas un arbre de sources NetHack."""
    for rel in (ROLE_C, U_INIT_C, OBJECTS_H):
        if not os.path.isfile(os.path.join(src, rel)):
            return _("Pas de %s dans %s") % (rel, src)
    return None


# --- marqueurs et retrait --------------------------------------------------

C_BLOCK_RE = re.compile(
    r"^[ \t]*/\* %s:begin (\S+) \*/\n.*?"
    r"^(?:#if 0 /\* %s:orig \1 \*/\n(.*?)^#endif /\* %s:end \1 \*/"
    r"|[ \t]*/\* %s:end \1 \*/)\n" % (TAG, TAG, TAG, TAG), re.M | re.S)
TILE_RE = re.compile(
    r"^\{\n(?:  \S+\n)+\}\n# %s:orig (.+?)\n((?:#   \S+\n)+)"
    r"# %s:end \1\n" % (TAG, TAG), re.M)
PO_ADDED_RE = re.compile(r"\n# %s: added\n(?:msg.*\n)+" % TAG)
# traduction d'origine : première ligne, puis lignes de suite (« orig+ »)
PO_ORIG_RE = re.compile(r"^# %s:orig (\".*\")\n((?:# %s:orig\+ \".*\"\n)*)"
                        r"((?:msgctxt .*\n)?msgid .*\n)msgstr .*\n"
                        % (TAG, TAG), re.M)


def strip_c(text):
    """Rend le texte C d'origine : un bloc avec original reprend
    l'original, un bloc ajouté disparaît."""
    return C_BLOCK_RE.sub(lambda mo: mo.group(2) or "", text)


def strip_tiles(text):
    def orig(mo):
        rows = [l[4:] for l in mo.group(2).splitlines()]
        return "{\n" + "".join("  %s\n" % r for r in rows) + "}\n"
    return TILE_RE.sub(orig, text)


def strip_po(text):
    text = PO_ADDED_RE.sub("", text)

    def orig(mo):
        more = "".join(l[len("# %s:orig+ " % TAG):] + "\n"
                       for l in mo.group(2).splitlines())
        return mo.group(3) + "msgstr " + mo.group(1) + "\n" + more
    return PO_ORIG_RE.sub(orig, text)


STRIP = {ROLE_C: strip_c, U_INIT_C: strip_c, INSIGHT_C: strip_c,
         ALLMAIN_C: strip_c, TILES: strip_tiles,
         PO_FR: strip_po, PO_CYBER: strip_po, POT: strip_po}


def clean_text(src, rel):
    """Texte d'origine du fichier (sans les modifications de l'éditeur)."""
    return STRIP[rel](_read(src, rel)) if rel in STRIP else _read(src, rel)


def installed_projects(src):
    """{rôle: chemin du projet} des rôles intégrés (commentaire de
    role.c ; vide pour une intégration sans ce commentaire)."""
    try:
        text = _read(src, ROLE_C)
    except OSError:
        return {}
    mo = re.search(r"/\* %s:begin %s \*/\n(.*?)/\* %s:end %s \*/" % (
        TAG, PROJECTS_KEY, TAG, PROJECTS_KEY), text, re.S)
    out = {}
    for line in (mo.group(1).split("\n") if mo else []):
        m2 = re.match(r"^ \*   ([A-Z_]+) (.+)$", line)
        if m2:
            out[m2.group(1)] = os.path.expanduser(
                m2.group(2).replace("*_/", "*/"))
    return out


def installed_roles(src, game):
    """Rôles modifiés dans les sources (entrée, inventaire, or et
    intrinsèques, tuiles), qu'ils aient un projet connu ou non."""
    keys = installed_keys(src)
    out = set()
    try:
        start = re.search(r"/\* %s:begin %s \*/.*?/\* %s:end %s \*/" % (
            TAG, START_KEY, TAG, START_KEY), _read(src, U_INIT_C), re.S)
    except OSError:
        start = None
    cases = set(re.findall(r"case (PM_\w+):", start.group())) if start \
        else set()
    for r in game.roles:
        key = D.role_key(r)
        tile = game.tile_names.get(r["mnum"])
        if key in keys or r["mnum"] in cases or \
                any("kit:" + n in keys for n in game.kit_names(r)) or \
                any("tile:%s,%s" % (tile, g) in keys for g in D.GENDERS):
            out.add(key)
    return out


def installed_keys(src):
    """Rôles et tuiles modifiés dans les sources : ensemble de clés
    (« VALKYRIE », « kit:Valkyrie », « tile:valkyrie,female »…)."""
    keys = set()
    for rel in (ROLE_C, U_INIT_C, INSIGHT_C, ALLMAIN_C):
        try:
            keys |= set(re.findall(r"/\* %s:begin (\S+) \*/" % TAG,
                                   _read(src, rel)))
        except OSError:
            pass
    try:
        keys |= {"tile:" + k for k in re.findall(r"^# %s:orig (.+)$" % TAG,
                                                  _read(src, TILES), re.M)}
    except OSError:
        pass
    return keys


# --- données du jeu -----------------------------------------------------------

class GameData:
    """Tout ce que l'éditeur lit dans les sources d'origine."""

    def __init__(self, src):
        role_c = clean_text(src, ROLE_C)
        self.roles = D.parse_roles(role_c)
        self.races = D.parse_races(role_c)
        u_init = clean_text(src, U_INIT_C)
        self.kits = {}
        for names in D.ROLE_KITS.values():
            for n in names:
                k = D.parse_kit(u_init, n)
                if k is not None:
                    self.kits[n] = k
        self.objects = D.parse_objects(_read(src, OBJECTS_H))
        self.by_sn = {o["sn"]: o for o in self.objects}
        po = {}
        for rel in (PO_FR, PO_CYBER):
            try:
                po[rel] = D.parse_po(clean_text(src, rel))
            except OSError:
                po[rel] = {}
        self.names = D.Names(po[PO_FR], po[PO_CYBER])
        try:
            self.po_refs = D.parse_po_refs(clean_text(src, POT))
        except OSError:
            self.po_refs = {}
        # lignes de l'entrée de chaque rôle (pour les références des .po)
        self.role_lines = {
            D.role_key(r): (role_c.count("\n", 0, r["start"]) + 1,
                            role_c.count("\n", 0, r["end"]) + 1)
            for r in self.roles}
        try:
            self.tiles_text = clean_text(src, TILES)
        except OSError:
            self.tiles_text = ""
        try:
            self.tile_names = role_tile_names(_read(src, MONSTERS_H))
        except OSError:
            self.tile_names = {}

    def role(self, key):
        for r in self.roles:
            if D.role_key(r) == key:
                return r
        return None

    def race(self, noun):
        for r in self.races:
            if r["noun"] == noun:
                return r
        return None

    def kit_names(self, role):
        return [n for n in D.ROLE_KITS.get(role["mnum"], [])
                if n in self.kits]

    def tile(self, role, gender):
        """Tuile d'origine du rôle (16 lignes), ou None."""
        name = self.tile_names.get(role["mnum"])
        if not name:
            return None
        return find_tile(self.tiles_text, name, gender)

    def monster_tiles(self):
        """[(nom, sexe)] de toutes les tuiles de monstres."""
        return re.findall(r"^# tile \d+ \((.+?),(male|female)\)$",
                          self.tiles_text, re.M)


# monstre ajouté par nhmonedit : MON(NAM("security bot"), …, SECURITY_BOT)
ROBOT_RE = re.compile(r"/\* nhmonedit:begin (\w+) \*/\s*"
                      r"MON\(NAMS?\(\"([^\"]*)\""
                      r".*?,\s*(\w+)\),?\s*/\* nhmonedit:end \1 \*/", re.S)


def monster_ids(src):
    """Identifiants PM_… des monstres de monsters.h (vide si le fichier
    est illisible) : dernier argument de chaque MON(NAM…)."""
    try:
        text = _read(src, MONSTERS_H)
    except OSError:
        return set()
    out = set()
    for mo in re.finditer(r"\bMON\(NAMS?\(", text):
        depth, k = 1, mo.start() + 3        # k : parenthèse de MON(
        while depth and k + 1 < len(text):
            k += 1
            depth += {"(": 1, ")": -1}.get(text[k], 0)
        last = re.search(r",\s*(\w+)\s*\)$", text[mo.start():k + 1])
        if last:
            out.add("PM_" + last.group(1))
    return out


def editor_monsters(src):
    """Monstres ajoutés par nhmonedit dans monsters.h : [(PM_…, nom)]."""
    try:
        text = _read(src, MONSTERS_H)
    except OSError:
        return []
    return [("PM_" + m.group(3), m.group(2)) for m in ROBOT_RE.finditer(text)]


def role_tile_names(monsters_h):
    """{PM_ROLE: nom du monstre dans monsters.txt} (« cave dweller »)."""
    out = {}
    for mnum in D.ROLE_KITS:
        mo = re.search(r"MON\((NAMS?\([^)]*\))(?:(?!MON\().)*?\b%s\)"
                       % mnum[3:], monsters_h, re.S)
        if mo:
            out[mnum] = re.findall(r'"([^"]*)"', mo.group(1))[-1]
    return out


def find_tile(text, name, gender):
    mo = re.search(r"^# tile \d+ \(%s,%s\)\n\{\n(.*?)^\}" % (
        re.escape(name), gender), text, re.M | re.S)
    if not mo:
        return None
    rows = [r.strip() for r in mo.group(1).split("\n") if r.strip()]
    return rows if len(rows) == D.TILE_SIZE else None


# --- src/role.c ----------------------------------------------------------------

def _line_span(text, start, end):
    """Étend [start, end) aux lignes entières (avec la virgule et le
    commentaire de fin de ligne)."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.index("\n", end) + 1
    return ls, le


def _wrap(key, new, orig):
    """Bloc remplacé : le nouveau texte, puis l'original en #if 0."""
    return ("/* %s:begin %s */\n%s#if 0 /* %s:orig %s */\n%s"
            "#endif /* %s:end %s */\n" % (TAG, key, new, TAG, key, orig,
                                          TAG, key))


def ranks_c(ranks, indent):
    rows = ["{ %s, %s }" % (D.n_str(m), D.n_str(f if f and f != m
                                               else None))
            for m, f in ranks]
    sep = ",\n" + " " * (indent + 2)
    return "{ " + sep.join(rows) + " }"


def role_entry(text, role, mod):
    """Texte de l'entrée du rôle avec les modifications (les champs non
    modifiés gardent leur texte et leurs commentaires)."""
    g = role["group"]
    it = g.items
    eff = D.effective(role, mod)
    reps = []
    if "ranks_en" in mod:
        col = it[1].start - (text.rfind("\n", 0, it[1].start) + 1)
        reps.append((it[1].start, it[1].end, ranks_c(mod["ranks_en"], col)))
    if "gods" in mod:
        for i, god in zip((2, 3, 4), mod["gods"]):
            reps.append((it[i].start, it[i].end, D.c_str(god)))
    if "petnum" in mod:
        # le commentaire du jeu (« Orion & canis major ») part avec l'animal
        note = re.match(r"[ \t]*/\*[^\n]*?\*/", text[it[9].end:])
        reps.append((it[9].start, it[9].end + (note.end() if note else 0),
                     mod["petnum"]))
    if "allow" in mod:
        bits = [b for b in D.RACE_BITS if b in eff["allow"]] + \
            [D.GENDER_BIT[x] for x in D.GENDERS
             if D.GENDER_BIT[x] in eff["allow"]] + \
            [D.ALIGN_BIT[x] for x in D.ALIGNS
             if D.ALIGN_BIT[x] in eff["allow"]]
        col = it[18].start - (text.rfind("\n", 0, it[18].start) + 1)
        lines, cur = [], ""
        for b in bits:
            if cur and col + len(cur) + len(b) + 3 > 78:
                lines.append(cur)
                cur = b
            else:
                cur = cur + " | " + b if cur else b
        reps.append((it[18].start, it[18].end, ("\n" + " " * (col + 4) +
                     "| ").join(lines + [cur]) if bits else "0"))
    for key, idx in (("attrbase", 19), ("attrdist", 20)):
        if key in mod:
            reps.append((it[idx].start, it[idx].end,
                         "{ %s }" % ", ".join(str(v) for v in mod[key])))
    for key, idx in (("hp", 21), ("en", 22)):
        if key in mod:
            for j in (0, 1):
                leaf = it[idx].items[j]
                reps.append((leaf.start, leaf.end, str(mod[key][j])))
    ls, le = _line_span(text, g.start, g.end)
    entry = text[ls:le]
    for s, e, new in sorted(reps, reverse=True):
        entry = entry[:s - ls] + new + entry[e - ls:]
    return entry


def role_mod_c(mod):
    """Les modifications qui touchent role.c."""
    return {k: v for k, v in mod.items()
            if k in ("ranks_en", "gods", "allow", "attrbase", "attrdist",
                     "hp", "en", "petnum")}


def _home(path):
    """Chemin avec ~ pour le dossier personnel."""
    home = os.path.expanduser("~")
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


def insert_projects(text, origins):
    """role.c avec, avant roles[], le projet de chaque rôle intégré."""
    if not origins:
        return text
    pos = D.find_array(text, "roles")
    ls = text.rfind("\n", 0, pos) + 1
    block = "/* %s:begin %s */\n" % (TAG, PROJECTS_KEY) + \
        "/* rôles modifiés avec nhheroedit, et leur projet :\n" + \
        "".join(" *   %s %s\n" % (k, _home(origins[k]).replace("*/", "*_/"))
                for k in sorted(origins)) + \
        " */\n/* %s:end %s */\n" % (TAG, PROJECTS_KEY)
    return text[:ls] + block + text[ls:]


def insert_roles(text, game, mods):
    """role.c (d'origine) avec les entrées des rôles modifiés."""
    roles = D.parse_roles(text)
    for role in sorted(roles, key=lambda r: r["start"], reverse=True):
        mod = role_mod_c(mods.get(D.role_key(role), {}))
        if not mod:
            continue
        ls, le = _line_span(text, role["start"], role["end"])
        new = role_entry(text, role, mod)
        if new == text[ls:le]:
            continue
        text = text[:ls] + _wrap(D.role_key(role), new, text[ls:le]) + \
            text[le:]
    return text


# --- src/u_init.c --------------------------------------------------------------

def insert_kits(text, game, mods):
    for key, mod in mods.items():
        for name, items in mod.get("kits", {}).items():
            mo = re.search(r"^static const struct trobj %s\[\] = \{\n.*?"
                           r"^\};\n" % re.escape(name), text, re.M | re.S)
            if not mo:
                raise InstallError(_("Inventaire %s introuvable dans %s")
                                   % (name, U_INIT_C))
            new = D.kit_c(name, items)
            if new == mo.group():
                continue
            text = text[:mo.start()] + _wrap("kit:" + name, new,
                                             mo.group()) + text[mo.end():]
    return text


def start_block(game, mods):
    """Bloc C de l'or et des intrinsèques de départ, ou ""."""
    cases = []
    for key in sorted(mods):
        mod = mods[key]
        role = game.role(key)
        if not role:
            continue
        lines = []
        if mod.get("gold") is not None:
            lines.append("        u.umoney0 = %dL;" % mod["gold"])
        for p in mod.get("intrinsics", []):
            lines.append("        %s |= FROMOUTSIDE;" % p)
        if lines:
            cases.append("    case %s:\n%s\n        break;" % (
                role["mnum"], "\n".join(lines)))
    if not cases:
        return ""
    return ("    /* %s:begin %s */\n"
            "    /* or et intrinsèques de départ choisis avec nhheroedit */\n"
            "    switch (Role_switch) {\n%s\n    default:\n        break;\n"
            "    }\n    /* %s:end %s */\n" % (TAG, START_KEY,
                                              "\n".join(cases), TAG,
                                              START_KEY))


def insert_start(text, game, mods):
    block = start_block(game, mods)
    if not block:
        return text
    fn = text.find("\nu_init_inventory_attrs(void)")
    mo = re.compile(r"^    u_init_race\(\);\n", re.M).search(text, fn)
    if fn < 0 or not mo:
        raise InstallError(_("u_init_race() introuvable dans "
                             "u_init_inventory_attrs() (%s)") % U_INIT_C)
    return text[:mo.end()] + block + text[mo.end():]


# --- tuiles ----------------------------------------------------------------------

def insert_tiles(text, game, mods):
    for key, mod in mods.items():
        role = game.role(key)
        if not role:
            continue
        name = game.tile_names.get(role["mnum"])
        for g in D.GENDERS:
            rows = mod.get("tile_" + g)
            if not rows or not name:
                continue
            mo = re.search(r"^# tile \d+ \(%s,%s\)\n\{\n((?:  \S+\n)+)\}\n"
                           % (re.escape(name), g), text, re.M)
            if not mo:
                raise InstallError(_("Tuile (%s,%s) introuvable dans %s")
                                   % (name, g, TILES))
            orig = [l.strip() for l in mo.group(1).splitlines()]
            if orig == rows:
                continue
            new = "{\n" + "".join("  %s\n" % r for r in rows) + "}\n" + \
                "# %s:orig %s,%s\n" % (TAG, name, g) + \
                "".join("#   %s\n" % r for r in orig) + \
                "# %s:end %s,%s\n" % (TAG, name, g)
            text = text[:mo.start(1) - 2] + new + text[mo.end():]
    return text


# --- src/insight.c : titre au féminin -------------------------------------------

# Un rang sans titre féminin propre (« Shieldmaiden ») se traduit au
# féminin par msgctxt "feminine" ; la ligne d'état et les textes de quête
# passent par gendered_word(), mais ^X et la liste des rangs atteints
# traduisent le titre masculin. Ces deux appels sont corrigés.
FEMININE_FIXES = [
    ("""                 _(rank_titl),
""", """                 gendered_word(rank_titl, innategend),
"""),
    ("""                         _(rank_of(rank_to_xlev(absidx - (ACH_RNK1 - 1)),
                                   Role_switch,
                                   (achidx < 0) ? TRUE : FALSE)));
""", """                         gendered_word(rank_of(rank_to_xlev(absidx
                                                            - (ACH_RNK1 - 1)),
                                               Role_switch,
                                               (achidx < 0) ? TRUE : FALSE),
                                       (achidx < 0) ? 1 : 0));
"""),
]


def insert_feminine(text, ranks):
    """insight.c (d'origine) avec le correctif du titre féminin, quand
    des titres de rang sont traduits (ranks : plan de rank_plan())."""
    if not ranks:
        return text
    for n, (old, new) in enumerate(FEMININE_FIXES):
        # l'appel corrigé est remplacé en entier (pas de #if 0 au milieu
        # des arguments d'une macro comme Snprintf)
        mo = re.compile(r"^[ \t]*Snprintf\((?:(?!;\n).)*?\n%s.*?;\n" %
                        re.escape(old), re.M | re.S).search(text)
        if not mo:
            continue
        key = "%s:%d" % (FEMININE_KEY, n + 1)
        orig = mo.group()
        fixed = orig.replace(old, new)
        text = text[:mo.start()] + _wrap(key, fixed, orig) + text[mo.end():]
    return text


# --- src/allmain.c : biographie du héros ---------------------------------------

STORY_BLOCK = """\
    /* %(tag)s:begin %(key)s */
    /* biographie du héros, passée par nhheroedit dans %(env)s */
    {
        /* getenv() : nh_getenv() refuse plus de BUFSZ / 2 caractères */
        const char *story = getenv("%(env)s");

        if (story && *story) {
            winid storywin = create_nhwindow(NHW_TEXT);
            char line[BUFSZ];

            while (*story) {
                copynchars(line, story, BUFSZ - 1);
                putstr(storywin, 0, line);
                story = strchr(story, '\\n');
                if (!story++)
                    break;
            }
            display_nhwindow(storywin, TRUE);
            destroy_nhwindow(storywin);
        }
    }
    /* %(tag)s:end %(key)s */
""" % {"tag": TAG, "key": STORY_KEY, "env": STORY_ENV}


def insert_story(text):
    """allmain.c (d'origine) avec la biographie après le texte
    d'introduction d'une nouvelle partie."""
    fn = text.find("\nnewgame(void)")
    mo = re.compile(r"^    if \(flags\.legacy\) \{\n.*?^    \}\n",
                    re.M | re.S).search(text, fn)
    if fn < 0 or not mo:
        raise InstallError(_("Texte d'introduction introuvable dans "
                             "newgame() (%s)") % ALLMAIN_C)
    return text[:mo.end()] + STORY_BLOCK + text[mo.end():]


def story_text(h, width=76):
    """Texte passé au jeu : le nom du héros puis sa biographie, en
    lignes de width colonnes au plus ; "" sans biographie."""
    import textwrap
    story = (h.get("story") or "").replace("\r", "").strip()
    if not story:
        return ""
    lines = [h["name"], ""]
    for para in story.split("\n"):
        lines += textwrap.wrap(para, width) or [""]
    return "\n".join(lines)


# --- traductions -----------------------------------------------------------------

def _po_q(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def _po_entry_re(ctx, msgid):
    """Entrée (contexte, msgid) : groupe 1 l'en-tête (msgctxt, msgid),
    groupe 2 les lignes de la traduction (une, ou "" puis des lignes de
    suite)."""
    head = (r"msgctxt %s\n" % re.escape(_po_q(ctx))) if ctx else ""
    return re.compile(r"^(%smsgid %s\n)msgstr ((?:\".*\"\n)+)" % (
        head, re.escape(_po_q(msgid))), re.M)


def po_find(text, ctx, msgid):
    """Correspondance de l'entrée (sans contexte : une entrée qui n'est
    pas précédée de msgctxt), ou None."""
    for mo in _po_entry_re(ctx, msgid).finditer(text):
        if ctx is None:
            before = text[:mo.start()].rsplit("\n", 2)
            if len(before) > 1 and before[-2].startswith("msgctxt"):
                continue
        return mo
    return None


def po_set(text, ctx, msgid, value):
    """Traduction de (ctx, msgid) mise à value : l'entrée existante est
    modifiée (l'ancienne traduction gardée en commentaire), sinon une
    entrée est ajoutée à la fin."""
    mo = po_find(text, ctx, msgid)
    if mo:
        lines = mo.group(2).splitlines()
        if D._po_unquote([l[1:-1] for l in lines]) == value:
            return text
        orig = "# %s:orig %s\n" % (TAG, lines[0]) + \
            "".join("# %s:orig+ %s\n" % (TAG, l) for l in lines[1:])
        return text[:mo.start()] + orig + mo.group(1) + \
            "msgstr %s\n" % _po_q(value) + text[mo.end():]
    return text + "\n# %s: added\n%smsgid %s\nmsgstr %s\n" % (
        TAG, "msgctxt %s\n" % _po_q(ctx) if ctx else "", _po_q(msgid),
        _po_q(value))


def rank_msgids(en_m, en_f):
    """(contexte, msgid) du titre masculin et du titre féminin."""
    return (None, en_m), ((None, en_f) if en_f and en_f != en_m
                          else ("feminine", en_m))


def rank_plan(game, mods):
    """[(contexte, msgid, fr, cyber)] des titres de rang à traduire."""
    out = []
    for key in sorted(mods):
        mod = mods[key]
        if not any(k in mod for k in ("ranks_en", "ranks_fr",
                                      "ranks_cyber")):
            continue
        role = game.role(key)
        if not role:
            continue
        table = D.ranks_table(role, game.names)
        en = mod.get("ranks_en", [r[:2] for r in table])
        fr = mod.get("ranks_fr", [r[2:4] for r in table])
        cy = mod.get("ranks_cyber", [r[4:6] for r in table])
        for i in range(9):
            for j, (ctx, msgid) in enumerate(rank_msgids(*en[i])):
                if msgid:
                    out.append((ctx, msgid, fr[i][j], cy[i][j]))
    return out


def rank_uses(game, key, msgid, theme="cyber"):
    """Où le jeu emploie déjà msgid, hors de l'entrée du rôle key : noms
    des autres rôles et fichiers (d'après nethack.pot)."""
    out = []
    for ref in game.po_refs.get((None, msgid), []):
        rel, _s, line = ref.rpartition(":")
        where = rel
        if rel == ROLE_C and line.isdigit():
            for k, (l1, l2) in game.role_lines.items():
                if l1 <= int(line) <= l2:
                    where = None if k == key else \
                        game.names.role(game.role(k), "male", theme)
                    break
        if where and where not in out:
            out.append(where)
    return out


def rank_conflicts(game, mods, theme="cyber"):
    """{rôle: [avertissements]} : titres anglais qui servent déjà ailleurs
    dans le jeu (changer leur traduction la change partout), ou que deux
    rôles du projet traduisent différemment."""
    out = {}
    seen = {}
    mods = active_mods(mods)
    for key in sorted(mods):
        if not game.role(key):
            continue
        told = set()
        for ctx, msgid, fr, cy in rank_plan(game, {key: mods[key]}):
            msgs = out.setdefault(key, [])
            prev = seen.setdefault((ctx, msgid), (key, fr, cy))
            if prev[0] != key and prev[1:] != (fr, cy) and msgid not in told:
                told.add(msgid)
                msgs.append(_("titre « %s » : traduit autrement pour le "
                              "rôle %s (une seule traduction possible)")
                            % (msgid, game.names.role(game.role(prev[0]),
                                                      "male", theme)))
            names = game.names
            changed = (fr.strip() and fr != names.get(msgid, ctx, "fr")) or \
                (cy.strip() and cy != names.get(msgid, ctx, "cyber"))
            if not changed or msgid in told:
                continue
            uses = rank_uses(game, key, msgid, theme)
            if uses:
                told.add(msgid)
                msgs.append(_("titre « %s » : le jeu l'emploie déjà (%s) ; "
                              "sa traduction y changera aussi — un autre "
                              "titre anglais l'évite")
                            % (msgid, ", ".join(uses[:4])))
    return {k: v for k, v in out.items() if v}


def insert_po(text, plan, kind, fr_names=None):
    """kind : fr, cyber ou pot. fr_names : traductions de fr.po (pour le
    thème, qui reprend celles de fr.po quand il n'a pas d'entrée)."""
    done = set()
    for ctx, msgid, fr, cy in plan:
        if (ctx, msgid) in done:
            continue
        done.add((ctx, msgid))
        if kind == "pot":
            if not po_find(text, ctx, msgid):
                text = po_set(text, ctx, msgid, "")
        elif kind == "fr":
            if fr.strip():
                text = po_set(text, ctx, msgid, fr)
        elif cy.strip():
            if po_find(text, ctx, msgid) or cy != (fr or "").strip() or \
                    not fr.strip():
                text = po_set(text, ctx, msgid, cy)
    return text


# --- opérations ------------------------------------------------------------------

def active_mods(mods):
    return {k: v for k, v in (mods or {}).items() if v}


def plan(src, mods, game=None, origins=None, story=None):
    """Nouveaux textes des fichiers : {chemin relatif: texte}, d'après
    les fichiers d'origine. Ne touche à rien sur le disque. origins :
    {rôle: chemin du projet}, noté dans role.c. story : ajouter
    l'affichage de la biographie (par défaut, dès qu'un rôle change)."""
    game = game or GameData(src)
    mods = active_mods(mods)
    for key in mods:
        if not game.role(key):
            raise InstallError(_("Rôle %s absent de %s") % (key, ROLE_C))
    pms = monster_ids(src)
    for key, mod in sorted(mods.items()):
        pet = mod.get("petnum", D.NO_PET)
        if pet != D.NO_PET and pms and pet not in pms:
            raise InstallError(_("Animal %s du rôle %s absent de %s (robot "
                                 "retiré de nhmonedit ?)")
                               % (pet, key, MONSTERS_H))
    out = {}
    out[ROLE_C] = insert_roles(clean_text(src, ROLE_C), game, mods)
    out[ROLE_C] = insert_projects(out[ROLE_C], {
        k: p for k, p in (origins or {}).items() if k in mods})
    u_init = insert_kits(clean_text(src, U_INIT_C), game, mods)
    out[U_INIT_C] = insert_start(u_init, game, mods)
    if os.path.isfile(os.path.join(src, TILES)):
        out[TILES] = insert_tiles(clean_text(src, TILES), game, mods)
    ranks = rank_plan(game, mods)
    if os.path.isfile(os.path.join(src, INSIGHT_C)):
        out[INSIGHT_C] = insert_feminine(clean_text(src, INSIGHT_C), ranks)
    if os.path.isfile(os.path.join(src, ALLMAIN_C)):
        text = clean_text(src, ALLMAIN_C)
        out[ALLMAIN_C] = insert_story(text) if (
            bool(mods) if story is None else story) else text
    for rel, kind in ((PO_FR, "fr"), (PO_CYBER, "cyber"), (POT, "pot")):
        if os.path.isfile(os.path.join(src, rel)):
            out[rel] = insert_po(clean_text(src, rel), ranks, kind)
    return out


def backup(src, backup_root):
    dest = os.path.join(backup_root, time.strftime("%Y%m%d-%H%M%S"))
    for rel in ALL_FILES:
        p = os.path.join(src, rel)
        if os.path.isfile(p):
            q = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.copy2(p, q)
    return dest


def list_backups(backup_root):
    out = []
    try:
        names = sorted(os.listdir(backup_root), reverse=True)
    except OSError:
        return out
    for n in names:
        d = os.path.join(backup_root, n)
        files = [rel for rel in ALL_FILES
                 if os.path.isfile(os.path.join(d, rel))]
        if os.path.isdir(d) and files:
            out.append((d, files))
    return out


def restore_plan(src, backup_dir):
    out = {}
    for rel in ALL_FILES:
        p = os.path.join(backup_dir, rel)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                text = f.read()
            if not os.path.isfile(os.path.join(src, rel)) or \
                    _read(src, rel) != text:
                out[rel] = text
    return out


def changed_files(src, files):
    return [rel for rel, t in files.items() if _read(src, rel) != t]


def apply(src, files, backup_root=None):
    """Écrit les fichiers prévus. Renvoie (fichiers modifiés, dossier de
    sauvegarde ou None)."""
    changed = changed_files(src, files)
    if not changed:
        return [], None
    saved = backup(src, backup_root) if backup_root else None
    for rel in changed:
        _write(src, rel, files[rel])
    return changed, saved


def install(src, mods, backup_root=None):
    return apply(src, plan(src, mods), backup_root)


def uninstall(src, backup_root=None):
    return install(src, {}, backup_root)


def diff(src, files):
    out = []
    for rel, new in files.items():
        old = _read(src, rel)
        if old != new:
            out += difflib.unified_diff(
                old.splitlines(True), new.splitlines(True),
                "a/" + rel, "b/" + rel, n=2)
    return "".join(out)


def check_po(src, files):
    """msgfmt --check des catalogues prévus (thème fusionné avec fr.po
    comme le Makefile). Renvoie un message d'erreur ou None ; None aussi
    quand msgfmt n'est pas installé."""
    if not shutil.which("msgfmt"):
        return None
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for rel in (PO_FR, PO_CYBER):
            text = files.get(rel)
            if text is None:
                try:
                    text = _read(src, rel)
                except OSError:
                    continue
            paths[rel] = os.path.join(d, os.path.basename(rel))
            with open(paths[rel], "w", encoding="utf-8") as f:
                f.write(text)
        cmds = []
        if PO_FR in paths:
            cmds.append(["msgfmt", "--check", "-o", os.devnull,
                         paths[PO_FR]])
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode:
                return r.stderr.strip()
        if PO_CYBER in paths and PO_FR in paths and shutil.which("msgcat"):
            r = subprocess.run("msgcat --use-first %s %s | msgfmt --check "
                               "-o /dev/null -" % (paths[PO_CYBER],
                                                   paths[PO_FR]),
                               shell=True, capture_output=True, text=True)
            if r.returncode:
                return r.stderr.strip()
    return None


# --- git -----------------------------------------------------------------------------

def _git(src, *args):
    try:
        r = subprocess.run(["git", "-C", src] + list(args),
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def is_git_repo(src):
    return _git(src, "rev-parse", "--is-inside-work-tree")[0]


def commit_message(game, mods, story=False):
    mods = active_mods(mods)
    if not mods and story:
        return "Show the hero's biography at the start (nhheroedit)"
    if not mods:
        return "Restore the roles changed with nhheroedit"
    names = ", ".join(game.role(k)["name"][0] if game.role(k) else k
                      for k in sorted(mods))
    return "Change the starting rules of roles with nhheroedit: " + names


def git_commit(src, paths, message):
    ok, out = _git(src, "add", "--", *paths)
    if not ok:
        return ok, out
    return _git(src, "commit", "-m", message, "--only", "--", *paths)
