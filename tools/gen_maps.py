#!/usr/bin/env python3
"""Generate the three chapters as UDMF PWADs (vanilla binary still available).

UDMF is plain text, so the map can be read, diffed and edited without a
Doom editor. The namespace is ZDoomTranslated on purpose: the engine runs
the classic xlat translation on it, which means line/sector specials keep
their *Doom* numbers. Writing the plain `zdoom` namespace instead would
demand hand-translating every special into its Hexen form (door 31 becomes
Door_LockedRaise plus a lock argument, exit 52 becomes Teleport_NewMap,
and the walk/use/shoot activation moves out of the special number into
separate linedef flags) - five chances to silently break gameplay in a way
that only shows up when a player walks into a door.

Pass `--format vanilla` to emit the old binary lumps instead.

Doors, locks and the exit switch use classic Doom linedef specials; gate
terminals are custom actors with their own DoomEd numbers (one class per
gate, since vanilla things have no args field).

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

UDMF lumps per map: FZxx marker, TEXTMAP, ENDMAP.
Vanilla lumps per map: FZxx marker, THINGS, LINEDEFS, SIDEDEFS, VERTEXES,
SECTORS. UZDoom builds nodes automatically when they are missing.
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "game/maps"
BOT_ROUTE_ZS = ROOT / "tools/testhooks/bot/zscript/fzbot_routes.zs"
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
# leave the arena empty.
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
# backpack (its sprite used to be FZEvidencePickup's placeholder; the crate
# now has real art, but the ednum is still a silent way to get an empty map).
FORBIDDEN_EDNUM = {2: "player 2 start", 3: "player 3 start",
                   4: "player 4 start", 8: "Backpack",
                   11: "deathmatch start 1", 12: "deathmatch start 2",
                   13: "deathmatch start 3", 14: "deathmatch start 4"}


def pad8(s):
    return s.encode("ascii")[:8].ljust(8, b"\0")


# ---------------------------------------------------------------- udmf --
UDMF_NS = "ZDoomTranslated"
UDMF_VERSION = "1.0"


def num(v):
    """UDMF is text: print integers as integers so the file stays readable
    and diffs stay small."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def quoted(name):
    return '"%s"' % name


def tex(raw):
    """SIDEDEFS and SECTORS store NUL-padded 8-char names; UDMF wants plain
    strings and uses "-" for 'no texture'."""
    if isinstance(raw, str):
        return raw or "-"
    out = raw.rstrip(b"\0").decode("ascii")
    return out or "-"


def wad_from(lumps):
    """Assemble a PWAD from (lumpname, payload) pairs."""
    body = bytearray()
    headers = []
    offset = 12
    for name, data in lumps:
        headers.append((offset, len(data), pad8(name)))
        body += data
        offset += len(data)
    out = bytearray(struct.pack("<4sii", b"PWAD", len(lumps), offset))
    out += body
    for off, size, nd in headers:
        out += struct.pack("<ii8s", off, size, nd)
    return bytes(out)


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


class MapBuilder:
    """Format-agnostic map model: geometry in, PWAD bytes out.

    `udmf_text()` is the serialization that matters now; `wad_bytes()` is
    kept so the old binary path keeps working (and so the two can be diffed
    against each other).
    """
    def __init__(self):
        self.verts = []
        self.vmap = {}
        self.sectors = []
        self.sides = []
        self.lines = []
        self.things = []
        self.used_names = set()
        # landmarks the tests and the route generator read instead of
        # hard-coding coordinates that a layout change would silently break
        self.marks = {}
        self.route = []

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

    def side3(self, sector, upper="-", lower="-", middle="-"):
        """Sidedef with all three sections set. Doorway lines between rooms
        of different ceiling/floor height need a real texture in the upper /
        lower slot, otherwise the engine has nothing to draw in the gap."""
        for name in (upper, lower, middle):
            self.used_names.add(name)
        idx = len(self.sides)
        self.sides.append((0, 0, pad8(upper), pad8(lower), pad8(middle), sector))
        return idx

    # ------------------------------------------------------ room layout --

    @staticmethod
    def _edge_pieces(a, b, links, opens):
        """Split an axis-aligned edge running a->b into wall / link / open
        pieces, in traversal order.

        links: [(lo, hi, other_sector, special)]  drawn here, two-sided
        opens: [(lo, hi)]                         left to the neighbour
        """
        lo, hi = (a, b) if a <= b else (b, a)
        cuts = []
        for l0, l1, other, sp in links:
            x0, x1 = max(lo, min(l0, l1)), min(hi, max(l0, l1))
            if x1 > x0:
                cuts.append((x0, x1, "link", other, sp))
        for o0, o1 in opens:
            x0, x1 = max(lo, min(o0, o1)), min(hi, max(o0, o1))
            if x1 > x0:
                cuts.append((x0, x1, "open", None, 0))
        cuts.sort()
        pieces = []
        cur = lo
        for x0, x1, kind, other, sp in cuts:
            if x0 > cur:
                pieces.append((cur, x0, "wall", None, 0))
            pieces.append((x0, x1, kind, other, sp))
            cur = x1
        if cur < hi:
            pieces.append((cur, hi, "wall", None, 0))
        if b < a:
            pieces = [(x1, x0, k, o, s) for x0, x1, k, o, s in reversed(pieces)]
        return pieces

    def room(self, x1, y1, x2, y2, sector, wall, links=None, opens=None):
        """Draw a rectangular room, drawing every shared edge exactly once.

        links (drawn here, two-sided): {"n"|"s"|"e"|"w": [(lo, hi, other, sp)]}
        opens (neighbour draws it):    {"n"|"s"|"e"|"w": [(lo, hi)]}

        Splitting walls into pieces per edge is what keeps the old "air wall"
        bug out: a gap is a *range on one edge drawn once*, not two rooms
        each punching a hole and hoping they line up."""
        self.draw_edges({"s": ("h", y1, x2, x1),
                         "w": ("v", x1, y1, y2),
                         "n": ("h", y2, x1, x2),
                         "e": ("v", x2, y2, y1)},
                        sector, wall, links, opens)

    def chamfer_room(self, x1, y1, x2, y2, cut, sector, wall,
                     links=None, opens=None):
        """Rectangular room with all four corners cut at 45 degrees.

        Same links/opens contract as room(). The straight runs are shortened
        by `cut` at both ends and four diagonal walls close the shape, so the
        floor is an octagon instead of a box - the cheapest way to make a
        hall read as a place rather than as a corridor with ambitions.

        Every diagonal's front side faces inward (the direction is chosen so
        the engine's right-hand rule puts the sidedef in the room).

        The four straight runs must also be wound like room()'s: s and n run
        counter-clockwise (x2->x1 and x1->x2), and e / w must run *against*
        the y axis in the same sense (e: y2-c -> y1+c, w: y1+c -> y2-c).
        Getting e/w backwards is invisible in a diff and lethal in game: the
        one-sided wall's front sidedef ends up facing the void, so from
        inside the hall you are looking at the *back* of the wall. The engine
        draws nothing there - the sector reads as a black hole you can see
        straight through, and it stays black no matter how close you walk.
        Chapter 2's bazaar (the only chamfered room in the game) shipped with
        exactly that for a whole revision."""
        c = cut
        self.draw_edges({"s": ("h", y1, x2 - c, x1 + c),
                         "e": ("v", x2, y2 - c, y1 + c),
                         "n": ("h", y2, x1 + c, x2 - c),
                         "w": ("v", x1, y1 + c, y2 - c)},
                        sector, wall, links, opens)
        for p0, p1 in (((x2, y1 + c), (x2 - c, y1)),
                       ((x2 - c, y2), (x2, y2 - c)),
                       ((x1, y2 - c), (x1 + c, y2)),
                       ((x1 + c, y1), (x1, y1 + c))):
            sd = self.side(sector, wall)
            self.line(p0[0], p0[1], p1[0], p1[1], front=sd, blocking=True)

    def draw_edges(self, edges, sector, wall, links=None, opens=None):
        """Draw one room's four axis-aligned edges, piece by piece.

        edges: {"s"|"w"|"n"|"e": (axis, fixed, from, to)} - the direction of
        each run is chosen so its front sidedef faces into the room."""
        links = links or {}
        opens = opens or {}
        for key, (axis, fixed, a, b) in edges.items():
            pieces = self._edge_pieces(a, b, links.get(key, []),
                                       opens.get(key, []))
            for t0, t1, kind, other, sp in pieces:
                if kind == "open":
                    continue
                if axis == "h":
                    p0, p1 = (t0, fixed), (t1, fixed)
                else:
                    p0, p1 = (fixed, t0), (fixed, t1)
                if kind == "wall":
                    sd = self.side(sector, wall)
                    self.line(p0[0], p0[1], p1[0], p1[1], front=sd,
                              blocking=True)
                else:
                    sd_f = self.side3(sector, wall, wall, "-")
                    sd_b = self.side3(other, wall, wall, "-")
                    self.line(p0[0], p0[1], p1[0], p1[1], front=sd_f,
                              back=sd_b, blocking=False, special=sp)

    def solid_block(self, x1, y1, x2, y2, sector, wall):
        """Pillar: a closed one-sided loop standing inside `sector`.

        Traversed counter-clockwise so the front sidedefs face outward into
        the room; the inside of the block stays void, which is what makes it
        solid to both the player and the line of sight."""
        pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        for i in range(4):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % 4]
            sd = self.side(sector, wall)
            self.line(ax, ay, bx, by, front=sd, blocking=True)

    def platform(self, x1, y1, x2, y2, outer, inner, wall):
        """Raised dais: a four-sided loop between `outer` and `inner`.

        The riser is drawn from the OUTER sector's lower texture - that is
        the side whose floor is lower, and the engine fills the step gap
        there."""
        for (ax, ay), (bx, by) in (((x1, y1), (x2, y1)),
                                   ((x2, y1), (x2, y2)),
                                   ((x2, y2), (x1, y2)),
                                   ((x1, y2), (x1, y1))):
            sd_f = self.side3(outer, "-", wall, "-")
            sd_b = self.side3(inner, "-", wall, "-")
            self.line(ax, ay, bx, by, front=sd_f, back=sd_b, blocking=False)

    def flight(self, x1, y1, x2, y2, n, base, rise, ceil_h, floor, ceil, light,
               wall):
        """Straight staircase: n sectors tiled along +y, each `rise` above
        the one before.

        End edges are deliberately left open - the room at the bottom and the
        room at the top each draw their own side as a two-sided link, which
        is the same one-edge-one-owner rule the rectangular rooms follow.
        Steps of 8-16 units are well under the 24-unit climb limit, so the
        flight is walkable without any special lines."""
        depth = (y2 - y1) // n
        if depth * n != y2 - y1:
            raise SystemExit("flight: depth %d does not divide into %d steps"
                             % (y2 - y1, n))
        secs = [self.sector(base + i * rise, ceil_h, floor, ceil, light)
                for i in range(n)]
        for i, s in enumerate(secs):
            ya, yb = y1 + depth * i, y1 + depth * (i + 1)
            sd = self.side(s, wall)
            self.line(x1, ya, x1, yb, front=sd, blocking=True)
            sd = self.side(s, wall)
            self.line(x2, yb, x2, ya, front=sd, blocking=True)
            if i:
                self.line(x1, ya, x2, ya,
                          front=self.side3(secs[i - 1], wall, wall, "-"),
                          back=self.side3(s, wall, wall, "-"), blocking=False)
        return secs

    # D1 doors (open once, STAY open): 31 = BLUE, 32 = yellow, 33 = RED.
    # DR doors (26/27/28) close again after a few seconds, which reads as
    # "the door keeps opening and closing" when the player is slow.
    DR_DOOR = {0: 31, 1: 33, 2: 32, 3: 31}

    def door(self, x1, y1, x2, y2, lock, sec_west, sec_east, face="DOORRED"):
        """A classic Doom door slab between two sectors.

        The door sector sits at the *neighbours'* floor height, not at 0.
        A Doom door opens by raising its ceiling to the lowest neighbouring
        ceiling, so if its floor is wrong the doorway becomes a step: with
        floor 0 between two rooms at floor 128 (chapter 3's upper gallery)
        the leaf covered only the top half and the bottom 128 units were a
        hole you could see the boss room through - the missing lower texture
        simply had nothing to draw. Chapters 1 and 2 are all at floor 0,
        which is exactly why this survived until the two-storey map.
        """
        special = self.DR_DOOR[lock]
        fh = self.sectors[sec_west][0]
        sec = self.sector(fh, fh, "FLOOR4_8", "FLOOR4_8", 170, special=0, tag=0)
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

    def udmf_text(self):
        """Serialize to a UDMF TEXTMAP.

        UDMF assigns indices by order of appearance, so the arrays are
        emitted in their own index order and the references (v1/v2,
        sidefront/sideback, sidedef.sector) line up without an index field.
        """
        out = ['namespace = "%s";' % UDMF_NS,
               'version = "%s";' % UDMF_VERSION, ""]

        def emit(kind, idx, props):
            out.append("%s // %d" % (kind, idx))
            out.append("{")
            out.extend("\t%s = %s;" % kv for kv in props)
            out.append("}")
            out.append("")

        for i, (x, y) in enumerate(self.verts):
            emit("vertex", i, [("x", num(x)), ("y", num(y))])

        for i, (v1, v2, fl, sp, tg, front, back) in enumerate(self.lines):
            props = [("v1", str(v1)), ("v2", str(v2))]
            if front is not None:
                props.append(("sidefront", str(front)))
            if back is not None:
                props.append(("sideback", str(back)))
            # Only emit flags that are set: activation (playercross /
            # playeruse / shoot) is deliberately absent - xlat derives it
            # from the Doom special number itself.
            if fl & 1:
                props.append(("blocking", "true"))
            if fl & 4:
                props.append(("twosided", "true"))
            if sp:
                props.append(("special", str(sp)))
            if tg:
                props.append(("arg0", str(tg)))   # Doom line tag == arg0
            emit("linedef", i, props)

        for i, (xo, yo, up, lo, mid, sec) in enumerate(self.sides):
            emit("sidedef", i, [("sector", str(sec)),
                                ("texturetop", quoted(tex(up))),
                                ("texturebottom", quoted(tex(lo))),
                                ("texturemiddle", quoted(tex(mid))),
                                ("offsetx", num(xo)),
                                ("offsety", num(yo))])

        for i, (fh, ch, fl, c, lt, sp, tg) in enumerate(self.sectors):
            props = [("heightfloor", num(fh)), ("heightceiling", num(ch)),
                     ("texturefloor", quoted(tex(fl))),
                     ("textureceiling", quoted(tex(c))),
                     ("lightlevel", num(lt))]
            if sp:
                props.append(("special", str(sp)))
            if tg:
                props.append(("id", str(tg)))     # Doom sector tag == id
            emit("sector", i, props)

        for i, (x, y, ang, typ, fl) in enumerate(self.things):
            # Doom option bits: 1/2/4 = easy/medium/hard, 8 = ambush,
            # 16 = multiplayer only. UDMF has FIVE skill flags: skill1/2 are
            # easy, skill3 medium, skill4/5 hard. Writing only three of them
            # left skill4/skill5 at their default (false), so the 4th and
            # 5th difficulty loaded an empty map.
            props = [("x", num(x)), ("y", num(y)), ("angle", str(ang)),
                     ("type", str(typ)),
                     ("skill1", "true" if fl & 1 else "false"),
                     ("skill2", "true" if fl & 1 else "false"),
                     ("skill3", "true" if fl & 2 else "false"),
                     ("skill4", "true" if fl & 4 else "false"),
                     ("skill5", "true" if fl & 4 else "false"),
                     ("single", "false" if fl & 16 else "true"),
                     ("coop", "true"), ("dm", "true")]
            if fl & 8:
                props.append(("ambush", "true"))
            emit("thing", i, props)

        return "\n".join(out)

    def udmf_bytes(self, mapname):
        text = self.udmf_text().encode("ascii")
        return wad_from([(mapname, b""), ("TEXTMAP", text), ("ENDMAP", b"")])

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
        return wad_from([(mapname, b""), ("THINGS", things),
                         ("LINEDEFS", lines), ("SIDEDEFS", sides),
                         ("VERTEXES", verts), ("SECTORS", secs)])


def shared_edges(rooms):
    """（保留为诊断工具，不参与生成）列出两个房间共用但只由一侧拥有的墙。

    这里踩过一次坑，记下来免得再走一遍：Doom 里两个相邻扇区之间**必须**
    有同一条线的两个 sidedef（line 两侧都属于某个扇区），一面真正的墙则由
    两侧各自朝内的 one-sided line 叠在同一坐标上实现。所以"共线重叠"在这里
    不是 bug，是这类矩形房间拼法的正常产物 —— 每一侧都能看到属于自己的
    那张墙，不会露出背面（背面才是黑洞）。
    真正错的只有两种：绕向反了（正面朝外，ch2 的八角厅就是），以及共用同一
    对顶点被重复画（会让 BSP 产生重复 seg、use/音效射线打两遍）。
    """
    out = {r["sec"]: {} for r in rooms}

    def add(sec, edge, lo, hi):
        if hi > lo:
            out[sec].setdefault(edge, []).append((lo, hi))

    for i, a in enumerate(rooms):
        ax1, ay1, ax2, ay2 = a["rect"]
        for b in rooms[i + 1:]:
            bx1, by1, bx2, by2 = b["rect"]
            if ax2 == bx1:
                add(b["sec"], "w", max(ay1, by1), min(ay2, by2))
            elif bx2 == ax1:
                add(a["sec"], "w", max(ay1, by1), min(ay2, by2))
            if ay2 == by1:
                add(b["sec"], "s", max(ax1, bx1), min(ax2, bx2))
            elif by2 == ay1:
                add(a["sec"], "s", max(ax1, bx1), min(ax2, bx2))
    return out


def build_rooms(m, rooms, conns):
    """Draw a set of rectangular rooms plus their connections.

    rooms: [dict(sec=, rect=(x1,y1,x2,y2), wall=, extra_opens={})]
    conns: [(west_or_south, east_or_north, "v"|"h", coord, lo, hi, special)]

    Each connection is declared once and lands on exactly one side: the west
    room's east edge ("v") or the south room's north edge ("h"). The other
    room is told that range is somebody else's problem, so no edge is ever
    drawn twice *as an opening*, and no gap can be sealed by accident.

    Solid shared walls are the one place both rooms draw the same span on
    purpose (see shared_edges()): the wall needs a front sidedef facing each
    room, and a one-sided line only has one.
    """
    by_sec = {r["sec"]: r for r in rooms}
    links = {r["sec"]: {} for r in rooms}
    opens = {r["sec"]: {} for r in rooms}

    def add(bucket, sec, edge, item):
        bucket[sec].setdefault(edge, []).append(item)

    for a, b, axis, coord, lo, hi, sp in conns:
        if axis == "v":
            add(links, a, "e", (lo, hi, b, sp))
            add(opens, b, "w", (lo, hi))
        else:
            add(links, a, "n", (lo, hi, b, sp))
            add(opens, b, "s", (lo, hi))
    for r in rooms:
        sec = r["sec"]
        if sec not in by_sec:
            raise SystemExit("room sector %r not in rooms" % (sec,))
        x1, y1, x2, y2 = r["rect"]
        for edge, ranges in (r.get("extra_opens") or {}).items():
            opens[sec].setdefault(edge, []).extend(ranges)
        for edge, ranges in (r.get("extra_links") or {}).items():
            links[sec].setdefault(edge, []).extend(ranges)
        if r.get("chamfer"):
            m.chamfer_room(x1, y1, x2, y2, r["chamfer"], sec, r["wall"],
                           links=links[sec], opens=opens[sec])
        else:
            m.room(x1, y1, x2, y2, sec, r["wall"],
                   links=links[sec], opens=opens[sec])


LAYOUTS = {"pipeline": None, "legacy": None}   # filled in below


def build_chapter(palette, enemies1, enemies2, boss_adds, gate_a, gate_b,
                  layout="pipeline"):
    if layout not in LAYOUTS:
        raise SystemExit("unknown layout %r, expected one of %s"
                         % (layout, ", ".join(sorted(LAYOUTS))))
    m = LAYOUTS[layout](palette, enemies1, enemies2, boss_adds,
                        gate_a, gate_b)
    # Which waypoint stands at gate A? The retry scenario sends the bot back
    # there after a wrong answer, and hard-coding "wp 3" is how it ended up
    # rewinding to an evidence crate once the route changed.
    m.gate_wp = min(range(len(m.route)),
                    key=lambda i: ((m.route[i][0] - m.marks["gate_a"][0]) ** 2
                                   + (m.route[i][1] - m.marks["gate_a"][1]) ** 2))
    return m


def layout_legacy(palette, enemies1, enemies2, boss_adds, gate_a, gate_b):
    m = MapBuilder()
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
    m.marks = {
        "start": (128, 256),
        "gate_a": (640, 480), "gate_b": (1600, 496),
        "boss": (2880, 256), "exit": (3308, 256),
        "evidence": [(896, -128), (1088, -128), (1280, -128)],
    }
    m.route = [
        (128, 256), (460, 256), (640, 256), (640, 470), (640, 256),
        (780, 256), (1088, 256), (864, -32), (896, -128), (864, -32),
        (1056, -32), (1088, -128), (1056, -32), (1248, -32), (1280, -128),
        (1248, -32), (1440, 256), (1584, 256), (1600, 486), (1600, 256),
        (1728, 256), (2208, 256), (2384, 256), (2512, 256), (2880, 256),
        (3180, 256), (3308, 256),
    ]
    return m


def layout_pipeline(palette, enemies1, enemies2, boss_adds, gate_a, gate_b):
    """Chapter 1 - "fraud order-brushing abyss": a zig-zag production line.

    A 160-wide spine runs east, turns north, turns east again; work rooms and
    evidence bays hang off it. Compared with the old single-hall layout the
    same floor space is cut into 16 sectors with three ceiling heights, so
    the player reads the level as rooms instead of one big box.

    Layout rules that the rest of the project depends on:
      * no door line other than the trial door (test_trial_door asserts the
        ONLY door specials in the map are the two red leaves)
      * every room boundary is drawn once, on one side of the connection
      * corridors stay >= 96 wide so the route bot can thread them
    """
    m = MapBuilder()
    wall, cwall = palette["wall"], palette["cwall"]
    floor, ceil = palette["floor"], palette["ceil"]

    def sec(ceil_h, light, w=wall):
        return m.sector(0, ceil_h, floor, ceil, light)

    brief = sec(128, 190)
    cor_a = sec(112, 170)
    cor_b = sec(112, 160)
    cor_c = sec(112, 150, cwall)
    w1 = sec(160, 200)
    w2 = sec(144, 180)
    w3 = sec(176, 190)
    w4 = sec(128, 170)
    ev1 = sec(96, 215)
    ev2 = sec(96, 205)
    ev3 = sec(96, 210)
    niche_a = sec(96, 220, cwall)
    niche_b = sec(96, 220, cwall)
    boss = sec(192, 140)
    dais = m.sector(16, 192, floor, ceil, 175)
    nook = sec(128, 220, cwall)

    rooms = [
        dict(sec=brief, rect=(0, 0, 256, 256), wall=wall),
        dict(sec=cor_a, rect=(256, 88, 1120, 248), wall=wall),
        dict(sec=cor_b, rect=(960, 248, 1120, 640), wall=wall),
        dict(sec=cor_c, rect=(1120, 480, 1600, 640), wall=cwall,
             extra_opens={"e": [(480, 640)]}),      # trial door sits here
        dict(sec=w1, rect=(352, 248, 672, 568), wall=wall),
        dict(sec=w2, rect=(760, -232, 1080, 88), wall=wall),
        dict(sec=w3, rect=(1150, 640, 1290, 960), wall=wall),
        dict(sec=w4, rect=(1216, 320, 1536, 480), wall=cwall),
        dict(sec=ev1, rect=(672, 248, 832, 408), wall=wall),
        dict(sec=ev2, rect=(400, -8, 560, 88), wall=wall),
        dict(sec=ev3, rect=(1400, 640, 1540, 736), wall=cwall),
        dict(sec=niche_a, rect=(620, -8, 700, 88), wall=cwall),
        dict(sec=niche_b, rect=(1120, 340, 1200, 420), wall=cwall),
        dict(sec=boss, rect=(1648, 320, 2160, 768), wall=wall,
             extra_opens={"w": [(480, 640)]}),      # trial door sits here
        dict(sec=nook, rect=(2160, 480, 2352, 640), wall=cwall,
             extra_opens={"e": [(480, 640)]}),      # exit switch wall
    ]
    conns = [
        (brief, cor_a, "v", 256, 88, 248, 0),
        (cor_a, w1, "h", 248, 380, 580, 0),
        (w1, ev1, "v", 672, 248, 408, 0),
        (ev2, cor_a, "h", 88, 400, 560, 0),
        (niche_a, cor_a, "h", 88, 620, 700, 0),
        (w2, cor_a, "h", 88, 800, 960, 0),
        (cor_a, cor_b, "h", 248, 960, 1120, 0),
        (cor_b, niche_b, "v", 1120, 340, 420, 0),
        (cor_b, cor_c, "v", 1120, 480, 640, 0),
        (cor_c, w3, "h", 640, 1180, 1260, 0),
        (cor_c, ev3, "h", 640, 1400, 1540, 0),
        (w4, cor_c, "h", 480, 1296, 1456, 0),
        (boss, nook, "v", 2160, 480, 640, 52),
    ]
    build_rooms(m, rooms, conns)

    # trial door: the only door in the chapter
    m.door(1600, 480, 1648, 640, LOCK_RED, sec_west=cor_c, sec_east=boss)
    # exit switch on the nook's far wall (visual landmark; the actual level
    # change is the W1 line above, so a missed use-trace cannot soft-lock)
    sd = m.side(nook, "SW1EXIT")
    m.line(2352, 640, 2352, 480, front=sd, blocking=True, special=11)

    # pillars: cover without blocking the centre line of each room
    for box in ((400, 380, 448, 428), (576, 380, 624, 428)):
        m.solid_block(*box, w1, wall)
    for box in ((820, -140, 868, -92), (964, -140, 1012, -92)):
        m.solid_block(*box, w2, wall)
    m.solid_block(1196, 780, 1244, 828, w3, wall)
    for box in ((1250, 370, 1298, 418), (1454, 370, 1502, 418)):
        m.solid_block(*box, w4, cwall)
    for box in ((1728, 368, 1792, 432), (2016, 368, 2080, 432),
                (1728, 656, 1792, 720), (2016, 656, 2080, 720)):
        m.solid_block(*box, boss, wall)
    m.platform(1776, 448, 2032, 640, boss, dais, wall)

    m.thing(128, 128, PLAYER1_START, angle=0)
    m.thing(180, 128, ED_BRIEF)
    m.thing(660, 40, GATE_EDNUM[gate_a])
    m.thing(1160, 380, GATE_EDNUM[gate_b])

    crates = [(480, 30), (800, 320), (1470, 690)]
    for cx, cy in crates:
        m.thing(cx, cy, ED_EVIDENCE)
    m.thing(520, 30, STIMPACK)
    m.thing(760, 350, STIMPACK)
    m.thing(1440, 690, STIMPACK)
    m.thing(512, 300, SHOTGUN)
    m.thing(560, 340, SHELLS)
    m.thing(560, 260, SHELLS)
    m.thing(900, 40, 2012)          # medikit, w2
    m.thing(1260, 700, 2012)        # medikit, w3 (was 1200,800 = inside the pillar)
    # (1300,400) 会插进 x=1298 那根柱子里：半径 20 的弹药盒有 18 单位埋在
    # 石材里，玩家看到的是"捡不到、像卡在墙上的道具"。挪到房间东北角空地。
    m.thing(1410, 445, 2007)        # clip box, w4 (was 1300,400 = inside the pillar)
    m.thing(700, 190, 2007)
    m.thing(1000, 560, 2018)        # armour, cor_b
    m.thing(2300, 560, 2007)

    slots = [(430, 500, w1), (620, 500, w1), (600, 280, w1),
             (860, 60, w2), (1000, 60, w2), (900, -180, w2),
             (1200, 700, w3), (1220, 900, w3),
             (1360, 400, w4), (1480, 400, w4),
             (1040, 420, cor_b), (1250, 600, cor_c)]
    for i, t in enumerate(enemies1):
        x, y, _s = slots[i % len(slots)]
        m.thing(x, y, t, angle=180)
    for i, t in enumerate(enemies2):
        x, y, _s = slots[(i + 5) % len(slots)]
        m.thing(x, y, t, angle=180)
    m.thing(1900, 544, BARON, angle=180)
    for i, t in enumerate(boss_adds):
        m.thing(1740 + i * 260, 520, t, angle=180)

    m.marks = {
        "start": (128, 128),
        "gate_a": (660, 40), "gate_b": (1160, 380),
        "boss": (1700, 560), "exit": (2256, 560),
        "evidence": crates,
    }
    # 27 waypoints, same semantic indices as the legacy route so the test
    # driver (wp22 = trial door, wp23 = boss room, wp24 = boss centre,
    # wp25 = exit nook, wp26 = exit switch) keeps working unchanged.
    # Every leg stays inside one room or crosses a declared opening: the
    # static test walks these segments and fails on a single wall clip.
    m.route = [
        (128, 128),     # 0 spawn
        (210, 168),     # 1 briefing, heading for the spine
        (480, 168),     # 2 spine, above evidence bay 1
        (480, 30),      # 3 evidence 1
        (480, 168),     # 4 back on the spine
        (660, 168),     # 5 spine, above the gate-A niche
        (660, 40),      # 6 gate A terminal
        (660, 168),     # 7 back on the spine
        (500, 216),     # 8 work room 1 doorway
        (512, 300),     # 9 work room 1 (shotgun + first firefight)
        (660, 360),     # 10 evidence bay 1 doorway, inside work room 1
        (800, 320),     # 11 evidence 2
        (660, 360),     # 12 back out of the bay
        (500, 216),     # 13 out of work room 1, threading the pillar gap
        (860, 168),     # 14 spine, above work room 2
        (1040, 180),    # 15 spine, east end
        (1080, 380),    # 16 north corridor
        (1160, 375),    # 17 gate B terminal
        (1080, 380),    # 18 back in the corridor
        (1080, 600),    # 19 corridor, turning east
        (1300, 560),    # 20 upper corridor
        (1470, 690),    # 21 evidence 3, in the bay off the upper corridor
        (1560, 560),    # 22 trial door face (waits for outside USE)
        (1700, 560),    # 23 through the door, boss room
        (1900, 544),    # 24 boss centre, on the dais
        (2256, 560),    # 25 exit nook
        (2320, 560),    # 26 exit switch face
    ]
    return m


def layout_market(palette, enemies1, enemies2, boss_adds, gate_a, gate_b):
    """Chapter 2 - "black-market bazaar": an octagonal hall with six radial
    stalls, a back loading corridor and a warehouse boss room.

    The point is that it does not read like chapter 1: where the pipeline is
    long thin rooms in series, this is one tall room you can see across, with
    booths hanging off it. All stall openings sit on the four straight edges
    of the chamfered hall, so the connection machinery (`room`/`opens`) is
    still the only thing drawing shared edges - no diagonal is ever shared
    with another room, which keeps the "drawn twice" bug out.
    """
    m = MapBuilder()
    wall, cwall = palette["wall"], palette["cwall"]
    floor, ceil = palette["floor"], palette["ceil"]

    def sec(ceil_h, light, w=wall):
        return m.sector(0, ceil_h, floor, ceil, light)

    brief = sec(128, 190)
    cor_in = sec(112, 170)
    hub = sec(192, 205)
    hub_dais = m.sector(16, 192, floor, ceil, 195)
    n1 = sec(144, 200)
    n2 = sec(144, 185)
    s1 = sec(136, 180)
    s2 = sec(136, 215)
    e1 = sec(152, 190)
    w1 = sec(128, 210)
    back = sec(104, 150, cwall)
    arena = sec(160, 175)
    boss = sec(192, 140)
    boss_dais = m.sector(16, 192, floor, ceil, 175)
    nook = sec(128, 220, cwall)

    rooms = [
        dict(sec=brief, rect=(0, 512, 256, 768), wall=wall),
        dict(sec=cor_in, rect=(256, 576, 640, 704), wall=wall),
        dict(sec=hub, rect=(640, 320, 1600, 1280), wall=wall, chamfer=128),
        # stalls: the booth walls are metal, the hall is brick - a one-line
        # reminder of which side of the counter you are standing on
        dict(sec=n1, rect=(800, 1280, 1040, 1520), wall=cwall,
             extra_opens={"s": [(800, 1040)]}),
        dict(sec=n2, rect=(1120, 1280, 1360, 1520), wall=cwall,
             extra_opens={"s": [(1120, 1360)]}),
        dict(sec=s1, rect=(800, 80, 1040, 320), wall=cwall,
             extra_opens={"n": [(800, 1040)]}),
        dict(sec=s2, rect=(1120, 80, 1360, 320), wall=cwall,
             extra_opens={"n": [(1120, 1360)]}),
        dict(sec=e1, rect=(1600, 720, 1888, 960), wall=cwall,
             extra_opens={"w": [(720, 960)]}),
        dict(sec=w1, rect=(368, 800, 640, 1040), wall=cwall,
             extra_opens={"e": [(800, 1040)]}),
        dict(sec=back, rect=(1600, 448, 2288, 576), wall=cwall,
             extra_opens={"w": [(448, 576)]}),
        dict(sec=arena, rect=(2288, 384, 2784, 960), wall=wall,
             extra_opens={"e": [(608, 736)]}),      # trial door sits here
        dict(sec=boss, rect=(2832, 320, 3424, 1024), wall=wall,
             extra_opens={"w": [(608, 736)]}),      # trial door sits here
        dict(sec=nook, rect=(3424, 608, 3616, 736), wall=cwall,
             extra_opens={"e": [(608, 736)]}),      # exit switch wall
    ]
    conns = [
        (brief, cor_in, "v", 256, 576, 704, 0),
        (cor_in, hub, "v", 640, 576, 704, 0),
        (w1, hub, "v", 640, 800, 1040, 0),
        (s1, hub, "h", 320, 800, 1040, 0),
        (s2, hub, "h", 320, 1120, 1360, 0),
        (hub, n1, "h", 1280, 800, 1040, 0),
        (hub, n2, "h", 1280, 1120, 1360, 0),
        (hub, e1, "v", 1600, 720, 960, 0),
        (hub, back, "v", 1600, 448, 576, 0),
        (back, arena, "v", 2288, 448, 576, 0),
        (boss, nook, "v", 3424, 608, 736, 52),
    ]
    build_rooms(m, rooms, conns)

    # trial door: the only door in the chapter
    m.door(2784, 608, 2832, 736, LOCK_RED, sec_west=arena, sec_east=boss)
    sd = m.side(nook, "SW1EXIT")
    m.line(3616, 736, 3616, 608, front=sd, blocking=True, special=11)

    # market fixtures: crates along the hall walls, stalls keep their floor
    # clear so the booths read as walk-in counters
    for box in ((1400, 400, 1480, 470), (1400, 600, 1480, 670),
                (1400, 1120, 1480, 1190), (660, 450, 740, 520),
                (700, 1120, 780, 1190)):
        m.solid_block(*box, hub, wall)
    m.platform(860, 600, 1160, 860, hub, hub_dais, wall)

    for box in ((2340, 400, 2400, 470), (2660, 840, 2720, 910)):
        m.solid_block(*box, arena, wall)
    for box in ((2900, 380, 2960, 450), (3300, 380, 3360, 450),
                (2900, 900, 2960, 970), (3300, 900, 3360, 970)):
        m.solid_block(*box, boss, wall)
    m.platform(2980, 600, 3280, 760, boss, boss_dais, wall)

    m.thing(128, 640, PLAYER1_START, angle=0)
    m.thing(180, 640, ED_BRIEF)
    m.thing(500, 920, GATE_EDNUM[gate_a])
    m.thing(1240, 1400, GATE_EDNUM[gate_b])

    crates = [(920, 200), (1700, 840), (1950, 512)]
    for cx, cy in crates:
        m.thing(cx, cy, ED_EVIDENCE)
    m.thing(700, 760, SHOTGUN)
    m.thing(760, 760, SHELLS)
    m.thing(700, 820, SHELLS)
    m.thing(940, 240, STIMPACK)
    m.thing(1290, 240, STIMPACK)
    m.thing(1740, 900, STIMPACK)
    m.thing(900, 1180, 2012)        # medikit, hall north
    m.thing(1520, 700, 2012)        # medikit, hall east (was 1450,620 = inside a crate pillar)
    m.thing(2500, 500, 2007)        # clip box, arena
    m.thing(2100, 470, 2007)        # clip box, back corridor
    m.thing(2560, 800, 2018)        # armour, arena
    m.thing(3350, 660, 2007)
    m.thing(3100, 672, BARON, angle=180)
    for i, t in enumerate(boss_adds):
        m.thing(2950 + i * 300, 780, t, angle=180)

    # (1400,1100) 和 (1950,470) 会让半径 30 的 Demon 有 8~10 单位埋进墙里
    # （玩家看到的是"怪半个身子在石材里"）。两个点沿 y 各让 20 单位。
    slots = [(700, 1100), (900, 1100), (1400, 1078), (790, 505),
             (1450, 545), (900, 250), (1250, 250), (1750, 900),
             (1500, 600), (2400, 900), (2600, 450), (1950, 490)]
    for i, t in enumerate(enemies1):
        x, y = slots[i % len(slots)]
        m.thing(x, y, t, angle=180)
    for i, t in enumerate(enemies2):
        x, y = slots[(i + 6) % len(slots)]
        m.thing(x, y, t, angle=180)

    m.marks = {
        "start": (128, 640),
        "gate_a": (500, 920), "gate_b": (1240, 1400),
        "boss": (2900, 672), "exit": (3500, 672),
        "evidence": crates,
    }
    m.route = [
        (128, 640),     # 0 spawn
        (300, 640),     # 1 corridor out of the briefing room
        (560, 640),     # 2 hall doorway
        (700, 640),     # 3 inside the hall
        (700, 850),     # 4 west side, in front of the west booth
        (450, 920),     # 5 gate A, inside the west booth
        (700, 850),     # 6 back into the hall
        (920, 600),     # 7 south side of the hall
        (920, 200),     # 8 evidence 1, south booth
        (920, 560),     # 9 out of the booth
        (1240, 700),    # 10 hall centre, on the raised dais
        (1240, 1180),   # 11 north side of the hall
        (1240, 1400),   # 12 gate B, north booth
        (1240, 1180),   # 13 back into the hall
        (1500, 900),    # 14 east side
        (1700, 840),    # 15 evidence 2, east booth
        (1500, 780),    # 16 back into the hall
        (1500, 512),    # 17 hall east, by the loading corridor
        (1700, 512),    # 18 loading corridor
        (1950, 512),    # 19 evidence 3, on the loading dock
        (2400, 512),    # 20 warehouse floor
        (2600, 660),    # 21 warehouse centre
        (2760, 672),    # 22 trial door face (waits for outside USE)
        (2860, 672),    # 23 through the door, boss warehouse
        (3100, 672),    # 24 boss centre, on the dais
        (3500, 672),    # 25 exit nook
        (3568, 672),    # 26 exit switch face
    ]
    return m


def layout_precinct(palette, enemies1, enemies2, boss_adds, gate_a, gate_b):
    """Chapter 3 - "the fake police station": two storeys joined by a flight
    of stairs.

    The briefing hall is deliberately double height (ceiling 256) so the
    staircase reads as going *up* to somewhere, and the upper storey sits at
    floor 128 with much lower ceilings - the change in headroom is what
    makes it feel like a different floor rather than a raised platform.

    The two storeys never overlap in plan: the upper corridor and its rooms
    are east/north of the hall, and the flight is the only thing that
    bridges the height difference.
    """
    m = MapBuilder()
    wall, cwall = palette["wall"], palette["cwall"]
    floor, ceil = palette["floor"], palette["ceil"]

    def sec(floor_h, ceil_h, light, w=wall):
        return m.sector(floor_h, ceil_h, floor, ceil, light)

    brief = sec(0, 128, 190)
    hall = sec(0, 256, 200)          # double height: the staircase needs room
    cells = sec(0, 128, 160, cwall)
    case = sec(0, 160, 185)
    u_cor = sec(128, 192, 180)
    archive = sec(128, 224, 195)
    interro = sec(128, 224, 210)
    boss = sec(128, 224, 150)
    boss_dais = sec(144, 224, 175)
    nook = sec(128, 224, 220, cwall)

    # eight 16-unit steps = one storey; floors 16..128
    steps = m.flight(560, 576, 752, 704, 8, 16, 16, 192, floor, ceil, 175,
                     wall)

    rooms = [
        dict(sec=brief, rect=(0, 0, 256, 256), wall=wall),
        dict(sec=hall, rect=(256, 64, 1152, 576), wall=wall,
             extra_links={"n": [(560, 752, steps[0], 0)]}),
        dict(sec=cells, rect=(256, -256, 1152, 64), wall=cwall),
        dict(sec=case, rect=(1152, 160, 1504, 480), wall=wall),
        dict(sec=u_cor, rect=(560, 704, 1408, 832), wall=wall,
             extra_links={"s": [(560, 752, steps[-1], 0)]},
             extra_opens={"e": [(704, 832)]}),      # trial door sits here
        dict(sec=archive, rect=(704, 832, 1024, 1088), wall=wall),
        dict(sec=interro, rect=(1088, 832, 1376, 1088), wall=cwall),
        dict(sec=boss, rect=(1456, 608, 1904, 1088), wall=wall,
             extra_opens={"w": [(704, 832)]}),      # trial door sits here
        dict(sec=nook, rect=(1904, 704, 2096, 832), wall=cwall,
             extra_opens={"e": [(704, 832)]}),      # exit switch wall
    ]
    conns = [
        (brief, hall, "v", 256, 96, 224, 0),
        (cells, hall, "h", 64, 400, 560, 0),
        (hall, case, "v", 1152, 240, 400, 0),
        (u_cor, archive, "h", 832, 704, 896, 0),
        (u_cor, interro, "h", 832, 1120, 1296, 0),
        (boss, nook, "v", 1904, 704, 832, 52),
    ]
    build_rooms(m, rooms, conns)

    # trial door between the upper gallery and the boss office
    m.door(1408, 704, 1456, 832, LOCK_RED, sec_west=u_cor, sec_east=boss)
    sd = m.side(nook, "SW1EXIT")
    m.line(2096, 832, 2096, 704, front=sd, blocking=True, special=11)

    # lobby columns and a reception desk in the hall
    for box in ((850, 450, 920, 520), (1010, 200, 1080, 270),
                (300, 470, 370, 540)):
        m.solid_block(*box, hall, wall)
    # cell block: a row of holding cells as dead-end niches is too much
    # geometry for the payoff, so the cells are one corridor with pillars
    for box in ((400, -240, 460, -200), (600, -240, 660, -200),
                (800, -240, 860, -200)):
        m.solid_block(*box, cells, cwall)
    for box in ((1520, 620, 1580, 690), (1780, 620, 1840, 690),
                (1520, 850, 1580, 920), (1780, 850, 1840, 920)):
        m.solid_block(*box, boss, wall)
    m.platform(1640, 720, 1760, 816, boss, boss_dais, wall)

    m.thing(128, 128, PLAYER1_START, angle=0)
    m.thing(180, 128, ED_BRIEF)
    m.thing(1170, 330, GATE_EDNUM[gate_a])
    m.thing(1230, 780, GATE_EDNUM[gate_b])

    crates = [(450, -180), (800, 960), (1230, 960)]
    for cx, cy in crates:
        m.thing(cx, cy, ED_EVIDENCE)
    m.thing(500, -100, SHOTGUN)
    m.thing(560, -100, SHELLS)
    m.thing(560, -160, SHELLS)
    m.thing(700, 300, STIMPACK)
    m.thing(1340, 300, STIMPACK)
    m.thing(900, -60, 2012)         # medikit, cell block
    m.thing(1380, 800, 2012)        # medikit, upper gallery (was 1440,780 = inside the trial door)
    m.thing(760, 1000, 2007)        # clip box, archive
    m.thing(1300, 1030, 2018)       # armour, interrogation room
    m.thing(1600, 760, 2012)        # medikit, boss office
    m.thing(1700, 768, BARON, angle=180)
    for i, t in enumerate(boss_adds):
        # y=820 时半径 31 的 Cacodemon 正好蹭进下面那对柱子 1 单位；让到 806
        m.thing(1560 + i * 240, 806, t, angle=180)

    slots = [(500, 200), (700, 200), (960, 300), (1000, 300), (600, -120),
             (900, -120), (1200, 240), (1350, 400), (700, 760), (900, 780),
             (1150, 900), (1300, 900)]
    for i, t in enumerate(enemies1):
        x, y = slots[i % len(slots)]
        m.thing(x, y, t, angle=180)
    for i, t in enumerate(enemies2):
        x, y = slots[(i + 5) % len(slots)]
        m.thing(x, y, t, angle=180)

    m.marks = {
        "start": (128, 128),
        "gate_a": (1170, 330), "gate_b": (1230, 780),
        "boss": (1600, 768), "exit": (1990, 768),
        "evidence": crates,
    }
    m.route = [
        (128, 128),     # 0 spawn
        (230, 160),     # 1 briefing room door
        (400, 160),     # 2 lobby, west end
        (400, 340),     # 3 lobby, in front of the cell block
        (450, -180),    # 4 evidence 1, cell block
        (700, -180),    # 5 down the cell row
        (520, -60),     # 6 back to the cell block door
        (450, 340),     # 7 lobby again
        (700, 340),     # 8 lobby centre
        (900, 340),     # 9 lobby east
        (1200, 320),    # 10 gate A, in the case room
        (900, 340),     # 11 back into the lobby
        (560, 540),     # 12 foot of the stairs
        (656, 600),     # 13 up the flight
        (656, 660),     # 14 still climbing
        (720, 780),     # 15 upper gallery
        (820, 960),     # 16 evidence 2, archive
        (800, 780),     # 17 back on the gallery
        (1000, 780),    # 18 gallery
        (1230, 780),    # 19 gate B
        (1230, 960),    # 20 evidence 3, interrogation room
        (1230, 780),    # 21 back on the gallery
        (1394, 770),    # 22 trial door face (waits for outside USE)
        (1500, 768),    # 23 through the door, boss office
        (1700, 768),    # 24 boss centre, on the dais
        (1990, 768),    # 25 exit nook
        (2060, 768),    # 26 exit switch face
    ]
    return m


LAYOUTS.update({"pipeline": layout_pipeline, "market": layout_market,
                "precinct": layout_precinct, "legacy": layout_legacy})


CHAPTERS = [
    dict(name="FZ01", layout="pipeline",
         palette=dict(wall="STARTAN2", cwall="COMPSPAN", floor="FLOOR4_8",
                      ceil="CEIL1_2"),
         enemies1=[ZOMBIE, ZOMBIE, ZOMBIE, IMP, IMP],
         enemies2=[SHOTGUNNER, SHOTGUNNER, IMP, IMP],
         boss_adds=[IMP, IMP],
         gate_a=11, gate_b=12),
    dict(name="FZ02", layout="market",
         palette=dict(wall="GRAY5", cwall="METAL1", floor="FLOOR5_3",
                      ceil="CEIL3_4"),
         enemies1=[SHOTGUNNER, SHOTGUNNER, DEMON, DEMON, ZOMBIE],
         enemies2=[SHOTGUNNER, SHOTGUNNER, SHOTGUNNER, DEMON, DEMON, DEMON],
         boss_adds=[CACO],
         gate_a=21, gate_b=22),
    dict(name="FZ03", layout="precinct",
         palette=dict(wall="FZW3WALL", cwall="STONE2", floor="FZF3FLR",
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



def own_tex_names() -> set:
    """Names supplied by our own PK3 (game/textures, game/flats).

    The IWAD-only check below is what keeps a typo from shipping as a
    checkerboard wall. Custom art is legitimate, so the check becomes
    "IWAD **or** a file we actually ship" - and it stays strict, because a
    name only counts once the PNG exists."""
    names = set()
    for sub in ("textures", "flats"):
        d = ROOT / "game" / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*.png"):
            names.add(p.stem.upper())
    return names


def validate(built):
    flats, textures = iwad_names()
    known = flats | textures | own_tex_names()
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


FORMATS = ("udmf", "vanilla")


def parse_format(argv):
    """`--format udmf|vanilla`, default udmf."""
    fmt = "udmf"
    for i, a in enumerate(argv):
        if a in ("--format", "-f"):
            if i + 1 >= len(argv):
                raise SystemExit("--format needs a value: " + "|".join(FORMATS))
            fmt = argv[i + 1].lower()
        elif a.startswith("--format="):
            fmt = a.split("=", 1)[1].lower()
    if fmt not in FORMATS:
        raise SystemExit("unknown format %r, expected one of %s"
                         % (fmt, ", ".join(FORMATS)))
    return fmt


def bot_routes_zs(built) -> str:
    """Render the automation bot's per-chapter route as ZScript.

    The route used to be hand-written into fzbot.zs. Every map reshuffle
    then silently left the robot walking last week's floor plan - the run
    still "passed" because the bot just got stuck in a wall and timed out
    on a route nobody re-read. Generating it from the same model that
    emits the geometry means a layout change can never drift.
    """
    out = [
        "// fzbot_routes.zs - GENERATED by tools/gen_maps.py, do not edit.",
        "//",
        "// Route for the automation bot, one block per chapter keyed on",
        "// level.mapname. Regenerate with `python tools/gen_maps.py`;",
        "// tools/test_game_logic.py fails when this file drifts from the maps.",
        "class FZBotRoutes",
        "{",
        "\tstatic int Count(String map)",
        "\t{",
    ]
    for name, m in built.items():
        out.append('\t\tif (map == "%s") return %d;' % (name, len(m.route)))
    out += ["\t\treturn 0;", "\t}", ""]

    out += ["\t// waypoint that stands at gate A: the retry scenario walks",
            "\t// back here after a wrong answer",
            "\tstatic int GateA(String map)",
            "\t{"]
    for name, m in built.items():
        out.append('\t\tif (map == "%s") return %d;' % (name, m.gate_wp))
    out += ["\t\treturn 0;", "\t}", ""]

    for fn, idx in (("X", 0), ("Y", 1)):
        out += ["\tstatic double %s(String map, int i)" % fn, "\t{"]
        for n, (name, m) in enumerate(built.items()):
            out.append('\t\t%s (map == "%s")'
                       % ("if" if n == 0 else "else if", name))
            out.append("\t\t{")
            out.append("\t\t\tswitch (i)")
            out.append("\t\t\t{")
            for i, p in enumerate(m.route):
                out.append("\t\t\t\tcase %d: return %d;" % (i, p[idx]))
            out.append("\t\t\t}")
            out.append("\t\t}")
        out += ["\t\treturn 0;", "\t}", ""]
    out.append("}")
    return "\n".join(out) + "\n"


def main(argv=None):
    fmt = parse_format(sys.argv[1:] if argv is None else argv)
    OUT.mkdir(parents=True, exist_ok=True)
    built = {}
    for ch in CHAPTERS:
        m = build_chapter(**{k: v for k, v in ch.items() if k != "name"})
        check_things(ch, m)
        path = OUT / (ch["name"] + ".wad")
        if fmt == "udmf":
            data = m.udmf_bytes(ch["name"])
        else:
            data = m.wad_bytes(ch["name"])
        path.write_bytes(data)
        built[ch["name"]] = m
        print("%s  %-7s %6d bytes  sectors %d  lines %d  things %d  "
              "gates %d/%d"
              % (path, fmt, len(data), len(m.sectors), len(m.lines),
                 len(m.things), GATE_EDNUM[ch["gate_a"]],
                 GATE_EDNUM[ch["gate_b"]]))
    validate(built)

    BOT_ROUTE_ZS.parent.mkdir(parents=True, exist_ok=True)
    BOT_ROUTE_ZS.write_text(bot_routes_zs(built), encoding="utf-8")
    print("%s  %d waypoints" % (BOT_ROUTE_ZS, sum(len(m.route) for m in built.values())))


if __name__ == "__main__":
    main()
