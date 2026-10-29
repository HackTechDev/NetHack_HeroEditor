"""Traduction anglaise : catalogue complet et cohérent, langue choisie."""

import ast
import glob
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import nhhero_i18n  # noqa: E402
from nhhero_i18n_en import EN  # noqa: E402

FORMAT = re.compile(r"%[-\d.]*[sdr%]")


def keys():
    """Textes passés à _() dans les modules du projet : {texte: lieu}."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "_" and n.args
                    and isinstance(n.args[0], ast.Constant)):
                out.setdefault(n.args[0].value, "%s:%d" % (
                    os.path.basename(path), n.lineno))
    # _(__doc__.strip()) : l'usage affiché par --help
    with open(os.path.join(ROOT, "nhheroedit.py"), encoding="utf-8") as f:
        out[ast.get_docstring(ast.parse(f.read()), clean=False).strip()] = \
            "nhheroedit.py"
    return out


class Catalog(unittest.TestCase):
    def test_every_text_translated(self):
        missing = ["%s %r" % (where, k) for k, where in keys().items()
                   if k not in EN]
        self.assertEqual(missing, [])

    def test_no_stale_entry(self):
        used = set(keys())
        self.assertEqual(sorted(k for k in EN if k not in used), [])

    def test_underscore_never_assigned(self):
        """Une fonction qui assigne « _ » (for _ in…) ne peut plus
        appeler _() : UnboundLocalError à l'exécution."""
        bad = []
        for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for fn in ast.walk(tree):
                if not isinstance(fn, ast.FunctionDef):
                    continue
                todo = list(ast.iter_child_nodes(fn))
                while todo:
                    n = todo.pop()
                    if isinstance(n, (ast.FunctionDef, ast.Lambda,
                                      ast.ListComp, ast.GeneratorExp,
                                      ast.SetComp, ast.DictComp)):
                        continue
                    if isinstance(n, ast.Name) and n.id == "_" and \
                            isinstance(n.ctx, ast.Store):
                        bad.append("%s:%d" % (os.path.basename(path),
                                              n.lineno))
                    todo.extend(ast.iter_child_nodes(n))
        self.assertEqual(bad, [])

    def test_same_placeholders(self):
        bad = [k for k, v in EN.items()
               if FORMAT.findall(k) != FORMAT.findall(v)]
        self.assertEqual(bad, [])


class Detect(unittest.TestCase):
    def detect(self, **env):
        old = dict(os.environ)
        try:
            for var in ("NHHEROEDIT_LANG", "LANGUAGE", "LC_ALL",
                        "LC_MESSAGES", "LANG"):
                os.environ.pop(var, None)
            os.environ["NHHEROEDIT_CONFIG"] = os.devnull
            os.environ.update(env)
            return nhhero_i18n.detect()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_locale(self):
        self.assertEqual(self.detect(LANG="fr_FR.UTF-8"), "fr")
        self.assertEqual(self.detect(LANG="en_US.UTF-8"), "en")
        self.assertEqual(self.detect(LANG="de_DE.UTF-8"), "en")
        self.assertEqual(self.detect(LANG="en_US.UTF-8",
                                     LC_ALL="fr_CA.UTF-8"), "fr")

    def test_config(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ini") as f:
            f.write("[editeur]\nlangue = en\n")
            f.flush()
            self.assertEqual(self.detect(LANG="fr_FR.UTF-8",
                                         NHHEROEDIT_CONFIG=f.name), "en")
            self.assertEqual(self.detect(LANG="en_US.UTF-8",
                                         NHHEROEDIT_LANG="fr",
                                         NHHEROEDIT_CONFIG=f.name), "fr")

    def test_override(self):
        self.assertEqual(self.detect(LANG="fr_FR.UTF-8",
                                     NHHEROEDIT_LANG="en"), "en")


class English(unittest.TestCase):
    def test_messages(self):
        env = dict(os.environ, NHHEROEDIT_LANG="en")
        out = subprocess.run(
            [sys.executable, "-c",
             "import nhheroedit as E, nhhero_data as D, nhhero_templates as T\n"
             "print(E.HELP[0])\n"
             "print(D.ALIGN_FR['chaotic'])\n"
             "print(T.template_list()[0][0])\n"],
            cwd=ROOT, env=env, capture_output=True, text=True,
            check=True).stdout
        self.assertEqual(out.split("\n")[:3], [
            "nhheroedit — hero editor for NetHack 5.0 (Night City)",
            "chaotic", "Street solo"])


if __name__ == "__main__":
    unittest.main()
