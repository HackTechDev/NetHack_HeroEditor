"""Tests de nhheroedit : lecture des tables du jeu, combinaisons permises,
options du héros, projets, et intégration dans une copie des sources
(écriture, relecture, retrait à l'identique, compilation des fichiers C
et des traductions).

python3 -m unittest discover -s tests   (depuis le dossier de l'éditeur)
Les sources sont cherchées dans ../NetHack-5.0.0 ou $NHHEROEDIT_SRC.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["NHHEROEDIT_LANG"] = "fr"     # messages vérifiés en français

import nhhero_config as C  # noqa: E402
import nhhero_data as D  # noqa: E402
import nhhero_game as G  # noqa: E402
import nhhero_install as I  # noqa: E402
import nhhero_project as P  # noqa: E402
import nhhero_templates as T  # noqa: E402
import nhheroedit as E  # noqa: E402

SRC = os.environ.get("NHHEROEDIT_SRC") or os.path.normpath(
    os.path.join(HERE, "..", "..", "NetHack-5.0.0"))
HAVE_SRC = I.check_tree(SRC) is None


def copy_tree(dest):
    """Copie des seuls fichiers lus ou écrits par l'éditeur."""
    for rel in I.ALL_FILES + [I.MONSTERS_H, I.OBJECTS_H]:
        p = os.path.join(SRC, rel)
        if os.path.isfile(p):
            q = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.copy2(p, q)
    return dest


class TestParser(unittest.TestCase):
    def test_initializer(self):
        text = 'x[] = { { N_("a"), 0 }, /* c */ 3 | B,\n#if 0\n{ 9 },\n' \
               '#endif\n "s\\"t" };'
        g = D.parse_init(text, text.index("{"))
        self.assertEqual(len(g.items), 3)
        self.assertEqual(D.c_string(g.items[0].items[0]), "a")
        self.assertIsNone(D.c_string(g.items[0].items[1]))
        self.assertEqual(D.c_mask(g.items[1]), {"3", "B"})
        self.assertEqual(D.c_string(g.items[2]), 's"t')

    def test_po_multiline(self):
        """Une traduction sur plusieurs lignes est remplacée sans entrée en
        double, et rendue à l'identique au retrait."""
        po = ('msgid "A"\nmsgstr "a"\n\n#, c-format\nmsgctxt "feminine"\n'
              'msgid "B"\nmsgstr ""\n"long "\n"titre"\n')
        t = I.po_set(I.po_set(po, "feminine", "B", "neuf"), None, "A", "aa")
        self.assertEqual(t.count('msgid "B"'), 1)
        self.assertEqual(D.parse_po(t), {(None, "A"): "aa",
                                         ("feminine", "B"): "neuf"})
        self.assertEqual(I.strip_po(t), po)
        self.assertEqual(I.po_set(po, "feminine", "B", "long titre"), po)

    def test_strength(self):
        self.assertEqual(D.c_int(D.Leaf("STR18(100)", 0, 0)), 118)
        self.assertEqual(D.attr_text(118), "18/**")
        self.assertEqual(D.attr_text(68), "18/50")

    def test_po(self):
        po = D.parse_po('msgid "a"\nmsgstr "b"\n\nmsgctxt "feminine"\n'
                        'msgid "a"\nmsgstr ""\n"c"\n')
        self.assertEqual(po[(None, "a")], "b")
        self.assertEqual(po[("feminine", "a")], "c")

    def test_names(self):
        self.assertTrue(D.valid_name("Kestrel"))
        for bad in ("", "a-b", "a,b", "x" * 32):
            self.assertFalse(D.valid_name(bad), bad)


@unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
class TestGameData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = I.GameData(SRC)

    def test_tables(self):
        self.assertEqual(len(self.g.roles), 13)
        self.assertEqual([r["noun"] for r in self.g.races],
                         ["human", "elf", "dwarf", "gnome", "orc"])
        for r in self.g.roles:
            self.assertEqual(len(r["ranks"]), 9)
            self.assertEqual(sum(r["attrdist"]), 100, r["name"])
            self.assertTrue(self.g.kit_names(r), r["name"])
            self.assertIn(r["mnum"], self.g.tile_names)
            for g in D.GENDERS:
                self.assertEqual(len(self.g.tile(r, g)), D.TILE_SIZE)

    def test_kits_known_objects(self):
        for name, items in self.g.kits.items():
            for o in items:
                if o["otyp"] != D.UNDEF_TYP:
                    self.assertIn(o["otyp"], self.g.by_sn, name)
            self.assertEqual(D.kit_problems(items, self.g.objects), [],
                             name)

    def test_combos_match_game(self):
        """Les combinaisons connues du jeu."""
        val = self.g.role("VALKYRIE")
        self.assertEqual(D.combos(val["allow"], self.g.races), [
            ("human", "female", "lawful"), ("human", "female", "neutral"),
            ("dwarf", "female", "lawful")])
        wiz = self.g.role("WIZARD")
        elf = self.g.race("elf")
        self.assertTrue(D.allowed(wiz["allow"], elf, "male", "chaotic"))
        self.assertFalse(D.allowed(wiz["allow"], elf, "male", "neutral"))

    def test_cyber_names(self):
        n = self.g.names
        val = self.g.role("VALKYRIE")
        self.assertEqual(n.role(val, "female", "cyber"), "Solo")
        self.assertEqual(n.role(val, "female", "en"), "Valkyrie")
        self.assertEqual(n.rank(val, 0, "female", "cyber"), "Gamine")
        self.assertEqual(n.race(self.g.race("elf"), "male", "cyber"),
                         "réplicant")
        self.assertEqual(n.monster("kitten", "cyber"), "chaton-robot")

    def test_templates_valid(self):
        for i in range(len(T.TEMPLATES)):
            h = T.from_template(i)
            res = D.validate(h, self.g.role(h["role"]),
                             self.g.race(h["race"]), {}, self.g.objects)
            self.assertEqual(res, [], h["name"])

    def test_start_values(self):
        val, hum = self.g.role("VALKYRIE"), self.g.race("human")
        self.assertEqual(D.start_hp(val["hpadv"][:2], hum), (16, 16))

    def test_options(self):
        h = T.from_template(1)      # Netrunner : chaton imposé par le rôle
        role, race = self.g.role(h["role"]), self.g.race(h["race"])
        opts = D.hero_options(h, role, race)
        self.assertIn("role:Wizard", opts)
        self.assertIn("catname:Bitmap", opts)
        cmd = G.game_command("/jeu", h, role, race, "-X")
        self.assertIn("NETHACKOPTIONS=", cmd)
        self.assertTrue(cmd.endswith("-u Glitch -X"))


@unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = copy_tree(self.tmp)
        self.g = I.GameData(self.src)
        val = self.g.role("VALKYRIE")
        tab = D.ranks_table(val, self.g.names)
        en = [r[:2] for r in tab]
        en[0] = ["Shieldmaiden", ""]
        cy = [r[4:6] for r in tab]
        cy[0] = ["Lame", "Lame"]
        fr = [r[2:4] for r in tab]
        fr[1] = ["Guetteur", "Guetteuse"]
        kit = self.g.kits["Valkyrie"] + [{
            "otyp": "BROADSWORD", "spe": 2, "cls": "WEAPON_CLASS",
            "qmin": 1, "qmax": 1, "bless": 1}]
        self.mods = {
            "VALKYRIE": {
                "ranks_en": en, "ranks_fr": fr, "ranks_cyber": cy,
                "gods": ["Tyr", "Odin", "_Freyja"],
                "allow": sorted(val["allow"] | {"MH_ELF", "ROLE_MALE",
                                                "ROLE_CHAOTIC"}),
                "attrbase": [12, 7, 7, 7, 10, 7], "hp": [16, 1],
                "en": [3, 2], "gold": 300,
                "intrinsics": ["HFast", "HTelepat"],
                "kits": {"Valkyrie": kit},
                "tile_female": ["N" * 16] * 16},
            "BARBARIAN": {"kits": {"Barbarian_1": kit[:2]}},
        }

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def originals(self):
        return {rel: I._read(self.src, rel) for rel in I.ALL_FILES}

    def test_roundtrip(self):
        orig = self.originals()
        ch, _bk = I.install(self.src, self.mods)
        self.assertEqual(sorted(ch), sorted(I.ALL_FILES))
        keys = I.installed_keys(self.src)
        for k in ("VALKYRIE", "kit:Valkyrie", "kit:Barbarian_1", "start",
                  "tile:valkyrie,female"):
            self.assertIn(k, keys)
        # relecture : le jeu d'origine est retrouvé sous les modifications
        g2 = I.GameData(self.src)
        self.assertEqual(g2.role("VALKYRIE")["ranks"],
                         self.g.role("VALKYRIE")["ranks"])
        self.assertEqual(g2.kits, self.g.kits)
        self.assertEqual(g2.names.get("Skirmisher", None, "fr"),
                         self.g.names.get("Skirmisher", None, "fr"))
        # une seconde intégration ne change rien
        self.assertEqual(I.install(self.src, self.mods)[0], [])
        # le retrait rend les fichiers à l'identique
        I.uninstall(self.src)
        self.assertEqual(self.originals(), orig)

    def test_written_values(self):
        files = I.plan(self.src, self.mods, self.g)
        role_c = files[I.ROLE_C]
        role = [r for r in D.parse_roles(role_c)
                if r["mnum"] == "PM_VALKYRIE"][0]
        self.assertEqual(role["ranks"][0], ["Shieldmaiden", None])
        self.assertEqual(role["gods"], ["Tyr", "Odin", "_Freyja"])
        self.assertIn("MH_ELF", role["allow"])
        self.assertEqual(role["attrbase"], [12, 7, 7, 7, 10, 7])
        self.assertEqual(role["hpadv"][:2], [16, 1])
        self.assertIn("u.umoney0 = 300L;", files[I.U_INIT_C])
        self.assertIn("HTelepat |= FROMOUTSIDE;", files[I.U_INIT_C])
        self.assertEqual(D.parse_kit(files[I.U_INIT_C], "Valkyrie"),
                         self.mods["VALKYRIE"]["kits"]["Valkyrie"])
        self.assertEqual(I.find_tile(files[I.TILES], "valkyrie", "female"),
                         ["N" * 16] * 16)
        fr = D.parse_po(files[I.PO_FR])
        cy = D.parse_po(files[I.PO_CYBER])
        self.assertEqual(fr[(None, "Skirmisher")], "Guetteur")
        self.assertEqual(fr[("feminine", "Skirmisher")], "Guetteuse")
        self.assertEqual(cy[(None, "Shieldmaiden")], "Lame")
        self.assertIn((None, "Shieldmaiden"),
                      D.parse_po(files[I.POT]))
        self.assertIn("gendered_word(rank_titl, innategend)",
                      files[I.INSIGHT_C])
        self.assertEqual(files[I.INSIGHT_C].count("nhheroedit:begin"), 2)

    def test_story(self):
        """Biographie : bloc ajouté à newgame() quand on le demande (ou
        qu'un rôle change), texte coupé en lignes pour le jeu."""
        files = I.plan(self.src, {}, self.g, story=True)
        self.assertIn('getenv("NHHEROEDIT_STORY")', files[I.ALLMAIN_C])
        self.assertEqual(I.plan(self.src, {}, self.g)[I.ALLMAIN_C],
                         I._read(self.src, I.ALLMAIN_C))
        h = T.from_template(0)
        text = I.story_text(h, 30)
        self.assertTrue(text.startswith("Kestrel\n\n"))
        self.assertTrue(all(len(l) <= 30 for l in text.split("\n")))
        self.assertEqual(I.story_text(dict(h, story=" ")), "")
        role, race = self.g.role(h["role"]), self.g.race(h["race"])
        self.assertIn("NHHEROEDIT_STORY=", G.game_command("/j", h, role,
                                                          race))

    def test_feminine_fix_only_for_ranks(self):
        """Le correctif du titre féminin n'est posé que si des titres de
        rang changent."""
        files = I.plan(self.src, {"VALKYRIE": {"gold": 5}}, self.g)
        self.assertEqual(files[I.INSIGHT_C],
                         I._read(self.src, I.INSIGHT_C))

    def test_same_feminine_title(self):
        """Un titre féminin identique au masculin n'est pas un titre
        féminin propre (sa traduction passe par msgctxt feminine)."""
        en = self.mods["VALKYRIE"]["ranks_en"]
        en[0] = ["Shieldmaiden", "Shieldmaiden"]
        files = I.plan(self.src, self.mods, self.g)
        self.assertIn('{ N_("Shieldmaiden"), 0 }', files[I.ROLE_C])
        cy = D.parse_po(files[I.PO_CYBER])
        self.assertEqual(cy[("feminine", "Shieldmaiden")], "Lame")

    def test_projects(self):
        """Le projet de chaque rôle intégré est noté dans role.c, relu,
        et retiré avec le reste."""
        orig = self.originals()
        home = os.path.expanduser("~/a/p.json")
        files = I.plan(self.src, self.mods, self.g,
                       {"VALKYRIE": home, "BARBARIAN": "/b/q.json",
                        "TOURIST": "/c/r.json"})
        self.assertIn(" *   VALKYRIE ~/a/p.json\n", files[I.ROLE_C])
        I.apply(self.src, files)
        self.assertEqual(I.installed_projects(self.src),
                         {"VALKYRIE": home, "BARBARIAN": "/b/q.json"})
        self.assertEqual(I.installed_roles(self.src, self.g),
                         {"VALKYRIE", "BARBARIAN"})
        self.assertEqual(D.parse_roles(files[I.ROLE_C])[0]["name"],
                         self.g.roles[0]["name"])
        I.uninstall(self.src)
        self.assertEqual(self.originals(), orig)
        self.assertEqual(I.installed_projects(self.src), {})

    def test_rank_conflicts(self):
        """Un titre anglais déjà employé par un autre rôle est signalé
        quand sa traduction change ; un titre neuf ne l'est pas."""
        self.assertEqual(I.rank_conflicts(self.g, self.mods), {})
        val = self.g.role("VALKYRIE")
        tab = D.ranks_table(val, self.g.names)
        en = [r[:2] for r in tab]
        en[0] = ["Rambler", ""]                 # titre du Touriste
        res = I.rank_conflicts(self.g, {"VALKYRIE": {"ranks_en": en}},
                               "en")
        self.assertEqual(len(res["VALKYRIE"]), 1)
        self.assertIn("Tourist", res["VALKYRIE"][0])
        # même titre, même traduction : rien à signaler
        fr = [r[2:4] for r in tab]
        cy = [r[4:6] for r in tab]
        tou = D.ranks_table(self.g.role("TOURIST"), self.g.names)
        fr[0], cy[0] = tou[0][2:4], tou[0][4:6]
        self.assertEqual(I.rank_conflicts(self.g, {"VALKYRIE": {
            "ranks_en": en, "ranks_fr": fr, "ranks_cyber": cy}}), {})
        # deux rôles du projet, deux traductions du même titre
        mods = {"VALKYRIE": {"ranks_en": en}, "TOURIST": {
            "ranks_fr": [["Flâneur", "Flâneuse"]] + [r[2:4]
                                                     for r in tou[1:]]}}
        res = I.rank_conflicts(self.g, mods)
        self.assertTrue(any("une seule traduction" in m
                            for m in res["VALKYRIE"]))

    @unittest.skipUnless(shutil.which("msgfmt"), "msgfmt absent")
    def test_po_compile(self):
        files = I.plan(self.src, self.mods, self.g)
        self.assertIsNone(I.check_po(self.src, files))

    @unittest.skipUnless(shutil.which("cc"), "compilateur C absent")
    def test_c_compiles(self):
        I.install(self.src, self.mods)
        for rel in (I.ROLE_C, I.U_INIT_C, I.INSIGHT_C, I.ALLMAIN_C):
            r = subprocess.run(
                ["cc", "-I" + os.path.join(SRC, "include"), "-Wall",
                 "-Wextra", "-Werror", "-DNOSTATICFN", "-c", "-o",
                 os.devnull, os.path.join(self.src, rel)],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])

    def test_bad_roles(self):
        self.assertRaises(I.InstallError, I.plan, self.src,
                          {"NOPE": {"gold": 1}}, self.g)
        val = self.g.role("VALKYRIE")
        res = D.role_problems(val, self.g.races[0],
                              {"attrbase": [18] * 6, "allow": []},
                              self.g.objects)
        self.assertTrue(any("75 points" in m for _g, m in res))
        self.assertTrue(any("aucune race" in m for _g, m in res))


class TestBuild(unittest.TestCase):
    def test_interfaces(self):
        """Les interfaces du dernier build viennent de dat/options ; make
        les reprend pour ne pas refaire un jeu tty seul."""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(G.build_interfaces(d), ([], None))
            os.makedirs(os.path.join(d, "dat"))
            with open(os.path.join(d, "dat", "options"), "w") as f:
                f.write('Supported windowing systems:\n\n    "tty" (text), '
                        '"curses"\n    (terminal), "X11", and "Qt", with a '
                        'default of "curses".\n\nNetHack 5.0\n')
            self.assertEqual(G.build_interfaces(d),
                             (["tty", "curses", "X11", "Qt"], "curses"))
            self.assertEqual(
                G.make_command(d, "", "-j2"),
                "make -j2 WANT_WIN_TTY=1 WANT_WIN_CURSES=1 WANT_WIN_X11=1 "
                "WANT_WIN_QT=1 WANT_DEFAULT=curses")
            self.assertEqual(G.make_command(d, "update", "-j2 WANT_WIN_ALL=1"),
                             "make update WANT_WIN_ALL=1")
            with open(os.path.join(d, "dat", "options"), "w") as f:
                f.write('Supported windowing system:\n\n    "tty" (text).'
                        '\n\nNetHack\n')
            self.assertEqual(G.build_interfaces(d), (["tty"], "tty"))


class TestGame(unittest.TestCase):
    def test_saves(self):
        """Sauvegarde trouvée par son nom exact, mise de côté, remise."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "save"))
            uid = os.getuid()
            for f in ("%dKestrel2" % uid, "%dDr_No.gz" % uid):
                open(os.path.join(d, "save", f), "w").close()
            self.assertIsNone(G.saved_game(d, "Kestrel"))
            p = G.saved_game(d, "Dr.No")
            self.assertTrue(p.endswith("%dDr_No.gz" % uid))
            aside = os.path.join(d, "aside")
            q = G.set_aside(p, "Dr.No", aside)
            self.assertIsNone(G.saved_game(d, "Dr.No"))
            self.assertEqual([x[1] for x in G.aside_games("Dr.No", aside)],
                             [q])
            self.assertEqual(G.put_back(q, d), p)
            self.assertEqual(G.aside_games("Dr.No", aside), [])
            q = G.set_aside(p, "Dr.No", aside)
            open(p, "w").close()
            self.assertIsNone(G.put_back(q, d))      # place prise

    def test_mode_allowed(self):
        """Droits des modes -D et -X lus dans sysconf, comme le jeu."""
        import pwd
        me = pwd.getpwuid(os.getuid()).pw_name
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(G.mode_allowed(d, "-D", "Kai"), (None, ""))
            with open(os.path.join(d, "sysconf"), "w") as f:
                f.write("# WIZARDS=*\nWIZARDS=root %s\nEXPLORERS=root\n"
                        % me)
            self.assertEqual(G.mode_allowed(d, "-D", "Kai"),
                             (True, "root " + me))
            self.assertFalse(G.mode_allowed(d, "-X", "Kai")[0])
            with open(os.path.join(d, "sysconf"), "a") as f:
                f.write("CHECK_PLNAME=1\nEXPLORERS=*\n")
            self.assertFalse(G.mode_allowed(d, "-D", "Kai")[0])
            self.assertTrue(G.mode_allowed(d, "-X", "Kai")[0])


class TestPet(unittest.TestCase):
    ROBOT = ("    /* nhmonedit:begin SECURITY_BOT */\n"
             "    MON(NAM(\"security bot\"), S_GOLEM,\n"
             "        LVL(6, 10, 4, 10, 0), (G_GENO | 2),\n"
             "        A(NO_ATTK, NO_ATTK, NO_ATTK, NO_ATTK, NO_ATTK, NO_ATTK),\n"
             "        SIZ(900, 0, MS_SOLDIER, MZ_MEDIUM), 0, 0,\n"
             "        M1_MINDLESS, M2_NEUTER, 0,\n"
             "        8, CLR_BRIGHT_BLUE, SECURITY_BOT),\n"
             "    /* nhmonedit:end SECURITY_BOT */\n")

    def test_model(self):
        role = {"petnum": "PM_LITTLE_DOG"}
        self.assertEqual(D.effective(dict(role, allow=[], attrbase=[],
                                          attrdist=[], hpadv=[0, 0],
                                          enadv=[0, 0], gods=[]),
                                     {"petnum": "PM_X"})["petnum"], "PM_X")
        self.assertEqual(D.normalize_mod({"petnum": "PM_SECURITY_BOT"}),
                         {"petnum": "PM_SECURITY_BOT"})
        self.assertEqual(D.normalize_mod({"petnum": "rm -rf"}), {})
        self.assertIs(D.role_with(role, {}), role)
        self.assertEqual(D.role_with(role, {"petnum": "PM_PONY"})["petnum"],
                         "PM_PONY")
        self.assertEqual(D.pet_monster("PM_KITTEN"), "kitten")
        self.assertEqual(D.pet_monster("PM_SECURITY_BOT"), "security bot")
        self.assertEqual(D.pet_monster("NON_PM"), "")

    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = copy_tree(tmp)
            p = os.path.join(d, I.MONSTERS_H)
            with open(p) as f:
                text = f.read()
            pos = text.index("    /*\n     * humans")
            with open(p, "w") as f:
                f.write(text[:pos] + self.ROBOT + text[pos:])
            self.assertEqual(I.editor_monsters(d),
                             [("PM_SECURITY_BOT", "security bot")])
            ids = I.monster_ids(d)
            self.assertTrue({"PM_KITTEN", "PM_SILVER_DRAGON",
                             "PM_SECURITY_BOT"} <= ids)
            out = I.plan(d, {"RANGER": {"petnum": "PM_SECURITY_BOT"}})
            self.assertIn("      PM_SECURITY_BOT,\n", out[I.ROLE_C])
            self.assertEqual(I.strip_c(out[I.ROLE_C]),
                             I.clean_text(d, I.ROLE_C))
            with self.assertRaises(I.InstallError):
                I.plan(d, {"RANGER": {"petnum": "PM_NOBODY"}})
        g = I.GameData(SRC)
        h = D.normalize({"name": "K", "role": "Ranger", "race": "human",
                         "gender": "female", "align": "neutral",
                         "petname": "Rex"})
        role = D.role_with(g.role("RANGER"), {"petnum": "PM_SECURITY_BOT"})
        self.assertFalse([o for o in D.hero_options(h, role, g.race("human"))
                          if "name:Rex" in o])
        self.assertTrue(any("sans nom" in m for _g, m in D.validate(
            h, g.role("RANGER"), g.race("human"),
            {"petnum": "PM_SECURITY_BOT"}, g.objects)))


class TestWeight(unittest.TestCase):
    def test_capacity(self):
        self.assertEqual(D.acurrstr(18), 18)
        self.assertEqual(D.acurrstr(18 + 50), 20)       # 18/50
        self.assertEqual(D.acurrstr(118), 21)           # 18/**
        self.assertEqual(D.capacity(10, 10), 550)
        self.assertEqual(D.capacity(118, 18), 1000)     # plafond
        self.assertEqual(D.encumbrance(550, 550), 0)
        self.assertEqual(D.encumbrance(551, 550), 1)
        self.assertEqual(D.encumbrance(900, 550), 2)
        self.assertEqual(D.gold_weight(800), 8)
        self.assertEqual(D.gold_weight(0), 0)

    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_kit(self):
        g = I.GameData(SRC)
        objs = {o["sn"]: o for o in g.objects}
        self.assertEqual(objs["TWO_HANDED_SWORD"]["wt"], 150)
        self.assertEqual(objs["RIN_ADORNMENT"]["wt"], 3)    # poids fixe
        self.assertEqual(objs["SPE_FORCE_BOLT"]["wt"], 50)
        val = g.kits["Valkyrie"]
        self.assertEqual(D.kit_weight([val], g.objects), (90, 90))
        rnd = [{"otyp": D.UNDEF_TYP, "cls": "RING_CLASS", "spe": None,
                "qmin": 2, "qmax": 2, "bless": None}]
        self.assertEqual(D.kit_weight([rnd], g.objects), (6, 6))
        self.assertEqual(D.kit_weight([val, rnd], g.objects, (800, 800)),
                         (14, 98))
        role, race = g.role("VALKYRIE"), g.race("human")
        h = D.normalize({"name": "K", "role": "VALKYRIE", "race": "human",
                         "gender": "female", "align": "neutral"})
        self.assertFalse([m for _g, m in D.validate(
            h, role, race, {}, g.objects, kits=[val]) if "chargé" in m])
        heavy = val + [{"otyp": "TWO_HANDED_SWORD", "cls": "WEAPON_CLASS",
                        "spe": 0, "qmin": 4, "qmax": 6, "bless": None}]
        msgs = [m for _g, m in D.validate(h, role, race, {}, g.objects,
                                          kits=[heavy])]
        self.assertTrue(any("peut commencer encombré" in m and "690-990" in m
                            for m in msgs), msgs)
        heavy[-1]["qmin"] = heavy[-1]["qmax"] = 10
        msgs = [m for _g, m in D.validate(h, role, race, {}, g.objects,
                                          kits=[heavy])]
        self.assertTrue(any("commence encombré quoi qu'il tire" in m
                            for m in msgs), msgs)


class TestTiles(unittest.TestCase):
    def test_layers(self):
        for name, layer in D.LAYERS:
            self.assertLessEqual(len(layer), D.TILE_SIZE, name)
            for line in layer:
                self.assertLessEqual(len(line), D.TILE_SIZE, name)
                self.assertFalse(set(line) - D.TILE_CHARS - {" "}, name)
        t = D.blank_tile()
        visor = D.apply_layer(t, D.LAYERS[0][1])
        self.assertEqual(visor[5], ".....BBBBBB.....")
        self.assertEqual(visor[:4], t[:4])
        moved = D.apply_layer(t, D.LAYERS[0][1], -1, 6)
        self.assertEqual(moved[4], "...........BBBBB")    # le reste sort
        self.assertEqual(D.apply_layer(t, ["A"], -1, 0), t)

    def test_direct_term(self):
        import nhhero_ui as U

        def yes(name):
            return name in ("xterm-direct", "tmux-direct")
        tc = {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
        self.assertEqual(U.direct_term(tc, None, yes), "xterm-direct")
        self.assertIsNone(U.direct_term(tc, False, yes))
        self.assertIsNone(U.direct_term({"TERM": "xterm-256color"},
                                        None, yes))
        self.assertEqual(U.direct_term({"TERM": "tmux-256color"}, True,
                                       yes), "tmux-direct")
        self.assertIsNone(U.direct_term({"TERM": "screen-256color"}, True,
                                        yes))
        self.assertIsNone(U.direct_term({"TERM": "xterm-direct",
                                         "COLORTERM": "truecolor"},
                                        None, yes))

    def test_images(self):
        import struct
        import zlib
        t = D.apply_layer(D.blank_tile(), D.LAYERS[0][1])
        png = D.tile_png(t, scale=2)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h = struct.unpack(">II", png[16:24])
        self.assertEqual((w, h), (32, 32))
        n = struct.unpack(">I", png[33:37])[0]
        self.assertEqual(png[37:41], b"IDAT")
        raw = zlib.decompress(png[41:41 + n])
        self.assertEqual(len(raw), 32 * (1 + 32 * 3))
        line = raw[10 * 97:11 * 97]         # ligne 10 = case 5 de la tuile
        self.assertEqual(tuple(line[1 + 3 * 10:1 + 3 * 11]), (0, 182, 255))
        svg = D.tile_svg(t, title="Solo <f>")
        self.assertIn("<title>Solo &lt;f></title>", svg)
        self.assertIn('<rect x="5" y="5" width="6" height="1" '
                      'fill="#00b6ff"/>', svg)


class TestDisplay(unittest.TestCase):
    def test_display_profile(self):
        """Profil d'affichage : options, règles MENUCOLOR, windowtype en
        tête du .nethackrc et en -w sur la ligne de commande."""
        h = T.from_template(0)
        self.assertEqual(D.display_options(h), [])
        h.update(windowtype="curses", symset="DECgraphics",
                 autopickup="gold", colors="nightcity")
        opts = D.display_options(h)
        self.assertEqual(opts[:3], ["symset:DECgraphics", "autopickup",
                                    "pickup_types:$"])
        self.assertIn("hilite_status:hitpoints/<33%/red&bold", opts)
        self.assertFalse(any(" " in o.split("/")[-1] for o in opts
                             if o.startswith("hilite")))
        self.assertTrue(D.display_lines(h)[0].startswith("MENUCOLOR="))
        h["autopickup"] = "off"
        self.assertIn("!autopickup", D.display_options(h))
        self.assertEqual(D.normalize(dict(h, colors="x", symset="a b"))[
            "colors"], "")
        self.assertEqual(D.normalize(dict(h, symset="a b"))["symset"], "")

    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_display_rc(self):
        g = I.GameData(SRC)
        h = T.from_template(0)
        h.update(windowtype="curses", colors="nightcity")
        role, race = g.role(h["role"]), g.race(h["race"])
        rc = D.nethackrc(h, role, race, g.names).splitlines()
        self.assertEqual(rc[1], "OPTIONS=windowtype:curses")
        self.assertTrue(rc[-1].startswith("MENUCOLOR="))
        cmd = G.game_command("/jeu", h, role, race, "-X")
        self.assertIn("nethack -wcurses -u Kestrel -X", cmd)


class TestFullRc(unittest.TestCase):
    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_full_rc(self):
        """Fichier complet : les options du joueur que le héros redéfinit
        sont mises en commentaire, les autres restent ; windowtype en
        tête."""
        g = I.GameData(SRC)
        h = T.from_template(0)
        h.update(windowtype="tty", autopickup="off")
        role, race = g.role(h["role"]), g.race(h["race"])
        base = ("# mon rc\nOPTIONS=windowtype:curses\n"
                "OPTIONS=name:util01,!legacy,autopickup,time\n"
                "OPTION=colour\nMENUCOLOR=\"x\"=red\n")
        rc = D.full_rc(base, h, role, race, g.names, extra="role:Wiz,news")
        lines = rc.splitlines()
        opts = [l for l in lines if l.startswith("OPTIONS=")]
        self.assertEqual(opts[0], "OPTIONS=windowtype:tty")
        self.assertIn("OPTIONS=!legacy,time", lines)
        self.assertIn("OPTIONS=news", lines)
        self.assertIn('MENUCOLOR="x"=red', lines)
        self.assertIn("OPTION=colour", lines)       # le héros n'y touche pas
        names = [D.option_name(o[8:]) for o in opts]
        for n in ("windowtype", "name", "role", "autopickup"):
            self.assertEqual(names.count(n), 1, n)
        self.assertEqual(D.option_name("!autopickup"), "autopickup")
        self.assertEqual(D.option_name(" colour"), "color")


class TestRandom(unittest.TestCase):
    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_random_hero(self):
        """Héros au hasard : combinaison permise, nom accepté par le jeu,
        rôles sans combinaison écartés."""
        import random
        g = I.GameData(SRC)
        rng = random.Random(5)
        for _i in range(200):
            h = T.random_hero(g.roles, g.races, lambda r: r["allow"], rng)
            role, race = g.role(h["role"]), g.race(h["race"])
            self.assertTrue(D.allowed(role["allow"], race, h["gender"],
                                      h["align"]), h)
            self.assertTrue(D.valid_name(h["name"]), h["name"])
            self.assertTrue(h["story"].startswith(h["name"] + " "))
            self.assertEqual([gr for gr, _m in D.validate(
                h, role, race, {}, g.objects) if gr == "erreur"], [])
        only = [g.role("SAMURAI")]
        self.assertEqual(T.random_hero(only, g.races,
                                       lambda r: r["allow"], rng)["role"],
                         "SAMURAI")
        self.assertIsNone(T.random_hero(only, g.races, lambda r: set()))


class TestHistory(unittest.TestCase):
    XLOG = ("version=5.0.0\tpoints=120\tdeathlev=3\tmaxlvl=4\tuid=%(uid)d"
            "\tname=Kestrel\tgender=Fem\tdeath=killed by a jackal\t"
            "flags=0x0\tturns=900\tconductX=atheist,wishless\n"
            "points=5\tuid=%(uid)d\tname=Kestrel\tdeath=quit\tflags=0x2\t"
            "maxlvl=1\n"
            "points=999\tuid=%(uid)d\tname=Autre\tdeath=quit\tflags=0\n"
            "ligne abîmée\n")

    def test_xlog(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "xlogfile"), "w") as f:
                f.write(self.XLOG % {"uid": os.getuid()})
            recs = G.read_xlog(d)
            self.assertEqual(len(recs), 3)
            games = G.hero_games(recs, "Kestrel")
            self.assertEqual([g["points"] for g in games], [120, 5])
            self.assertEqual(G.hero_games(recs, "Kestrel", uid=1), [])
            self.assertEqual(G.games_summary(games), {
                "count": 2, "best": 120, "maxlvl": 4, "ascended": 0})
            self.assertEqual(G.game_mode(games[1]), "découverte")
        self.assertEqual(G.read_xlog("/nonexistent"), [])

    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_death_text(self):
        names = I.GameData(SRC).names
        rec = {"death": "killed by a jackal", "gender": "Fem"}
        self.assertEqual(G.death_text(rec, names, "fr"), "tuée par un chacal")
        self.assertEqual(G.death_text(rec, names, "en"), "killed by a jackal")
        self.assertEqual(G.death_text({"death": "quit"}, names, "fr"),
                         "a abandonné")

    @unittest.skipUnless(HAVE_SRC, "sources de NetHack absentes")
    def test_launcher(self):
        g = I.GameData(SRC)
        h = D.normalize({"name": "Kestrel", "role": "Valkyrie",
                         "race": "human", "gender": "female",
                         "align": "neutral"})
        blank = D.normalize({"name": ""})
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "xlogfile"), "w") as f:
                f.write(self.XLOG % {"uid": os.getuid()})
            out = G.launcher_heroes([h, blank], g, d, "fr")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["name"], "Kestrel")
            self.assertFalse(out[0]["save"])
            self.assertIn("parties : 2, record 120 ; dernière : a "
                          "abandonné", out[0]["description"])
            os.mkdir(os.path.join(d, "save"))
            open(os.path.join(d, "save", G.save_base("Kestrel")), "w").close()
            self.assertTrue(G.launcher_heroes([h], g, d)[0]["save"])
        self.assertIn("aucune partie",
                      G.launcher_heroes([h], g, None)[0]["description"])


class TestProject(unittest.TestCase):
    def test_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.json")
            h = T.from_template(0)
            mods = {"VALKYRIE": {"gold": 5, "intrinsics": ["HFast"]}}
            P.write_project(path, [h], mods)
            heroes, roles = P.read_project(path)
            self.assertEqual(heroes, [h])
            self.assertEqual(roles, mods)
            exp = P.export_path(d, h)
            P.write_hero(exp, h, mods["VALKYRIE"])
            self.assertEqual(P.read_project(exp), ([h], mods))

    def test_normalize(self):
        mod = D.normalize_mod({"gold": "x", "attrbase": [1, 2],
                               "intrinsics": ["HFast", "bogus"],
                               "zzz": 1})
        self.assertEqual(mod, {"intrinsics": ["HFast"]})
        self.assertEqual(D.normalize({"name": 3})["name"], "")

    def test_config(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ini",
                                         delete=False) as f:
            f.write("[editeur]\ntheme = fr\nsouris = non\n"
                    "couleurs = 24bits\n[jeu]\nbidule = 1\n"
                    "cartes = ~/nhmapedit.sh\n")
        try:
            cfg, errs = C.load(f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(cfg["theme"], "fr")
        self.assertFalse(cfg["mouse"])
        self.assertTrue(cfg["truecolor"])
        self.assertEqual(cfg["maps"], os.path.expanduser("~/nhmapedit.sh"))
        self.assertEqual(len(errs), 1)

    def test_quest(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "dat"))
            for lvl in ("goal", "strt"):
                open(os.path.join(d, "dat", "Val-%s.lua" % lvl), "w").close()
            self.assertEqual([lvl for _p, lvl, _d in G.quest_levels(d, "Val")],
                             ["strt", "goal"])
            self.assertEqual(G.quest_levels(d, "Sam"), [])
            tool = os.path.join(d, "nhmapedit.sh")
            open(tool, "w").close()
            self.assertIsNone(G.map_editor({"maps": tool}))
            os.chmod(tool, 0o755)
            self.assertEqual(G.map_editor({"maps": tool}), tool)
        if HAVE_SRC:
            self.assertEqual(len(G.quest_levels(SRC, "Val")), 5)

    def test_args(self):
        p, s, a = E.parse_args(["x.json", "--src", "/tmp"])
        self.assertTrue(p.endswith("x.json"))
        self.assertEqual(s, "/tmp")
        self.assertIsNone(a)
        self.assertEqual(E.parse_args(["--heros"])[2], ("heros",))
        self.assertEqual(E.parse_args(["--jouer", "Kestrel"])[2],
                         ("jouer", "Kestrel"))


if __name__ == "__main__":
    unittest.main()
