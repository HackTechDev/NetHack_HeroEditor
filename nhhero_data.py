"""Données de NetHack pour l'éditeur de héros : lecture des tables du jeu
(rôles et races de src/role.c, inventaires de départ de src/u_init.c,
objets de include/objects.h, tuiles de win/share/monsters.txt,
traductions des fichiers .po), modèle d'un héros et d'un rôle modifié,
calculs (attributs, PV, combinaisons permises) et vérifications.

Ce module ne touche à aucun fichier : la lecture des sources (après
retrait des modifications de l'éditeur) est dans nhhero_install.
"""

import re
import struct
import zlib

from nhhero_i18n import _

# --- constantes du jeu ----------------------------------------------------

ATTRS = ["Str", "Int", "Wis", "Dex", "Con", "Cha"]
ATTR_FR = {"Str": _("Force"), "Int": _("Intelligence"), "Wis": _("Sagesse"),
           "Dex": _("Dextérité"), "Con": _("Constitution"),
           "Cha": _("Charisme")}
ATTR_SHORT = {"Str": _("For"), "Int": _("Int"), "Wis": _("Sag"),
              "Dex": _("Dex"), "Con": _("Con"), "Cha": _("Cha")}

GENDERS = ["male", "female"]
GENDER_BIT = {"male": "ROLE_MALE", "female": "ROLE_FEMALE"}
GENDER_FR = {"male": _("masculin"), "female": _("féminin")}

ALIGNS = ["lawful", "neutral", "chaotic"]
ALIGN_BIT = {"lawful": "ROLE_LAWFUL", "neutral": "ROLE_NEUTRAL",
             "chaotic": "ROLE_CHAOTIC"}
ALIGN_FR = {"lawful": _("loyal"), "neutral": _("neutre"),
            "chaotic": _("chaotique")}
# dieux : lgod, ngod, cgod de struct Role
ALIGN_GOD = {"lawful": 0, "neutral": 1, "chaotic": 2}

RACE_BITS = ["MH_HUMAN", "MH_ELF", "MH_DWARF", "MH_GNOME", "MH_ORC"]

# rangs : niveaux d'expérience de chaque titre (xlev_to_rank de botl.c)
RANK_LEVELS = ["1-2", "3-5", "6-9", "10-13", "14-17", "18-21", "22-25",
               "26-29", "30"]

# animal de compagnie : option pettype ("" = au choix du jeu)
PETS = [("", _("au choix du jeu (selon le rôle)")),
        ("cat", _("chaton")), ("dog", _("petit chien")),
        ("horse", _("poney")), ("none", _("aucun animal"))]
PET_NAME_OPTION = {"cat": "catname", "dog": "dogname",
                   "horse": "horsename"}
PET_OF_PM = {"PM_KITTEN": "cat", "PM_LITTLE_DOG": "dog", "PM_PONY": "horse"}
PET_MONSTER = {"cat": "kitten", "dog": "little dog", "horse": "pony"}
# animal imposé par le rôle (petnum de struct Role) : NON_PM laisse le
# joueur choisir (pettype) ; les robots de nhmonedit s'ajoutent à la liste
NO_PET = "NON_PM"
ROLE_PETS = [(NO_PET, "")] + [(pm, PET_MONSTER[p])
                              for pm, p in PET_OF_PM.items()]

# options de « jeu de rôle » (conduites choisies avant la partie)
CONDUCTS = [
    ("pauper", _("sans le sou : aucun objet au départ")),
    ("nudist", _("nudiste : sans armure")),
    ("blind", _("aveugle de naissance")),
    ("deaf", _("sourd de naissance")),
    ("!bones", _("sans fichiers de bones (niveaux hantés)")),
]

# profil d'affichage du héros (options d'interface)
AUTOPICKUP = [("", _("comme le .nethackrc")),
              ("off", _("aucun ramassage automatique")),
              ("gold", _("l'argent seulement")),
              ("light", _("argent, parchemins, potions, anneaux, amulettes, "
                          "baguettes, livres"))]
PICKUP_TYPES = {"gold": "$", "light": '$?!/="+'}
COLORS = [("", _("comme le .nethackrc")),
          ("nightcity", _("Night City : PV et énergie en couleur, objets "
                          "bénis et maudits"))]
# règles du profil « nightcity » (Guidebook, hilite_status et MENUCOLOR)
NIGHTCITY_HILITES = [
    "hitpoints/100%/green&normal", "hitpoints/<100%/lightgreen&normal",
    "hitpoints/<66%/yellow&normal", "hitpoints/<50%/orange&normal",
    "hitpoints/<33%/red&bold", "hitpoints/<15%/red&inverse",
    "power/<33%/magenta&normal", "gold/up/yellow/down/brown",
    "characteristics/up/green/down/red", "condition/major/orange&inverse",
]
NIGHTCITY_MENUCOLORS = [
    '" blessed "=lightcyan', '" cursed "=red', '" uncursed "=gray',
    '"\\(being worn\\)"=lightmagenta',
    '"\\((weapon|wielded)( in .*)?\\)"=lightgreen',
]
DISPLAY_KEYS = ("windowtype", "symset", "autopickup", "colors")

# intrinsèques donnés au départ (u_init.c, après les objets)
INTRINSICS = [
    ("HFast", _("rapidité")),
    ("HStealth", _("discrétion")),
    ("HSee_invisible", _("voir l'invisible")),
    ("HTelepat", _("télépathie")),
    ("HInfravision", _("infravision")),
    ("HSearching", _("recherche automatique")),
    ("HWarning", _("avertissement (danger proche)")),
    ("HRegeneration", _("régénération")),
    ("HJumping", _("saut")),
    ("HTeleport_control", _("contrôle de la téléportation")),
    ("HFire_resistance", _("résistance au feu")),
    ("HCold_resistance", _("résistance au froid")),
    ("HSleep_resistance", _("résistance au sommeil")),
    ("HShock_resistance", _("résistance à l'électricité")),
    ("HPoison_resistance", _("résistance au poison")),
    ("HDisint_resistance", _("résistance à la désintégration")),
    ("HClairvoyant", _("clairvoyance")),
]
INTRINSIC_FR = dict(INTRINSICS)

# inventaires de départ de chaque rôle dans u_init.c
ROLE_KITS = {
    "PM_ARCHEOLOGIST": ["Archeologist"],
    "PM_BARBARIAN": ["Barbarian_0", "Barbarian_1"],
    "PM_CAVE_DWELLER": ["Cave_man"],
    "PM_HEALER": ["Healer"],
    "PM_KNIGHT": ["Knight"],
    "PM_MONK": ["Monk"],
    "PM_CLERIC": ["Priest"],
    "PM_RANGER": ["Ranger"],
    "PM_ROGUE": ["Rogue"],
    "PM_SAMURAI": ["Samurai"],
    "PM_TOURIST": ["Tourist"],
    "PM_VALKYRIE": ["Valkyrie"],
    "PM_WIZARD": ["Wizard"],
}
# or de départ fixé par le jeu (u.umoney0 dans u_init_role())
GAME_GOLD = {"PM_HEALER": _("1001 à 2000"), "PM_TOURIST": _("1 à 1000")}

# classes d'objets : macro de objects.h -> classe
MACRO_CLASS = {
    "WEAPON": "WEAPON_CLASS", "PROJECTILE": "WEAPON_CLASS",
    "BOW": "WEAPON_CLASS", "ARMOR": "ARMOR_CLASS", "HELM": "ARMOR_CLASS",
    "CLOAK": "ARMOR_CLASS", "SHIELD": "ARMOR_CLASS",
    "GLOVES": "ARMOR_CLASS", "BOOTS": "ARMOR_CLASS",
    "RING": "RING_CLASS", "AMULET": "AMULET_CLASS", "TOOL": "TOOL_CLASS",
    "CONTAINER": "TOOL_CLASS", "WEPTOOL": "TOOL_CLASS",
    "FOOD": "FOOD_CLASS", "POTION": "POTION_CLASS",
    "SCROLL": "SCROLL_CLASS", "SPELL": "SPBOOK_CLASS",
    "WAND": "WAND_CLASS", "COIN": "COIN_CLASS", "GEM": "GEM_CLASS",
    "ROCK": "GEM_CLASS",
}
# classes proposées pour un objet (dans l'ordre de l'inventaire)
CLASSES = [
    ("WEAPON_CLASS", _("arme"), _("armes")),
    ("ARMOR_CLASS", _("armure"), _("armures")),
    ("RING_CLASS", _("anneau"), _("anneaux")),
    ("AMULET_CLASS", _("amulette"), _("amulettes")),
    ("TOOL_CLASS", _("outil"), _("outils")),
    ("FOOD_CLASS", _("nourriture"), _("nourriture")),
    ("POTION_CLASS", _("potion"), _("potions")),
    ("SCROLL_CLASS", _("parchemin"), _("parchemins")),
    ("SPBOOK_CLASS", _("livre de sort"), _("livres de sorts")),
    ("WAND_CLASS", _("baguette"), _("baguettes")),
    ("GEM_CLASS", _("gemme ou pierre"), _("gemmes et pierres")),
]
CLASS_FR = {c: s for c, s, _p in CLASSES}
CLASS_FR_PLURAL = {c: p for c, _s, p in CLASSES}
# objets qu'on ne peut pas donner au départ (uniques, invocation…)
FORBIDDEN_OBJECTS = {
    "AMULET_OF_YENDOR", "FAKE_AMULET_OF_YENDOR", "CANDELABRUM_OF_INVOCATION",
    "BELL_OF_OPENING", "SPE_BOOK_OF_THE_DEAD", "SPE_BLANK_PAPER",
    "SPE_NOVEL", "GOLD_PIECE", "BOULDER", "STATUE", "HEAVY_IRON_BALL",
    "IRON_CHAIN", "ACID_VENOM", "BLINDING_VENOM", "STRANGE_OBJECT",
    "CORPSE", "EGG", "TIN",
}

UNDEF_TYP = "UNDEF_TYP"
MAX_KIT = 30        # lignes d'un inventaire (52 lettres au plus en jeu)

TILE_SIZE = 16
TILE_PALETTE = [
    (".", (71, 108, 108)), ("A", (0, 0, 0)), ("B", (0, 182, 255)),
    ("C", (255, 108, 0)), ("D", (255, 0, 0)), ("E", (0, 0, 255)),
    ("F", (0, 145, 0)), ("G", (108, 255, 0)), ("H", (255, 255, 0)),
    ("I", (255, 0, 255)), ("J", (145, 71, 0)), ("K", (204, 79, 0)),
    ("L", (255, 182, 145)), ("M", (237, 237, 237)),
    ("N", (255, 255, 255)), ("O", (215, 215, 215)),
    ("P", (108, 145, 182)), ("Q", (18, 18, 18)), ("R", (54, 54, 54)),
    ("S", (73, 73, 73)), ("T", (82, 82, 82)), ("U", (205, 205, 205)),
    ("V", (104, 104, 104)), ("W", (131, 131, 131)),
    ("X", (140, 140, 140)), ("Y", (149, 149, 149)),
    ("Z", (195, 195, 195)), ("0", (100, 100, 100)),
    ("1", (72, 108, 108)),
]
TILE_CHARS = {c for c, _rgb in TILE_PALETTE}

# calques Night City, à poser sur une tuile de héros (l dans l'éditeur
# de pixels) ; espace : transparent. Placés pour la silhouette commune
# des héros du jeu (yeux à la ligne 5, bras aux colonnes 4 et 11).
LAYERS = [
    (_("Visière"), [
        "", "", "", "",
        "     I    I",
        "     BBBBBB",
    ]),
    (_("Implants"), [
        "", "", "", "",
        "         I",
        "",
        "      B",
        "       B",
    ]),
    (_("Bras mécanique"), [
        "", "", "", "", "", "", "", "",
        "    Z",
        "    X",
        "    B",
        "    X",
        "    U",
    ]),
    (_("Manteau long"), [
        "", "", "", "", "", "", "",
        "     I    I",
        "    RR    RR",
        "     R    R",
        "     R    R",
        "     R    R",
        "     RR  RR",
        "     RR  RR",
        "    RRR  RRR",
    ]),
    (_("Arme"), [
        "", "", "", "", "", "", "", "",
        "",
        "           XXXXB",
        "            S",
        "            S",
    ]),
]


def apply_layer(tile, layer, dy=0, dx=0):
    """Tuile avec le calque posé, décalé de (dy, dx) ; ce qui sort de la
    tuile est perdu."""
    rows = [list(r) for r in tile]
    for j, line in enumerate(layer):
        for i, c in enumerate(line):
            y, x = j + dy, i + dx
            if c != " " and 0 <= y < TILE_SIZE and 0 <= x < TILE_SIZE:
                rows[y][x] = c
    return ["".join(r) for r in rows]

# thèmes d'affichage des noms : anglais (noms internes), français, cyber
THEMES = ["cyber", "fr", "en"]
THEME_FR = {"cyber": _("Night City (fr@cyber)"), "fr": _("français"),
            "en": _("anglais (noms internes)")}


# --- lecture du C ---------------------------------------------------------

class Leaf:
    """Valeur simple d'un initialiseur C (texte brut, sans commentaires,
    espaces réduits)."""

    def __init__(self, text, start, end):
        self.text, self.start, self.end = text, start, end

    def __repr__(self):
        return "Leaf(%r)" % self.text


class Group:
    """{ … } d'un initialiseur C : liste de Leaf et de Group."""

    def __init__(self, items, start, end):
        self.items, self.start, self.end = items, start, end

    def __repr__(self):
        return "Group(%r)" % self.items


_TOKEN = re.compile(r"""
    (?P<comment>/\*.*?\*/|//[^\n]*)
  | (?P<pre>^[ \t]*\#[^\n]*(?:\\\n[^\n]*)*)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<open>\{) | (?P<close>\}) | (?P<comma>,)
  | (?P<space>\s+)
  | (?P<other>[^\s{},"'/]+|/)
""", re.S | re.M | re.X)


def parse_init(text, pos):
    """Initialiseur C qui commence par « { » à la position pos. Renvoie
    le Group ; les commentaires et lignes du préprocesseur sont sautés."""
    stack = []
    cur = None
    leaf, lstart, lend = [], None, None

    def flush():
        nonlocal leaf, lstart
        if leaf:
            cur.items.append(Leaf(" ".join("".join(leaf).split()),
                                  lstart, lend))
        leaf, lstart = [], None

    skip = 0            # profondeur dans un « #if 0 »
    for mo in _TOKEN.finditer(text, pos):
        kind = mo.lastgroup
        if kind == "pre":
            d = mo.group().strip()
            if skip:
                if re.match(r"#\s*if", d):
                    skip += 1
                elif re.match(r"#\s*endif", d):
                    skip -= 1
            elif re.match(r"#\s*if\s+0\b", d):
                skip = 1
            continue
        if kind == "comment" or skip:
            continue
        if kind == "space":
            if leaf:
                leaf.append(" ")
            continue
        if kind == "open":
            if cur is not None:
                flush()
                stack.append(cur)
            cur = Group([], mo.start(), None)
        elif kind == "close":
            flush()
            cur.end = mo.end()
            if not stack:
                return cur
            parent = stack.pop()
            parent.items.append(cur)
            cur = parent
        elif kind == "comma":
            flush()
        else:
            if cur is None:
                raise ValueError("initialiseur attendu")
            if lstart is None:
                lstart = mo.start()
            leaf.append(mo.group())
            lend = mo.end()
    raise ValueError("initialiseur non terminé")


def c_string(leaf):
    """N_("x"), "x" ou 0 -> chaîne ou None."""
    if isinstance(leaf, Group):
        raise ValueError("chaîne attendue : %r" % leaf)
    t = leaf.text
    mo = re.match(r'^(?:N_\s*\(\s*)?"((?:\\.|[^"\\])*)"\s*\)?$', t)
    if mo:
        return mo.group(1).replace('\\"', '"').replace("\\\\", "\\")
    if t in ("0", "NULL", "(const char *) 0"):
        return None
    raise ValueError("chaîne attendue : %r" % t)


def c_int(leaf):
    t = leaf.text
    mo = re.match(r"^STR18\((\d+)\)$", t)
    if mo:
        return 18 + int(mo.group(1))
    return int(t, 0)


def c_mask(leaf):
    """« MH_HUMAN | ROLE_MALE » -> ensemble des noms."""
    return {p.strip() for p in leaf.text.split("|") if p.strip()} - {"0"}


def c_str(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def n_str(s):
    return "N_(%s)" % c_str(s) if s is not None else "0"


def find_array(text, name):
    """Position du « { » de l'initialiseur du tableau name, ou None."""
    mo = re.search(r"\b%s\s*\[[^\]]*\]\s*=\s*\{" % re.escape(name), text)
    return mo.end() - 1 if mo else None


# --- rôles et races (src/role.c) -------------------------------------------

def parse_roles(text):
    """Rôles de roles[] : liste de dicts (valeurs du jeu). Chaque rôle
    garde aussi les positions de son entrée (start, end)."""
    pos = find_array(text, "roles")
    if pos is None:
        raise ValueError("roles[] introuvable")
    out = []
    for g in parse_init(text, pos).items:
        if not isinstance(g, Group):
            continue            # UNDEFINED_ROLE
        it = g.items
        if len(it) != 32:
            raise ValueError("entrée de roles[] inattendue (%d champs)"
                             % len(it))
        ranks = [[c_string(r.items[0]), c_string(r.items[1])]
                 for r in it[1].items]
        out.append({
            "name": [c_string(it[0].items[0]), c_string(it[0].items[1])],
            "ranks": ranks,
            "gods": [c_string(it[i]) for i in (2, 3, 4)],
            "filecode": c_string(it[5]),
            "mnum": it[8].text,
            "petnum": it[9].text.split("/*")[0].strip(),
            "allow": c_mask(it[18]),
            "attrbase": [c_int(x) for x in it[19].items],
            "attrdist": [c_int(x) for x in it[20].items],
            "hpadv": [c_int(x) for x in it[21].items],
            "enadv": [c_int(x) for x in it[22].items],
            "xlev": c_int(it[23]),
            "initrecord": c_int(it[24]),
            "spelstat": it[29].text,
            "start": g.start, "end": g.end,
            "group": g,
        })
    return out


def parse_races(text):
    pos = find_array(text, "races")
    if pos is None:
        raise ValueError("races[] introuvable")
    out = []
    for g in parse_init(text, pos).items:
        if not isinstance(g, Group) or len(g.items) != 16:
            continue
        it = g.items
        out.append({
            "noun": c_string(it[0]), "adj": c_string(it[1]),
            "filecode": c_string(it[3]),
            "individual": [c_string(it[4].items[0]),
                           c_string(it[4].items[1])],
            "mnum": it[5].text,
            "allow": c_mask(it[8]),
            "self": c_mask(it[9]),
            "attrmin": [c_int(x) for x in it[12].items],
            "attrmax": [c_int(x) for x in it[13].items],
            "hpadv": [c_int(x) for x in it[14].items],
            "enadv": [c_int(x) for x in it[15].items],
        })
    return out


# --- inventaires (src/u_init.c) --------------------------------------------

def parse_kit(text, name):
    """Objets du tableau trobj name : liste de dicts, ou None."""
    pos = find_array(text, name)
    if pos is None:
        return None
    out = []
    for g in parse_init(text, pos).items:
        it = g.items
        if it[0].text == "0":
            break
        spe = it[1].text
        bless = it[5].text
        out.append({"otyp": it[0].text,
                    "spe": None if spe == "UNDEF_SPE" else c_int(it[1]),
                    "cls": it[2].text,
                    "qmin": c_int(it[3]), "qmax": c_int(it[4]),
                    "bless": None if bless == "UNDEF_BLESS"
                    else c_int(it[5])})
    return out


def kit_c(name, items):
    """Texte C du tableau d'inventaire."""
    lines = ["static const struct trobj %s[] = {" % name]
    for o in items:
        lines.append("    { %s, %s, %s, %d, %d, %s }," % (
            o["otyp"], "UNDEF_SPE" if o["spe"] is None else o["spe"],
            o["cls"], o["qmin"], o["qmax"],
            "UNDEF_BLESS" if o["bless"] is None else o["bless"]))
    lines.append("    { 0, 0, 0, 0, 0, 0 }")
    lines.append("};")
    return "\n".join(lines) + "\n"


# --- objets (include/objects.h) --------------------------------------------

def parse_objects(text):
    """Objets du jeu : [{sn, name, cls, desc}] dans l'ordre de objects.h
    (sans les objets interdits au départ)."""
    out = []
    macros = "|".join(sorted(MACRO_CLASS, key=len, reverse=True))
    for mo in re.finditer(r"^(%s|OBJECT)\(" % macros, text, re.M):
        macro = mo.group(1)
        # fin de l'appel : parenthèses équilibrées
        depth, i = 0, mo.end() - 1
        while i < len(text):
            c = text[i]
            if c == '"':
                i = text.index('"', i + 1)
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        call = re.sub(r"/\*.*?\*/", "", text[mo.end():i], flags=re.S)
        strs = re.findall(r'"((?:\\.|[^"\\])*)"', call)
        sn = re.findall(r"(\w+)\s*$", call.strip())
        if not strs or not sn:
            continue
        sn = sn[0]
        if macro == "OBJECT":
            cm = re.search(r"\b([A-Z]+_CLASS)\b", call)
            cls = cm.group(1) if cm else None
        else:
            cls = MACRO_CLASS[macro]
        if cls not in CLASS_FR or sn in FORBIDDEN_OBJECTS:
            continue
        desc = strs[1] if len(strs) > 1 and macro not in (
            "RING", "WAND", "FOOD", "COIN") else None
        if macro in ("RING", "WAND"):
            desc = strs[1] if len(strs) > 1 else None
        out.append({"sn": sn, "name": strs[0], "cls": cls, "desc": desc})
    return out


# --- traductions (fichiers .po) ---------------------------------------------

def _po_unquote(parts):
    s = "".join(parts)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                       .get(n, n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_po(text):
    """{(contexte ou None, msgid): msgstr} ; pour un pluriel, msgstr[0]."""
    out = {}
    for block in re.split(r"\n\s*\n", text):
        cur, vals = None, {}
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            mo = re.match(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[\d\])?)'
                          r'\s+"(.*)"$', line)
            if mo:
                cur = mo.group(1)
                vals[cur] = [mo.group(2)]
            elif line.startswith('"') and cur:
                vals[cur].append(line[1:-1])
        if "msgid" not in vals:
            continue
        ctx = _po_unquote(vals["msgctxt"]) if "msgctxt" in vals else None
        msgstr = vals.get("msgstr") or vals.get("msgstr[0]") or [""]
        out[(ctx, _po_unquote(vals["msgid"]))] = _po_unquote(msgstr)
    return out


def parse_po_refs(text):
    """{(contexte ou None, msgid): [références « fichier:ligne »]} d'après
    les commentaires « #: » (de nethack.pot)."""
    out = {}
    for block in re.split(r"\n\s*\n", text):
        refs = []
        for line in block.split("\n"):
            if line.startswith("#: "):
                refs += line[3:].split()
        if not refs:
            continue
        key = parse_po(block)
        for k in key:
            out[k] = refs
    return out


class Names:
    """Noms traduits selon le thème : cyber (fr@cyber.po, puis fr.po),
    fr (fr.po) ou en (le texte anglais)."""

    def __init__(self, fr=None, cyber=None):
        self.fr = fr or {}
        self.cyber = cyber or {}

    def get(self, msgid, ctx=None, theme="cyber"):
        if msgid is None:
            return None
        if theme == "en":
            return msgid
        if theme == "cyber":
            v = self.cyber.get((ctx, msgid))
            if v and v not in ("m", "f"):
                return v
        v = self.fr.get((ctx, msgid))
        return v or msgid

    def role(self, role, gender, theme="cyber"):
        m, f = role["name"]
        if gender == "female":
            return self.get(f, None, theme) if f else \
                self.get(m, "feminine", theme)
        return self.get(m, None, theme)

    def rank(self, role, i, gender, theme="cyber"):
        """Titre du rang i (dans le jeu, le rang précédent sert si le
        titre est vide)."""
        for j in range(i, -1, -1):
            m, f = role["ranks"][j]
            if gender == "female" and f:
                return self.get(f, None, theme)
            if m:
                return self.get(m, "feminine", theme) if gender == "female" \
                    else self.get(m, None, theme)
        return self.role(role, gender, theme)

    def race(self, race, gender, theme="cyber"):
        noun = race["noun"]
        if gender == "female":
            v = self.get(noun, "feminine", theme)
            if v != noun or theme == "en":
                return v
        return self.get(noun, None, theme)

    def obj(self, o, theme="cyber"):
        return self.get(o["name"], "object", theme)

    def monster(self, name, theme="cyber"):
        return self.get(name, "monster", theme)


# --- rôles modifiés ----------------------------------------------------------

# champs d'un rôle que l'éditeur peut changer (absents : valeur du jeu)
ROLE_FIELDS = ["ranks_en", "ranks_fr", "ranks_cyber", "gods", "allow",
               "attrbase", "attrdist", "hp", "en", "kits", "gold",
               "intrinsics", "petnum", "tile_male", "tile_female"]


def role_key(role):
    """Clé d'un rôle dans le projet : son identifiant PM_ sans PM_."""
    return role["mnum"][3:]


def ranks_table(role, names):
    """Titres du jeu : 9 x [en_m, en_f, fr_m, fr_f, cy_m, cy_f] (le
    titre féminin anglais est vide quand le jeu n'en a pas)."""
    out = []
    for m, f in role["ranks"]:
        row = [m or "", f or ""]
        for th in ("fr", "cyber"):
            row.append(names.get(m, None, th) if m else "")
            row.append((names.get(f, None, th) if f else
                        names.get(m, "feminine", th)) if m else "")
        out.append(row)
    return out


def effective(role, mod, names=None):
    """Valeurs du rôle après les modifications mod (dict)."""
    mod = mod or {}
    out = {
        "allow": set(mod["allow"]) if "allow" in mod else set(role["allow"]),
        "attrbase": list(mod.get("attrbase", role["attrbase"])),
        "attrdist": list(mod.get("attrdist", role["attrdist"])),
        "hp": list(mod.get("hp", role["hpadv"][:2])),
        "en": list(mod.get("en", role["enadv"][:2])),
        "gods": list(mod.get("gods", role["gods"])),
        "gold": mod.get("gold"),
        "intrinsics": list(mod.get("intrinsics", [])),
        "petnum": mod.get("petnum", role["petnum"]),
    }
    return out


def role_with(role, mod):
    """Le rôle avec l'animal imposé de mod (pour les options du héros)."""
    if not role or "petnum" not in (mod or {}):
        return role
    return dict(role, petnum=mod["petnum"])


def pet_monster(petnum, robots=()):
    """Nom anglais du monstre PM_… (robots : [(PM_…, nom)]), ou ""."""
    if petnum == NO_PET:
        return ""
    if petnum in PET_OF_PM:
        return PET_MONSTER[PET_OF_PM[petnum]]
    return dict(robots).get(petnum) or petnum[3:].lower().replace("_", " ")


def allowed(role_allow, race, gender=None, align=None):
    """La combinaison est-elle permise par le rôle et la race ?"""
    if not race["self"] & role_allow:
        return False
    if gender and (GENDER_BIT[gender] not in role_allow or
                   GENDER_BIT[gender] not in race["allow"]):
        return False
    if align and (ALIGN_BIT[align] not in role_allow or
                  ALIGN_BIT[align] not in race["allow"]):
        return False
    return True


def combos(role_allow, races):
    """[(race, genre, alignement)] permis."""
    return [(r["noun"], g, a) for r in races for g in GENDERS
            for a in ALIGNS if allowed(role_allow, r, g, a)]


def attr_range(base, race):
    """(min, max) d'un attribut au départ : la base du rôle, bornée par
    la race ; au plus 18 (init_attr répartit 75 points en tout)."""
    lo = max(base[0], race[0])
    return lo, max(lo, race[1])


def attr_text(v, attr=0):
    """Valeur d'un attribut ; 18/xx pour la force (attr 0)."""
    if v > 18 and attr == 0:
        return "18/%02d" % (v - 18) if v < 118 else "18/**"
    return str(v)


def start_hp(role_hp, race):
    """(minimum, maximum) des PV au départ : newhp() au niveau 0."""
    fix = role_hp[0] + race["hpadv"][0]
    rnd = role_hp[1] + race["hpadv"][1]
    return fix + (1 if role_hp[1] else 0) + (1 if race["hpadv"][1] else 0), \
        fix + rnd


def start_en(role_en, race):
    fix = role_en[0] + race["enadv"][0]
    rnd = role_en[1] + race["enadv"][1]
    return fix + (1 if role_en[1] else 0) + (1 if race["enadv"][1] else 0), \
        fix + rnd


# --- héros --------------------------------------------------------------------

def new_hero():
    return {
        "name": "", "role": "VALKYRIE", "race": "human",
        "gender": "female", "align": "neutral", "pet": "",
        "petname": "", "fruit": "", "conducts": [], "story": "",
        "notes": "", "windowtype": "", "symset": "", "autopickup": "",
        "colors": "",
    }


def normalize(h):
    out = new_hero()
    for k, v in (h or {}).items():
        if k in out and isinstance(v, type(out[k])):
            out[k] = v
    out["conducts"] = [c for c in out["conducts"]
                       if c in dict(CONDUCTS)]
    for k, choices in (("autopickup", AUTOPICKUP), ("colors", COLORS)):
        if out[k] not in dict(choices):
            out[k] = ""
    for k in ("windowtype", "symset"):
        if not re.match(r"^[A-Za-z0-9_]*$", out[k]):
            out[k] = ""
    return out


def normalize_mod(mod):
    """Modifications d'un rôle : seules les clés connues et bien formées
    sont gardées."""
    out = {}
    for k in ROLE_FIELDS:
        if k not in (mod or {}):
            continue
        v = mod[k]
        if k in ("attrbase", "attrdist") and isinstance(v, list) and \
                len(v) == 6 and all(isinstance(x, int) for x in v):
            out[k] = v
        elif k in ("hp", "en") and isinstance(v, list) and len(v) == 2:
            out[k] = [int(x) for x in v]
        elif k == "gods" and isinstance(v, list) and len(v) == 3:
            out[k] = [str(x) for x in v]
        elif k == "allow" and isinstance(v, list):
            out[k] = sorted(str(x) for x in v)
        elif k.startswith("ranks_") and isinstance(v, list) and len(v) == 9:
            out[k] = [[str(a), str(b)] for a, b in v]
        elif k == "kits" and isinstance(v, dict):
            out[k] = {n: [normalize_item(o) for o in items]
                      for n, items in v.items() if isinstance(items, list)}
        elif k == "gold" and (v is None or isinstance(v, int)):
            out[k] = v
        elif k == "petnum" and isinstance(v, str) and \
                re.fullmatch(r"NON_PM|PM_[A-Z0-9_]+", v):
            out[k] = v
        elif k == "intrinsics" and isinstance(v, list):
            out[k] = [x for x in v if x in INTRINSIC_FR]
        elif k.startswith("tile_") and isinstance(v, list) and \
                len(v) == TILE_SIZE:
            out[k] = [str(r) for r in v]
    return out


def normalize_item(o):
    return {"otyp": str(o.get("otyp", UNDEF_TYP)),
            "spe": o.get("spe") if isinstance(o.get("spe"), int) else None,
            "cls": str(o.get("cls", "WEAPON_CLASS")),
            "qmin": int(o.get("qmin", 1)), "qmax": int(o.get("qmax", 1)),
            "bless": o.get("bless") if o.get("bless") in (0, 1) else None}


def valid_name(name):
    """Le nom du héros est-il accepté par le jeu (option name) ?"""
    return bool(name) and len(name) <= 31 and \
        not re.search(r"[-,:=/\\\x00-\x1f]", name)


def hero_options(h, role, race):
    """Options NetHack du héros (NETHACKOPTIONS ou .nethackrc)."""
    opts = ["name:" + h["name"]] if h["name"] else []
    opts += ["role:" + role["name"][0], "race:" + race["noun"],
             "gender:" + h["gender"], "alignment:" + h["align"]]
    if h["pet"]:
        opts.append("pettype:" + h["pet"])
    if h["petname"] and h["pet"] != "none":
        pet = h["pet"] or PET_OF_PM.get(role["petnum"])
        keys = [PET_NAME_OPTION[pet]] if pet else \
            [] if role["petnum"] != NO_PET else ["catname", "dogname"]
        opts += ["%s:%s" % (k, h["petname"]) for k in keys]
    if h["fruit"]:
        opts.append("fruit:" + h["fruit"])
    opts += h["conducts"]
    return opts


def display_options(h):
    """Options du profil d'affichage (sauf windowtype, passée à part :
    -w sur la ligne de commande, première ligne d'un .nethackrc)."""
    opts = []
    if h["symset"]:
        opts.append("symset:" + h["symset"])
    if h["autopickup"] == "off":
        opts.append("!autopickup")
    elif h["autopickup"]:
        opts += ["autopickup", "pickup_types:" +
                 PICKUP_TYPES[h["autopickup"]]]
    if h["colors"] == "nightcity":
        opts += ["color", "menucolors", "statushilites:10"] + \
            ["hilite_status:" + r for r in NIGHTCITY_HILITES]
    return opts


def display_lines(h):
    """Lignes de configuration du profil qui ne passent pas par
    NETHACKOPTIONS (règles MENUCOLOR)."""
    if h["colors"] == "nightcity":
        return ["MENUCOLOR=" + r for r in NIGHTCITY_MENUCOLORS]
    return []


def nethackrc(h, role, race, names, theme="cyber"):
    """Fragment de .nethackrc du héros (windowtype d'abord, comme le
    demande le jeu)."""
    lines = ["# %s — %s, %s, %s (nhheroedit)" % (
        h["name"] or "?", names.role(role, h["gender"], theme),
        names.race(race, h["gender"], theme), ALIGN_FR[h["align"]])]
    if h["windowtype"]:
        lines.append("OPTIONS=windowtype:" + h["windowtype"])
    for o in hero_options(h, role, race) + display_options(h):
        lines.append("OPTIONS=" + o)
    lines += display_lines(h)
    return "\n".join(lines) + "\n"


# autres noms d'options (optlist.h)
OPTION_ALIASES = {"colour": "color", "align": "alignment",
                  "character": "role", "pet": "pettype"}


def option_name(item):
    """Nom de l'option d'un élément d'OPTIONS= (« !autopickup »,
    « nolegacy », « name:Kai ») : en minuscules, alias résolus."""
    name = item.strip().lstrip("!").split(":", 1)[0].strip().lower()
    return OPTION_ALIASES.get(name, name)


def full_rc(base, h, role, race, names, theme="cyber", extra="",
            source="~/.nethackrc"):
    """Fichier d'options complet : windowtype du héros, puis le texte
    base (votre .nethackrc) et les options extra (NETHACKOPTIONS), puis
    le héros. Les options de base que le héros redéfinit sont mises en
    commentaire (le jeu refuse une option donnée deux fois)."""
    hero = nethackrc(h, role, race, names, theme).splitlines()
    head = [l for l in hero if l.startswith("OPTIONS=windowtype:")]
    hero = [l for l in hero if l not in head]
    mine = {option_name(l[len("OPTIONS="):]) for l in head + hero
            if l.startswith("OPTIONS=")}

    def redefined(item):
        n = option_name(item)
        return n in mine or (n.startswith("no") and n[2:] in mine)

    out = ["# Fichier d'options complet de %s (nhheroedit) :" % (
        h["name"] or "?"),
        "#   %s, puis les options du héros." % source,
        "# Pour jouer : NETHACKOPTIONS=@<ce fichier> nethack"] + head + [""]
    lines = base.splitlines()
    if extra:
        lines += ["", "# NETHACKOPTIONS", "OPTIONS=" + extra]
    for line in lines:
        mo = re.match(r"^\s*OPTIONS?\s*=\s*(.*)$", line, re.I)
        if not mo:
            out.append(line)
            continue
        items = mo.group(1).split(",")
        keep = [i for i in items if not redefined(i)]
        if len(keep) == len(items):
            out.append(line)
            continue
        out.append("# nhheroedit, redéfini par le héros : " + line.strip())
        if [i for i in keep if i.strip()]:
            out.append("OPTIONS=" + ",".join(keep))
    return "\n".join(out + [""] + hero) + "\n"


def kit_problems(items, objects):
    """Problèmes d'un inventaire : [(gravité, message)]."""
    out = []
    by_sn = {o["sn"]: o for o in objects}
    if len(items) > MAX_KIT:
        out.append(("erreur", _("plus de %d objets au départ") % MAX_KIT))
    for i, o in enumerate(items):
        n = i + 1
        if o["otyp"] != UNDEF_TYP:
            ob = by_sn.get(o["otyp"])
            if not ob:
                out.append(("erreur", _("objet %d : %s inconnu du jeu")
                            % (n, o["otyp"])))
            elif ob["cls"] != o["cls"]:
                out.append(("erreur", _("objet %d : classe %s au lieu de %s")
                            % (n, o["cls"], ob["cls"])))
        if not 1 <= o["qmin"] <= o["qmax"] <= 127:
            out.append(("erreur", _("objet %d : quantité %d à %d invalide "
                                    "(1 à 127, min ≤ max)") %
                        (n, o["qmin"], o["qmax"])))
        if o["spe"] is not None and not -127 <= o["spe"] <= 127:
            out.append(("erreur", _("objet %d : enchantement hors limites")
                        % n))
        if o["spe"] is not None and abs(o["spe"]) > 7 and \
                o["cls"] in ("WEAPON_CLASS", "ARMOR_CLASS"):
            out.append(("attention", _("objet %d : enchantement %+d très "
                                       "élevé (risque d'évaporation)")
                        % (n, o["spe"])))
    return out


def validate(h, role, race, mod, objects, others=()):
    """Problèmes du héros (et de son rôle modifié) : [(gravité, msg)]."""
    out = []
    if not valid_name(h["name"]):
        out.append(("erreur", _("nom du héros vide, trop long (31 "
                                "caractères) ou avec - , : = / \\")))
    elif any(ord(c) > 127 for c in h["name"]):
        out.append(("attention", _("nom avec accents : le jeu peut le "
                                   "refuser ou le modifier (fichier de "
                                   "sauvegarde)")))
    if role is None:
        return out + [("erreur", _("rôle %s absent du jeu") % h["role"])]
    if race is None:
        return out + [("erreur", _("race %s absente du jeu") % h["race"])]
    eff = effective(role, mod)
    if not allowed(eff["allow"], race):
        out.append(("erreur", _("le rôle n'accepte pas cette race")))
    else:
        if not allowed(eff["allow"], race, h["gender"]):
            out.append(("erreur", _("ce sexe n'est pas permis pour ce rôle "
                                    "ou cette race")))
        if not allowed(eff["allow"], race, None, h["align"]):
            out.append(("erreur", _("cet alignement n'est pas permis pour "
                                    "ce rôle ou cette race")))
    if any(o["name"] == h["name"] for o in others if h["name"]):
        out.append(("attention", _("un autre héros du projet porte ce nom "
                                   "(même partie sauvegardée)")))
    petnum = eff["petnum"]
    if h["pet"] and h["pet"] != "none" and petnum != NO_PET:
        out.append(("attention", _("le rôle a un animal imposé (%s) : "
                                   "l'option pettype est sans effet")
                    % pet_monster(petnum)))
    if h["petname"] and h["pet"] != "none" and petnum != NO_PET and \
            petnum not in PET_OF_PM:
        out.append(("attention", _("le jeu ne nomme que le chaton, le petit "
                                   "chien et le poney : %s restera sans "
                                   "nom") % pet_monster(petnum)))
    if h["fruit"] and len(h["fruit"]) > 31:
        out.append(("erreur", _("nom du fruit trop long (31 caractères)")))
    if re.search(r"[,:]", h["fruit"] + h["petname"]):
        out.append(("erreur", _("« , » et « : » sont interdits dans le "
                                "nom de l'animal et du fruit")))
    out += role_problems(role, race, mod, objects)
    return out


def role_problems(role, race, mod, objects):
    out = []
    if not mod:
        return out
    eff = effective(role, mod)
    if sum(eff["attrdist"]) != 100:
        out.append(("attention", _("répartition des attributs : total %d au "
                                   "lieu de 100") % sum(eff["attrdist"])))
    if sum(eff["attrbase"]) > 75:
        out.append(("erreur", _("attributs de base : total %d, plus que les "
                                "75 points du jeu") % sum(eff["attrbase"])))
    if any(not 3 <= v <= 18 for v in eff["attrbase"]):
        out.append(("erreur", _("un attribut de base doit aller de 3 à 18")))
    if any(not 0 <= v <= 100 for v in eff["attrdist"]):
        out.append(("erreur", _("une répartition doit aller de 0 à 100")))
    if not any(b in eff["allow"] for b in RACE_BITS):
        out.append(("erreur", _("le rôle n'accepte plus aucune race")))
    if not any(GENDER_BIT[g] in eff["allow"] for g in GENDERS):
        out.append(("erreur", _("le rôle n'accepte plus aucun sexe")))
    if not any(ALIGN_BIT[a] in eff["allow"] for a in ALIGNS):
        out.append(("erreur", _("le rôle n'accepte plus aucun alignement")))
    if eff["hp"][0] < 1 or eff["hp"][0] + eff["hp"][1] > 100:
        out.append(("erreur", _("PV de départ du rôle : 1 à 100")))
    if eff["en"][0] < 0 or eff["en"][0] + eff["en"][1] > 100:
        out.append(("erreur", _("énergie de départ du rôle : 0 à 100")))
    if eff["gold"] is not None and not 0 <= eff["gold"] <= 100000:
        out.append(("erreur", _("or de départ : 0 à 100000")))
    for g in eff["gods"]:
        if not g.strip("_ ") or re.search(r'["\\]', g):
            out.append(("erreur", _("nom de dieu vide ou avec \" \\")))
    for k in ("ranks_en", "ranks_fr", "ranks_cyber"):
        for i, (m, f) in enumerate(mod.get(k, [])):
            if k == "ranks_en" and not m.strip():
                out.append(("erreur", _("rang %d : titre anglais masculin "
                                        "vide") % (i + 1)))
            if re.search(r'["\\\n]', m + f):
                out.append(("erreur", _("rang %d : caractère interdit")
                            % (i + 1)))
    for name, items in mod.get("kits", {}).items():
        out += [(g, "%s : %s" % (name, m))
                for g, m in kit_problems(items, objects)]
    for g in GENDERS:
        t = mod.get("tile_" + g)
        if t and any(len(r) != TILE_SIZE or set(r) - TILE_CHARS for r in t):
            out.append(("erreur", _("tuile %s mal formée") % GENDER_FR[g]))
    return out


def blank_tile():
    return ["." * TILE_SIZE for _i in range(TILE_SIZE)]


# --- tuile en image (e dans l'éditeur de pixels) ----------------------------

TILE_SCALE = 8      # une case de la tuile = 8x8 pixels


def tile_png(tile, scale=TILE_SCALE):
    """PNG (RVB, sans bibliothèque) de la tuile agrandie."""
    rgb = dict(TILE_PALETTE)
    raw = b""
    for r in tile:
        line = b"\0" + b"".join(bytes(rgb[c]) * scale for c in r)
        raw += line * scale

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xffffffff)
    w, h = len(tile[0]) * scale, len(tile) * scale
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def tile_svg(tile, scale=TILE_SCALE, title=""):
    """SVG de la tuile : un rectangle par suite de cases de même couleur."""
    rgb = dict(TILE_PALETTE)
    w, h = len(tile[0]) * scale, len(tile) * scale
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" shape-rendering="crispEdges">'
           % (w, h, len(tile[0]), len(tile))]
    if title:
        out.append("<title>%s</title>" % title.replace("&", "&amp;")
                   .replace("<", "&lt;"))
    for y, r in enumerate(tile):
        x = 0
        while x < len(r):
            n = 1
            while x + n < len(r) and r[x + n] == r[x]:
                n += 1
            out.append('<rect x="%d" y="%d" width="%d" height="1" '
                       'fill="#%02x%02x%02x"/>' % ((x, y, n) + rgb[r[x]]))
            x += n
    out.append("</svg>")
    return "\n".join(out) + "\n"
