#!/usr/bin/env python3
"""Static logic tests for the anti-fraud demo maps and gate system.

No engine, no window: this reads the generated WADs, MAPINFO and the
ZScript sources and cross-checks them against each other. It is the test
that would have caught every blocker we actually shipped:

  * a gate terminal placed with the wrong ednum (chapter 2 got an evidence
    crate + the master proof, chapter 3 got unregistered numbers, so the
    choice menus - and therefore the evidence, and therefore the key -
    never existed)                                  -> test_thing_numbers
  * a thing ednum that the engine silently drops     -> test_thing_numbers
  * a monster slot filled with a backpack / player
    start instead of a monster                       -> test_thing_numbers
  * a gate id in the map with no menu text, no
    outcome mapping or a mismatched "correct" index   -> test_gate_data
  * the stage token a terminal waits for disagreeing
    with the token the outcome hands out              -> test_stage_tokens
  * the trial door missing / wrong special / blocking
    leaves (door you can never walk through)          -> test_trial_door
  * a room sealed off by geometry (the classic
    "air wall" from drawing a boundary twice)         -> test_reachability

Usage: python tools/test_game_logic.py [-v]
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gen_maps  # noqa: E402  (chapter table + ednum constants, single source)

GAME = ROOT / "game"
MAPS = GAME / "maps"
ZSCRIPT = GAME / "zscript"
VERBOSE = "-v" in sys.argv

# Engine ednums this project places. Anything outside this set must be
# registered in MAPINFO's doomednums block (i.e. be one of ours).
EXPECTED_ENGINE_EDNUMS = {
    1: "player 1 start",
    9: "ShotgunGuy",
    2001: "Shotgun",
    2002: "Chaingun",
    2007: "Clip",
    2008: "Shells",
    2011: "Stimpack",
    2012: "Medikit",
    2018: "ArmorBonus",
    3001: "DoomImp",
    3002: "Demon",
    3003: "BaronOfHell",
    3004: "Zombieman",
    3005: "Cacodemon",
}

# Doom door specials: 26/27/28 = blue/yellow/red DR (closes again),
# 31/32/33 = blue/yellow/red D1 (opens once, stays open).
DOOR_SPECIALS = {26: "blue DR", 27: "yellow DR", 28: "red DR",
                 31: "blue D1", 32: "yellow D1", 33: "red D1"}
EXIT_SPECIAL = 52      # W1 Exit Level
SWITCH_SPECIAL = 11    # S1 Exit / decorative switch wall

FAILS: list[str] = []
CHECKS = [0]


# --------------------------------------------------------------- helpers --

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def func_body(src: str, name: str) -> str:
    """Return the braced body of `name(...)`, brace-matched."""
    m = re.search(r"\b%s\s*\([^)]*\)\s*(?:const\s*)?\{" % re.escape(name), src)
    if not m:
        return ""
    i = m.end() - 1
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return ""


def parse_udmf(text: str) -> dict:
    """Parse a UDMF TEXTMAP into the same dict shape parse_wad returns, so
    every geometry check below works without knowing the map format.

    UDMF assigns indices by order of appearance, which is also how the
    binary lumps are ordered, so v1/v2/sidefront/back stay comparable."""
    kinds = ("vertex", "linedef", "sidedef", "sector", "thing")
    blocks: dict[str, list[dict[str, str]]] = {k: [] for k in kinds}
    for m in re.finditer(r"\b(%s)\b[^{]*\{([^}]*)\}" % "|".join(kinds),
                         text, re.S):
        props = dict(re.findall(r"([a-z0-9_]+)\s*=\s*([^;]+);", m.group(2)))
        blocks[m.group(1)].append({k: v.strip() for k, v in props.items()})

    def num(blk: dict, key: str, default: int = 0) -> int:
        raw = blk.get(key)
        return default if raw is None else int(float(raw))

    def on(blk: dict, key: str) -> bool:
        return blk.get(key, "false") == "true"

    def tex(blk: dict, key: str) -> str:
        return (blk.get(key, '"-"').strip('"') or "-").upper()

    def flags(blk: dict) -> int:
        # Rebuild the Doom option bits so the thing checks stay identical.
        f = 0
        for bit, name in ((1, "skill1"), (2, "skill2"), (4, "skill3")):
            if on(blk, name):
                f |= bit
        if on(blk, "ambush"):
            f |= 8
        if not on(blk, "single"):
            f |= 16
        return f

    verts = [(num(b, "x"), num(b, "y")) for b in blocks["vertex"]]
    sides = [(num(b, "offsetx"), num(b, "offsety"),
              tex(b, "texturetop"), tex(b, "texturebottom"),
              tex(b, "texturemiddle"), num(b, "sector"))
             for b in blocks["sidedef"]]
    lines = [{"v1": num(b, "v1"), "v2": num(b, "v2"),
              "flags": (1 if on(b, "blocking") else 0)
                       | (4 if on(b, "twosided") else 0),
              "special": num(b, "special"),
              # the Doom line tag lives in arg0 in the translated namespace
              "tag": num(b, "arg0"),
              "front": num(b, "sidefront") if "sidefront" in b else None,
              "back": num(b, "sideback") if "sideback" in b else None}
             for b in blocks["linedef"]]
    sectors = [{"floor": num(b, "heightfloor"),
                "ceil": num(b, "heightceiling"),
                "floor_tex": tex(b, "texturefloor"),
                "ceil_tex": tex(b, "textureceiling"),
                "light": num(b, "lightlevel"),
                "special": num(b, "special"),
                "tag": num(b, "id")}
               for b in blocks["sector"]]
    things = [(num(b, "x"), num(b, "y"), num(b, "angle"), num(b, "type"),
               flags(b)) for b in blocks["thing"]]
    return {"things": things, "verts": verts, "sides": sides,
            "lines": lines, "sectors": sectors}


def parse_wad(path: Path) -> dict:
    return parse_bytes(path.read_bytes(), str(path))


def parse_bytes(data: bytes, label: str = "map") -> dict:
    magic, num, ofs = struct.unpack_from("<4sii", data, 0)
    if magic not in (b"IWAD", b"PWAD"):
        raise SystemExit("%s: not a WAD" % label)
    lumps: dict[str, bytes] = {}
    order: list[str] = []
    for i in range(num):
        pos, size, nm = struct.unpack_from("<ii8s", data, ofs + 16 * i)
        key = nm.rstrip(b"\0").decode("ascii", "replace").upper()
        lumps[key] = data[pos:pos + size]
        order.append(key)

    if "TEXTMAP" in lumps:
        out = parse_udmf(lumps["TEXTMAP"].decode("ascii"))
        out["lumps"] = lumps
        out["order"] = order
        return out

    things = [struct.unpack_from("<hhhHH", lumps["THINGS"], 10 * i)
              for i in range(len(lumps["THINGS"]) // 10)]
    verts = [struct.unpack_from("<hh", lumps["VERTEXES"], 4 * i)
             for i in range(len(lumps["VERTEXES"]) // 4)]
    sides = [struct.unpack_from("<hh8s8s8sh", lumps["SIDEDEFS"], 30 * i)
             for i in range(len(lumps["SIDEDEFS"]) // 30)]
    lines = [struct.unpack_from("<HHHHhHH", lumps["LINEDEFS"], 14 * i)
             for i in range(len(lumps["LINEDEFS"]) // 14)]
    sectors = [struct.unpack_from("<hh8s8shhh", lumps["SECTORS"], 26 * i)
               for i in range(len(lumps["SECTORS"]) // 26)]

    def name(raw: bytes) -> str:
        return raw.rstrip(b"\0").decode("ascii", "replace").upper()

    return {
        "lumps": lumps,
        "order": order,
        "things": things,                       # x,y,angle,type,flags
        "verts": verts,
        "sides": [(xo, yo, name(u), name(l), name(m), sec)
                  for xo, yo, u, l, m, sec in sides],
        "lines": [{"v1": v1, "v2": v2, "flags": fl, "special": sp, "tag": tg,
                   "front": None if fr == 0xFFFF else fr,
                   "back": None if bk == 0xFFFF else bk}
                  for v1, v2, fl, sp, tg, fr, bk in lines],
        "sectors": [{"floor": fh, "ceil": ch, "floor_tex": name(fl),
                     "ceil_tex": name(c), "light": lt, "special": sp,
                     "tag": tg}
                    for fh, ch, fl, c, lt, sp, tg in sectors],
    }


def sector_bbox(w: dict, idx: int) -> tuple[int, int, int, int]:
    """Bounding box of a sector, from the vertices of the lines that touch
    it. The generator only makes axis-aligned rectangles, so the box is the
    sector itself - good enough to locate a thing unambiguously."""
    xs, ys = [], []
    for ln in w["lines"]:
        for sd in (ln["front"], ln["back"]):
            if sd is None:
                continue
            if w["sides"][sd][5] != idx:
                continue
            for v in (ln["v1"], ln["v2"]):
                xs.append(w["verts"][v][0])
                ys.append(w["verts"][v][1])
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def sector_at(w: dict, x: int, y: int) -> int:
    hits = [i for i in range(len(w["sectors"]))
            if (lambda b: b[0] < x < b[2] and b[1] < y < b[3])(sector_bbox(w, i))]
    if len(hits) != 1:
        raise SystemExit("point (%d,%d) is in %d sectors %s"
                         % (x, y, len(hits), hits))
    return hits[0]


def sector_graph(w: dict) -> dict[int, set[int]]:
    g: dict[int, set[int]] = {i: set() for i in range(len(w["sectors"]))}
    for ln in w["lines"]:
        if ln["front"] is None or ln["back"] is None:
            continue
        a = w["sides"][ln["front"]][5]
        b = w["sides"][ln["back"]][5]
        if a != b:
            g[a].add(b)
            g[b].add(a)
    return g


def reachable(w: dict, start: int) -> set[int]:
    g = sector_graph(w)
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in g[cur]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


# ------------------------------------------------------------ zscript ----

def zscript_text() -> str:
    return strip_comments("\n".join(read(p) for p in sorted(ZSCRIPT.glob("*.zs"))))


def mapinfo() -> tuple[dict[int, str], dict[str, str | None]]:
    src = strip_comments(read(GAME / "mapinfo" / "MAPINFO"))
    doomed: dict[int, str] = {}
    block = re.search(r"doomednums\s*\{(.*?)\}", src, re.S)
    if block:
        for num, cls in re.findall(r"(\d+)\s*=\s*([A-Za-z0-9_]+)", block.group(1)):
            doomed[int(num)] = cls
    chain: dict[str, str | None] = {}
    for name, body in re.findall(r"map\s+(\S+)\s+\"[^\"]*\"\s*\{(.*?)\}",
                                 src, re.S):
        nxt = re.search(r"Next\s*=\s*\"([^\"]+)\"", body)
        chain[name] = nxt.group(1) if nxt else None
    return doomed, chain


def gate_classes(zs: str) -> dict[int, str]:
    """gate id -> class name, from `class FZGateNN : FZGateTerminal {
    override int GateId() const { return NN; } }`."""
    out: dict[int, str] = {}
    for cls, gid in re.findall(
            r"class\s+(FZGate\d+)\s*:\s*FZGateTerminal\s*\{\s*"
            r"override\s+int\s+GateId\s*\(\s*\)\s*const\s*\{\s*return\s+(\d+)\s*;",
            zs):
        out[int(gid)] = cls
    return out


def gate_data(zs: str) -> dict[int, dict]:
    body = func_body(zs, "Get")
    out: dict[int, dict] = {}
    for case in re.findall(r"case\s+(\d+)\s*:(.*?)break\s*;", body, re.S):
        gid = int(case[0])
        blob = case[1]
        entry = {}
        for field in ("title", "scenario", "optA", "optB"):
            m = re.search(r'\.%s\s*=\s*"(.*?)"\s*;' % field, blob, re.S)
            entry[field] = (m.group(1) if m else "").replace("\\n", "\n")
        m = re.search(r"\.correct\s*=\s*(\d+)", blob)
        entry["correct"] = int(m.group(1)) if m else None
        out[gid] = entry
    return out


def msg_ids(zs: str) -> set[int]:
    body = func_body(zs, "MsgText")
    return {int(i) for i in re.findall(r"case\s+(\d+)\s*:\s*return", body)}


def switch_entries(zs: str, func: str) -> dict[int, object]:
    """Parse a `switch (x) { case A: case B: return V; ... }` into
    {A: V, B: V}. Multiple labels may share one return, which a naive
    case->return regex misses."""
    body = func_body(zs, func)
    out: dict[int, object] = {}
    pending: list[int] = []
    for m in re.finditer(r"case\s+(\d+)\s*:|\breturn\s+([^;]+);", body):
        if m.group(1) is not None:
            pending.append(int(m.group(1)))
            continue
        raw = m.group(2).strip()
        if raw.startswith("'"):
            val: object = raw.strip("'")
        else:
            try:
                val = int(raw)
            except ValueError:
                val = raw
        for gid in pending:
            out[gid] = val
        pending = []
    return out


# -------------------------------------------------------------- checks ----

def check(name: str, cond: bool, detail: str = "") -> bool:
    CHECKS[0] += 1
    if cond:
        if VERBOSE:
            print("  ok   " + name)
    else:
        FAILS.append("%s%s" % (name, ("  [" + detail + "]") if detail else ""))
        print("  FAIL " + name + (("  [" + detail + "]") if detail else ""))
    return cond


def test_thing_numbers(chapters, doomed, zs):
    print("\n== 地图物件编号 ==")
    gate_cls = gate_classes(zs)
    registered = set(doomed)
    for ch in chapters:
        _m, w = chapter_map(ch)
        types = [t[3] for t in w["things"]]
        counts = {t: types.count(t) for t in set(types)}
        gates = [ch["gate_a"], ch["gate_b"]]
        gate_ed = [gen_maps.GATE_EDNUM[g] for g in gates]

        check("%s: 两个终端 ednum 各 1 个" % ch["name"],
              all(counts.get(e, 0) == 1 for e in gate_ed),
              "gates=%s present=%s" % (gate_ed, {e: counts.get(e, 0) for e in gate_ed}))
        check("%s: 终端 ednum 已在 MAPINFO doomednums 注册" % ch["name"],
              all(e in registered for e in gate_ed),
              "missing %s" % [e for e in gate_ed if e not in registered])
        check("%s: 终端类 GateId 与章节编号一致" % ch["name"],
              all(e in registered and gate_cls.get(gates[i]) == doomed[e]
                  for i, e in enumerate(gate_ed)),
              "%s" % [(gates[i], doomed.get(e), gate_cls.get(gates[i]))
                      for i, e in enumerate(gate_ed)])
        check("%s: 唯一玩家出生点" % ch["name"], counts.get(1, 0) == 1,
              "found %d" % counts.get(1, 0))
        check("%s: 3 个证据箱 + 1 个简报" % ch["name"],
              counts.get(gen_maps.ED_EVIDENCE, 0) == 3
              and counts.get(gen_maps.ED_BRIEF, 0) == 1,
              "ev=%d brief=%d" % (counts.get(gen_maps.ED_EVIDENCE, 0),
                                  counts.get(gen_maps.ED_BRIEF, 0)))
        check("%s: 恰好 1 个 Boss" % ch["name"],
              counts.get(gen_maps.BARON, 0) == 1,
              "found %d" % counts.get(gen_maps.BARON, 0))

        unknown = sorted(t for t in counts
                         if t not in EXPECTED_ENGINE_EDNUMS
                         and t not in registered)
        check("%s: 没有未注册的物件编号" % ch["name"], not unknown,
              "unknown %s" % unknown)

        forbidden = {t: counts[t] for t in counts
                     if t in gen_maps.FORBIDDEN_EDNUM}
        check("%s: 没有把玩家出生点/背包当敌人摆" % ch["name"], not forbidden,
              "%s" % {t: gen_maps.FORBIDDEN_EDNUM[t] for t in forbidden})

        # every enemy-ish thing must be a real monster
        monsters = set(gen_maps.MONSTER_SET)
        placed_monsters = {t for t in counts if t in monsters}
        check("%s: 敌人全部是真怪物" % ch["name"], len(placed_monsters) >= 1,
              "monsters=%s" % placed_monsters)
        check("%s: 怪物数量 >= 8" % ch["name"],
              sum(counts.get(t, 0) for t in monsters) >= 8,
              "total %d" % sum(counts.get(t, 0) for t in monsters))


def test_gate_data(chapters, zs):
    print("\n== 抉择文案与结果映射 ==")
    data = gate_data(zs)
    msgs = msg_ids(zs)
    right = switch_entries(zs, "GateMsgRight")
    wrong = switch_entries(zs, "GateMsgWrong")
    dmg = switch_entries(zs, "GateDmg")
    amb = switch_entries(zs, "GateAmb")
    amb_n = switch_entries(zs, "GateAmbCount")
    correct = switch_entries(zs, "GateCorrect")

    gids = [g for ch in chapters for g in (ch["gate_a"], ch["gate_b"])]
    for gid in gids:
        d = data.get(gid, {})
        check("gate %d: 有标题/剧情/两个选项" % gid,
              bool(d.get("title")) and bool(d.get("scenario"))
              and bool(d.get("optA")) and bool(d.get("optB")),
              "title=%r" % d.get("title"))
        check("gate %d: 选项顺序与 GateCorrect 一致" % gid,
              d.get("correct") == correct.get(gid, -1),
              "data=%s outcome=%s" % (d.get("correct"), correct.get(gid)))
        check("gate %d: 正确提示文案存在" % gid, right.get(gid) in msgs,
              "id=%s" % right.get(gid))
        check("gate %d: 识破提示文案存在" % gid, wrong.get(gid) in msgs,
              "id=%s" % wrong.get(gid))
        check("gate %d: 有扣血/伏击配置" % gid,
              gid in dmg and gid in amb and amb_n.get(gid, 0) > 0,
              "dmg=%s amb=%s n=%s" % (dmg.get(gid), amb.get(gid), amb_n.get(gid)))
        # the text must actually teach the right answer, i.e. mention the
        # scam mechanism rather than a placeholder
        check("gate %d: 不是占位文案" % gid,
              "未知" not in (d.get("title") or "未知"), d.get("title", ""))

    check("所有 gate 都在 GateStage 映射里", set(gids) <= set(
        switch_entries(zs, "GateStage")), "missing %s" % (
        set(gids) - set(switch_entries(zs, "GateStage"))))


def test_stage_tokens(chapters, zs):
    """The terminal waits for FZStage1/2 chosen by `gid % 10`, the outcome
    hands out whatever GateStage(gid) says. If the two disagree the terminal
    either never opens or never closes - and a chapter leak makes the second
    gate of every later chapter dead on arrival."""
    print("\n== 进度令牌一致性 ==")
    stage = switch_entries(zs, "GateStage")
    for ch in chapters:
        for gid in (ch["gate_a"], ch["gate_b"]):
            want = "FZStage1" if gid % 10 == 1 else "FZStage2"
            check("%s gate %d: 终端等待的令牌 == 发放的令牌" % (ch["name"], gid),
                  stage.get(gid) == want,
                  "terminal=%s outcome=%s" % (want, stage.get(gid)))
        check("%s: 两个终端等待不同令牌" % ch["name"],
              (ch["gate_a"] % 10) != (ch["gate_b"] % 10),
              "ids %d/%d" % (ch["gate_a"], ch["gate_b"]))

    gates_src = strip_comments(read(ZSCRIPT / "fz_gates.zs"))
    body = func_body(gates_src, "WorldLoaded") + func_body(gates_src, "ClearChapterState")
    check("换关时会重置章节状态（WorldLoaded）", bool(body), "no WorldLoaded")
    for token in ("FZEvidence", "RedCard", "FZStage1", "FZStage2", "FZStage3",
                  "FZGateLock", "FZGateCool"):
        check("换关重置清除了 %s" % token, token in body, "not cleared")


def test_evidence_chain(zs):
    print("\n== 证据链与钥匙 ==")
    maxamt = re.search(r"class\s+FZEvidence\s*:\s*Inventory.*?"
                       r"Inventory\.MaxAmount\s+(\d+)", zs, re.S)
    need = re.search(r"CountInv\(\"FZEvidence\"\)\s*>=\s*(\d+)", zs)
    check("FZEvidence 上限 >= 3", maxamt is not None and int(maxamt.group(1)) >= 3,
          "MaxAmount=%s" % (maxamt.group(1) if maxamt else "?"))
    check("证据链阈值 = 3", need is not None and int(need.group(1)) == 3,
          "threshold=%s" % (need.group(1) if need else "?"))
    check("红卡由证据链发放（含 RedCard）",
          "GiveInventory(\"RedCard\"" in zs and "CountInv(\"RedCard\")" in zs)

    # 抉择的否决权。三个证据箱自己就能凑满 3 件，所以如果红卡只认证据数，
    # "两题全答错、只捡箱子"照样能开门——反诈题白答。红卡必须同时要求
    # 两道抉择的 Stage 令牌，答题才真正决定能不能结案。
    grant = func_body(zs, "Grant")
    check("红卡要求两道抉择都答对（FZStage1 + FZStage2）",
          "FZStage1" in grant and "FZStage2" in grant,
          "Grant() 没有检查 Stage 令牌：证据箱能独自开门")

    # 反面保障：答错不能把终端锁死，否则"答对才算"就成了死路。done 只允许
    # 在答对时置位，答错只能进冷却（走开再回来可重答）。
    choice = func_body(zs, "GateChoice")
    check("答错不退休终端（done 仅在答对时置位）",
          re.search(r"if\s*\(\s*choice\s*==\s*GateCorrect\(gid\)\s*\)\s*"
                    r"g\.done\s*=\s*true", choice) is not None,
          "GateChoice() 里 done 的置位条件不是答对")
    check("终端冷却走开即失效（mCool 到期后可重触发）",
          "mCool > 0" in zs and "StartCool" in zs,
          "缺少每终端冷却：站着不动会被反复喂菜单")


def test_trial_door(chapters):
    print("\n== 审判门与出口 ==")
    for ch in chapters:
        m, w = chapter_map(ch)
        name = ch["name"]
        doors = [ln for ln in w["lines"] if ln["special"] in DOOR_SPECIALS]
        red = [ln for ln in doors if ln["special"] == 33]
        door_sectors = {w["sides"][ln["back"]][5] for ln in red
                        if ln["back"] is not None}
        check("%s: 只有 1 扇红卡 D1 门（两片门扇同一门扇区）" % name,
              len(doors) == len(red) and len(red) == 2 and len(door_sectors) == 1,
              "doors=%s sectors=%s" % ([(d["special"], DOOR_SPECIALS[d["special"]])
                                       for d in doors], sorted(door_sectors)))

        exits = [ln for ln in w["lines"] if ln["special"] == EXIT_SPECIAL]
        check("%s: 有 W1 出口触发线（special 52）" % name, len(exits) == 1,
              "found %d" % len(exits))
        switches = [ln for ln in w["lines"] if ln["special"] == SWITCH_SPECIAL]
        check("%s: 有出口开关墙（special 11）" % name, len(switches) == 1,
              "found %d" % len(switches))

        if not red:
            continue
        faces = set()
        for dl in red:
            check("%s: 门扇不是 blocking（否则开了也走不过去）" % name,
                  not (dl["flags"] & 1), "flags=%d" % dl["flags"])
            check("%s: 门扇双面（有 back sidedef）" % name,
                  dl["front"] is not None and dl["back"] is not None)
            if dl["front"] is not None:
                # sidedef order is upper / lower / middle: the door leaf
                # must live on the UPPER section or it renders see-through
                upper = w["sides"][dl["front"]][2]
                faces.add(upper)
                check("%s: 门面图形在 upper 层" % name, upper not in ("", "-"),
                      "upper=%r" % upper)
        check("%s: 两片门扇贴同一张门面图" % name, len(faces) == 1,
              "faces=%s" % sorted(faces))
        door_sec = sorted(door_sectors)[0]
        check("%s: 门扇扇区 floor == ceil（关闭状态）" % name,
              w["sectors"][door_sec]["floor"] == w["sectors"][door_sec]["ceil"])

        # the door must sit between the arena and the boss room
        neighbours = {w["sides"][ln[k]][5] for ln in w["lines"]
                      if ln["front"] is not None and ln["back"] is not None
                      and (w["sides"][ln["front"]][5] == door_sec
                           or w["sides"][ln["back"]][5] == door_sec)
                      for k in ("front", "back")}
        boss_sec = sector_at(w, *m.marks["boss"])
        check("%s: 门后就是 Boss 房" % name, boss_sec in neighbours,
              "door neighbours=%s boss=%d" % (sorted(neighbours), boss_sec))


def chapter_map(ch) -> tuple:
    """Build a chapter in memory and return (model, parsed map)."""
    m = gen_maps.build_chapter(**{k: v for k, v in ch.items() if k != "name"})
    return m, parse_bytes(m.udmf_bytes(ch["name"]), ch["name"])


def seg_cross(p1, p2, p3, p4) -> bool:
    """True when two segments properly cross. Touching endpoints and
    collinear overlaps return False on purpose: a route that runs along a
    wall is a design smell but not a wall clip."""
    def orient(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0]))

    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def test_route(chapters):
    """The bot route must be walkable: every leg stays inside the level and
    never crosses a one-sided line. This is the cheap stand-in for actually
    watching the bot walk - the drive test only proves it arrived."""
    print("\n== 机器人路线可走性 ==")
    for ch in chapters:
        m, w = chapter_map(ch)
        name = ch["name"]
        route = m.route
        check("%s: 路线 27 个路点（22 审判门 / 23 Boss 房 / 24 Boss 中心）"
              % name, len(route) == 27, "got %d" % len(route))

        boxes = [(min(w["verts"][v][0] for v in vals),
                  min(w["verts"][v][1] for v in vals),
                  max(w["verts"][v][0] for v in vals),
                  max(w["verts"][v][1] for v in vals))
                 for vals in _sector_vertex_sets(w)]
        outside = [(i, p) for i, p in enumerate(route)
                   if not any(b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]
                              for b in boxes)]
        check("%s: 每个路点都落在房间里（不在虚空）" % name, not outside,
              "np=%s" % outside[:3])

        solids = [((w["verts"][ln["v1"]]), (w["verts"][ln["v2"]]))
                  for ln in w["lines"] if ln["back"] is None]
        bad = []
        for i in range(len(route) - 1):
            a, b = route[i], route[i + 1]
            for p3, p4 in solids:
                if seg_cross(a, b, p3, p4):
                    bad.append((i, tuple(a), tuple(b), p3, p4))
                    break
        check("%s: 相邻路点之间不穿墙" % name, not bad,
              "%s" % (bad[:2],))


def test_bot_routes(chapters):
    """The bot's route file must be the one the current maps were built from.

    The coordinates moved out of fzbot.zs into a generated file, so the
    remaining risk is a stale file: edit the layout, forget to regenerate,
    and the robot walks walls while every static check still passes. This
    compares the file against what the generator would produce right now."""
    print("\n== 机器人路点文件与地图同步 ==")
    bot = gen_maps.ROOT / "tools/testhooks/bot"
    built = {ch["name"]: chapter_map(ch)[0] for ch in chapters}
    path = gen_maps.BOT_ROUTE_ZS
    check("路点文件已生成", path.exists(), str(path))
    if path.exists():
        check("路点文件与当前地图一致（不一致就跑 tools/gen_maps.py）",
              path.read_text(encoding="utf-8") == gen_maps.bot_routes_zs(built),
              "fzbot_routes.zs drifted from the maps")
    check("zscript.txt 引入了路点文件",
          '#include "zscript/fzbot_routes.zs"'
          in (bot / "zscript.txt").read_text(encoding="utf-8"))
    hook = (bot / "zscript" / "fzbot.zs").read_text(encoding="utf-8")
    check("fzbot.zs 不再内嵌坐标（全部走生成文件）",
          "FZBotRoutes.X(level.mapname" in hook
          and "case 22: return" not in hook)


def _sector_vertex_sets(w):
    """Vertex index set per sector, from the lines that touch it."""
    out = [set() for _ in w["sectors"]]
    for ln in w["lines"]:
        for sd in (ln["front"], ln["back"]):
            if sd is None:
                continue
            out[w["sides"][sd][5]].update((ln["v1"], ln["v2"]))
    return out


def test_headroom(chapters):
    """No floor-to-ceiling gap may be shorter than a standing player.

    A sector whose ceiling sits below 56 units above its floor is only
    passable by crouching, which turns a mandatory exit alcove into a
    soft-lock. Chapter 3 shipped one for a while: the exit nook was built at
    floor 128 / ceiling 160 and the bot still "passed", because the W1 exit
    line sits on the doorway *before* the alcove - the run ended happily and
    nobody walked into the room it had built."""
    print("\n== 站着能过（净空检查） ==")
    for ch in chapters:
        _m, w = chapter_map(ch)
        low = [(i, s["floor"], s["ceil"]) for i, s in enumerate(w["sectors"])
               if s["floor"] != s["ceil"] and s["ceil"] - s["floor"] < 64]
        check("%s: 所有扇区站着能过（净空 >= 64）" % ch["name"], not low,
              "sectors with floor/ceil too close: %s" % (low,))


def test_reachability(chapters):
    """Everything the player must touch has to be in the same connected
    component as the player start - this is the regression test for the
    'air wall' class of bug (a room boundary drawn twice seals its gaps).

    Coordinates come from the generator's own landmark table, so a layout
    change cannot leave the assertion pointing at last week's floor plan."""
    print("\n== 可达性（空气墙回归） ==")
    for ch in chapters:
        m, w = chapter_map(ch)
        name = ch["name"]
        marks = m.marks
        start = sector_at(w, *marks["start"])
        seen = reachable(w, start)
        must = {
            "gate %d" % ch["gate_a"]: sector_at(w, *marks["gate_a"]),
            "gate %d" % ch["gate_b"]: sector_at(w, *marks["gate_b"]),
            "boss": sector_at(w, *marks["boss"]),
            "exit": sector_at(w, *marks["exit"]),
        }
        for i, pos in enumerate(marks["evidence"]):
            must["evidence %d" % (i + 1)] = sector_at(w, *pos)
        for label, sec in must.items():
            check("%s: %s 与出生点连通" % (name, label), sec in seen,
                  "sector %d not reachable" % sec)

        # gate terminals must not be buried inside a wall: their sector has
        # to have a two-sided line to something else
        g = sector_graph(w)
        for label in ("gate %d" % ch["gate_a"], "gate %d" % ch["gate_b"]):
            sec = must[label]
            check("%s: %s 所在凹室有开口" % (name, label), bool(g[sec]),
                  "sector %d has no neighbours" % sec)


def test_map_chain(chapters, chain, doomed):
    print("\n== 章节链与注册表 ==")
    names = [ch["name"] for ch in chapters]
    for i, n in enumerate(names):
        check("%s 在 MAPINFO 中有 map 定义" % n, n in chain, "missing")
        if i + 1 < len(names):
            check("%s -> Next = %s" % (n, names[i + 1]),
                  chain.get(n) == names[i + 1], "Next=%s" % chain.get(n))
        else:
            check("%s 是最后一章（无 Next）" % n, chain.get(n) is None,
                  "Next=%s" % chain.get(n))
    check("每张 WAD 都在 MAPINFO 里", set(names) <= set(chain))
    check("doomednums 覆盖所有自定义类",
          {"FZGate11", "FZGate12", "FZGate21", "FZGate22", "FZGate31",
           "FZGate32", "FZEvidencePickup", "FZMasterProof",
           "FZBriefingActor"} <= set(doomed.values()),
          "registered=%s" % sorted(set(doomed.values())))


def test_textures(chapters):
    print("\n== 贴图/地板名存在性 ==")
    flats, textures = gen_maps.iwad_names()
    known = flats | textures | gen_maps.own_tex_names()
    for ch in chapters:
        _m, w = chapter_map(ch)
        used = {s[2] for s in w["sides"]} | {s[3] for s in w["sides"]} \
            | {s[4] for s in w["sides"]}
        used |= {sec["floor_tex"] for sec in w["sectors"]}
        used |= {sec["ceil_tex"] for sec in w["sectors"]}
        used.discard("-")
        check("%s: 所有贴图/地板名都在 IWAD 或自带贴图里" % ch["name"],
              used <= known, "missing %s" % sorted(used - known))


def test_format_equivalence(chapters):
    """UDMF and the binary lumps must describe the same level.

    UDMF is what we ship now; a silent divergence would mean the text map
    and the binary map stopped being the same place, and every geometry
    check above would be validating the wrong thing."""
    print("\n== UDMF 与二进制输出等价 ==")
    for ch in chapters:
        m = gen_maps.build_chapter(**{k: v for k, v in ch.items()
                                      if k != "name"})
        u = parse_bytes(m.udmf_bytes(ch["name"]), ch["name"] + "_udmf")
        b = parse_bytes(m.wad_bytes(ch["name"]), ch["name"] + "_bin")
        name = ch["name"]
        check("%s: 顶点/边/扇区完全一致" % name,
              u["verts"] == b["verts"] and u["sides"] == b["sides"]
              and u["sectors"] == b["sectors"],
              "v=%d/%d s=%d/%d sec=%d/%d"
              % (len(u["verts"]), len(b["verts"]), len(u["sides"]),
                 len(b["sides"]), len(u["sectors"]), len(b["sectors"])))
        check("%s: 线条数、顶点对、双面与遮挡标志一致" % name,
              len(u["lines"]) == len(b["lines"])
              and all((x["v1"], x["v2"], x["flags"], x["front"], x["back"])
                      == (y["v1"], y["v2"], y["flags"], y["front"], y["back"])
                      for x, y in zip(u["lines"], b["lines"])))
        check("%s: 行特殊值与 tag 一致" % name,
              [(x["special"], x["tag"]) for x in u["lines"]]
              == [(y["special"], y["tag"]) for y in b["lines"]])
        check("%s: 物件坐标/朝向/编号/选项位一致" % name,
              u["things"] == b["things"],
              "%s vs %s" % (u["things"][:3], b["things"][:3]))


def main() -> int:
    chapters = gen_maps.CHAPTERS
    doomed, chain = mapinfo()
    zs = zscript_text()

    missing = [ch["name"] for ch in chapters
               if not (MAPS / (ch["name"] + ".wad")).exists()]
    if missing:
        print("missing maps %s - run tools/gen_maps.py" % missing)
        return 2

    test_map_chain(chapters, chain, doomed)
    test_format_equivalence(chapters)
    test_thing_numbers(chapters, doomed, zs)
    test_gate_data(chapters, zs)
    test_stage_tokens(chapters, zs)
    test_evidence_chain(zs)
    test_trial_door(chapters)
    test_route(chapters)
    test_bot_routes(chapters)
    test_headroom(chapters)
    test_reachability(chapters)
    test_textures(chapters)

    print()
    if FAILS:
        print("%d/%d 项检查失败：" % (len(FAILS), CHECKS[0]))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("全部静态检查通过：%d/%d（%d 章）"
          % (CHECKS[0], CHECKS[0], len(chapters)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
