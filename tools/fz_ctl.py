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
  python tools/fz_ctl.py boot          menu/boot flow screenshots
  python tools/fz_ctl.py tour          chapter-1 route, real key menus
  python tools/fz_ctl.py gate          stop at the first gate, show menu
  python tools/fz_ctl.py esc           ESC opens/closes the main menu
  python tools/fz_ctl.py full          three-chapter marathon
"""
from __future__ import annotations

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
ROUTE_MARKERS = ("FZBOT: stop at wp", "FZBOT: ROUTE DONE")

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
    STAGE.mkdir(exist_ok=True)
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
        for p in SHOTS.iterdir():
            try:
                p.unlink()
            except OSError:
                pass
    for f in (LOG, OUTLOG, STAGE / "driver.log"):
        if f.exists():
            f.unlink()


def launch(bot: int = 1, stop: int = -1, combat: int = 0,
           timeout: int = 150, monsters: bool = True,
           extra: list[str] | None = None):
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
    try:
        winbot.console_cmd(hwnd, "quit")
    except Exception as e:  # noqa: BLE001
        print(f"quit via console failed ({e}); killing")
        proc.kill()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    try:
        fh.flush()
        fh.close()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.5)


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
           after_route: float = 0.0) -> bool:
    """Drive the game with REAL keys until the route signals completion.

    Menus are answered only on an explicit engine log cue
    ("FZ: gate menu <id>"), so blind Enter can never pick the wrong
    option. Intermission pages get Enter after each chapter. E is tapped
    for doors and the exit switch.
    """
    wb = winbot
    menus_seen = 0
    routes_seen = 0
    inter_enters = 0
    next_enter_at = 0.0
    last_e = 0.0
    last_enter = 0.0
    door_pressed = False
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
            if not door_pressed and "reached wp 22" in txt:
                door_pressed = True
                time.sleep(0.5)
                wb.capture(hwnd, SHOTS / "door_before.png")
                if wb.focus(hwnd):
                    wb.tap("e", 0.12)
                    dbg("pressed E at the trial door")
                else:
                    dbg("door: focus failed, cannot press E")
                time.sleep(0.8)
                wb.capture(hwnd, SHOTS / "door_after.png")
                continue

            if routes > routes_seen:
                routes_seen = routes
                inter_enters = 3
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
    "full": (None, dict(bot=1, stop=-1, combat=1, timeout=160,
                        monsters=True, want_routes=3, deadline=560,
                        fire=True, extra=["+set", "fz_autoanswer", "1"])),
}

# Scenarios that arm the in-engine route bot, and are therefore expected to
# print "FZBOT: route armed". boot/esc drive the stock menus instead.
BOT_SCENARIOS = ("tour", "gate", "menu", "door", "exit", "full")


# ----------------------------------------------------------------- main --

def run(scenario: str) -> int:
    build_all()
    preflight()
    if scenario == "check":
        return 0
    clean()
    stepfn, opts = SCENARIOS[scenario]
    driver_opts = {}
    for k in ("want_routes", "deadline"):
        if k in opts:
            driver_opts[k] = opts.pop(k)
    fire = opts.pop("fire", False)
    answer = opts.pop("answer", True)
    after_route = opts.pop("after_route", 0.0)
    proc, fh = launch(**opts)
    hwnd = wait_window(proc)
    print(f"window {hwnd:x}; running {scenario}")
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
        if scenario == "full":
            for cmd in ("give shotgun 1", "give shell 100",
                        "give rocketlauncher 1", "give rocketbox 5", "god"):
                winbot.console_cmd(hwnd, cmd)
        if driver_opts:
            ok = driver(hwnd, proc, time.time() + driver_opts["deadline"],
                        want_routes=driver_opts.get("want_routes", 1),
                        fire=fire)
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

    return report(scenario, ok)


def report(scenario: str, driver_ok: bool = True) -> int:
    print("\n== log ==")
    txt = read_log_tail()
    checks: list[tuple[str, bool, str]] = []

    def check(name, cond, detail=""):
        checks.append((name, cond, detail))
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if not cond and detail else ""))

    bot_lines = [l.strip() for l in txt.splitlines() if "FZBOT:" in l]
    for l in bot_lines[-30:]:
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
    if spawns:
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
    if scenario == "tour":
        check("reached trial door (wp22)",
              any("reached wp 22" in l for l in reached),
              f"{len(reached)} waypoints")
    if scenario == "full":
        armed = txt.count("FZBOT: route armed")
        done = txt.count("FZBOT: ROUTE DONE")
        check("three chapters armed", armed >= 3, f"armed={armed}")
        check("three routes done", done >= 3, f"done={done}")
        check("no timeout", "FZBOT: TIMEOUT" not in txt)

    shots = sorted(SHOTS.glob("*.png"), key=lambda p: p.stat().st_mtime)
    check("screenshots captured", len(shots) >= 3, f"found {len(shots)}")
    print("\nshots: " + ", ".join(p.name for p in shots[-14:]))
    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    scen = sys.argv[1] if len(sys.argv) > 1 else "tour"
    sys.exit(run(scen))
