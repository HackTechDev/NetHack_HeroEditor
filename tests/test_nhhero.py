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
        for rel in (I.ROLE_C, I.U_INIT_C, I.INSIGHT_C):
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
            f.write("[editeur]\ntheme = fr\nsouris = non\n[jeu]\n"
                    "bidule = 1\n")
        try:
            cfg, errs = C.load(f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(cfg["theme"], "fr")
        self.assertFalse(cfg["mouse"])
        self.assertEqual(len(errs), 1)

    def test_args(self):
        p, s = E.parse_args(["x.json", "--src", "/tmp"])
        self.assertTrue(p.endswith("x.json"))
        self.assertEqual(s, "/tmp")


if __name__ == "__main__":
    unittest.main()
