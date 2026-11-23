# art/ — 自制美术母版

这个目录放**画出来的东西**，不放引擎能直接读的东西。引擎读 `game/`。

## 目录

```
art/source/<精灵名>/<帧>.jpg      AI 草稿（2K）。有它才能重跑管线、复查某一帧为什么长这样
art/sprites/<精灵名>/<帧>.png     64×64 / 64×72 母版（RGBA，脚踩底边，已量化到家族色板）
game/sprites/<精灵名><帧>0.png    引擎文件：4 字符名 + 帧字母 + 旋转号 0
```

`art/source` 是生成输入，`art/sprites` 是生成产物，`game/sprites` 是把产物摆进引擎。
三者同源，任何一层都能重来。

`art/source/` 里的 2K 草稿**不入库**（单张 150–250KB，`.gitignore` 里排除），母版
`art/sprites/` 几 KB 一张、正常入库——它是交付物，不是构建产物。

## 当前已有

6 个怪物位已全部换成自研图，共 **78 张**（6 × 13 帧）：

| 精灵名 | 家族 | 怪物 | 替换的原版类 | 画布 | 帧 |
|---|---|---|---|---|---|
| `FZFR` | A 受害者/傀儡 | 刷手 | `ZombieMan` | 64×64 | A–M |
| `FZRN` | A 变体（土黄） | 跑分马仔 | `ShotgunGuy` | 64×64 | A–M |
| `FZSC` | B 灰产从业者 | 黄牛 | `DoomImp` | 64×72 | A–M |
| `FZBK` | B 变体（褐） | 黑市掮客 | `Demon` | 64×72 | A–M |
| `FZCP` | C 冒充权威 | 假警察 | `Cacodemon` | 64×64 | A–M |
| `FZCH` | C 变体（黑红） | 影子会长（Boss） | `BaronOfHell` | 64×64，`Scale 1.7` | A–M |

三个变体由 `生图/pixelpipe/variant.py` 从原型配色生成（描边、白票摞、糊脸、警徽、
手机屏都保留），类定义在 `game/zscript/fz_actors.zs`，全部 `replaces` 原版类，
所以地图里的 3004/3001/3002/3003/3005 不用改。

### 武器 / 弹道 / 道具（原位替换，不改任何脚本）

这些不走新精灵名，而是**直接覆盖原版那张贴图**，所以引擎里的位置、大小、HUD 对位
全不变。每条都按原版的画布尺寸和内容框落位：

| 原版 lump | 换成 | 内容 |
|---|---|---|
| `PUFF` A–D | 命中纸屑 | 纸片爆开，逐帧变大 |
| `BAL1` A–E | 飞出的票摞 | 黄牛扔的票 |
| `BAL2` A–E | 诈骗短信 | 绿色屏幕矩形 |
| `BAL7` A–E（含 1–8 八方向） | 假公章冲击波 | 红章逐帧放大、炸开 |
| `CLIP` / `SHEL` | 弹夹 / 霰弹 | 7×12 / 14×10，沿用原版画布 |
| `STIM` / `MEDI` | 警惕值药瓶 / 反诈手册 | 19×10 / 29×20 |
| `ARM1` / `BPAK` / `BKEY` | 防骗盾 / 证据箱 / 主谋证据 | 后两个就是自定义 actor 借用的图 |
| `PISG` A–E / `SHTG` A–D | ~~警示枪 / 封条枪~~ | **已回退原版**，见下 |

> **手持武器没做成**（2026-11-22 回退）：`art/sprites/props/FZPistol/` 与
> `FZShotgun/` 是那轮 AI 草稿（56×68 的枪的侧视图，没有手、没有透视），
> 贴到屏幕底部会读成"枪口朝左"，不是能用的成品，别拿它们当参考。
> 现在 `game/sprites/` 里没有 `PISG*` / `SHTG*`，玩家手上直接用 Freedoom 原版帧。
> 重画时先跑 `python tools\weapon_ref.py` 看原版每帧的真实占位（画布各不相同），
> 规则见 `docs/角色美术设计.md` §4.2 与 `docs/下一步.md` §5.1。

### 贴图（墙面 / 地面 / 天花 / 天空）

地图引用的是 Freedoom 名字，所以同样是**覆盖同名 lump**，尺寸严格照 Freedoom 的
`textures.cfg`（1 像素 = 1 世界单位，改尺寸砖块就会变形），并且做了接缝修正
（`tools/gen_textures.py check` 实测接缝 0.0）：

| lump | 内容 | 尺寸 |
|---|---|---|
| `STARTAN2` / `COMPSPAN` | 第一章 主墙（冷蓝灰钢板）/ 次墙（设备机架条） | 128×128 / 32×128 |
| `GRAY5` / `METAL1` | 第二章 主墙（水泥砌块）/ 次墙（锈蚀瓦楞板） | 64×128 |
| `STONE2` | 第三章 次墙（冷灰石砌） | 128×128 |
| `DOORRED` / `DOORTRAK` / `SW1EXIT` | 审判门面 / 门轨 / 出口开关 | 8×128 / 8×128 / 32×72 |
| `FLOOR4_8` `FLOOR5_3` | 一章金属地板 / 二章水泥地 | 64×64 |
| `CEIL1_2` `CEIL3_4` `CEIL3_1` | 各章天花 | 64×64 |
| `SKY1` | 雨夜城市天际线 | 256×128 |

`DOORRED` / `DOORTRAK` / `COMPSPAN` / `SW1EXIT` 这四条是**程序化绘制**的：8 像素宽
的窄条和交互开关经 AI 缩小后会糊成一团，手写更可靠。

**没有替换的两处**：`PISF` / `SHTF`（枪口焰）——生成的火焰不成形，退回原版，
宁可保留原图也不要贴一张错的。墙面/地面/天空 18 槽里只有 `FZW3WALL` / `FZF3FLR`
两张占位已接进，其余仍是 Freedoom。

## 重新生成

生成端在 `D:\Project\生图\pixelpipe\`：

```powershell
cd D:\Project\生图\pixelpipe
D:\System\Python\python.exe run.py A          # 出图（已存在则复用草稿）
D:\System\Python\python.exe review.py A       # 联系表 + GIF + 逐帧验收表
D:\System\Python\python.exe overview.py       # 三家族一览
```

改单帧：`run.py A --only K --force`，然后 `review.py A` 复查。

## 规矩（`gen_sprites.py check` 会挡住违规）

1. 脚踩底边：画布最后一行必须有像素，否则怪物浮空。
2. 左右居中：引擎默认偏移是"水平居中、底边落地"。
3. 帧字母就是文件名，末尾的 `0` 是旋转号（单面朝向玩家），别改成 1。
4. 不用抗锯齿、不用半透明：alpha 只有 0 和 255。
5. 每个家族一套色板（≤10 色），六只怪才像一套。
