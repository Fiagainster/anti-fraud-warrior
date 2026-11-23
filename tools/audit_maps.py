#!/usr/bin/env python3
"""几何审计：不启动引擎，直接对着生成的 WAD 找“硬伤”。

检查项（每一项都对应一种玩家能看见的症状）：
  A 扇区边界闭合性   -> 边界不闭合 = 缺口 = 黑洞 / 能看穿
  B 重合线           -> 同一条边画两次 = 闪烁 / Z 冲突 / 空气墙
  C 两面条的高度缝   -> upper/lower 是 "-" 但有高度差 = 透明带（透视）
  D 物件落点          -> 落在虚空 / 柱子里 = 怪物和道具卡在墙里
  E 扇区重叠          -> 空间重叠 = BSP 退化，画面错乱
  F 楼层天花板        -> ceil < floor 或净空不足
用法: python audit_maps.py [FZ01 FZ02 ...]
"""
from __future__ import annotations

import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "game" / "maps"

# 物件半径（引擎里的默认值）。UDMF 的 thing 不带 radius 字段，所以只能查表；
# 表里没有的按 20 算（原版道具/小怪的默认值）。自查 D2 用得到：中心点合法
# 但体积压进墙，玩家看到的就是"卡在墙里"。
THING_RADIUS = {
    1: 0,        # 玩家出生点
    9: 20,       # ShotgunGuy（霰弹枪兵，ednum 9）
    2001: 20,    # Shotgun（地面武器）
    2007: 20, 2008: 20, 2011: 20, 2012: 20, 2018: 20,  # 弹/药/甲
    # 怪物：号段按 UZDoom 的 mapinfo/doomitems.txt，半径按各职业默认值。
    # 别凭印象填：3002 是 Demon（30）、3005 是 Cacodemon（31），写错这两个
    # 会让下面 D2 的体积检查对最胖的两只怪整体失效。
    3001: 20,    # DoomImp
    3002: 30,    # Demon
    3003: 24,    # BaronOfHell（我们的 FZChairman）
    3004: 20,    # Zombieman
    3005: 31,    # Cacodemon
    3006: 16,    # LostSoul
    3920: 16, 3921: 16, 3922: 16, 3923: 16, 3924: 16, 3925: 16,  # 终端
    3930: 12,    # 证据箱
    3931: 12,    # 主谋证据
    3932: 1,     # 简报
}


# ------------------------------------------------------------ parsing ----

def parse_udmf(text: str) -> dict:
    kinds = ("vertex", "linedef", "sidedef", "sector", "thing")
    blocks = {k: [] for k in kinds}
    for m in re.finditer(r"\b(%s)\b[^{]*\{([^}]*)\}" % "|".join(kinds), text, re.S):
        props = dict(re.findall(r"([a-z0-9_]+)\s*=\s*([^;]+);", m.group(2)))
        blocks[m.group(1)].append({k: v.strip() for k, v in props.items()})

    def num(b, k, d=0):
        v = b.get(k)
        return d if v is None else int(float(v))

    def on(b, k):
        return b.get(k, "false") == "true"

    def tex(b, k):
        return (b.get(k, '"-"').strip('"') or "-").upper()

    return {
        "verts": [(num(b, "x"), num(b, "y")) for b in blocks["vertex"]],
        "sides": [{"ox": num(b, "offsetx"), "oy": num(b, "offsety"),
                   "up": tex(b, "texturetop"), "lo": tex(b, "texturebottom"),
                   "mid": tex(b, "texturemiddle"), "sec": num(b, "sector")}
                  for b in blocks["sidedef"]],
        "lines": [{"v1": num(b, "v1"), "v2": num(b, "v2"),
                   "blocking": on(b, "blocking"), "twosided": on(b, "twosided"),
                   "special": num(b, "special"), "tag": num(b, "arg0"),
                   "front": num(b, "sidefront") if "sidefront" in b else None,
                   "back": num(b, "sideback") if "sideback" in b else None}
                  for b in blocks["linedef"]],
        "sectors": [{"floor": num(b, "heightfloor"),
                     "ceil": num(b, "heightceiling"),
                     "floortex": tex(b, "texturefloor"),
                     "ceiltex": tex(b, "textureceiling"),
                     "light": num(b, "lightlevel"),
                     "special": num(b, "special"), "tag": num(b, "id")}
                    for b in blocks["sector"]],
        "things": [{"x": num(b, "x"), "y": num(b, "y"),
                    "angle": num(b, "angle"), "type": num(b, "type")}
                   for b in blocks["thing"]],
    }


def load(path: Path) -> dict:
    data = path.read_bytes()
    magic, n, ofs = struct.unpack_from("<4sii", data, 0)
    assert magic == b"PWAD", magic
    lumps = {}
    for i in range(n):
        pos, size, nm = struct.unpack_from("<ii8s", data, ofs + 16 * i)
        lumps[nm.rstrip(b"\0").decode().upper()] = data[pos:pos + size]
    return parse_udmf(lumps["TEXTMAP"].decode("ascii"))


# ------------------------------------------------------------ geometry ---

def sector_edges(w: dict, sec: int):
    """Directed boundary edges of one sector: (v_from, v_to, line_idx, side)."""
    out = []
    for i, ln in enumerate(w["lines"]):
        if ln["front"] is not None and w["sides"][ln["front"]]["sec"] == sec:
            out.append((ln["v1"], ln["v2"], i, "front"))
        if ln["back"] is not None and w["sides"][ln["back"]]["sec"] == sec:
            out.append((ln["v2"], ln["v1"], i, "back"))
    return out


def loops(w: dict, sec: int):
    """Chain a sector's edges into loops.

    返回 (闭合环数, 缺口顶点列表, 边表)。判定口径是“每个顶点进出度相等”：
    平面划分里一条正常闭合的环，任何顶点的入边数必须等于出边数；少了就是
    缺口 —— 画面上的黑洞 / 能看穿就是这么来的。"""
    edges = sector_edges(w, sec)
    indeg = defaultdict(int)
    outdeg = defaultdict(int)
    for a, b, i, s in edges:
        outdeg[a] += 1
        indeg[b] += 1
    unbalanced = sorted(v for v in set(indeg) | set(outdeg)
                        if indeg[v] != outdeg[v])
    nxt = defaultdict(list)
    for a, b, i, s in edges:
        nxt[a].append((b, i))
    used = set()
    closed = 0
    for a, b, i, _s in edges:
        if i in used:
            continue
        cur, cnt = a, 0
        path = [a]
        ok = False
        while True:
            cand = [(bb, ii) for bb, ii in nxt[cur] if ii not in used]
            if not cand:
                break
            bb, ii = cand[0]
            used.add(ii)
            path.append(bb)
            cur = bb
            cnt += 1
            if cur == a:
                ok = True
                break
            if cnt > len(edges) + 2:
                break
        if ok:
            closed += 1
    return closed, unbalanced, edges


def point_in_poly(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def sector_polys(w: dict) -> dict[int, list]:
    """每个扇区的多边形环（外环 + 内环/柱子洞）。

    追踪规则：每个有向边都把扇区保持在右边，走到端点时选“最右转”的下一
    条边，这样在凹角/柱子处不会串到别的环上去。"""
    import math
    out = {}
    for sec in range(len(w["sectors"])):
        edges = sector_edges(w, sec)
        nxt = defaultdict(list)
        for a, b, i, _ in edges:
            nxt[a].append((b, i))
        used = set()
        rings = []
        for a, b, i, _ in edges:
            if i in used:
                continue
            ring = [a]
            cur_from, cur_to, li = a, b, i
            used.add(li)
            ok = False
            guard = 0
            while guard <= len(edges) + 2:
                guard += 1
                if cur_to == a:
                    ok = True
                    break
                ring.append(cur_to)
                p0 = w["verts"][cur_from]
                p1 = w["verts"][cur_to]
                din = (p1[0] - p0[0], p1[1] - p0[1])
                best, bestang = None, None
                for bb, ii in nxt[cur_to]:
                    if ii in used:
                        continue
                    p2 = w["verts"][bb]
                    dout = (p2[0] - p1[0], p2[1] - p1[1])
                    ang = math.atan2(din[0] * dout[1] - din[1] * dout[0],
                                     din[0] * dout[0] + din[1] * dout[1])
                    # 最右转 = 最小角度（负得最多）
                    if bestang is None or ang < bestang:
                        bestang, best = ang, (bb, ii)
                if best is None:
                    break
                bb, ii = best
                used.add(ii)
                cur_from, cur_to = cur_to, bb
            if ok and len(ring) >= 3:
                rings.append([w["verts"][v] for v in ring])
        out[sec] = rings
    return out


def poly_area(poly) -> float:
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def in_sector(pt, rings) -> bool:
    """点在扇区里 = 在最大的环里、且不在任何较小的环里（柱子洞）。"""
    if not rings:
        return False
    rings = sorted(rings, key=poly_area, reverse=True)
    if not point_in_poly(pt, rings[0]):
        return False
    return not any(point_in_poly(pt, r) for r in rings[1:])


# ------------------------------------------------------------- checks ----

def audit(name: str, w: dict):
    print("\n" + "=" * 68)
    print("== %s  扇区 %d / 线 %d / 侧 %d / 物件 %d"
          % (name, len(w["sectors"]), len(w["lines"]), len(w["sides"]),
             len(w["things"])))
    print("=" * 68)
    problems = []

    # -- A: 边界闭合
    print("\n[A] 扇区边界闭合性")
    for sec in range(len(w["sectors"])):
        closed, dangling, edges = loops(w, sec)
        if not edges:
            problems.append("%s: sector %d 没有任何边界线（悬空扇区）" % (name, sec))
            continue
        if dangling or closed == 0:
            s = w["sectors"][sec]
            problems.append(
                "%s: sector %d 边界不闭合（闭合环 %d 个，缺口顶点 %s, f/c=%d/%d, 光 %d）"
                % (name, sec, closed, dangling[:6], s["floor"], s["ceil"],
                   s["light"]))
    print("  不闭合扇区: %d" % sum(1 for p in problems if "边界不闭合" in p
                                  or "悬空扇区" in p))

    # -- B: 重合线
    #
    # 判据要分两种情况，否则会把"正确做法"当成 bug 报出来：
    #
    #   * 两侧房间共墙：每个房间各画一条 one-sided 线，方向相反、各自朝内
    #     （line A: v1→v2 属扇区 X，line B: v2→v1 属扇区 Y）。这是本项目
    #     矩形拼法的标准做法，从任何一侧看都只有一条面朝你，另一条背面剔除，
    #     不会 Z 冲突。合法。
    #   * 真重复：同一条线在同一侧画了两遍（方向相同、前扇区也相同），
    #     或者两条线的前扇区都是同一个 —— 那才是同向重叠，才会闪面。
    #
    # 所以按 (顶点对, 方向, 前扇区) 归类，而不是只按顶点对。
    print("\n[B] 重合/重复线")
    seen = defaultdict(list)
    for i, ln in enumerate(w["lines"]):
        front = w["sides"][ln["front"]]["sec"] if ln["front"] is not None else None
        key = (ln["v1"], ln["v2"], front)
        seen[key].append(i)
    dup = 0
    for key, idxs in seen.items():
        if len(idxs) > 1:
            p1, p2 = w["verts"][key[0]], w["verts"][key[1]]
            problems.append("%s: 线段 %s-%s（前扇区 %s）被同向画了 %d 次（行 %s）"
                            % (name, p1, p2, key[2], len(idxs), idxs))
            dup += 1
    # 反向成对 = 共墙，单独计数留档，不算问题
    back2back = defaultdict(set)
    for i, ln in enumerate(w["lines"]):
        front = w["sides"][ln["front"]]["sec"] if ln["front"] is not None else None
        back2back[tuple(sorted((ln["v1"], ln["v2"])))].add(front)
    pairs = sum(1 for secs in back2back.values() if len(secs) > 1)
    print("  同向重复线段: %d" % dup)
    print("  反向共墙（合法，两侧各自朝内）: %d" % pairs)

    # -- B2: 共线重叠（更隐蔽：顶点不同但对齐重合）
    #
    # 同样要分情况。两个房间共墙时，A 房把这条边切成 2 段、B 房切成 3 段是
    # 完全正常的（切点由各自的连通口决定），算下来必然"共线重叠"。只有当
    # 两条重叠线的前扇区是同一个（同一侧画了两遍）时，才会出现同向叠面。
    print("\n[B2] 共线重叠墙（只报同侧重叠）")
    buckets = defaultdict(list)
    for i, ln in enumerate(w["lines"]):
        p1, p2 = w["verts"][ln["v1"]], w["verts"][ln["v2"]]
        front = w["sides"][ln["front"]]["sec"] if ln["front"] is not None else None
        if p1[0] == p2[0]:
            lo, hi = sorted((p1[1], p2[1]))
            buckets[("v", p1[0])].append((lo, hi, i, front))
        elif p1[1] == p2[1]:
            lo, hi = sorted((p1[0], p2[0]))
            buckets[("h", p1[1])].append((lo, hi, i, front))
    nover = 0
    shared = 0
    for key, segs in buckets.items():
        segs.sort()
        for x in range(len(segs)):
            lo1, hi1, i1, s1 = segs[x]
            for y in range(x + 1, len(segs)):
                lo2, hi2, i2, s2 = segs[y]
                if lo2 >= hi1:
                    break
                ov = min(hi1, hi2) - max(lo1, lo2)
                if ov <= 0:
                    continue
                if s1 != s2:
                    shared += 1        # 两侧各画一条，合法共墙
                    continue
                nover += 1
                problems.append(
                    "%s: 行 %d 与 %d 同侧共线重叠 %d 单位（扇区 %s, %s=%d）"
                    % (name, i1, i2, ov, s1, key[0], key[1]))
    print("  同侧共线重叠: %d" % nover)
    print("  两侧共墙切割点不同（合法）: %d" % shared)

    # -- C: 两面条的高度缝没贴图
    print("\n[C] 两面条高度缝的贴图")
    holes = 0
    for i, ln in enumerate(w["lines"]):
        if ln["front"] is None or ln["back"] is None:
            continue
        fs = w["sides"][ln["front"]]["sec"]
        bs = w["sides"][ln["back"]]["sec"]
        f, b = w["sectors"][fs], w["sectors"][bs]
        # 上缝：天花板高的那一侧要 upper
        for (mine, other, key) in ((fs, b, "up"), (bs, f, "up")):
            pass
        if f["ceil"] > b["ceil"]:
            if w["sides"][ln["front"]]["up"] == "-":
                holes += 1
                problems.append("%s: 行 %d 前侧上缝缺贴图（ceil %d>%d）"
                                % (name, i, f["ceil"], b["ceil"]))
        if b["ceil"] > f["ceil"]:
            if w["sides"][ln["back"]]["up"] == "-":
                holes += 1
                problems.append("%s: 行 %d 后侧上缝缺贴图（ceil %d>%d）"
                                % (name, i, b["ceil"], f["ceil"]))
        if f["floor"] > b["floor"]:
            if w["sides"][ln["front"]]["lo"] == "-":
                holes += 1
                problems.append("%s: 行 %d 前侧下缝缺贴图（floor %d>%d）"
                                % (name, i, f["floor"], b["floor"]))
        if b["floor"] > f["floor"]:
            if w["sides"][ln["back"]]["lo"] == "-":
                holes += 1
                problems.append("%s: 行 %d 后侧下缝缺贴图（floor %d>%d）"
                                % (name, i, b["floor"], f["floor"]))
    print("  缺贴图的高度缝: %d" % holes)

    # -- D: 物件落点
    print("\n[D] 物件落点")
    polys = sector_polys(w)
    def sector_of(pt):
        hits = [s for s, rings in polys.items() if in_sector(pt, rings)]
        return hits
    for t in w["things"]:
        hits = sector_of((t["x"], t["y"]))
        if len(hits) != 1:
            problems.append("%s: 物件 type=%d @(%d,%d) 落在 %d 个扇区里 %s"
                            % (name, t["type"], t["x"], t["y"], len(hits), hits))
        else:
            s = w["sectors"][hits[0]]
            head = s["ceil"] - s["floor"]
            if head < 56 and t["type"] not in (1,):
                problems.append("%s: 物件 type=%d @(%d,%d) 净空只有 %d"
                                % (name, t["type"], t["x"], t["y"], head))
    print("  落点异常: %d" % sum(1 for p in problems if "落在" in p or "净空只有" in p))

    # -- G: 单面墙的朝向（绕向）
    #
    # 这是最容易被漏掉的一类硬伤，也是玩家说的"黑洞/能透视"：
    # 一条单面线的正面朝哪边，由 v1→v2 的方向决定 —— 扇区必须落在**右手边**。
    # 绕反了以后：
    #   * 边界照样闭合（A 查不出来）；
    #   * 贴图照样有名字（C 查不出来）；
    #   * 物件照样落在扇区里（D 查不出来）；
    #   * 可是从房间里面看是墙面背面 —— 引擎直接不画，于是"黑洞"，而且
    #     因为没有面挡着，能一路看穿到隔壁/虚空。
    # 判据：沿直线取中点，向右手法线方向挪 1~3 单位，落点必须在自己这一侧
    # 的扇区里。两侧共墙（反向成对）也照样成立：每条线只管自己那一边。
    print("\n[G] 单面墙朝向（绕反 = 黑洞/能透视）")
    polys_g = sector_polys(w)
    backface = 0
    for i, ln in enumerate(w["lines"]):
        if ln["front"] is None or ln["back"] is not None:
            continue                       # 只看单面墙
        x1, y1 = w["verts"][ln["v1"]]
        x2, y2 = w["verts"][ln["v2"]]
        dx, dy = x2 - x1, y2 - y1
        L = (dx * dx + dy * dy) ** 0.5
        if L == 0:
            continue
        # 右手法线：把方向旋转 -90°，即 (x,y) -> (y,-x)
        nx, ny = dy / L, -dx / L
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        own = w["sides"][ln["front"]]["sec"]
        ok = any(in_sector((mx + nx * d, my + ny * d), polys_g[own])
                 for d in (1.0, 2.0, 3.0))
        if not ok:
            left_ok = any(in_sector((mx - nx * d, my - ny * d), polys_g[own])
                          for d in (1.0, 2.0, 3.0))
            backface += 1
            problems.append(
                "%s: 行 %d 单面墙 (%s)-(%s) 绕反了（扇区 %d 在背面%s）"
                % (name, i, (x1, y1), (x2, y2), own,
                   "，正面那一侧是别人" if left_ok else "，两侧都不在"))
    print("  绕反的单面墙: %d" % backface)

    # -- D2: 物件体积（半径）压进墙/柱子
    #
    # D 只查中心点：中心在走廊里、身体压进柱子 20 单位的怪，D 认为一切正常，
    # 玩家看到的是"卡在墙里"。这里按物件半径采样一圈，再量到每一条单面墙
    # （实心边界）的距离 —— 距离小于半径就是嵌进去了。
    print("\n[D2] 物件半径与墙体净距")
    jammed = 0
    wall_segs = []
    for i, ln in enumerate(w["lines"]):
        if ln["back"] is not None:
            continue                        # 只有单面墙是实心边界
        wall_segs.append((w["verts"][ln["v1"]], w["verts"][ln["v2"]], i))
    for t in w["things"]:
        if t["type"] in (1,):               # 玩家出生点不查
            continue
        r = t.get("radius")
        if r is None:
            r = THING_RADIUS.get(t["type"], 16)
        if not r:
            continue
        px, py = t["x"], t["y"]
        worst = None
        for (x1, y1), (x2, y2), li in wall_segs:
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 == 0:
                continue
            u = ((px - x1) * dx + (py - y1) * dy) / L2
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            qx, qy = x1 + u * dx, y1 + u * dy
            dist = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
            gap = dist - r
            if worst is None or gap < worst[0]:
                worst = (gap, li)
        if worst is not None and worst[0] < 0:
            jammed += 1
            problems.append(
                "%s: 物件 type=%d @(%d,%d) 半径 %d 压进墙 %d 号 %.1f 单位"
                % (name, t["type"], px, py, r, worst[1], -worst[0]))
    print("  体积嵌墙的物件: %d" % jammed)

    # -- E: 扇区多边形重叠（采样）
    print("\n[E] 扇区重叠（同高度才算法有问题）")
    boxes = {}
    for s, rings in polys.items():
        if not rings:
            continue
        outer = max(rings, key=poly_area)
        boxes[s] = (min(p[0] for p in outer), min(p[1] for p in outer),
                    max(p[0] for p in outer), max(p[1] for p in outer))
    overl = set()
    secs = list(boxes)
    for i in range(len(secs)):
        for j in range(i + 1, len(secs)):
            a, b = secs[i], secs[j]
            ba, bb = boxes[a], boxes[b]
            if ba[2] <= bb[0] or bb[2] <= ba[0] or ba[3] <= bb[1] or bb[3] <= ba[1]:
                continue
            x0, y0 = max(ba[0], bb[0]), max(ba[1], bb[1])
            x1, y1 = min(ba[2], bb[2]), min(ba[3], bb[3])
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            probes = [((x0 + x1) / 2, (y0 + y1) / 2),
                      (x0 + 8, y0 + 8), (x1 - 8, y1 - 8)]
            for p in probes:
                if in_sector(p, polys[a]) and in_sector(p, polys[b]):
                    overl.add((a, b))
                    break
    for a, b in sorted(overl):
        problems.append("%s: 扇区 %d 与 %d 空间重叠（bbox %s / %s）"
                        % (name, a, b, boxes[a], boxes[b]))
    print("  重叠扇区对: %d" % len(overl))

    # -- F: 楼层/天花板
    print("\n[F] 楼层与天花板")
    for i, s in enumerate(w["sectors"]):
        if s["ceil"] < s["floor"]:
            problems.append("%s: sector %d ceil(%d) < floor(%d)"
                            % (name, i, s["ceil"], s["floor"]))
        if s["ceil"] - s["floor"] < 56 and s["ceil"] != s["floor"]:
            problems.append("%s: sector %d 净空 %d < 56"
                            % (name, i, s["ceil"] - s["floor"]))
    print("  异常: %d" % sum(1 for p in problems if "ceil(" in p or "净空" in p))

    print("\n---- 汇总 %s: %d 条问题 ----" % (name, len(problems)))
    for p in problems:
        print("  * " + p)
    return problems


def main():
    names = sys.argv[1:] or ["FZ01", "FZ02", "FZ03"]
    allp = []
    for n in names:
        w = load(MAPS / (n + ".wad"))
        allp += audit(n, w)
    print("\n总计 %d 条" % len(allp))
    # 非零退出码 = 有问题，这样 tools/fz_ctl.py static 能把它当回归门禁跑。
    # 玩家看得见的症状（黑洞、能透视、卡墙、闪面）在这份清单里都各有一项，
    # 所以"0 条"是有意义的通过条件，不是"跑完没崩"。
    return 0 if not allp else 1


if __name__ == "__main__":
    sys.exit(main())
