"""Briques de l'interface curses : couleurs, fenêtres surgissantes
(menu filtrable, cases à cocher, saisie d'une ligne, texte long,
visionneuse, confirmation) et éditeur de tuile 16x16."""

import curses
import os
import time
import unicodedata

import nhhero_data as D
from nhhero_i18n import _

ESC = "\x1b"


class Cancel(Exception):
    pass


# --- couleurs -----------------------------------------------------------

BASIC_RGB = [
    (curses.COLOR_BLACK, (0, 0, 0)), (curses.COLOR_RED, (205, 0, 0)),
    (curses.COLOR_GREEN, (0, 205, 0)), (curses.COLOR_YELLOW, (205, 205, 0)),
    (curses.COLOR_BLUE, (0, 0, 238)), (curses.COLOR_MAGENTA, (205, 0, 205)),
    (curses.COLOR_CYAN, (0, 205, 205)), (curses.COLOR_WHITE, (229, 229, 229)),
]


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def rgb_to_curses(rgb):
    """Couleur curses la plus proche d'un RGB (256 couleurs si possible)."""
    if curses.COLORS >= 256:
        steps = [0, 95, 135, 175, 215, 255]

        def near(v):
            return min(range(6), key=lambda i: abs(steps[i] - v))
        ci = [near(v) for v in rgb]
        cube = 16 + 36 * ci[0] + 6 * ci[1] + ci[2]
        cube_rgb = tuple(steps[i] for i in ci)
        avg = sum(rgb) // 3
        gi = min(23, max(0, (avg - 8) // 10))
        gray_rgb = (8 + 10 * gi,) * 3
        return cube if _dist(rgb, cube_rgb) <= _dist(rgb, gray_rgb) \
            else 232 + gi
    return min(BASIC_RGB, key=lambda c: _dist(rgb, c[1]))[0]


class Colors:
    def __init__(self):
        self.ok = curses.has_colors()
        self.pairs = {}
        self.next = 1
        if self.ok:
            curses.start_color()
            try:
                curses.use_default_colors()
                self.default = -1
            except curses.error:
                self.default = curses.COLOR_BLACK
        self.tile = {c: rgb_to_curses(rgb) for c, rgb in D.TILE_PALETTE} \
            if self.ok else {}

    def pair(self, fg, bg=None):
        if not self.ok:
            return 0
        bg = self.default if bg is None else bg
        key = (fg, bg)
        if key not in self.pairs:
            if self.next >= curses.COLOR_PAIRS:
                return 0
            try:
                curses.init_pair(self.next, fg, bg)
            except curses.error:
                return 0
            self.pairs[key] = curses.color_pair(self.next)
            self.next += 1
        return self.pairs[key]

    def fg(self, c, bold=False):
        return self.pair(c) | (curses.A_BOLD if bold else 0)

    def pixel(self, ch, fg=None):
        bg = self.tile.get(ch, curses.COLOR_BLACK)
        if fg is None:
            fg = curses.COLOR_WHITE
        return self.pair(fg, bg)

    def halfblock(self, top, bottom):
        """Attribut pour « ▀ » : haut en avant-plan, bas en fond."""
        return self.pair(self.tile.get(top, 0), self.tile.get(bottom, 0))


# --- dessin -------------------------------------------------------------

def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in s)


def fold(s):
    """Minuscules sans accents, pour filtrer (« Sécurité » -> « securite »)."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c))


def clip(s, n):
    if n <= 0:
        return ""
    if len(s) <= n:
        return s
    return s[:max(0, n - 1)] + "…"


def put(win, y, x, s, attr=0, maxw=None):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    n = w - x if maxw is None else min(maxw, w - x)
    s = clip(s, n)
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass        # dernière case de la fenêtre


def box(win, title="", attr=0):
    h, w = win.getmaxyx()
    put(win, 0, 0, "╭" + "─" * (w - 2) + "╮", attr)
    for y in range(1, h - 1):
        put(win, y, 0, "│", attr)
        put(win, y, w - 1, "│", attr)
    put(win, h - 1, 0, "╰" + "─" * (w - 2) + "╯", attr)
    if title:
        put(win, 0, 2, " %s " % title, attr | curses.A_BOLD)


# --- souris -------------------------------------------------------------

class Mouse:
    """Événement souris rendu par get_key() à la place d'une touche.
    kind : click, double, right, drag (bouton gauche enfoncé qui se
    déplace), up, down (molette). y, x : coordonnées de l'écran."""

    def __init__(self, kind, y, x):
        self.kind, self.y, self.x = kind, y, x

    def inside(self, win):
        """(ligne, colonne) relatives à win, ou None hors de la fenêtre."""
        by, bx = win.getbegyx()
        h, w = win.getmaxyx()
        if by <= self.y < by + h and bx <= self.x < bx + w:
            return self.y - by, self.x - bx
        return None

    def __repr__(self):
        return "Mouse(%s, %d, %d)" % (self.kind, self.y, self.x)


_mouse = {"on": False, "held": False, "last": (0, -1, -1)}
_WHEEL_UP = getattr(curses, "BUTTON4_PRESSED", 0x10000)
_WHEEL_DOWN = getattr(curses, "BUTTON5_PRESSED", 0x200000)


def enable_mouse(motion=False):
    """Active la souris (sauf NHHEROEDIT_MOUSE=0). motion : suivre aussi
    les déplacements bouton enfoncé (pour peindre la tuile)."""
    if os.environ.get("NHHEROEDIT_MOUSE", "1") == "0":
        return
    mask = curses.ALL_MOUSE_EVENTS
    if motion:
        mask |= curses.REPORT_MOUSE_POSITION
    try:
        curses.mousemask(mask)
        curses.mouseinterval(0)     # appui et relâchement sans attente
        _mouse["on"] = True
    except curses.error:
        pass


def _mouse_event():
    try:
        _id, x, y, _z, b = curses.getmouse()
    except curses.error:
        return None
    if b & _WHEEL_UP:
        return Mouse("up", y, x)
    if b & _WHEEL_DOWN:
        return Mouse("down", y, x)
    if b & curses.BUTTON3_PRESSED:
        return Mouse("right", y, x)
    if b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
        _mouse["held"] = bool(b & curses.BUTTON1_PRESSED)
        t, ly, lx = _mouse["last"]
        now = time.monotonic()
        double = now - t < 0.4 and (ly, lx) == (y, x)
        _mouse["last"] = (0 if double else now, y, x)
        return Mouse("double" if double else "click", y, x)
    if b & curses.BUTTON1_RELEASED:
        _mouse["held"] = False
        return None
    if b & curses.REPORT_MOUSE_POSITION and _mouse["held"]:
        return Mouse("drag", y, x)
    return None


def get_key(win, idle=False):
    """Touche lue : caractère (str), code curses (int) ou Mouse.
    Les relâchements et déplacements sans bouton sont ignorés. idle :
    renvoie None quand le délai de win.timeout() passe sans touche."""
    while True:
        try:
            k = win.get_wch()
        except curses.error:
            if idle:
                return None
            continue
        except KeyboardInterrupt:
            return ESC
        if k == curses.KEY_MOUSE:
            ev = _mouse_event()
            if ev is None:
                continue
            return ev
        return k


def wheel(k):
    """-1 / +1 pour la molette, 0 sinon."""
    if isinstance(k, Mouse):
        return {"up": -1, "down": 1}.get(k.kind, 0)
    return 0


def centered(stdscr, h, w):
    H, W = stdscr.getmaxyx()
    h, w = min(h, H), min(w, W)
    win = curses.newwin(h, w, max(0, (H - h) // 2), max(0, (W - w) // 2))
    win.keypad(True)
    return win


def is_enter(k):
    return k in ("\n", "\r", curses.KEY_ENTER)


def is_backspace(k):
    return k in ("\x7f", "\b", curses.KEY_BACKSPACE)


# --- fenêtres surgissantes ----------------------------------------------

class Popups:
    """Les fenêtres de dialogue ; self.stdscr, self.colors et
    self.redraw() sont fournis par l'éditeur."""

    def accent(self):
        return self.colors.fg(curses.COLOR_MAGENTA, True)

    def cyan(self):
        return self.colors.fg(curses.COLOR_CYAN, True)

    def message_box(self, title, lines):
        w = min(max([width(l) for l in lines] + [width(title) + 6]) + 4, 100)
        win = centered(self.stdscr, len(lines) + 4, w)
        box(win, title, self.accent())
        for i, l in enumerate(lines):
            put(win, 2 + i, 2, l)
        win.refresh()
        get_key(win)
        self.redraw()

    def confirm(self, question, title=_("Confirmation")):
        lines = question.split("\n")
        w = min(max(width(l) for l in lines + [title]) + 6, 100)
        win = centered(self.stdscr, len(lines) + 4, max(w, 30))
        box(win, title, self.accent())
        for i, l in enumerate(lines):
            put(win, 1 + i, 2, l)
        put(win, len(lines) + 2, 2, _("[o]ui / [n]on"), self.cyan())
        win.refresh()
        while True:
            k = get_key(win)
            if k in ("o", "O", "y", "Y"):
                self.redraw()
                return True
            if k in ("n", "N", ESC, "q"):
                self.redraw()
                return False

    def input_line(self, prompt, initial="", hint=""):
        """Saisie d'une ligne. Renvoie le texte, ou lève Cancel."""
        H, W = self.stdscr.getmaxyx()
        w = min(max(60, width(prompt) + 6), W - 2)
        win = centered(self.stdscr, 6 if hint else 5, w)
        text = list(initial)
        pos = len(text)
        off = 0
        fw = w - 4
        curses.curs_set(1)
        try:
            while True:
                win.erase()
                box(win, prompt, self.accent())
                if pos < off:
                    off = pos
                if pos - off >= fw:
                    off = pos - fw + 1
                put(win, 2, 2, "".join(text[off:off + fw]).ljust(fw),
                    curses.A_UNDERLINE)
                if hint:
                    put(win, 3, 2, hint, curses.A_DIM)
                put(win, 4 if hint else 3, 2,
                    _("Entrée : valider   Échap : annuler"), curses.A_DIM)
                win.move(2, 2 + width("".join(text[off:pos])))
                win.refresh()
                k = get_key(win)
                if is_enter(k):
                    return "".join(text)
                if k == ESC:
                    raise Cancel
                if is_backspace(k):
                    if pos:
                        del text[pos - 1]
                        pos -= 1
                elif k == curses.KEY_DC:
                    if pos < len(text):
                        del text[pos]
                elif k == curses.KEY_LEFT:
                    pos = max(0, pos - 1)
                elif k == curses.KEY_RIGHT:
                    pos = min(len(text), pos + 1)
                elif k in (curses.KEY_HOME, "\x01"):
                    pos = 0
                elif k in (curses.KEY_END, "\x05"):
                    pos = len(text)
                elif k == "\x15":           # Ctrl-U : efface
                    text, pos = [], 0
                elif isinstance(k, str) and k.isprintable():
                    text.insert(pos, k)
                    pos += 1
        finally:
            curses.curs_set(0)
            self.redraw()

    def input_int(self, prompt, value, lo, hi, hint=""):
        hint = hint or _("entier de %d à %d") % (lo, hi)
        text = str(value)
        while True:
            text = self.input_line(prompt, text, hint)
            try:
                v = int(text.strip())
            except ValueError:
                v = None
            if v is not None and lo <= v <= hi:
                return v
            hint = _("⚠ valeur invalide : un entier de %d à %d") % (lo, hi)

    def menu(self, title, items, current=0, filterable=True):
        """items : liste de (libellé, description). Renvoie l'indice
        choisi, ou lève Cancel. Les lettres tapées filtrent la liste."""
        H, W = self.stdscr.getmaxyx()
        lw = max([width(a) for a, _ in items] + [10])
        dw = max([width(b) for _, b in items] + [0])
        w = min(max(lw + dw + 8, width(title) + 8, 40), W - 2)
        h = min(len(items) + 4, H - 2)
        win = centered(self.stdscr, h, w)
        flt = ""
        sel = current if 0 <= current < len(items) else 0
        top = 0
        try:
            while True:
                shown = [i for i, (a, b) in enumerate(items)
                         if fold(flt) in fold(a + " " + b)]
                if sel not in shown:
                    sel = shown[0] if shown else -1
                rows = h - 4
                idx = shown.index(sel) if sel in shown else 0
                if idx < top:
                    top = idx
                if idx >= top + rows:
                    top = idx - rows + 1
                win.erase()
                box(win, title, self.accent())
                put(win, 1, 2, (_("filtre : ") + flt) if flt else
                    _("tapez pour filtrer  ↑↓ Entrée Échap"), curses.A_DIM)
                for r, i in enumerate(shown[top:top + rows]):
                    a, b = items[i]
                    attr = curses.A_REVERSE if i == sel else 0
                    line = a.ljust(lw) + ("  " + b if b else "")
                    put(win, 2 + r, 2, line.ljust(w - 4), attr, w - 4)
                if len(shown) > rows:
                    put(win, h - 1, w - 12, " %d/%d " % (idx + 1, len(shown)))
                win.refresh()
                k = get_key(win)
                if is_enter(k) and sel >= 0:
                    return sel
                if isinstance(k, Mouse) and shown:
                    pos = k.inside(win)
                    r = pos[0] - 2 if pos else -1
                    if wheel(k):
                        idx = max(0, min(len(shown) - 1, idx + 3 * wheel(k)))
                    elif 0 <= r < rows and top + r < len(shown):
                        # un clic choisit la ligne, un second la valide
                        if shown[top + r] == sel or k.kind == "double":
                            return shown[top + r]
                        idx = top + r
                    sel = shown[idx]
                    continue
                if k == ESC:
                    if flt:
                        flt = ""
                        continue
                    raise Cancel
                if not shown:
                    if is_backspace(k):
                        flt = flt[:-1]
                    elif isinstance(k, str) and k.isprintable():
                        flt += k
                    continue
                if k == curses.KEY_UP:
                    idx = max(0, idx - 1)
                elif k == curses.KEY_DOWN:
                    idx = min(len(shown) - 1, idx + 1)
                elif k == curses.KEY_PPAGE:
                    idx = max(0, idx - rows)
                elif k == curses.KEY_NPAGE:
                    idx = min(len(shown) - 1, idx + rows)
                elif k == curses.KEY_HOME:
                    idx = 0
                elif k == curses.KEY_END:
                    idx = len(shown) - 1
                elif is_backspace(k):
                    flt = flt[:-1]
                elif filterable and isinstance(k, str) and k.isprintable():
                    flt += k
                    continue
                sel = shown[idx]
        finally:
            self.redraw()

    def checklist(self, title, items, selected):
        """items : liste de (nom, description) ; selected : noms cochés.
        Renvoie la liste des noms cochés (dans l'ordre de items)."""
        H, W = self.stdscr.getmaxyx()
        sel = set(selected)
        lw = max(width(a) for a, _ in items)
        w = min(max(lw + max(width(b) for _, b in items) + 12, 40), W - 2)
        h = min(len(items) + 5, H - 2)
        win = centered(self.stdscr, h, w)
        cur, top = 0, 0
        try:
            while True:
                rows = h - 4
                if cur < top:
                    top = cur
                if cur >= top + rows:
                    top = cur - rows + 1
                win.erase()
                box(win, title, self.accent())
                put(win, 1, 2, _("Espace ou clic : cocher   Entrée : valider"
                    "   Échap : annuler"), curses.A_DIM)
                for r, (n, d) in enumerate(items[top:top + rows]):
                    i = top + r
                    mark = "[x]" if n in sel else "[ ]"
                    attr = curses.A_REVERSE if i == cur else 0
                    if n in sel:
                        attr |= self.cyan()
                    put(win, 2 + r, 2, ("%s %s  %s" % (mark, n.ljust(lw), d))
                        .ljust(w - 4), attr, w - 4)
                win.refresh()
                k = get_key(win)
                if is_enter(k):
                    return [n for n, _ in items if n in sel]
                if k == ESC:
                    raise Cancel
                if isinstance(k, Mouse):
                    pos = k.inside(win)
                    r = pos[0] - 2 if pos else -1
                    if wheel(k):
                        cur = max(0, min(len(items) - 1, cur + 3 * wheel(k)))
                    elif k.kind in ("click", "double") and 0 <= r < rows \
                            and top + r < len(items):
                        cur = top + r
                        sel.symmetric_difference_update({items[cur][0]})
                elif k == " ":
                    n = items[cur][0]
                    sel.symmetric_difference_update({n})
                    cur = min(len(items) - 1, cur + 1)
                elif k == curses.KEY_UP:
                    cur = max(0, cur - 1)
                elif k == curses.KEY_DOWN:
                    cur = min(len(items) - 1, cur + 1)
                elif k == curses.KEY_PPAGE:
                    cur = max(0, cur - rows)
                elif k == curses.KEY_NPAGE:
                    cur = min(len(items) - 1, cur + rows)
        finally:
            self.redraw()

    def viewer(self, title, lines):
        """Texte en lecture seule. lines : chaînes ou (chaîne, attribut)."""
        lines = [l if isinstance(l, tuple) else (l, 0) for l in lines]
        H, W = self.stdscr.getmaxyx()
        win = centered(self.stdscr, H - 2, min(W - 2, 110))
        h, w = win.getmaxyx()
        top, left = 0, 0
        try:
            while True:
                rows = h - 3
                win.erase()
                box(win, title, self.accent())
                for r, (l, a) in enumerate(lines[top:top + rows]):
                    put(win, 1 + r, 2, l[left:].expandtabs(8), a, w - 4)
                put(win, h - 1, 2, _(" ↑↓ PgUp PgDn ←→  q/Échap : fermer "
                    " %d-%d/%d ") % (top + 1, min(top + rows, len(lines)),
                                    len(lines)), curses.A_DIM)
                win.refresh()
                k = get_key(win)
                if k in (ESC, "q", "\n", "\r", curses.KEY_ENTER):
                    return
                if wheel(k):
                    top = max(0, min(max(0, len(lines) - rows),
                                     top + 3 * wheel(k)))
                elif k == curses.KEY_UP:
                    top = max(0, top - 1)
                elif k == curses.KEY_DOWN:
                    top = min(max(0, len(lines) - rows), top + 1)
                elif k in (curses.KEY_PPAGE, "b"):
                    top = max(0, top - rows)
                elif k in (curses.KEY_NPAGE, " "):
                    top = min(max(0, len(lines) - rows), top + rows)
                elif k == curses.KEY_HOME:
                    top = 0
                elif k == curses.KEY_END:
                    top = max(0, len(lines) - rows)
                elif k == curses.KEY_LEFT:
                    left = max(0, left - 8)
                elif k == curses.KEY_RIGHT:
                    left += 8
                elif k == curses.KEY_RESIZE:
                    return
        finally:
            self.redraw()

    def text_area(self, title, text):
        """Éditeur de texte multiligne (retour à la ligne visuel).
        Échap : terminer. Renvoie le texte."""
        H, W = self.stdscr.getmaxyx()
        win = centered(self.stdscr, min(H - 2, 20), min(W - 2, 76))
        h, w = win.getmaxyx()
        tw = w - 4
        lines = text.split("\n") if text else [""]
        r, c = 0, 0
        top = 0
        curses.curs_set(1)
        try:
            while True:
                # lignes visuelles : (ligne, début)
                vis = []
                for i, l in enumerate(lines):
                    for s in range(0, max(1, len(l) + 1), tw):
                        vis.append((i, s))
                        if len(l) - s < tw:
                            break
                cur = max(j for j, (i, s) in enumerate(vis)
                          if i == r and s <= c)
                rows = h - 3
                if cur < top:
                    top = cur
                if cur >= top + rows:
                    top = cur - rows + 1
                win.erase()
                box(win, title, self.accent())
                for j, (i, s) in enumerate(vis[top:top + rows]):
                    put(win, 1 + j, 2, lines[i][s:s + tw])
                put(win, h - 1, 2, _(" Échap : terminer   Entrée : "
                    "nouveau paragraphe "), curses.A_DIM)
                vi, vs = vis[cur]
                win.move(1 + cur - top, 2 + (c - vs))
                win.refresh()
                k = get_key(win)
                if k == ESC:
                    return "\n".join(lines).strip("\n")
                line = lines[r]
                if is_enter(k):
                    lines[r:r + 1] = [line[:c], line[c:]]
                    r, c = r + 1, 0
                elif is_backspace(k):
                    if c:
                        lines[r] = line[:c - 1] + line[c:]
                        c -= 1
                    elif r:
                        c = len(lines[r - 1])
                        lines[r - 1:r + 1] = [lines[r - 1] + line]
                        r -= 1
                elif k == curses.KEY_DC:
                    if c < len(line):
                        lines[r] = line[:c] + line[c + 1:]
                    elif r + 1 < len(lines):
                        lines[r:r + 2] = [line + lines[r + 1]]
                elif k == curses.KEY_LEFT:
                    if c:
                        c -= 1
                    elif r:
                        r, c = r - 1, len(lines[r - 1])
                elif k == curses.KEY_RIGHT:
                    if c < len(line):
                        c += 1
                    elif r + 1 < len(lines):
                        r, c = r + 1, 0
                elif k in (curses.KEY_UP, curses.KEY_DOWN):
                    j = cur + (-1 if k == curses.KEY_UP else 1)
                    if 0 <= j < len(vis):
                        i, s = vis[j]
                        r = i
                        c = min(len(lines[i]), s + (c - vs))
                elif k == curses.KEY_HOME:
                    c = vs
                elif k == curses.KEY_END:
                    c = min(len(line), vs + tw - 1) \
                        if len(line) - vs >= tw else len(line)
                elif isinstance(k, str) and k.isprintable():
                    lines[r] = line[:c] + k + line[c:]
                    c += 1
        finally:
            curses.curs_set(0)
            self.redraw()

    # --- éditeur de tuile -------------------------------------------------

    def export_image(self, tile, base, title):
        """Écrit la tuile en PNG ou en SVG, agrandie (D.TILE_SCALE)."""
        try:
            svg = self.menu(_("Exporter la tuile"), [
                ("PNG", _("image %dx%d") % (D.TILE_SIZE * D.TILE_SCALE,
                                            D.TILE_SIZE * D.TILE_SCALE)),
                ("SVG", _("dessin vectoriel, net à toute taille"))],
                filterable=False) == 1
            path = os.path.expanduser(self.input_line(
                _("Écrire l'image dans"), base + (".svg" if svg else ".png")))
        except Cancel:
            return
        if os.path.exists(path) and not self.confirm(
                _("Remplacer %s ?") % path):
            return
        try:
            if svg:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(D.tile_svg(tile, title=title))
            else:
                with open(path, "wb") as f:
                    f.write(D.tile_png(tile))
        except OSError as e:
            self.message_box(_("Écriture impossible"), [str(e)])
            return
        self.message_box(_("Exporter la tuile"),
                         [_("Image écrite : %s") % path])

    def tile_editor(self, tile, title, importer=None, original=None,
                    other=None, image=None):
        """Dessin d'une tuile 16x16. Échap garde le dessin, q propose de
        l'abandonner ; renvoie la tuile retenue. importer() : tuile
        choisie dans le jeu (ou None) ; original : tuile du jeu, que o
        rétablit ; other : (titre, tuile) de l'autre sexe, montrée à
        côté et que c recopie ; image : chemin proposé (sans extension)
        pour l'export en PNG ou SVG (e)."""
        pal = [c for c, _ in D.TILE_PALETTE]
        rgb = dict(D.TILE_PALETTE)
        grid = [list(r) for r in tile]
        orig = [r[:] for r in grid]
        undo = []
        y = x = 7
        color = "P"
        layer = None        # [nom, lignes, dy, dx] du calque en pose
        S = D.TILE_SIZE
        help_lines = [
            _("←↑→↓ : déplacer     Espace : peindre"),
            _("A-Z . 0 1 : choisir la couleur et peindre"),
            _("Tab / + - : couleur suivante / précédente"),
            _("p : pipette    f : remplir la zone"),
            _("r : remplacer cette couleur partout"),
            _("m : symétrie gauche -> droite"),
            _("h : retourner     i : importer une tuile du jeu"),
            _("o : tuile d'origine du rôle") + (
                _("   c : copier l'autre sexe") if other else ""),
            _("l : poser un calque Night City (visière, bras...)"),
            _("e : exporter en image (PNG, SVG)"),
            _("x : tout effacer  u : annuler  q : abandonner"),
            _("souris : clic peindre, clic droit pipette,"),
            _("         molette couleur     Échap : terminer"),
        ]
        enable_mouse(motion=True)
        try:
            while True:
                self.stdscr.erase()
                H, W = self.stdscr.getmaxyx()
                put(self.stdscr, 0, 0, (_(" Tuile : %s  (versions graphiques "
                                          "Qt et X11) ") % title).ljust(W),
                    self.colors.pair(curses.COLOR_BLACK,
                                     curses.COLOR_MAGENTA) | curses.A_BOLD)
                oy, ox = 2, 2
                shown = grid
                if layer:
                    shown = D.apply_layer(grid, *layer[1:])
                    put(self.stdscr, 1, 2, _("Calque %s : flèches pour le "
                                             "placer, Entrée pour le poser, "
                                             "Échap pour renoncer")
                        % layer[0], curses.A_BOLD)
                for j in range(S):
                    for i in range(S):
                        ch = shown[j][i]
                        a = self.colors.pixel(ch)
                        s = "  "
                        if (j, i) == (y, x) and not layer:
                            s = "[]"
                            a = self.colors.pixel(
                                ch, curses.COLOR_WHITE
                                if sum(rgb[ch]) < 380 else curses.COLOR_BLACK)
                            a |= curses.A_BOLD
                        put(self.stdscr, oy + j, ox + 2 * i, s, a)
                # aperçu en taille réelle (demi-blocs)
                px = ox + 2 * S + 3
                put(self.stdscr, oy, px, _("Aperçu"), curses.A_DIM)
                for j in range(0, S, 2):
                    for i in range(S):
                        put(self.stdscr, oy + 1 + j // 2, px + i, "▀",
                            self.colors.halfblock(shown[j][i],
                                                  shown[j + 1][i]))
                if other:
                    put(self.stdscr, oy + 9, px, clip(other[0], S + 2),
                        curses.A_DIM)
                    for j in range(0, S, 2):
                        for i in range(S):
                            put(self.stdscr, oy + 10 + j // 2, px + i, "▀",
                                self.colors.halfblock(other[1][j][i],
                                                      other[1][j + 1][i]))
                # palette
                qx = px + S + 3
                put(self.stdscr, oy, qx, _("Palette"), curses.A_DIM)
                for k, c in enumerate(pal):
                    yy = oy + 1 + k % 15
                    xx = qx + (k // 15) * 12
                    mark = ">" if c == color else " "
                    put(self.stdscr, yy, xx, "%s%s " % (mark, c),
                        curses.A_BOLD if c == color else 0)
                    put(self.stdscr, yy, xx + 3, "    ", self.colors.pixel(c))
                for k, l in enumerate(help_lines):
                    put(self.stdscr, oy + S + 2 + k if oy + S + 2 + k < H
                        else H - 1, 2, l, curses.A_DIM)
                put(self.stdscr, oy + S, qx, _("Couleur %s %s")
                    % (color, rgb[color]))
                self.stdscr.refresh()
                k = get_key(self.stdscr)

                def save():
                    undo.append([r[:] for r in grid])
                    del undo[:-50]
                if layer:
                    moves = {curses.KEY_UP: (-1, 0), curses.KEY_DOWN: (1, 0),
                             curses.KEY_LEFT: (0, -1),
                             curses.KEY_RIGHT: (0, 1)}
                    if k in moves:
                        layer[2] += moves[k][0]
                        layer[3] += moves[k][1]
                    elif k in (" ", "\n", "\r", curses.KEY_ENTER):
                        save()
                        grid = [list(r) for r in shown]
                        layer = None
                    elif k == ESC or k == "q":
                        layer = None
                    continue
                if k == ESC:
                    return ["".join(r) for r in grid]
                if isinstance(k, Mouse):
                    j, i = k.y - oy, (k.x - ox) // 2
                    on_grid = 0 <= j < S and 0 <= k.x - ox < 2 * S
                    if wheel(k):
                        color = pal[(pal.index(color) + wheel(k)) % len(pal)]
                    elif on_grid and k.kind == "right":
                        y, x = j, i
                        color = grid[y][x]
                    elif on_grid and k.kind in ("click", "double", "drag"):
                        if k.kind != "drag":
                            save()      # un trait = une annulation
                        y, x = j, i
                        grid[y][x] = color
                    elif k.kind == "click":
                        for n, c in enumerate(pal):
                            if k.y == oy + 1 + n % 15 and \
                                    qx + (n // 15) * 12 <= k.x < \
                                    qx + (n // 15) * 12 + 7:
                                color = c
                    continue
                if k == curses.KEY_UP:
                    y = (y - 1) % S
                elif k == curses.KEY_DOWN:
                    y = (y + 1) % S
                elif k == curses.KEY_LEFT:
                    x = (x - 1) % S
                elif k == curses.KEY_RIGHT:
                    x = (x + 1) % S
                elif k in (" ", "\n", "\r", curses.KEY_ENTER):
                    save()
                    grid[y][x] = color
                elif isinstance(k, str) and k in pal:
                    save()
                    color = k
                    grid[y][x] = color
                elif k in ("\t", "+"):
                    color = pal[(pal.index(color) + 1) % len(pal)]
                elif k in (curses.KEY_BTAB, "-"):
                    color = pal[(pal.index(color) - 1) % len(pal)]
                elif k == "p":
                    color = grid[y][x]
                elif k == "f":
                    save()
                    old = grid[y][x]
                    if old != color:
                        stack = [(y, x)]
                        while stack:
                            j, i = stack.pop()
                            if 0 <= j < S and 0 <= i < S \
                                    and grid[j][i] == old:
                                grid[j][i] = color
                                stack += [(j + 1, i), (j - 1, i),
                                          (j, i + 1), (j, i - 1)]
                elif k == "r":
                    save()
                    old = grid[y][x]
                    grid = [[color if c == old else c for c in r]
                            for r in grid]
                elif k == "m":
                    save()
                    for r in grid:
                        r[S // 2:] = r[:S // 2][::-1]
                elif k == "h":
                    save()
                    grid = [r[::-1] for r in grid]
                elif k == "x":
                    save()
                    grid = [["."] * S for _ in range(S)]
                elif k == "u" and undo:
                    grid = undo.pop()
                elif k == "i" and importer:
                    rows = importer()
                    if rows:
                        save()
                        grid = [list(r) for r in rows]
                elif k == "o" and original:
                    save()
                    grid = [list(r) for r in original]
                elif k == "l":
                    try:
                        n = self.menu(_("Calque Night City"),
                                      [(name, "") for name, _l in D.LAYERS],
                                      filterable=False)
                    except Cancel:
                        continue
                    layer = [D.LAYERS[n][0], D.LAYERS[n][1], 0, 0]
                elif k == "e" and image:
                    self.export_image(["".join(r) for r in grid], image,
                                      title)
                elif k == "c" and other:
                    save()
                    grid = [list(r) for r in other[1]]
                elif k == "q":
                    if grid == orig or self.confirm(
                            _("Garder les modifications de la tuile ?")):
                        return ["".join(r) for r in grid]
                    return ["".join(r) for r in orig]
        finally:
            enable_mouse()
            self.redraw()
