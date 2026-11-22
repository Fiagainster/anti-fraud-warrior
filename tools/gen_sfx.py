"""程序化合成第一批游戏音效（预听用，未进游戏）。

用法: python tools/gen_sfx.py [输出目录]
默认输出到 sfx_preview/：按类别分目录、按编号命名，audition/ 下是连播版。
所有声音由振荡器 / 噪声 / 包络 / 滤波实时合成，不依赖任何素材库。
"""
import os
import sys

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "sfx_preview")


# ---------------- 基础工具 ----------------

def n_samples(dur):
    return int(SR * dur)


def tvec(n):
    return np.arange(n) / SR


def env(n, attack=0.001, decay=20.0):
    a = max(1, int(SR * attack))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[a:] = np.exp(-decay * tvec(n - a))
    return e


def sine(f0, dur, f1=None):
    n = n_samples(dur)
    f = np.linspace(f0, f1 if f1 is not None else f0, n)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def square(f0, dur, duty=0.5, f1=None, seed=0):
    n = n_samples(dur)
    f = np.linspace(f0, f1 if f1 is not None else f0, n)
    ph = np.cumsum(f) / SR
    ph = ph + seed * 0.13
    return np.where((ph % 1.0) < duty, 1.0, -1.0)


def noise(dur, seed=7):
    return np.random.default_rng(seed).uniform(-1, 1, n_samples(dur))


def lp(x, cutoff):
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def hp(x, cutoff):
    return x - lp(x, cutoff)


def sat(x, drive=2.0):
    return np.tanh(drive * x) / np.tanh(drive)


def room(x, taps=((0.021, 0.34), (0.043, 0.20), (0.071, 0.11))):
    y = x.copy()
    for ms, g in taps:
        d = int(SR * ms)
        if d < len(x):
            y[d:] += lp(x[:-d], 3000) * g
    return y


def brighten(x, shelf=0.55, cutoff=3500):
    """给高频加一层存在感，听感上更"炸"。"""
    return x + hp(x, cutoff) * shelf


def norm(x, peak=0.99):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def loud(x, target_rms=0.19):
    """峰值归一到 0.99 后把 RMS 顶上去，再软削波，听起来更响。"""
    x = norm(x, 0.99)
    rms = np.sqrt(np.mean(x ** 2)) or 1e-6
    g = min(target_rms / rms, 6.0)
    return norm(sat(x * g, 1.4), 0.99)


def place(buf, sig, at):
    s = int(SR * at)
    end = min(len(buf), s + len(sig))
    if end > s:
        buf[s:end] += sig[: end - s]
    return buf


# ---------------- 枪械 ----------------

def shot_layers(crack_hp, crack_gain, blast_cut, blast_dur, blast_decay,
                body_f0, body_f1, body_dur, body_decay, body_gain,
                dur, ring=(0.0, 0.0), seed=1):
    """枪声的原始分层（未加空间、未归一）：瞬时爆裂 + 枪口噪声 + 低频顶 + 可选枪管余振。"""
    buf = np.zeros(n_samples(dur))

    click = hp(noise(0.0025, seed), 6000) * env(n_samples(0.0025), 0.0002, 400) * 1.15
    place(buf, click, 0.0)

    crack = hp(noise(0.008, seed + 1), crack_hp) * env(n_samples(0.008), 0.0002, 210)
    place(buf, crack * crack_gain, 0.0004)

    blast = lp(noise(blast_dur, seed + 2), blast_cut) * env(n_samples(blast_dur), 0.0006, blast_decay)
    place(buf, blast * 1.15, 0.0006)

    body = sine(body_f0, body_dur, body_f1) * env(n_samples(body_dur), 0.001, body_decay)
    place(buf, body * body_gain, 0.0)

    if ring[0] > 0:
        r = ring[0]
        ring_sig = np.zeros(n_samples(0.09))
        place(ring_sig, sine(r, 0.09, r * 0.96) * 0.5, 0.0)
        place(ring_sig, sine(r * 1.47, 0.07, r * 1.4) * 0.3, 0.0)
        place(buf, ring_sig * env(n_samples(0.09), 0.0003, 34) * ring[1], 0.001)

    return buf


def gun(crack_hp, crack_gain, blast_cut, blast_dur, blast_decay,
        body_f0, body_f1, body_dur, body_decay, body_gain,
        dur, tail_taps=None, ring=(0.0, 0.0), shelf=0.55, seed=1):
    buf = shot_layers(crack_hp, crack_gain, blast_cut, blast_dur, blast_decay,
                      body_f0, body_f1, body_dur, body_decay, body_gain,
                      dur, ring=ring, seed=seed)
    buf = room(buf, tail_taps or ((0.020, 0.32), (0.041, 0.19), (0.069, 0.10)))
    buf = brighten(buf, shelf)
    return loud(buf)


def sweep_lp(x, f0, f1):
    """低通截止频率随时间从 f0 滑到 f1，模拟枪口噪声"撕裂 → 闷下去"。"""
    n = len(x)
    fc = np.geomspace(f0, f1, n)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    y = np.zeros(n)
    acc = 0.0
    for i in range(n):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def pistol_v3(style="crisp", seed=71):
    """手枪 v3：去掉金属"叮"，靠滑落低通和短促机械噪声做真实感。"""
    cfg = {
        "crisp": dict(crack=2600, cgain=1.7, blast_dur=0.10, blast_decay=34, cut=(9000, 900),
                      body=(190, 70, 0.14, 26, 0.85), mech=(0.040, 0.055, 0.10),
                      taps=((0.015, 0.22), (0.032, 0.12)), shelf=0.9, dur=0.40),
        "thump": dict(crack=1200, cgain=1.5, blast_dur=0.14, blast_decay=20, cut=(5000, 500),
                      body=(130, 45, 0.22, 14, 1.2), mech=(0.055, 0.075, 0.08),
                      taps=((0.024, 0.34), (0.052, 0.20), (0.088, 0.10)), shelf=0.5, dur=0.52),
        "corridor": dict(crack=2000, cgain=1.6, blast_dur=0.11, blast_decay=28, cut=(8000, 800),
                         body=(170, 60, 0.16, 20, 0.95), mech=(0.045, 0.060, 0.09),
                         taps=((0.030, 0.42), (0.066, 0.28), (0.105, 0.17), (0.150, 0.09)),
                         shelf=0.8, dur=0.60),
        "doom": dict(crack=1500, cgain=1.4, blast_dur=0.07, blast_decay=40, cut=(6000, 1400),
                     body=(175, 80, 0.10, 32, 0.8), mech=(0.035, 0.050, 0.10),
                     taps=((0.012, 0.16),), shelf=0.6, dur=0.30),
        "snub": dict(crack=2200, cgain=1.9, blast_dur=0.08, blast_decay=42, cut=(9500, 1200),
                     body=(200, 80, 0.10, 30, 0.8), mech=(0.030, 0.045, 0.12),
                     taps=((0.014, 0.20), (0.028, 0.10)), shelf=1.0, dur=0.34),
    }[style]

    buf = np.zeros(n_samples(cfg["dur"]))
    place(buf, hp(noise(0.0016, seed), 7000) * env(n_samples(0.0016), 0.0001, 500) * 1.2, 0.0)

    crack = hp(noise(0.007, seed + 1), cfg["crack"]) * env(n_samples(0.007), 0.0002, 220)
    place(buf, crack * cfg["cgain"], 0.0003)

    blast = sweep_lp(noise(cfg["blast_dur"], seed + 2), *cfg["cut"])
    place(buf, blast * env(n_samples(cfg["blast_dur"]), 0.0006, cfg["blast_decay"]) * 1.25, 0.0005)

    f0, f1, bdur, bdecay, bgain = cfg["body"]
    place(buf, sine(f0, bdur, f1) * env(n_samples(bdur), 0.001, bdecay) * bgain, 0.0)

    shhk_at, clack_at, mgain = cfg["mech"]
    place(buf, hp(noise(0.020, seed + 3), 1600) * env(n_samples(0.020), 0.0003, 95) * mgain * 0.7, shhk_at)
    place(buf, lp(noise(0.012, seed + 4), 3200) * env(n_samples(0.012), 0.0002, 190) * mgain, clack_at)

    buf = room(buf, cfg["taps"])
    buf = brighten(buf, cfg["shelf"])
    return loud(buf, 0.21)


def shotgun(style="bright", seed=21):
    if style == "bright":
        return gun(1200, 1.8, 3200, 0.34, 11, 95, 44, 0.36, 8, 1.25,
                   0.85, tail_taps=((0.024, 0.42), (0.050, 0.26), (0.083, 0.15)),
                   shelf=0.85, seed=seed)
    if style == "cinema":
        s = gun(600, 1.6, 2000, 0.42, 7, 78, 34, 0.55, 5.5, 1.5,
                1.40, tail_taps=((0.032, 0.5), (0.071, 0.34), (0.128, 0.22), (0.190, 0.12)),
                shelf=0.5, seed=seed)
        sub = sine(46, 0.75, 30) * env(n_samples(0.75), 0.004, 4.5) * 0.9
        place(s, sub, 0.01)
        return np.clip(s, -1, 1)
    if style == "tight":
        return gun(1600, 1.6, 3800, 0.20, 18, 110, 52, 0.24, 12, 1.1,
                   0.52, tail_taps=((0.018, 0.30), (0.038, 0.16)),
                   shelf=0.8, seed=seed)
    buf = gun(900, 1.7, 2600, 0.36, 10, 88, 40, 0.42, 7.5, 1.35,
              1.05, tail_taps=((0.028, 0.45), (0.058, 0.28), (0.096, 0.16)),
              shelf=0.7, seed=seed)
    for at in (0.62, 0.74):
        clk = lp(noise(0.028, seed + int(at * 100)), 2600) * env(n_samples(0.028), 0.0003, 90)
        place(buf, clk * 0.45, at)
        place(buf, hp(noise(0.006, seed + int(at * 137)), 3000) * env(n_samples(0.006), 0.0002, 300) * 0.5, at)
    return np.clip(loud(buf), -1, 1)


# ---------------- 拾取 ----------------

def evidence(seed=31):
    buf = np.zeros(n_samples(0.42))
    place(buf, square(880, 0.06, 0.35) * env(n_samples(0.06), 0.001, 30) * 0.38, 0.005)
    place(buf, square(1320, 0.11, 0.30) * env(n_samples(0.11), 0.001, 20) * 0.34, 0.075)
    place(buf, hp(noise(0.010, seed), 4000) * env(n_samples(0.010), 0.0003, 200) * 0.30, 0.0)
    return loud(lp(buf, 7000), 0.15)


def ammo(seed=32):
    buf = np.zeros(n_samples(0.30))
    place(buf, hp(noise(0.008, seed), 3000) * env(n_samples(0.008), 0.0002, 200) * 0.6, 0.0)
    place(buf, sine(520, 0.07, 470) * env(n_samples(0.07), 0.001, 40) * 0.55, 0.004)
    place(buf, sine(780, 0.09, 690) * env(n_samples(0.09), 0.001, 30) * 0.45, 0.072)
    return loud(buf, 0.14)


def health(seed=33):
    buf = np.zeros(n_samples(0.40))
    place(buf, sine(660, 0.10, 620) * env(n_samples(0.10), 0.002, 18) * 0.55, 0.0)
    place(buf, sine(520, 0.14, 390) * env(n_samples(0.14), 0.002, 11) * 0.55, 0.11)
    place(buf, sine(1040, 0.04) * env(n_samples(0.04), 0.002, 60) * 0.12, 0.005)
    return loud(lp(buf, 6500), 0.14)


def armor(seed=34):
    buf = np.zeros(n_samples(0.45))
    clank = np.zeros(n_samples(0.20))
    place(clank, sine(1900, 0.20, 1750) * 0.5, 0.0)
    place(clank, sine(2830, 0.16, 2600) * 0.3, 0.0)
    place(buf, clank * env(n_samples(0.20), 0.0005, 22) * 0.5, 0.0)
    place(buf, hp(noise(0.012, seed), 2500) * env(n_samples(0.012), 0.0003, 150) * 0.4, 0.0)
    place(buf, sine(320, 0.16, 240) * env(n_samples(0.16), 0.002, 16) * 0.35, 0.02)
    return loud(room(buf), 0.15)


def keycard(seed=35):
    buf = np.zeros(n_samples(0.48))
    for i, f in enumerate((700, 880, 1175)):
        at = 0.02 + i * 0.085
        place(buf, square(f, 0.08, 0.3) * env(n_samples(0.08), 0.001, 28) * 0.32, at)
    return loud(lp(buf, 6200), 0.14)


# ---------------- 门禁 ----------------

def gate_open(seed=41):
    buf = np.zeros(n_samples(1.15))
    place(buf, sine(58, 1.0, 46) * env(n_samples(1.0), 0.05, 3.0) * 0.8, 0.0)
    place(buf, lp(noise(0.8, seed), 1000) * env(n_samples(0.8), 0.07, 3.4) * 0.38, 0.07)
    for at in (0.10, 0.26, 0.42, 0.58, 0.74):
        scrape = hp(noise(0.03, seed + int(at * 100)), 1800) * env(n_samples(0.03), 0.0003, 90) * 0.18
        place(buf, scrape, at)
    place(buf, sine(95, 0.24, 46) * env(n_samples(0.24), 0.001, 20) * 0.6, 0.88)
    return loud(room(buf), 0.16)


def gate_close(seed=43):
    buf = np.zeros(n_samples(1.0))
    swish = lp(noise(0.5, seed), 2500) * env(n_samples(0.5), 0.20, 6) * 0.35
    place(buf, swish, 0.0)
    place(buf, sine(70, 0.5, 40) * env(n_samples(0.5), 0.02, 5) * 0.7, 0.35)
    thud = lp(noise(0.20, seed + 1), 700) * env(n_samples(0.20), 0.0006, 18) * 0.9
    place(buf, thud, 0.62)
    place(buf, sine(60, 0.30, 34) * env(n_samples(0.30), 0.001, 12) * 0.8, 0.62)
    return loud(room(buf), 0.17)


def alarm(seed=42):
    buf = np.zeros(n_samples(1.05))
    for i, at in enumerate((0.0, 0.21, 0.42, 0.63)):
        f = 760 if i % 2 == 0 else 1010
        beep = square(f, 0.18, 0.28) * env(n_samples(0.18), 0.001, 10) * 0.45
        place(buf, beep, at)
        place(buf, hp(noise(0.006, seed + i * 7), 4000) * env(n_samples(0.006), 0.0002, 250) * 0.25, at)
    return loud(room(lp(buf, 7000), ((0.040, 0.28), (0.085, 0.16))), 0.16)


# ---------------- UI ----------------

def menu_move(seed=51):
    return loud(square(1250, 0.05, 0.22) * env(n_samples(0.05), 0.001, 55), 0.10)


def menu_ok(seed=52):
    buf = np.zeros(n_samples(0.26))
    place(buf, square(880, 0.06, 0.30) * env(n_samples(0.06), 0.001, 26) * 0.35, 0.0)
    place(buf, square(1320, 0.11, 0.26) * env(n_samples(0.11), 0.001, 18) * 0.32, 0.06)
    place(buf, hp(noise(0.005, seed), 5000) * env(n_samples(0.005), 0.0002, 300) * 0.2, 0.0)
    return loud(lp(buf, 7000), 0.12)


def menu_back(seed=53):
    buf = np.zeros(n_samples(0.22))
    place(buf, square(900, 0.06, 0.3) * env(n_samples(0.06), 0.001, 30) * 0.32, 0.0)
    place(buf, square(620, 0.10, 0.3) * env(n_samples(0.10), 0.001, 24) * 0.30, 0.06)
    return loud(lp(buf, 6000), 0.12)


SOUNDS = {
    "weapons/05_shotgun_bright": shotgun("bright", 21),
    "weapons/08_shotgun_pump": shotgun("pump", 27),
    "weapons/09_pistol_crisp": pistol_v3("crisp", 71),
    "weapons/10_pistol_thump": pistol_v3("thump", 73),
    "weapons/11_pistol_corridor": pistol_v3("corridor", 75),
    "weapons/12_pistol_doom": pistol_v3("doom", 77),
    "weapons/13_pistol_snub": pistol_v3("snub", 79),
    "pickup/01_evidence": evidence(),
    "pickup/02_ammo": ammo(),
    "pickup/03_health": health(),
    "pickup/04_armor": armor(),
    "pickup/05_keycard": keycard(),
    "gates/01_open": gate_open(),
    "gates/02_close": gate_close(),
    "gates/03_alarm": alarm(),
    "ui/01_move": menu_move(),
    "ui/02_ok": menu_ok(),
    "ui/03_back": menu_back(),
}

AUDITION = {
    "audition/weapons": [k for k in SOUNDS if k.startswith("weapons/")],
    "audition/pistols_v3": [k for k in SOUNDS if k.startswith("weapons/") and k.split("/")[1][:2] >= "09"],
    "audition/pickup": [k for k in SOUNDS if k.startswith("pickup/")],
    "audition/gates_ui": [k for k in SOUNDS if k.startswith(("gates/", "ui/"))],
}


def write_wav(path, data):
    import wave

    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def concat(names, gap=0.55):
    total = int(SR * 0.15) + sum(len(SOUNDS[n]) for n in names) + int(SR * gap * (len(names) - 1)) + int(SR * 0.2)
    buf = np.zeros(total)
    at = int(SR * 0.15)
    for n in names:
        place(buf, SOUNDS[n], at / SR)
        at += len(SOUNDS[n]) + int(SR * gap)
    return np.clip(buf, -1, 1)


if __name__ == "__main__":
    for name, data in SOUNDS.items():
        write_wav(os.path.join(OUT, name + ".wav"), data)
        print(f"{name:28s} {len(data) / SR:5.2f}s  peak={np.max(np.abs(data)):.2f}")
    for name, names in AUDITION.items():
        write_wav(os.path.join(OUT, name + ".wav"), concat(names))
    all_names = [n for names in AUDITION.values() for n in names]
    write_wav(os.path.join(OUT, "audition/all.wav"), concat(all_names, gap=0.6))
    print(f"共 {len(SOUNDS)} 个单音 + {len(AUDITION) + 1} 个连播")
