#!/usr/bin/env python3
"""fz_ctl - one-command takeover of the anti-fraud demo.

Pipeline:
  1. tools/build.py packs the PK3; test hooks pack into fz-bot.pk3.
  2. A preflight run with -errorlog (batchrun) compiles every script and
     MAPINFO; errors print instead of popping a modal dialog. Exit 1337.
  3. Real run: UZDoom windowed; the in-engine route bot walks the chapter
     with real physics; THIS script drives the keyboard (winbot/SendInput)
     to answer choice menus, intermissions, doors and the exit switch.
  4. Exit is event driven: as soon as the route prints its final marker
     the engine is told to quit - no fixed sleeps at the end.

Usage:
  python tools/fz_ctl.py check         preflight only (script compile)
  python tools/fz_ctl.py static        WAD/MAPINFO/ZScript cross-checks
  python tools/fz_ctl.py boot          menu/boot flow screenshots
  python tools/fz_ctl.py tour          chapter-1 route, real key menus
  python tools/fz_ctl.py gate          stop at the first gate, show menu
  python tools/fz_ctl.py esc           ESC opens/closes the main menu
  python tools/fz_ctl.py chapter FZ02  one chapter end to end (default FZ02)
  python tools/fz_ctl.py lock          全部答错 -> 审判门必须打不开
  python tools/fz_ctl.py boss          杀掉 Boss -> 主谋证据 -> 出口
  python tools/fz_ctl.py full          three-chapter marathon
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import winbot  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "_staging" / "fztest"
SHOTS = STAGE / "bot_shots"
LOG = STAGE / "run.log"          # -logfile (best effort, flushed enough)
OUTLOG = STAGE / "bot_stdout.log"
PRELOG = STAGE / "preflight.log"
EXE = STAGE / "uzdoom.exe"
IWAD = STAGE / "freedoom1.wad"
BOT_PK3 = STAGE / "fz-bot.pk3"
HOOK_SRC = ROOT / "tools/testhooks/bot"

CHAPTER_WADS = ["FZ01.wad", "FZ02.wad", "FZ03.wad"]

FATAL_MARKERS = ("Script error", "errors while parsing", "Fatal error",
                 "Execution could not continue", "Access violation")
# Anything here means "this run is over, stop driving". The exit marker is
# what lets the harness quit the instant a chapter ends; TIMEOUT means the
# bot gave up (expected in the all-wrong run).
ROUTE_MARKERS = ("FZBOT: stop at wp", "FZBOT: ROUTE DONE",
                 "FZBOT: exit triggered", "FZBOT: TIMEOUT")

BOT_CFG = """[Doom.Bindings]
Ctrl=+attack
Space=+use
F=+use

[Doom.ConsoleVariables]
screenblocks=10
hud_althud=false
crosshair=1
"""


# ---------------------------------------------------------------- build --

def build_all() -> None:
    # STAGE must exist before anything is written into it: a fresh clone has
    # no _staging/ at all, and packaging the bot PK3 used to fail with
    # FileNotFoundError before stage() got a chance to mkdir.
    STAGE.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-I", str(ROOT / "tools/build.py")],
                   check=True)
    with zipfile.ZipFile(BOT_PK3, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HOOK_SRC / "MAPINFO", "MAPINFO")
        z.write(HOOK_SRC / "zscript.txt", "zscript.txt")
        for p in sorted((HOOK_SRC / "zscript").rglob("*.zs")):
            z.write(p, str(p.relative_to(HOOK_SRC)).replace("\\", "/"))
    stage()


def _insert_in_section(txt: str, header: str, lines: list[str]) -> str:
    """Insert key=value lines at the END of an INI section (so they win
    over earlier duplicates) or append the section when missing."""
    idx = txt.find(header)
    if idx < 0:
        return txt + "\n" + header + "\n" + "\n".join(lines) + "\n"
    start = idx + len(header)
    nxt = txt.find("\n[", start)
    end = nxt if nxt >= 0 else len(txt)
    block = txt[start:end]
    if not block.endswith("\n"):
        block += "\n"
    return txt[:start] + block + "\n".join(lines) + "\n" + txt[end:]


def build_test_cfg() -> str:
    """Start from the REAL player config (full default binds, visuals,
    language), then override only what the automation needs. A minimal
    hand-written config silently drops every default binding - including
    Escape, which made the main menu unreachable."""
    base = ROOT / "config/uzdoom.cfg"
    if not base.exists():
        base = ROOT / "build/uzdoom.cfg"  # legacy location
    txt = base.read_text(encoding="utf-8", errors="replace") if base.exists() else ""
    txt = _insert_in_section(txt, "[Doom.Bindings]", [
        "Escape=menu_main",
        "Ctrl=+attack",      # fire (default is +crouch in 5.0.3)
        "F=+use",
        "Space=+use",
    ])
    txt = _insert_in_section(txt, "[Doom.ConsoleVariables]", [
        "screenblocks=10",
        "hud_althud=false",
        "crosshair=1",
        "vid_fullscreen=0",
        "vid_defwidth=1280",
        "vid_defheight=720",
        "gl_texture_filter=0",
        "language=zh-Hans",
        "alwaysrun=1",
    ])
    return txt

ENGINE_FILES = [
    "uzdoom.exe", "uzdoom.pk3", "game_support.pk3", "lights.pk3",
    "brightmaps.pk3", "game_widescreen_gfx.pk3",
    "libcurl-x64.dll", "sndfile.dll", "soft_oal.dll",
]


def _provision_engine() -> None:
    """A fresh clone has no vendor binaries in the staging dir yet. Copy
    them from vendor/ (after `fetch_vendor.py import`) so the harness works
    without any manual setup."""
    import shutil
    if not EXE.exists():
        src = ROOT / "vendor/uzdoom-5.0.3"
        if not (src / "uzdoom.exe").exists():
            raise SystemExit(
                "engine missing. Import it once:\n"
                "  python tools/fetch_vendor.py import --uzdoom <dir> "
                "--freedoom <freedoom1.wad> --font <ttf>")
        for name in ENGINE_FILES:
            if (src / name).exists():
                shutil.copy2(src / name, STAGE / name)
    if not IWAD.exists():
        src = ROOT / "vendor/freedoom-0.13.0/freedoom1.wad"
        if not src.exists():
            raise SystemExit(
                "freedoom1.wad missing. Import it once:\n"
                "  python tools/fetch_vendor.py import --freedoom <freedoom1.wad>")
        shutil.copy2(src, IWAD)


def stage() -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    _provision_engine()
    (STAGE / "fanzha-demo.pk3").write_bytes(
        (ROOT / "build/fanzha-demo.pk3").read_bytes())
    for name in CHAPTER_WADS:
        (STAGE / name).write_bytes((ROOT / "build/maps" / name).read_bytes())
    (STAGE / "bot.cfg").write_text(build_test_cfg(), encoding="ascii")
    if not EXE.exists() or not IWAD.exists():
        raise SystemExit(f"stage missing engine/iwad: {EXE} {IWAD}")
    print(f"staged -> {STAGE}")


# -------------------------------------------------------------- preflight --

def game_args(preflight: bool) -> list[str]:
    args = [str(EXE), "-config", str(STAGE / "bot.cfg"), "-iwad", str(IWAD)]
    if preflight:
        # -errorlog => batchrun: compile everything, then exit 1337 with NO
        # modal dialog. This is the compile gate that keeps bad ZScript from
        # ever reaching a play session.
        args += ["-errorlog", str(PRELOG)]
    else:
        args += ["-logfile", str(LOG)]
    for w in CHAPTER_WADS:
        args += ["-file", str(STAGE / w)]
    args += ["-file", str(STAGE / "fanzha-demo.pk3"),
             "-file", str(BOT_PK3), "-nosound"]
    return args


def preflight() -> None:
    if PRELOG.exists():
        PRELOG.unlink()
    print("== preflight (script compile) ==")
    try:
        proc = subprocess.run(game_args(preflight=True), cwd=str(STAGE),
                              capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("FAIL preflight timed out")
        sys.exit(2)

    # -errorlog does not reliably produce a file here (same 5.0.3 quirk as
    # -logfile), and the engine prints parse errors on STDOUT instead. The
    # old code only read PRELOG, so a missing file read as "clean" and this
    # gate passed every script - including broken ones. Scan all channels.
    chunks = []
    if PRELOG.exists():
        chunks.append(PRELOG.read_text(encoding="utf-8", errors="replace"))
    for stream in (proc.stdout, proc.stderr):
        if stream:
            chunks.append(stream.decode("utf-8", "replace"))
    txt = "\n".join(chunks)

    bad = [l for l in txt.splitlines() if any(k in l for k in FATAL_MARKERS)]
    if bad:
        print("FAIL preflight: script/MAPINFO errors:")
        for l in bad[:20]:
            print("  " + l.strip())
        sys.exit(2)
    if proc.returncode not in (0, 1337):
        print(f"FAIL preflight: exit code {proc.returncode} "
              "(1337 = batchrun finished, so the engine died before compiling)")
        sys.exit(2)
    if not any(l.startswith("adding ") for l in txt.splitlines()):
        print("FAIL preflight: engine never loaded the PK3s - nothing was compiled")
        sys.exit(2)
    print("PASS preflight: scripts compiled clean")


# --------------------------------------------------------------- launch --

def kill_stage_instances() -> int:
    """Kill only the uzdoom processes THIS harness started.

    A blanket `taskkill /IM uzdoom.exe` also takes down the player's own
    game, which the README explicitly promises never happens. Match on the
    executable path instead - `_staging/fztest/uzdoom.exe` is unique to us.
    """
    target = str(EXE).replace("'", "''")
    script = (
        "Get-Process uzdoom -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.Path -eq '{target}' }} | "
        "ForEach-Object { $_.Id }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 0
    pids = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=30)
    return len(pids)


def clean() -> None:
    killed = kill_stage_instances()
    if killed:
        print(f"  cleaned {killed} leftover staging instance(s)")
    time.sleep(0.6)
    # The Vulkan pipeline cache is shared by every UZDoom install on this
    # machine, so we never delete it behind the user's back - just point at
    # it when a run dies (deleting it is the documented cure for AVs).
    cache = Path.home() / "AppData/Local/doom/uzdoom/vulkanpipelinecache"
    if cache.exists() and any(cache.glob("*")):
        print(f"  note: on random crashes delete {cache}")
    if SHOTS.exists():
        # The sandbox blocks bulk deletions (50+ files per turn), and a full
        # purge is 60-70 engine dumps. Trim the oldest dumps under a small
        # per-run budget instead: the newest ones are the evidence we keep,
        # and the fixed-name captures (menu_*/door_*/99_final) are simply
        # overwritten by the next run.
        dumps = sorted(SHOTS.glob("Screenshot_Doom_*.png"),
                       key=lambda p: p.stat().st_mtime)
        budget = 12
        for p in dumps:
            if budget <= 0:
                break
            try:
                p.unlink()
                budget -= 1
            except OSError:
                pass
    for f in (LOG, OUTLOG, STAGE / "driver.log"):
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass


def launch(bot: int = 1, stop: int = -1, combat: int = 0,
           timeout: int = 150, monsters: bool = True,
           extra: list[str] | None = None, mapname: str | None = None):
    args = game_args(preflight=False) + [
        "-skill", "1",
        "-shotdir", str(SHOTS),
        "+set", "enablescriptscreenshot", "1",
        "+set", "fz_bot", str(bot),
        "+set", "fz_bot_stop", str(stop),
        "+set", "fz_bot_combat", str(combat),
        "+set", "fz_bot_timeout", str(timeout),
        "+set", "vid_fullscreen", "0",
        "+set", "vid_defwidth", "1280",
        "+set", "vid_defheight", "720",
        "+set", "gl_texture_filter", "0",
        "+set", "language", "zh-Hans",
        "+set", "alwaysrun", "1",
    ]
    if extra:
        args += extra
    if mapname:
        # skip title/difficulty; the route bot picks up at wp0
        args += ["+map", mapname]
    if not monsters:
        args.append("-nomonsters")
    SHOTS.mkdir(exist_ok=True)
    fh = open(OUTLOG, "wb")
    proc = subprocess.Popen(args, cwd=str(STAGE), stdout=fh, stderr=fh)
    return proc, fh


def fatal_now() -> str:
    for f in (LOG, OUTLOG):
        if f.exists():
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = [l.strip() for l in txt.splitlines()
                    if any(k in l for k in FATAL_MARKERS)]
            if hits:
                return "\n".join(hits[:10])
    return ""


def dbg(msg: str) -> None:
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    with open(STAGE / "driver.log", "a", encoding="utf-8") as f:
        f.write(line + chr(10))
    print("  [driver] " + msg)


def read_log_tail() -> str:
    parts = []
    for f in (LOG, OUTLOG):
        if f.exists():
            try:
                parts.append(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(parts)


def wait_window(proc: subprocess.Popen, seconds: float = 90.0) -> int:
    end = time.time() + seconds
    while time.time() < end:
        err = fatal_now()
        if err:
            proc.kill()
            raise RuntimeError("engine reported a fatal error:\n" + err)
        hwnd = winbot.find_uzdoom(min_area=320 * 200, pid=proc.pid)
        if hwnd:
            time.sleep(1.5)
            return hwnd
        time.sleep(0.4)
    proc.kill()
    raise RuntimeError("uzdoom window not found")


def quit_engine(hwnd: int, proc: subprocess.Popen, fh) -> None:
    # The console path is unreliable here (synthetic keys do not reach SDL
    # raw input), so `quit` usually never executes. Waiting 15 s for a
    # graceful exit kept the engine simulating after the run was over - long
    # enough for the bot to walk into the NEXT chapter and pollute the log
    # with a phantom segment. Give it two seconds, then terminate our own
    # process handle (never a blanket taskkill).
    try:
        winbot.console_cmd(hwnd, "quit")
    except Exception as e:  # noqa: BLE001
        print(f"quit via console failed ({e}); killing")
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    try:
        fh.flush()
        fh.close()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.4)


# ---------------------------------------------------------------- steps --

def boot_steps() -> list:
    return [
        ("wait", 3.0), ("shot", "00_boot"),
        ("tap", "enter"), ("wait", 1.6), ("shot", "01_menu"),
        ("tap", "enter"), ("wait", 1.6), ("shot", "02_skill"),
        ("tap", "enter"), ("wait", 5.0), ("shot", "03_ingame"),
    ]


# ------------------------------------------------------------ key driver --

def driver(hwnd, proc, deadline: float, want_routes: int = 1,
           fire: bool = False, answer: bool = True,
           after_route: float = 0.0,
           want_chapters: int = 1, grace: float = 7.0,
           stop_on: str = "") -> bool:
    """Drive the game with REAL keys until the route signals completion.

    Menus are answered in-engine (fz_autoanswer), so blind Enter can never
    pick a wrong option. Intermission pages get Enter after each chapter.
    E is tapped whenever the route reports a new "reached wp 22" (the trial
    door face) - each chapter has its own, so the trigger is counted, not
    latched. The boss is downed from inside the engine (fz_bot_killboss),
    not by a console command: synthetic console keys do not reliably reach
    SDL raw input here.

    End of run: the last route stop before the exit is wp24 (boss-room
    centre), and the exit line is ~1.5 s of walking beyond it. Since the
    final chapter ends in the engine's end sequence (no next map, no event
    we can hook - Doom-format line specials are renumbered by the loader,
    so matching "special 52" from ZScript never fires), the driver grabs a
    screenshot at wp24 and quits `grace` seconds later. `want_chapters`
    keeps that from firing in the middle of the three-chapter marathon.

    `stop_on` closes a run the moment a literal engine message shows up.
    The lock scenario uses it on "Red key needed for this door.": that is
    the engine's own verdict on the trial door, which beats waiting for
    the bot's tic timeout (wticks is reset by every level restart, so a
    run that dies to the ambush never reaches it).
    """
    wb = winbot
    menus_seen = 0
    routes_seen = 0
    doors_seen = 0
    wp24_seen = 0
    grace_until = 0.0
    next_enter_at = 0.0
    last_e = 0.0
    last_enter = 0.0
    firing = False
    if fire and wb.focus(hwnd):
        wb._send_key(wb.VK["ctrl"])
        firing = True
    try:
        while time.time() < deadline:
            err = fatal_now()
            if err:
                proc.kill()
                raise RuntimeError("engine reported a fatal error:\n" + err)
            txt = read_log_tail()
            opens = txt.count("FZ: gate menu")
            routes = sum(txt.count(m) for m in ROUTE_MARKERS)
            armed = txt.count("FZBOT: route armed on")

            if stop_on and stop_on in txt:
                time.sleep(0.4)
                try:
                    wb.capture(hwnd, SHOTS / "locked_door.png")
                except Exception as e:  # noqa: BLE001
                    print(f"lock capture failed: {e}")
                dbg("stop_on hit: %s" % stop_on.strip())
                return True

            # A bot timeout means the route is over: it stops moving and the
            # driver would otherwise sit on the deadline doing nothing (the
            # stuck full run burned six minutes that way). Grab the frame
            # that shows the blockage and hand control back to the report.
            if "FZBOT: TIMEOUT" in txt:
                time.sleep(0.4)
                try:
                    wb.capture(hwnd, SHOTS / "timeout.png")
                except Exception as e:  # noqa: BLE001
                    print(f"timeout capture failed: {e}")
                dbg("bot timed out - stopping")
                return False

            if grace_until and time.time() >= grace_until:
                dbg("chapter over (wp24 + grace) - stopping")
                return True

            if opens > menus_seen:
                menus_seen = opens
                time.sleep(0.6)
                wb.capture(hwnd, SHOTS / f"menu_{menus_seen}_before.png")
                if not answer:
                    time.sleep(3.0)
                    dbg("menu held open for screenshot")
                    return True
                # fz_autoanswer commits inside the engine, so this works
                # even when the OS keyboard focus is elsewhere.
                time.sleep(2.2)
                wb.capture(hwnd, SHOTS / f"menu_{menus_seen}_after.png")
                dbg("menu %d answered in-engine" % menus_seen)
                continue

            # trial door: walk-up + E. Capture the leaf first so a
            # see-through/mis-textured door shows up in the artefacts.
            doors = txt.count("reached wp 22")
            if doors > doors_seen:
                doors_seen = doors
                time.sleep(0.5)
                wb.capture(hwnd, SHOTS / f"door_{doors_seen}_before.png")
                if wb.focus(hwnd):
                    wb.tap("e", 0.12)
                    dbg("pressed E at the trial door (#%d)" % doors_seen)
                else:
                    dbg("door: focus failed, cannot press E")
                time.sleep(0.8)
                wb.capture(hwnd, SHOTS / f"door_{doors_seen}_after.png")
                continue

            # chapter-over grace, only once every chapter we care about has
            # loaded (otherwise the marathon would stop after chapter 1)
            if armed >= want_chapters:
                # Each chapter has exactly one wp24, so the CURRENT chapter
                # has arrived at its boss centre only when the global count
                # reaches the number of chapters loaded so far. A plain
                # "wp24 > seen" test quits the marathon the moment chapter 3
                # loads, because chapters 1 and 2 already contributed to the
                # global count.
                wp24 = txt.count("reached wp 24")
                if wp24 >= armed and wp24 > wp24_seen:
                    wp24_seen = wp24
                    time.sleep(0.4)
                    try:
                        wb.capture(hwnd, SHOTS / f"bossroom_{wp24}.png")
                    except Exception as e:  # noqa: BLE001
                        print(f"bossroom capture failed: {e}")
                    grace_until = time.time() + grace
                    dbg("wp24 reached -> quitting in %.0fs" % grace)
                    continue

            if routes > routes_seen:
                routes_seen = routes
                next_enter_at = time.time() + 2.5

            if routes >= want_routes:
                if after_route > 0:
                    deadline = max(deadline, time.time() + after_route)
                    want_routes = 10 ** 9  # keep driving until deadline
                else:
                    return True

            now = time.time()
            # hard guard: never inject OS keys unless OUR window owns the
            # foreground, otherwise they land in the user's own game.
            if not wb.focus(hwnd):
                time.sleep(0.5)
                continue
            # Keep tapping Enter: intermission pages (case files) wait for
            # it indefinitely, and choice menus are committed in-engine, so
            # a stray Enter can never pick a wrong option.
            if now - last_enter > 2.4:
                wb.tap("enter", 0.08)
                last_enter = now
            elif now - last_e > 4.5:
                wb.tap("e", 0.07)
                last_e = now
            time.sleep(0.4)
        return False
    finally:
        if firing:
            try:
                wb._send_key(wb.VK["ctrl"], up=True)
            except Exception:  # noqa: BLE001
                pass


# ------------------------------------------------------------ scenarios --

def sc_boot() -> list:
    return boot_steps() + [("console", "inventorylist"), ("shot", "99_final")]


def sc_gate() -> list:
    return boot_steps()


def sc_esc() -> list:
    return boot_steps() + [
        ("wait", 0.8),
        # the player reports ESC needs a longer press to register reliably;
        # automation mirrors real play (hold) instead of a synthetic tap
        ("key", "esc", 2.0), ("wait", 1.0), ("shot", "10_esc_menu"),
        ("key", "esc", 2.0), ("wait", 1.0), ("shot", "11_esc_closed"),
        ("shot", "99_final"),
    ]


SCENARIOS = {
    "boot": (sc_boot, dict(bot=0, monsters=True)),
    "tour": (None, dict(bot=1, stop=23, timeout=130, monsters=False,
                        want_routes=1, deadline=170,
                        extra=["+set", "fz_autoanswer", "1"])),
    "gate": (sc_gate, dict(bot=1, stop=4, timeout=60, monsters=False,
                           want_routes=1, deadline=80,
                           extra=["+set", "fz_autoanswer", "1"])),
    "esc": (sc_esc, dict(bot=0, monsters=False)),
    "menu": (None, dict(bot=1, stop=4, timeout=60, monsters=False,
                        want_routes=1, deadline=50, answer=False)),
    "door": (None, dict(bot=1, stop=24, timeout=110, monsters=False,
                        want_routes=1, deadline=140,
                        extra=["+set", "fz_autoanswer", "1"])),
    "exit": (None, dict(bot=1, stop=-1, timeout=150, monsters=False,
                        want_routes=1, deadline=210, after_route=25,
                        extra=["+set", "fz_autoanswer", "1"])),
    # one chapter, no monsters: gates -> evidence -> door -> exit. Fast
    # enough to run per chapter while fixing map/logic bugs.
    "chapter": (None, dict(bot=1, stop=-1, timeout=100, monsters=False,
                           want_routes=1, deadline=160,
                           extra=["+set", "fz_autoanswer", "1"])),
    # every answer wrong, but all three evidence crates collected: the chain
    # count reaches 3 and the trial door must STILL stay shut, because the
    # red card now also requires both chapter choices to be answered
    # correctly. That is the behavioural proof that the menus have a veto;
    # before this rule the crates alone were enough to walk through.
    # `fz_bot_god` keeps the run deterministic: a wrong answer summons an
    # ambush, and a point blank shotgun blast can restart the chapter.
    "lock": (None, dict(bot=1, stop=-1, timeout=110, monsters=False,
                        want_routes=1, deadline=180, expect_locked=True,
                        stop_on="Red key needed for this door.",
                        extra=["+set", "fz_autoanswer", "2",
                               "+set", "fz_bot_god", "1"])),
    # 反例之二：答错之后能不能补救。第一题故意答错（choice 1），机器人走开再
    # 回到终端重答（choice 0），必须照样拿到红卡、开门进 Boss 房——这就是
    # "答对才算" 不会变成死路的实测证据。
    "retry": (None, dict(bot=1, stop=24, timeout=150, monsters=False,
                         want_routes=1, deadline=240,
                         extra=["+set", "fz_autoanswer", "3",
                                "+set", "fz_bot_retry", "1",
                                "+set", "fz_bot_god", "1"])),
    # boss death -> master proof -> stage 3 -> exit. The boss is dropped by
    # the in-engine seam (fz_bot_killboss) rather than a console `kill
    # monsters`: synthetic console keys do not reliably reach SDL's raw
    # input in this harness, and the seam goes through the exact same
    # DamageMobj path a player's shotgun would.
    "boss": (None, dict(bot=1, stop=-1, combat=1, timeout=110,
                        monsters=True, want_routes=1, deadline=200,
                        fire=True, extra=["+set", "fz_autoanswer", "1",
                                          "+set", "fz_bot_killboss", "1",
                                          "+set", "fz_bot_god", "1",
                                          "+set", "fz_bot_ammo", "1"])),
    "full": (None, dict(bot=1, stop=-1, combat=1, timeout=190,
                        monsters=True, want_routes=3, deadline=780,
                        want_chapters=3, grace=8.0,
                        fire=True, extra=["+set", "fz_autoanswer", "1",
                                          "+set", "fz_bot_killboss", "1",
                                          "+set", "fz_bot_god", "1",
                                          "+set", "fz_bot_ammo", "1"])),
}

# Scenarios that arm the in-engine route bot, and are therefore expected to
# print "FZBOT: route armed". boot/esc drive the stock menus instead.
BOT_SCENARIOS = ("tour", "gate", "menu", "door", "exit", "chapter", "lock",
                 "retry", "boss", "full")

CHAPTER_SCENARIOS = ("chapter", "lock", "retry", "boss", "full")


# ----------------------------------------------------------------- main --

def static_tests() -> int:
    print("== static logic tests (WAD / MAPINFO / ZScript) ==")
    r = subprocess.run([sys.executable, "-I",
                        str(ROOT / "tools/test_game_logic.py")],
                       cwd=str(ROOT))
    return 0 if r.returncode == 0 else 2


def run(scenario: str, mapname: str | None = None) -> int:
    if scenario == "static":
        return static_tests()
    build_all()
    preflight()
    if scenario == "check":
        return 0
    clean()
    stepfn, opts = SCENARIOS[scenario]
    opts = dict(opts)                      # SCENARIOS is module state
    driver_opts = {}
    for k in ("want_routes", "deadline", "want_chapters", "grace"):
        if k in opts:
            driver_opts[k] = opts.pop(k)
    fire = opts.pop("fire", False)
    answer = opts.pop("answer", True)
    after_route = opts.pop("after_route", 0.0)
    opts.pop("kill_boss", None)           # legacy flag, replaced by the seam
    expect_locked = opts.pop("expect_locked", False)
    stop_on = opts.pop("stop_on", "")
    if scenario in CHAPTER_SCENARIOS and not mapname:
        mapname = "FZ01"
    if mapname:
        opts["mapname"] = mapname
    proc, fh = launch(**opts)
    hwnd = wait_window(proc)
    print(f"window {hwnd:x}; running {scenario}"
          + (f" on {mapname}" if mapname else ""))
    winbot.SHOT_DIR = SHOTS
    ok = False
    try:
        if stepfn is not None:
            for step in stepfn():
                op = step[0]
                if op == "wait":
                    end = time.time() + step[1]
                    while time.time() < end:
                        err = fatal_now()
                        if err:
                            raise RuntimeError("engine fatal:\n" + err)
                        time.sleep(0.3)
                elif op == "key":
                    winbot.focus(hwnd)
                    winbot.hold_key(step[1], step[2])
                elif op == "tap":
                    winbot.focus(hwnd)
                    winbot.tap(step[1])
                elif op == "console":
                    winbot.console_cmd(hwnd, step[1])
                elif op == "shot":
                    winbot.capture(hwnd, SHOTS / f"{step[1]}.png")
                else:
                    raise ValueError(f"unknown op {op!r}")
        # NOTE: no console injection here. Synthetic `~`/Escape events do
        # not reliably reach SDL raw input in this harness (the console
        # silently refuses to open), so every need is met by an in-engine
        # seam instead: fz_bot_killboss drops the boss, the map already
        # hands out a shotgun + shells on the route, and fz_bot clamps
        # health so the marathon survives the ambushes.
        if driver_opts:
            ok = driver(hwnd, proc, time.time() + driver_opts["deadline"],
                        want_routes=driver_opts.get("want_routes", 1),
                        fire=fire,
                        want_chapters=driver_opts.get("want_chapters", 1),
                        grace=driver_opts.get("grace", 7.0),
                        stop_on=stop_on)
            print(f"driver finished: {'route complete' if ok else 'deadline hit'}")
            try:
                winbot.capture(hwnd, SHOTS / "99_final.png")
            except Exception as e:  # noqa: BLE001
                print(f"final capture failed: {e}")
        quit_engine(hwnd, proc, fh)
    except Exception as exc:
        proc.kill()
        try:
            fh.flush()
            fh.close()
        except Exception:  # noqa: BLE001
            pass
        print(f"\nABORT: {exc}")
        return 2

    return report(scenario, ok, mapname, expect_locked)


# ------------------------------------------------------------- reporting --

def chapter_segments(txt: str) -> list[tuple[str, list[str]]]:
    """Split the log into one segment per loaded map (in load order), using
    the bot's "route armed on <map>" banner as the separator."""
    segs: list[tuple[str, list[str]]] = []
    for line in txt.splitlines():
        m = re.search(r"FZBOT: route armed on (\S+)", line)
        if m:
            segs.append((m.group(1), [line]))
        elif segs:
            segs[-1][1].append(line)
    return segs


def check_chapter(check, name: str, lines: list[str], positive=True):
    """Per-chapter assertions. `positive=False` is the all-wrong run: the
    gate menus must still appear and be answered, the three crates can even
    fill the evidence count to 3, but the red card is withheld because both
    chapter choices were answered wrong - so the trial door has to stay
    shut. That is the veto the menus are supposed to have.

    The opening waypoint line carries the inventory the chapter started
    with, which is the direct test for the cross-chapter leak: chapter 2
    must begin with zero evidence / no red card / no stage tokens even
    though the player carried all of them out of chapter 1."""
    text = "\n".join(lines)
    spawns = [l for l in lines if "FZBOT: spawns" in l]
    gates = [l for l in lines if "FZDBG: gate" in l]
    wp0 = [l for l in lines if "reached wp 0 " in l]
    wp22 = [l for l in lines if "reached wp 22" in l]
    wp23 = [l for l in lines if "reached wp 23" in l]
    wp24 = [l for l in lines if "reached wp 24" in l]
    wp25 = [l for l in lines if "reached wp 25" in l]
    # wp25 sits past the exit threshold. If the bot ever walks there the
    # level did NOT end, i.e. the exit line failed.
    exit_ok = not wp25 and "ROUTE DONE" not in text

    check(f"{name}: 自定义物件生成正确（终端 2/证据 3/简报 1）",
          any("gates=2" in l and "evidence=3" in l and "brief=1" in l
              for l in spawns),
          "; ".join(spawns[:2]) or "no spawn probe line")
    check(f"{name}: 章节起始状态干净（证据/红卡/进度=0）",
          bool(wp0) and any("ev=0" in l and "red=0" in l and "st1=0" in l
                            and "st2=0" in l and "st3=0" in l for l in wp0),
          "; ".join(wp0[:1]) or "no wp0 line")
    check(f"{name}: 两道抉择菜单都弹出来了", len(gates) >= 2,
          f"gates answered={len(gates)}")
    want = "choice 0" if positive else "choice 1"
    check(f"{name}: 抉择已作答且选项正确（{want}）",
          len(gates) >= 2 and all(want in l for l in gates),
          "; ".join(gates[:3]))
    check(f"{name}: 走到审判门（wp22）", bool(wp22),
          f"last waypoint line: {text.strip().splitlines()[-1][:80]}")

    if positive:
        check(f"{name}: 门前证据链完整（ev=3 red=1）",
              any("ev=3" in l and "red=1" in l for l in wp22),
              "; ".join(wp22[:1]))
        check(f"{name}: 审判门开启并走进 Boss 房（wp23）", bool(wp23),
              "no wp23: door stayed locked")
        check(f"{name}: 出口生效（越过出口线后关卡结束）", exit_ok,
              "; ".join(wp25[:1]) or "route ran to the end without exiting")
    else:
        # 全答错、但三个证据箱都捡了：证据数照样能到 3，红卡仍然不给。
        # 这就是"抉择有否决权"的行为证据（旧规则下箱子独自就能开门）。
        check(f"{name}: 全错时证据箱仍能凑满 3 件（ev=3）",
              any("ev=3" in l for l in wp22), "; ".join(wp22[:1]))
        check(f"{name}: 全错不发红卡（red=0）",
              not any("red=1" in l for l in wp22 + wp24),
              "; ".join(wp22[:1]))
        check(f"{name}: 全错时审判门打不开（无 wp23）", not wp23,
              "door opened without the key!")
    return {"wp22": bool(wp22), "wp23": bool(wp23), "wp24": bool(wp24),
            "exit": exit_ok}


def report(scenario: str, driver_ok: bool, mapname: str | None = None,
           expect_locked: bool = False) -> int:
    print("\n== log ==")
    txt = read_log_tail()
    checks: list[tuple[str, bool, str]] = []

    def check(name, cond, detail=""):
        checks.append((name, cond, detail))
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if not cond and detail else ""))

    bot_lines = [l.strip() for l in txt.splitlines() if "FZBOT:" in l or "FZDBG:" in l]
    for l in bot_lines[-40:]:
        print("  " + l)
    reached = [l for l in bot_lines if "reached wp" in l]
    spawns = [l for l in bot_lines if "spawns" in l]

    check("log captured", bool(txt.strip()), f"bytes={len(txt)}")
    check("no script errors",
          not any(k in txt for k in FATAL_MARKERS))
    # boot/esc drive the stock menus without the route bot, so asserting
    # "bot armed" there would fail by construction.
    if scenario in BOT_SCENARIOS:
        check("bot armed", "FZBOT: route armed" in txt)
    if spawns and scenario not in CHAPTER_SCENARIOS:
        for l in spawns[:3]:
            print("  spawn probe: " + l)
        check("custom things spawned",
              any("gates=2" in l and "evidence=3" in l and "brief=1" in l
                  for l in spawns),
              "; ".join(spawns[:2]))

    if scenario in ("tour", "gate"):
        check("route finished", driver_ok)
    if scenario == "gate":
        check("gate answered correctly (choice 0)",
              "FZDBG: gate" in txt and "choice 0" in txt)
    if scenario == "tour":
        check("evidence collected (ev=3)", any("ev=3" in l for l in reached))
        check("both gate menus answered (st2)",
              any("st2=1" in l for l in reached))
        check("reached trial door (wp22)",
              any("reached wp 22" in l for l in reached),
              f"{len(reached)} waypoints")
    if scenario == "exit":
        check("exit switch ended chapter 1",
              "FZBOT: route armed on FZ02" in txt,
              "FZ02 never loaded")
    if scenario == "door":
        check("trial door opened (entered boss room)",
              any("reached wp 23" in l for l in reached)
              or "stop at wp 24" in txt,
              "no wp23 line: door did not open")
        check("no script errors on use", "needs" not in txt.lower())

    segs = chapter_segments(txt)

    if scenario == "chapter":
        if segs:
            st = check_chapter(check, segs[0][0], segs[0][1], positive=True)
            if mapname == "FZ03":
                # last chapter: the exit starts the end sequence instead of
                # loading another map, so there is no second segment to look
                # for - the exit marker is the end-of-chapter proof.
                check("最后一章：出口触发结束序列", st["exit"],
                      "exit line never fired")
            else:
                check("本章出口把玩家送进下一章",
                      len(segs) >= 2,
                      "no next chapter armed (exit line never fired)")
        else:
            check("route armed", False, "no segment in log")

    if scenario == "lock":
        if segs:
            check_chapter(check, segs[0][0], segs[0][1], positive=False)
            maps = [n for n, _ in segs]
            check("门锁着时没有进入下一章",
                  not ({"FZ02", "FZ03"} & set(maps)), f"maps={maps}")
            # The engine prints this on a use-trace against a locked door,
            # so it is first-hand proof the block is the lock, not a bot
            # navigation failure (a stuck bot would print nothing).
            check("门锁着有引擎提示（Red key needed）",
                  "Red key needed for this door." in txt,
                  "the door never reported itself locked")
            check("没有在门锁着的情况下误判为通关",
                  not any("reached wp 23" in l or "reached wp 24" in l
                          for l in bot_lines))
            if len(segs) > 1:
                # 答错会召唤伏击，玩家被打死就会重开本章。重开后终端必须
                # 还能弹出并接受作答 - 否则就是"死了以后这道题永远答不了"
                # 的软锁。重开后可能被伏击怪堵在门口，所以只要求重开后的
                # 第一道题能正常走完（>=1），不要求跑完全程。
                gates2 = [l for l in segs[-1][1] if "FZDBG: gate" in l]
                check("本章重开后终端仍可作答（没有软锁）", len(gates2) >= 1,
                      f"only {len(gates2)} gate menus after restart")
                check("重开后的状态也是干净的（ev=0 red=0）",
                      any("reached wp 0" in l and "ev=0" in l and "red=0" in l
                          for l in segs[-1][1]),
                      "restarted chapter carried stale state")
            check("没有因为空转崩掉", not any(k in txt for k in FATAL_MARKERS))

    if scenario == "retry":
        # 答错 → 回终端重答 → 照样能结案。这一组断言是"答对才算证据"不会
        # 变成死路的实测依据：终端在答错时不退休，冷却结束后可重新触发。
        g11 = [l for l in bot_lines if "FZDBG: gate 11" in l]
        check("第一题先答错（choice 1）",
              any("choice 1" in l for l in g11), "; ".join(g11[:2]))
        check("答错后回到终端重答（同一终端弹出第二次）", len(g11) >= 2,
              f"gate 11 menus={len(g11)}")
        check("重答答对（choice 0）",
              any("choice 0" in l for l in g11), "; ".join(g11[-2:]))
        check("重答后拿到红卡（red=1）",
              any("red=1" in l for l in reached), "no red=1 line")
        check("重答后审判门打开（进 Boss 房 wp23）",
              any("reached wp 23" in l for l in reached),
              "door never opened after the retry")

    if scenario == "boss":
        if segs:
            st = check_chapter(check, segs[0][0], segs[0][1], positive=True)
            lines = segs[0][1]
            seq = [l for l in lines if "st3=" in l]
            # The chapter must start with no stage-3 token and end with it.
            # It can flip either from the fz_bot_killboss seam or from the
            # bot's own shotgun fire - both go through WorldThingDied, so
            # the assertion is on the state change, not on who pulled the
            # trigger.
            first3 = next((l for l in seq if "st3=" in l), "")
            flip = any("st3=1" in l for l in seq)
            check("主谋证据来自 Boss 掉落（本章 st3 由 0 变为 1）",
                  "st3=0" in first3 and flip,
                  f"first={first3[:60]} flip={flip}")
            check("捡到主谋证据后走出出口", len(segs) >= 2 and st["wp24"],
                  "never reached the exit")

    if scenario == "full":
        armed = len(segs)
        check("三章全部加载（3 次 route armed）", armed >= 3, f"armed={armed}")
        check("没有 TIMEOUT / 卡死", "FZBOT: TIMEOUT" not in txt)
        for name, lines in segs:
            check_chapter(check, name, lines, positive=True)

    shots = sorted(SHOTS.glob("*.png"), key=lambda p: p.stat().st_mtime)
    check("screenshots captured", len(shots) >= 3, f"found {len(shots)}")
    print("\nshots: " + ", ".join(p.name for p in shots[-14:]))
    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    scen = sys.argv[1] if len(sys.argv) > 1 else "tour"
    arg_map = sys.argv[2].upper() if len(sys.argv) > 2 else None
    sys.exit(run(scen, arg_map))
