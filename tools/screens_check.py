# tools/screens_check.py
# The every-screen check: opens the game in browser mode on each standard test
# save (tools/make_test_saves.py) and clicks through every section and page of
# the green bar (screens/nav.SECTIONS), every view toggle and tab on them, the
# pop-ups (player card, team window, game summary, offseason report), the team
# picker, the draft room, and the Contracts tab's Re-sign and Free agency views
# with a player picked. It never presses Sim, Next, Save, or anything that
# changes the league.
#
# It reports every server error (a Python traceback in the game's log, a
# "500 Server error" page), every error in the browser's console, and anything
# it couldn't click, with the save and page it happened on, and saves a
# 1600x900 screenshot of each step (the size of the Gemini package,
# docs/for-gemini/). Exit code 1 if anything went wrong.
#
#   python tools/make_test_saves.py           # once, or after engine changes (~1.5 min)
#   python tools/screens_check.py             # ~4 min; screenshots in tools/data/screens/
#   python tools/screens_check.py --saves 12-fa-wave1,15-draft-day     # just these saves
#   python tools/screens_check.py --no-shots  # faster: errors only
#
# The browser is Microsoft Edge (already on every Windows PC), driven by
# Playwright (python -m pip install -r requirements-dev.txt). Playwright is a
# development tool only: the game never imports it, so it's not in the .exe.
#
# The test saves are copied to a temporary folder first, so they're never
# changed; your own saves (saves/) are never touched.

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAVES_DIR = ROOT / "tools" / "data" / "test_saves"
OUT_DIR = ROOT / "tools" / "data" / "screens"
SIZE = {"width": 1600, "height": 900}

# Toggles that are settings, not views (clicking them changes the league).
SKIP_TOGGLES = {"I run my practice squad", "Staff runs it"}
# Toggles that only change a speed (nothing new to see).
SPEED_WORDS = {"Slow", "Normal", "Fast", "Very fast", "Pause", "To my pick"}

# Waits until the page has stopped changing for 200 ms (NiceGUI redraws through
# a websocket, so there's no "page loaded" event to wait for); 8 s at most.
SETTLE_JS = """() => new Promise(res => {
  let t; const done = () => { obs.disconnect(); res(true); };
  const obs = new MutationObserver(() => { clearTimeout(t); t = setTimeout(done, 200); });
  obs.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
  t = setTimeout(done, 200); setTimeout(done, 8000);
})"""

# Marks the clickable views on the page behind any pop-up (or inside the top
# pop-up when inside=true): view toggles and tab rows, each with data-chk="<n>".
MARK_JS = """(inside) => {
  document.querySelectorAll('[data-chk]').forEach(e => e.removeAttribute('data-chk'));
  const dialogs = [...document.querySelectorAll('.q-dialog .fof-popup')];
  const top = dialogs[dialogs.length - 1];
  const out = [];
  document.querySelectorAll('.q-btn-toggle, .q-tabs').forEach(e => {
    if (!e.offsetParent || e.closest('.main-tabs')) return;
    const inDialog = !!e.closest('.q-dialog');
    if (inside ? !(top && top.contains(e)) : inDialog) return;
    const items = [...e.querySelectorAll(e.classList.contains('q-tabs') ? '.q-tab' : 'button')];
    e.setAttribute('data-chk', String(out.length));
    out.push(items.map(b => b.innerText.trim()));
  });
  return out;
}"""

# Browser console messages that are known to be harmless: listed in the report, but
# they don't count as errors. Quasar (the screens' widget kit) prints this when a
# tooltip or menu outlives the element it was attached to, which happens when a
# part of the page is redrawn (e.g. the green bar after picking another team).
HARMLESS = [(re.compile(r'^Anchor: target "#c\d+" not found$'),
             "a tooltip or menu outlived the element it belonged to when that part of the page was redrawn")]

# Server log tracebacks that are known to be harmless (not the game's code): Python's
# networking on Windows reports a browser connection that closed while a page was
# being left (asyncio's proactor, WinError 10054).
HARMLESS_SERVER = [(lambda block: "ConnectionResetError: [WinError 10054]" in block
                    and "_call_connection_lost" in block,
                    "Windows reported a browser connection closed while leaving a page (asyncio)")]

TRACEBACK = "Traceback (most recent call last)"
ERROR_LINE = re.compile(r"^(\w[\w.]*(Error|Exception|Exit|Interrupt)|ERROR\b)")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def slug(text):
    return re.sub(r'[\\/:*?"<>|]+', "-", text).strip()[:90]


# ---- The game, in browser mode ------------------------------------------------

class Server:
    """python app.py --browser on a saves folder of its own; its log is read as it comes."""

    def __init__(self, saves_dir, log_path):
        self.port = free_port()
        self.lines = []
        self.lock = threading.Lock()
        self.log = open(log_path, "w", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "app.py", "--browser", "--no-show", f"--port={self.port}",
             f"--saves-dir={saves_dir}"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.port}"
        t0 = time.time()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError("The game stopped while starting:\n" + "".join(self.lines[-40:]))
            try:
                urllib.request.urlopen(self.url + "/", timeout=2)
                break
            except OSError:
                if time.time() - t0 > 90:
                    raise RuntimeError("The game didn't start in 90 s:\n" + "".join(self.lines[-40:]))
                time.sleep(0.3)

    def _read(self):
        for line in self.proc.stdout:
            with self.lock:
                self.lines.append(line)
            self.log.write(line)
            self.log.flush()

    def mark(self):
        with self.lock:
            return len(self.lines)

    def since(self, i):
        with self.lock:
            return self.lines[i:]

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def server_errors(lines):
    """Tracebacks and ERROR lines in the game's log: [(last line, the whole block)]."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if TRACEBACK in line:
            block = [line]
            j = i + 1
            while j < len(lines) and len(block) < 80:
                block.append(lines[j])
                if ERROR_LINE.match(lines[j]) and not lines[j].startswith(" "):
                    break
                j += 1
            out.append((block[-1].strip(), "".join(block)))
            i = j + 1
            continue
        if ERROR_LINE.match(line) and "ERROR" in line[:10]:
            out.append((line.strip(), line))
        i += 1
    return out


# ---- One worker: a server, a browser page, some saves --------------------------

class Worker:
    def __init__(self, name, browser, server, shots):
        self.name, self.server, self.shots = name, server, shots
        self.context = browser.new_context(viewport=SIZE)
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        self.problems = []
        self.harmless = {}                          # known-harmless console messages: why -> count
        self.steps = 0
        self.where = "starting"
        self.folder = None
        self.n = 0
        self.log_mark = server.mark()
        self.page.on("console", self._console)
        self.page.on("pageerror", lambda e: self.problem("browser error", str(e)))
        self.page.on("response", lambda r: r.status >= 500 and self.problem("server error",
                                                                              f"HTTP {r.status} for {r.url}"))

    def _console(self, msg):
        if msg.type != "error":
            return
        for pattern, why in HARMLESS:
            if pattern.match(msg.text):
                self.harmless[why] = self.harmless.get(why, 0) + 1
                return
        self.problem("browser console error", msg.text)

    def problem(self, kind, detail, block=None):
        self.problems.append({"where": self.where, "kind": kind, "detail": detail, "block": block})

    # ---- Steps ----
    def settle(self):
        try:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.evaluate(SETTLE_JS)
        except Exception as e:                      # the page went away mid-wait (a navigation)
            self.page.wait_for_timeout(300)
            if "Execution context was destroyed" not in str(e):
                raise

    def check(self):
        """After a step: the game's log, a 500 page, the game still running."""
        time.sleep(0.05)
        new = self.server.since(self.log_mark)
        self.log_mark += len(new)
        for last, block in server_errors(new):
            why = next((w for test, w in HARMLESS_SERVER if test(block)), None)
            if why:
                self.harmless[why] = self.harmless.get(why, 0) + 1
            else:
                self.problem("server error", last, block)
        try:
            body = self.page.inner_text("body", timeout=3000)
        except Exception:
            body = ""
        if re.search(r"\b500\b", body[:400]) and "Server error" in body[:400]:
            self.problem("server error", "the page shows '500 Server error'", body[:1500])
        if self.server.proc.poll() is not None:
            self.problem("server error", "the game stopped running")
            raise RuntimeError("the game stopped running")

    def step(self, label, action=None, shot=True):
        """Do one thing (action), wait for the page, check for errors, take a screenshot."""
        self.where = f"{self.folder} > {label}" if self.folder else label
        self.steps += 1
        ok = True
        if action is not None:
            try:
                action()
            except Exception as e:
                ok = False
                self.problem("couldn't do it", f"{type(e).__name__}: {str(e).splitlines()[0][:300]}")
        try:
            self.settle()
        except Exception as e:
            self.problem("couldn't do it", f"page didn't settle: {str(e).splitlines()[0][:200]}")
        self.check()
        if shot and ok and self.shots is not None:
            self.n += 1
            folder = self.shots / (self.folder or "menus")
            folder.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(folder / f"{self.n:02d} - {slug(label)}.png"))
        return ok

    def click(self, locator):
        locator.first.click()

    # ---- The menu screens ----
    def menus(self):
        self.folder, self.n = "00-menus", 0
        for label, path in (("Main menu", "/"), ("Load game", "/load"), ("Settings", "/settings"),
                            ("New game - league settings", "/new")):
            self.step(label, lambda p=path: self.page.goto(self.server.url + p))

    # ---- One save ----
    def open_save(self, entry):
        self.folder, self.n = entry["key"], 0
        p = self.page

        def load():
            p.goto(self.server.url + "/load")
            row = p.locator(".save-row", has_text=entry["name"])
            row.get_by_role("button", name="Load").click()
            p.wait_for_url("**/game", timeout=60000)
            p.locator(".top-band").wait_for(timeout=60000)
        return self.step("Opened", load)

    def check_save(self, entry):
        from screens import nav
        if not self.open_save(entry):
            return
        p = self.page
        self.close_popups()                         # e.g. the draft room opens by itself while drafting
        for section, pages in nav.SECTIONS:
            btn = p.locator(".nav-hub-btn", has_text=re.compile(rf"^\s*{re.escape(section)}\s*$"))
            if not self._appears(btn, timeout=1500):
                continue                            # not shown at this time of year (e.g. Draft in season)
            if section == "Draft" and p.locator(".subnav-btn").filter(has_text="Draft").count() == 0 \
                    and p.locator(".dviews, .dtop").count() == 0:
                self.draft_room(btn)
                continue
            self.step(section, lambda: self.click(btn), shot=len(pages) == 1)
            for page_name in pages:
                label = nav.PAGE_LABELS.get(page_name, page_name)
                pb = p.locator(".subnav-btn", has_text=re.compile(rf"^\s*{re.escape(label)}\s*\d*\s*$"))
                if not self._appears(pb, timeout=1500):
                    continue
                name = f"{section} - {label}" if len(pages) > 1 else section
                if len(pages) > 1:
                    self.step(name, lambda: self.click(pb))
                if page_name == "Draft":
                    self.draft_views(name)          # the startup draft, a page of its own
                self.views(name)
        if "contracts_resign" in entry["expect"] or "contracts_fa" in entry["expect"]:
            self.contracts(entry)
        self.popups(entry)
        self.team_picker()

    def views(self, name, inside=False):
        """Click every option of every view toggle and tab row showing, then put it back."""
        p = self.page

        def option(gi, ii):
            p.evaluate(MARK_JS, inside)
            tabs = p.locator(f'.q-tabs[data-chk="{gi}"]').count()
            return p.locator(f'[data-chk="{gi}"] ' + (".q-tab" if tabs else "button")).nth(ii)

        def active(el):
            # (a toggle's chosen option has its toggle-color, green-10 on every toggle in screens/;
            # if that changes, the only harm is one extra screenshot of the view already showing)
            cls = (el.get_attribute("class") or "").split()
            return "q-tab--active" in cls or "bg-green-10" in cls

        groups = p.evaluate(MARK_JS, inside)
        for gi, items in enumerate(groups):
            if not items or any(t in SKIP_TOGGLES for t in items) or set(items) <= SPEED_WORDS:
                continue
            groups_now = p.evaluate(MARK_JS, inside)
            if gi >= len(groups_now) or groups_now[gi] != items:
                continue                            # the page changed under it (another toggle's view)
            # the option showing now (that's the page's own screenshot); put back at the end
            first_active = next((ii for ii in range(len(items)) if active(option(gi, ii))), None)
            for ii, text in enumerate(items):
                el = option(gi, ii)
                if not text or ii == first_active or el.count() == 0:
                    continue
                if not el.is_enabled():
                    continue                        # greyed out at this time of year (e.g. Playoffs)
                self.step(f"{name} - {text}", lambda el=el: el.click())
            if first_active is not None:
                el = option(gi, first_active)
                if el.count() and not active(el):
                    self.step(f"{name} - back to {items[first_active]}", lambda: el.click(), shot=False)

    # ---- The draft ----
    def draft_room(self, btn):
        p = self.page
        if not self.step("Draft room", lambda: (self.click(btn),
                                                p.locator(".q-dialog .dtop").first.wait_for())):
            return
        self.draft_views("Draft room")
        self.close_popups()

    def draft_views(self, name):
        p = self.page
        views = p.locator(".dviews button")
        texts = [t.strip() for t in views.all_inner_texts()]
        for i, text in enumerate(texts[1:], 1):
            self.step(f"{name} - {text}", lambda i=i: views.nth(i).click())
        if len(texts) > 1:
            self.step(f"{name} - back to {texts[0]}", lambda: views.nth(0).click(), shot=False)

    # ---- Contracts with a player picked ----
    def _appears(self, locator, timeout=5000):
        """True once the element is on the page (waits: the page strip is rebuilt on every page
        change, and under a heavy CPU load a single look could catch it mid-rebuild and report
        a page as missing; Oct 25, the layout session's finding)."""
        try:
            locator.first.wait_for(state="attached", timeout=timeout)
            return True
        except Exception:
            return False

    def go(self, section, page_label=None):
        p = self.page
        btn = p.locator(".nav-hub-btn", has_text=re.compile(rf"^\s*{re.escape(section)}\s*$"))
        if not self._appears(btn):
            return False
        btn.first.click()
        self.settle()
        if page_label:
            pb = p.locator(".subnav-btn", has_text=re.compile(rf"^\s*{re.escape(page_label)}\s*\d*\s*$"))
            if not self._appears(pb):
                return False
            pb.first.click()
            self.settle()
        return True

    def contracts(self, entry):
        p = self.page
        if not self.go("Team", "Contracts"):
            self.problem("missing", "no Contracts page")
            return
        for view, need in (("Re-sign", "contracts_resign"), ("Free agency", "contracts_fa")):
            if need not in entry["expect"]:
                continue
            toggle = p.locator(".q-btn-toggle button", has_text=re.compile(rf"^\s*{re.escape(view)}\s*$"))
            if toggle.count() == 0:
                self.problem("missing", f"no '{view}' view on the Contracts page")
                continue
            self.step(f"Contracts - {view}", lambda: toggle.first.click(), shot=False)
            # (not the table's invisible scrolling spacer, tbody.q-virtual-scroll__padding)
            rows = p.locator(".q-tab-panel .q-table tbody:not(.q-virtual-scroll__padding) tr:visible")                 .filter(has=p.locator("td"))
            if rows.count() == 0 or "No data" in rows.first.inner_text():
                self.problem("missing", f"the Contracts page's {view} list is empty")
                continue
            self.step(f"Contracts - {view} - first player picked", lambda: rows.first.click())
        self.step("Contracts - back to Payroll",
                  lambda: p.locator(".q-btn-toggle button", has_text="Payroll").first.click(), shot=False)

    # ---- Pop-ups ----
    def popups(self, entry):
        p = self.page
        if self.go("Team", "Roster"):
            link = p.locator('.q-tab-panel a[href^="/player/"]')
            if link.count():
                if self.step("Player card pop-up", lambda: (link.first.click(),
                                                            p.locator(".fof-popup").first.wait_for())):
                    self.views("Player card pop-up", inside=True)
                self.close_popups()
            else:
                self.problem("missing", "no player links on the Roster page")
        if self.go("League", "Standings"):
            link = p.locator('.q-tab-panel a[href^="/team/"]')
            if link.count():
                if self.step("Team window pop-up", lambda: (link.first.click(),
                                                            p.locator(".fof-popup").first.wait_for())):
                    self.views("Team window pop-up", inside=True)
                self.close_popups()
            else:
                self.problem("missing", "no team links on the Standings page")
        # A played game's summary: Home's "Game summary" button (your last game), else the
        # one on the Watch a game page.
        for section, page_label in (("Home", None), ("Schedule", "Watch a game")):
            if not self.go(section, page_label):
                continue
            btn = p.locator(".q-tab-panel button:visible", has_text=re.compile(r"^\s*Game summary\s*$"))
            if btn.count():
                if self.step(f"Game summary pop-up (from {section})",
                             lambda: (btn.first.click(), p.locator(".fof-popup").first.wait_for())):
                    self.views("Game summary pop-up", inside=True)
                self.close_popups()
                break
        else:
            if "games_played" in entry["expect"]:
                self.problem("missing", "no Game summary button on Home or Watch a game")
        report = p.locator(".top-band button").filter(has=p.locator("i", has_text="description"))
        if report.count():
            if self.step("Offseason report pop-up", lambda: (report.first.click(),
                                                              p.locator(".fof-popup").first.wait_for())):
                self.views("Offseason report pop-up", inside=True)
            self.close_popups()
        elif "offseason_report" in entry["expect"]:
            self.problem("missing", "no offseason report button in the bar")

    def close_popups(self):
        p = self.page
        for _ in range(6):
            open_ = p.locator(".q-dialog .fof-popup")
            if open_.count() == 0:
                return
            close = open_.last.locator(".fof-popup-head button").filter(
                has=p.locator("i", has_text=re.compile(r"^close$")))
            if close.count():
                close.first.click()
            else:
                p.keyboard.press("Escape")
            self.settle()
        self.problem("couldn't do it", "a pop-up wouldn't close")

    # ---- The team picker ----
    def team_picker(self):
        p = self.page
        picker = p.locator(".team-picker-btn")
        if picker.count() == 0:
            return
        if not self.step("Team picker menu", lambda: (picker.first.click(),
                                                      p.locator(".q-menu .q-item").first.wait_for())):
            return
        items = p.locator(".q-menu .q-item")
        texts = items.all_inner_texts()
        other = next((i for i, t in enumerate(texts) if t.strip() != "Free agents" and "(your team)" not in t), None)
        if other is None:
            p.keyboard.press("Escape")
            return
        self.step(f"Viewing another team ({texts[other].strip()})", lambda: items.nth(other).click())
        if self.go("Team", "Roster"):
            self.step("Viewing another team - Roster")
        if self.step("Free agent pool - Roster", lambda: (picker.first.click(),
                                                          p.locator(".q-menu .q-item", has_text="Free agents")
                                                          .first.click())):
            pass
        mine = p.get_by_role("button", name=re.compile("My Team"))
        if mine.count():
            self.step("Back to my team", lambda: mine.first.click(), shot=False)

    def close(self):
        self.context.close()


def run_worker(name, saves, menus, test_dir, run_root, shots, results):
    """One game server and browser for a share of the saves (each worker its own copy)."""
    from playwright.sync_api import sync_playwright
    folder = run_root / name
    folder.mkdir(parents=True)
    for e in saves:
        shutil.copyfile(test_dir / e["file"], folder / e["file"])
        hist = test_dir / (Path(e["file"]).stem + ".history.db")
        if hist.exists():
            shutil.copyfile(hist, folder / hist.name)
    server = Server(folder, run_root / f"{name}-game-log.txt")
    w = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge")
            w = Worker(name, browser, server, shots)
            if menus:
                w.menus()
            for e in saves:
                t0 = time.time()
                try:
                    w.check_save(e)
                except Exception as ex:
                    w.problem("check stopped", f"{type(ex).__name__}: {str(ex).splitlines()[0][:300]}")
                    if server.proc.poll() is not None:
                        break
                print(f"  [{name}] {e['key']:<24} {time.time() - t0:5.0f}s")
            w.close()
            browser.close()
    finally:
        server.stop()
        results[name] = {"problems": w.problems if w else [{"where": name, "kind": "check stopped",
                                                             "detail": "worker didn't start", "block": None}],
                         "steps": w.steps if w else 0, "harmless": w.harmless if w else {}}


def empty_folder(folder):
    """Delete what's in a folder but keep the folder (OneDrive can briefly lock a
    folder that was just emptied, so removing the folder itself fails now and then)."""
    import os, stat
    folder.mkdir(parents=True, exist_ok=True)

    def retry(fn, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        time.sleep(0.2)
        fn(path)
    for item in folder.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item, onexc=retry)
        else:
            item.unlink()


def main():
    ap = argparse.ArgumentParser(description="Open every screen on every test save and report errors.")
    ap.add_argument("--saves", help="comma-separated save keys (default: all), e.g. 12-fa-wave1")
    ap.add_argument("--test-saves", type=Path, default=SAVES_DIR)
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="screenshots and the report")
    ap.add_argument("--no-shots", action="store_true", help="no screenshots (faster)")
    ap.add_argument("--workers", type=int, default=3, help="game copies checked side by side (default 3)")
    a = ap.parse_args()
    try:
        import playwright  # noqa: F401
    except ImportError:
        raise SystemExit("Playwright isn't installed. Run:\n    python -m pip install -r requirements-dev.txt")
    index_file = a.test_saves / "index.json"
    if not index_file.exists():
        raise SystemExit(f"No test saves in {a.test_saves}. Make them first:\n    python tools/make_test_saves.py")
    index = json.loads(index_file.read_text(encoding="utf-8"))
    entries = index["saves"]
    if a.saves:
        want = [k.strip() for k in a.saves.split(",")]
        entries = [e for e in entries if any(e["key"] == k or e["key"].startswith(k) for k in want)]
        if not entries:
            raise SystemExit(f"No test save matches {a.saves}.")
    out = a.out.resolve()
    empty_folder(out)
    shots = None if a.no_shots else out
    run_root = Path(tempfile.mkdtemp(prefix="screens-check-"))
    n = max(1, min(a.workers, len(entries)))
    shares = [entries[i::n] for i in range(n)]
    print(f"Checking {len(entries)} saves with {n} game copies side by side"
          + ("" if shots is None else f"; screenshots in {out}"))
    t0 = time.time()
    results = {}
    threads = [threading.Thread(target=run_worker, args=(f"w{i + 1}", share, i == 0 and not a.saves,
                                                         a.test_saves, run_root, shots, results))
               for i, share in enumerate(shares)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for i in range(n):
        log = run_root / f"w{i + 1}-game-log.txt"
        if log.exists():
            shutil.copyfile(log, out / log.name)
    shutil.rmtree(run_root, ignore_errors=True)

    problems = [pr for r in results.values() for pr in r["problems"]]
    steps = sum(r["steps"] for r in results.values())
    harmless = {}
    for r in results.values():
        for why, k in r["harmless"].items():
            harmless[why] = harmless.get(why, 0) + k
    lines = [f"Screens check: {len(entries)} saves, {steps} steps, {time.time() - t0:.0f}s, "
             f"{len(problems)} problem(s)", ""]
    for pr in problems:
        lines.append(f"[{pr['kind']}] {pr['where']}")
        lines.append(f"    {pr['detail']}")
        if pr.get("block"):
            lines += ["    | " + ln for ln in pr["block"].rstrip().splitlines()]
        lines.append("")
    if not problems:
        lines.append("No errors: every screen opened cleanly.")
    for why, k in harmless.items():
        lines.append(f"(Not counted: {k} known-harmless message(s): {why}.)")
    report = "\n".join(lines)
    (out / "report.txt").write_text(report + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps({"saves": [e["key"] for e in entries], "steps": steps,
                                                 "problems": problems, "harmless": harmless}, indent=2), encoding="utf-8")
    # Short version on screen (tracebacks are in report.txt).
    print()
    for ln in lines[:2]:
        print(ln)
    for pr in problems[:40]:
        print(f"  [{pr['kind']}] {pr['where']}\n      {pr['detail'][:200]}")
    if len(problems) > 40:
        print(f"  ... and {len(problems) - 40} more")
    print(("No errors: every screen opened cleanly." if not problems else "") + f"\nReport: {out / 'report.txt'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
