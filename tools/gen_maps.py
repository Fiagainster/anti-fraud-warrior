#!/usr/bin/env python3
"""Generate the three chapters as VANILLA-format PWADs.

Vanilla binary lumps sidestep the UDMF loader crash entirely, and the
axis-aligned room layout needs no UDMF features. Doors, locks and the exit
switch use classic Doom linedef specials; gate terminals are custom actors
with their own DoomEd numbers (one class per gate, since vanilla things
have no args field).

Hard rules learned the painful way (do not regress):
  * texture/flat names are NUL padded, never space padded - space padding
    breaks lookups in UZDoom and renders the missing-texture checkerboard.
  * thing option flags must be 7 (all single-player skills). Bit 16 means
    "multiplayer only": with 7|16 every placed thing is filtered out of a
    single-player game (no terminals, no pickups, no monsters).
  * every room boundary is drawn exactly once, with ALL its gaps supplied
    in one call - re-calling rect_walls redraws walls over earlier gaps
    and seals corridors with invisible walls.
  * alcoves must sit strictly outside their host room, sharing the host's
    edge line; overlapping sector space degenerates BSP output.
  * DoomEd numbers in vanilla THINGS are read as SIGNED 16-bit: any
    ednum > 32767 arrives as a negative number and the thing is
    dropped as "Unknown type". Keep custom ednums <= 32767
    (we use 3920-3932).
  * every name used on sidedefs/sectors is validated against the IWAD at
    generation time; unknown names fail the build instead of the player.

Lumps per map: FZxx marker, THINGS, LINEDEFS, SIDEDEFS, VERTEXES, SECTORS.
UZDoom builds nodes automatically when they are missing.
"""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "game/maps"
IWAD = ROOT / "vendor/freedoom-0.13.0/freedoom1.wad"
LOCK_RED = 1

# ---------------------------------------------------------------- ednums --
# Custom gameplay things (must match game/mapinfo/MAPINFO doomednums).
# One gate class per gate id: vanilla THINGS have no args field, so the id
# has to be baked into the class. `3920 + (gate - 11)` looked obvious and
# was wrong: it produced 3930/3931 for chapter 2 (evidence crate + master
# proof) and 3940/3941 for chapter 3 (unregistered, so the engine silently
# dropped both terminals - no choice menu, no evidence, trial door shut).
GATE_EDNUM = {11: 3920, 12: 3921, 21: 3922, 22: 3923, 31: 3924, 32: 3925}
ED_EVIDENCE = 3930
ED_PROOF = 3931
ED_BRIEF = 3932

# Engine ednums we place. Keep names explicit: 4 is "player 4 start" and 8
# is "Backpack", both of which load without a single warning and quietly
# leave the arena empty (a backpack even looks like our evidence crate).
ZOMBIE = 3004
SHOTGUNNER = 9
IMP = 3001
DEMON = 3002
BARON = 3003
CACO = 3005
STIMPACK = 2011
SHOTGUN = 2001
SHELLS = 2008
PLAYER1_START = 1

MONSTER_SET = {ZOMBIE, SHOTGUNNER, IMP, DEMON, BARON, CACO}

# ednums that must never show up as a monster: multi-player starts and the
# backpack (it is also the placeholder sprite of FZEvidencePickup).
FORBIDDEN_EDNUM = {2: "player 2 start", 3: "player 3 start",
                   4: "player 4 start", 8: "Backpack",
                   11: "deathmatch start 1", 12: "deathmatch start 2",
                   13: "deathmatch start 3", 14: "deathmatch start 4"}


def pad8(s):
    return s.encode("ascii")[:8].ljust(8, b"\0")


def iwad_names():
    """Collect flat names (F* namespaces) and texture names (TEXTURE1/2)."""
    data = IWAD.read_bytes()
    magic, num, ofs = struct.unpack_from("<4sii", data, 0)
    if magic not in (b"IWAD", b"PWAD"):
        raise SystemExit("%s: not a WAD (%r)" % (IWAD, magic))
    dir_ = []
    for i in range(num):
        pos, size, nm = struct.unpack_from("<ii8s", data, ofs + 16 * i)
        dir_.append((nm.rstrip(b"\0").decode("ascii", "replace").upper(), pos, size))
    idx = {nm: (pos, size) for nm, pos, size in dir_}

    flats = set()
    depth = 0
    for nm, pos, size in dir_:
        if nm in ("F_START", "FF_START", "F1_START", "F2_START", "F3_START"):
            depth += 1
        elif nm in ("F_END", "FF_END", "F1_END", "F2_END", "F3_END"):
            depth = max(0, depth - 1)
        elif depth > 0 and size > 0:
            flats.add(nm)

    textures = set()
    for tl in ("TEXTURE1", "TEXTURE2"):
        if tl in idx:
            pos, size = idx[tl]
            count = struct.unpack_from("<i", data, pos)[0]
            offs = struct.unpack_from("<%di" % count, data, pos + 4)
            for o in offs:
                textures.add(data[pos + o:pos + o + 8].rstrip(b"\0")
                             .decode("ascii", "replace").upper())
    return flats, textures


class VanillaMap:
    def __init__(self):
        self.verts = []
        self.vmap = {}
        self.sectors = []
        self.sides = []
        self.lines = []
        self.things = []
        self.used_names = set()

    def vertex(self, x, y):
        key = (x, y)
        if key in self.vmap:
            return self.vmap[key]
        idx = len(self.verts)
        self.verts.append((x, y))
        self.vmap[key] = idx
        return idx

    def side(self, sector, middle):
        self.used_names.add(middle)
        idx = len(self.sides)
        self.sides.append((0, 0, pad8("-"), pad8("-"), pad8(middle), sector))
        return idx

    def side_upper(self, sector, upper, middle="-"):
        """Sidedef whose visible face is the UPPER texture. Classic Doom
        doors draw their leaf on the upper section (the gap between the
        closed door ceiling and the neighbour ceiling); putting the door
        graphic in the middle instead leaves a see-through 'air wall'."""
        self.used_names.add(upper)
        self.used_names.add(middle)
        idx = len(self.sides)
        self.sides.append((0, 0, pad8(upper), pad8("-"), pad8(middle), sector))
        return idx

    def sector(self, floor_h, ceil_h, floor, ceil, light, special=0, tag=0):
        self.used_names.add(floor)
        self.used_names.add(ceil)
        idx = len(self.sectors)
        self.sectors.append((floor_h, ceil_h, pad8(floor), pad8(ceil),
                             light, special, tag))
        return idx

    def line(self, x1, y1, x2, y2, front, back=None, special=0, tag=0,
             blocking=True):
        v1 = self.vertex(x1, y1)
        v2 = self.vertex(x2, y2)
        flags = 0
        if back is not None:
            flags |= 4
        if blocking:
            flags |= 1
        idx = len(self.lines)
        self.lines.append((v1, v2, flags, special, tag, front, back))
        return idx

    def thing(self, x, y, type_, angle=0):
        idx = len(self.things)
        # options 7 = present on all single-player skills. NEVER set bit 16.
        self.things.append((x, y, angle, type_, 7))
        return idx

    def rect_walls(self, x1, y1, x2, y2, sector, wall, gaps=None):
        """Draw a room boundary once. gaps maps edge -> tuple or list of
        (lo, hi) coordinate ranges (world coords along the edge)."""
        gaps = gaps or {}
        # Counterclockwise (y-up): interior on the RIGHT of travel, so the
        # front sidedefs face inward.
        edges = [("s", (x2, y1), (x1, y1)), ("w", (x1, y1), (x1, y2)),
                 ("n", (x1, y2), (x2, y2)), ("e", (x2, y2), (x2, y1))]
        for side, (ax, ay), (bx, by) in edges:
            g = gaps.get(side)
            if g is None:
                gap_list = []
            elif isinstance(g, tuple) and g and isinstance(g[0], (int, float)):
                gap_list = [g]
            else:
                gap_list = list(g)
            horiz = abs(bx - ax) > 0
            for x0, y0, xb, yb, is_gap in self._segments(ax, ay, bx, by,
                                                         gap_list, horiz):
                if is_gap:
                    continue
                sd = self.side(sector, wall)
                self.line(x0, y0, xb, yb, front=sd, blocking=True)

    @staticmethod
    def _segments(ax, ay, bx, by, gaps, horiz):
        """Split an edge at gap ranges; traversal-direction aware.

        All math stays on integer grid coords: t measures distance along
        the edge from (ax, ay) toward (bx, by)."""
        if not gaps:
            return [(ax, ay, bx, by, False)]
        length = abs(bx - ax) if horiz else abs(by - ay)
        fwd = (bx >= ax) if horiz else (by >= ay)

        def pt(t):
            if length == 0:
                return (ax, ay)
            if horiz:
                return (ax + (bx - ax) * t // length, ay)
            return (ax, ay + (by - ay) * t // length)

        rngs = []
        for ga, gb in gaps:
            t1 = (ga - ax) if horiz else (ga - ay)
            t2 = (gb - ax) if horiz else (gb - ay)
            if not fwd:
                t1, t2 = -t1, -t2
            lo, hi = sorted((t1, t2))
            lo = max(0, min(length, lo))
            hi = max(0, min(length, hi))
            if hi > lo:
                rngs.append((lo, hi))
        rngs.sort()
        segs = []
        cur = 0
        for lo, hi in rngs:
            if lo > cur:
                segs.append((*pt(cur), *pt(lo), False))
            if hi > cur:
                segs.append((*pt(max(cur, lo)), *pt(hi), True))
            cur = max(cur, hi)
        if cur < length:
            segs.append((*pt(cur), bx, by, False))
        return segs

    def open_v(self, x, y0, y1, sec_east, sec_west, special=0):
        sd_e = self.side(sec_east, "-")
        sd_w = self.side(sec_west, "-")
        self.line(x, y0, x, y1, front=sd_e, back=sd_w, blocking=False,
                  special=special)

    def open_h(self, x0, x1, y, sec_south, sec_north, special=0):
        sd_s = self.side(sec_south, "-")
        sd_n = self.side(sec_north, "-")
        self.line(x0, y, x1, y, front=sd_s, back=sd_n, blocking=False,
                  special=special)

    # D1 doors (open once, STAY open): 31 = BLUE, 32 = yellow, 33 = RED.
    # DR doors (26/27/28) close again after a few seconds, which reads as
    # "the door keeps opening and closing" when the player is slow.
    DR_DOOR = {0: 31, 1: 33, 2: 32, 3: 31}

    def door(self, x1, y1, x2, y2, lock, sec_west, sec_east, face="DOORRED"):
        special = self.DR_DOOR[lock]
        sec = self.sector(0, 0, "FLOOR4_8", "FLOOR4_8", 170, special=0, tag=0)
        sd = self.side(sec, "DOORTRAK")
        self.line(x1, y2, x2, y2, front=sd, blocking=True)
        sd = self.side(sec, "DOORTRAK")
        self.line(x2, y1, x1, y1, front=sd, blocking=True)
        # NOTE: two-sided door leaves must NOT have ML_BLOCKING (flag 1) -
        # that bit makes the line impassable even when the door is open.
        # A closed door blocks via its zero-height sector, nothing else.
        sd_f = self.side_upper(sec_west, face)
        sd_b = self.side_upper(sec, face)
        self.line(x1, y2, x1, y1, front=sd_f, back=sd_b, blocking=False,
                  special=special, tag=0)
        sd_f = self.side_upper(sec_east, face)
        sd_b = self.side_upper(sec, face)
        self.line(x2, y1, x2, y2, front=sd_f, back=sd_b, blocking=False,
                  special=special, tag=0)

    def wad_bytes(self, mapname):
        things = b"".join(struct.pack("<hhhHH", x, y, a, t, f)
                          for (x, y, a, t, f) in self.things)
        lines = b"".join(struct.pack("<HHHHhHH", v1, v2, fl, sp, tg,
                                     0xFFFF if r is None else r,
                                     0xFFFF if l is None else l)
                         for (v1, v2, fl, sp, tg, r, l) in self.lines)
        sides = b"".join(struct.pack("<hh8s8s8sh", xo, yo, u, lw, m, s)
                         for (xo, yo, u, lw, m, s) in self.sides)
        secs = b"".join(struct.pack("<hh8s8shhh", fh, ch, fl, c, lt, sp, tg)
                        for (fh, ch, fl, c, lt, sp, tg) in self.sectors)
        verts = b"".join(struct.pack("<hh", x, y) for (x, y) in self.verts)
        lumps = [(mapname, b""), ("THINGS", things), ("LINEDEFS", lines),
                 ("SIDEDEFS", sides), ("VERTEXES", verts), ("SECTORS", secs)]
        out = bytearray()
        offset = 12
        body = bytearray()
        headers = []
        for name, data in lumps:
            headers.append((offset, len(data), pad8(name)))
            body += data
            offset += len(data)
        out += struct.pack("<4sii", b"PWAD", len(lumps), offset)
        out += body
        for off, size, nd in headers:
            out += struct.pack("<ii8s", off, size, nd)
        return bytes(out)


def build_chapter(palette, enemies1, enemies2, boss_adds, gate_a, gate_b):
    m = VanillaMap()
    wall = palette["wall"]
    cwall = palette["cwall"]
    floor = palette["floor"]
    ceil = palette["ceil"]

    brief = m.sector(0, 128, floor, ceil, 190)
    c1 = m.sector(0, 128, floor, ceil, 200)
    ga = m.sector(0, 128, floor, ceil, 210)
    a1 = m.sector(0, 128, floor, ceil, 180)
    evs = [m.sector(0, 128, floor, ceil, 200) for _ in range(3)]
    c2 = m.sector(0, 128, floor, ceil, 200)
    gb = m.sector(0, 128, floor, ceil, 210)
    a2 = m.sector(0, 128, floor, ceil, 180)
    boss = m.sector(0, 128, floor, ceil, 150)
    nook = m.sector(0, 128, floor, ceil, 220)

    # Room boundaries: each drawn exactly once, all gaps supplied at once.
    m.rect_walls(0, 0, 512, 512, brief, wall, gaps={"e": (192, 320)})
    m.rect_walls(512, 192, 704, 320, c1, cwall,
                 gaps={"w": (192, 320), "e": (192, 320), "n": (608, 672)})
    m.rect_walls(576, 320, 704, 544, ga, wall, gaps={"s": (608, 672)})
    m.rect_walls(704, -64, 1472, 576, a1, wall,
                 gaps={"w": (192, 320), "e": (192, 320),
                       "s": [(832, 896), (1024, 1088), (1216, 1280)]})
    m.rect_walls(800, -192, 992, -64, evs[0], wall, gaps={"n": (832, 896)})
    m.rect_walls(992, -192, 1184, -64, evs[1], wall, gaps={"n": (1024, 1088)})
    m.rect_walls(1184, -192, 1376, -64, evs[2], wall, gaps={"n": (1216, 1280)})
    m.rect_walls(1472, 192, 1664, 320, c2, cwall,
                 gaps={"w": (192, 320), "e": (192, 320), "n": (1568, 1632)})
    m.rect_walls(1536, 320, 1664, 544, gb, wall, gaps={"s": (1568, 1632)})
    m.rect_walls(1664, -64, 2432, 576, a2, wall,
                 gaps={"w": (192, 320), "e": (192, 320)})
    m.rect_walls(2464, -64, 3136, 576, boss, wall,
                 gaps={"w": (192, 320), "e": (192, 320)})
    # east side is left OPEN: the exit switch line below IS that wall.
    # Drawing both would stack two coincident lines and the use-trace
    # would hit the plain wall instead of the switch.
    m.rect_walls(3136, 192, 3328, 320, nook, cwall,
                 gaps={"w": (192, 320), "e": (192, 320)})

    m.open_v(512, 192, 320, sec_east=c1, sec_west=brief)
    m.open_v(704, 192, 320, sec_east=a1, sec_west=c1)
    m.open_h(608, 672, 320, sec_south=c1, sec_north=ga)
    m.open_h(832, 896, -64, sec_south=evs[0], sec_north=a1)
    m.open_h(1024, 1088, -64, sec_south=evs[1], sec_north=a1)
    m.open_h(1216, 1280, -64, sec_south=evs[2], sec_north=a1)
    m.open_v(1472, 192, 320, sec_east=c2, sec_west=a1)
    m.open_h(1568, 1632, 320, sec_south=c2, sec_north=gb)
    m.open_v(1664, 192, 320, sec_east=a2, sec_west=c2)
    # W1 Exit Level (special 52): walking into the exit nook ends the
    # chapter. The switch wall below is the visible "exit" landmark; the
    # walk-over trigger guarantees the transition even if a use-trace
    # misses the switch line.
    m.open_v(3136, 192, 320, sec_east=nook, sec_west=boss, special=52)

    m.door(2432, 192, 2464, 320, LOCK_RED, sec_west=a2, sec_east=boss)

    # winding matters: y DECREASES here (320 -> 192 = heading south), which
    # puts the front side - and the switch texture - on the WEST (player
    # side). Going north instead faces the void and renders black.
    sd = m.side(nook, "SW1EXIT")
    m.line(3328, 320, 3328, 192, front=sd, blocking=True, special=11)

    m.thing(128, 256, PLAYER1_START, angle=0)
    m.thing(256, 256, ED_BRIEF)  # briefing streamer
    # gate terminals: one class per gate (vanilla things have no args)
    m.thing(640, 480, GATE_EDNUM[gate_a])
    m.thing(1600, 496, GATE_EDNUM[gate_b])

    for evx in (896, 1088, 1280):
        m.thing(evx, -128, ED_EVIDENCE)
        m.thing(evx, -176, STIMPACK)

    m.thing(768, 256, SHOTGUN)
    m.thing(832, 192, SHELLS)
    m.thing(832, 320, SHELLS)
    m.thing(736, -16, 2012)
    m.thing(736, 528, 2012)
    m.thing(1728, 256, 2002)
    m.thing(1792, 192, 2007)
    m.thing(1792, 320, 2007)
    m.thing(1728, -16, 2018)
    m.thing(1728, 528, 2012)
    m.thing(2496, 256, 2018)
    m.thing(2496, 64, 2012)
    m.thing(2496, 448, 2007)

    for i, t in enumerate(enemies1):
        m.thing(896 + (i % 3) * 192, 32 + (i // 3) * 320, t, angle=180)
    for i, t in enumerate(enemies2):
        m.thing(1856 + (i % 3) * 160, 32 + (i // 3) * 320, t, angle=180)
    m.thing(2880, 256, BARON, angle=180)
    for i, t in enumerate(boss_adds):
        m.thing(2560, 64 + i * 192, t, angle=180)
    return m


CHAPTERS = [
    dict(name="FZ01",
         palette=dict(wall="STARTAN2", cwall="COMPSPAN", floor="FLOOR4_8",
                      ceil="CEIL1_2"),
         enemies1=[ZOMBIE, ZOMBIE, ZOMBIE, IMP, IMP],
         enemies2=[SHOTGUNNER, SHOTGUNNER, IMP, IMP],
         boss_adds=[IMP, IMP],
         gate_a=11, gate_b=12),
    dict(name="FZ02",
         palette=dict(wall="GRAY5", cwall="METAL1", floor="FLOOR5_3",
                      ceil="CEIL5_1"),
         enemies1=[SHOTGUNNER, SHOTGUNNER, DEMON, DEMON, ZOMBIE],
         enemies2=[SHOTGUNNER, SHOTGUNNER, SHOTGUNNER, DEMON, DEMON, DEMON],
         boss_adds=[CACO],
         gate_a=21, gate_b=22),
    dict(name="FZ03",
         palette=dict(wall="BROWN1", cwall="STONE2", floor="FLOOR0_3",
                      ceil="CEIL3_1"),
         enemies1=[SHOTGUNNER, IMP, IMP, IMP, ZOMBIE],
         enemies2=[CACO, CACO, DEMON, DEMON, SHOTGUNNER],
         boss_adds=[CACO, CACO],
         gate_a=31, gate_b=32),
]


def check_things(ch, m):
    """Fail the build when a chapter's thing list would break the flow.

    Every one of these has already happened once and each one fails
    silently in game, so they are asserted at generation time."""
    types = [t[3] for t in m.things]
    problems = []

    def count(t):
        return types.count(t)

    for gid in (ch["gate_a"], ch["gate_b"]):
        if gid not in GATE_EDNUM:
            problems.append("gate id %d has no ednum" % gid)
            continue
        if count(GATE_EDNUM[gid]) != 1:
            problems.append("gate %d (ednum %d) placed %d times"
                            % (gid, GATE_EDNUM[gid], count(GATE_EDNUM[gid])))
    if ch["gate_a"] == ch["gate_b"]:
        problems.append("chapter reuses gate id %d" % ch["gate_a"])
    if count(PLAYER1_START) != 1:
        problems.append("player 1 starts: %d" % count(PLAYER1_START))
    if count(ED_BRIEF) != 1:
        problems.append("briefing actors: %d" % count(ED_BRIEF))
    if count(ED_EVIDENCE) != 3:
        problems.append("evidence crates: %d (want 3, one per alcove)"
                        % count(ED_EVIDENCE))
    if count(BARON) != 1:
        problems.append("chapter bosses: %d (want exactly 1 baron)"
                        % count(BARON))
    for bad, what in FORBIDDEN_EDNUM.items():
        if count(bad):
            problems.append("ednum %d (%s) placed %d times"
                            % (bad, what, count(bad)))
    gate_ednums = set(GATE_EDNUM.values())
    for group in ("enemies1", "enemies2", "boss_adds"):
        for t in ch[group]:
            if t not in MONSTER_SET:
                problems.append("%s has ednum %d, which is not a monster"
                                % (group, t))
    # a gate terminal must not share an ednum with anything else
    for t in types:
        if t in gate_ednums and t not in (GATE_EDNUM[ch["gate_a"]],
                                          GATE_EDNUM[ch["gate_b"]]):
            problems.append("stray gate ednum %d in %s" % (t, ch["name"]))
    if problems:
        raise SystemExit("%s: %s" % (ch["name"], "; ".join(sorted(set(problems)))))



def validate(built):
    flats, textures = iwad_names()
    known = flats | textures
    bad = sorted({n for m in built.values() for n in m.used_names
                  if n not in known and n != "-"})
    if bad:
        raise SystemExit("names not in IWAD (flat or texture): "
                         + ", ".join(bad))
    only_tex = sorted({n for m in built.values() for n in m.used_names
                       if n in textures and n not in flats})
    if only_tex:
        print("textures used as flats (fine in ZDoom): " + ", ".join(only_tex))
    print("validated %d maps against %s: %d flats, %d textures"
          % (len(built), IWAD.name, len(flats), len(textures)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    built = {}
    for ch in CHAPTERS:
        m = build_chapter(**{k: v for k, v in ch.items() if k != "name"})
        check_things(ch, m)
        path = OUT / (ch["name"] + ".wad")
        path.write_bytes(m.wad_bytes(ch["name"]))
        built[ch["name"]] = m
        print(path, "sectors", len(m.sectors), "lines", len(m.lines),
              "things", len(m.things),
              "gates", GATE_EDNUM[ch["gate_a"]], GATE_EDNUM[ch["gate_b"]])
    validate(built)


if __name__ == "__main__":
    main()
