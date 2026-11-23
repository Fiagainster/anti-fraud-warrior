# 配乐源文件（乐谱 JSON）

`game/music/*.ogg` 的**源头**。这里放的是音符级乐谱，不是音频：每个文件描述
「哪条轨、什么音色、第几秒起、持续多久、什么音高、多大力度的音符」，
渲染器把它变成真实乐器采样。

| 文件 | 曲目 | 渲染产物 |
|---|---|---|
| `title.json` | 标题 / 选章 | `game/music/title.ogg` |
| `ch1.json` | 第一章 刷单深渊 | `game/music/ch1.ogg` |
| `ch2.json` | 第二章 装备黑市 | `game/music/ch2.ogg` |
| `ch3.json` | 第三章 警服幻影 | `game/music/ch3.ogg` |
| `boss.json` | 主席战 | `game/music/boss.ogg` |
| `manifest.json` | — | 每首的 BPM、循环点（小节/秒/采样）、分轨清单 |

## 格式

```json
{
  "title": "FZ ch1 刷单深渊",
  "tracks": [
    { "name": "固定音型", "instrument": "pick-bass", "role": "bass", "gainDb": 4.36,
      "pan": 0, "reverb": 0.25, "notes": [[0.0, 0.19, "A1", 100], [0.0, 0.19, "A2", 70]] }
  ]
}
```

- 音符是 `[起始秒, 时值秒, 音高(或音高数组), 力度1–127]`；
- 音高可写音名（`A1`、`F#4`、`Bb2`）或 MIDI 号；
- `drums: true` 的轨走鼓组，音高写鼓件名（`kick` / `snare` / `hat-closed` …）；
- `role` 是声部角色（bass/lead/pad/bell…），渲染时按角色目标电平自动标定 `gainDb`。

## 怎么重新渲染

渲染链**不在本仓库**，在配乐工作区 `D:\Project\音乐美术生成\music\`：

```
compose.py       编曲 → 本目录的 *.json
calibrate.py     逐轨单独渲染测固有电平 → 按 role 目标反推 gainDb
build_music.py   渲染 + 环境层 + 循环折叠 + −16 LUFS 归一 + OGG q5 封装（写 LOOP_START/LOOP_END）
```

它依赖两个外部件：DSH 的 `anyaudio` 插件（本地 SoundFont 渲染）与 ffmpeg
（imageio-ffmpeg 的静态二进制即可）。改完乐谱后把 `build_music.py` 产出的
`out/*.ogg` 拷回 `game/music/`，再 `python tools\build.py`。

格式细则与每首的编排说明见 `docs/音频设计.md` §4 与 §4.1。
