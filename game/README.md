# game/ — PK3 工程

这是「反诈战士」的主工程，最终打包成 `build/fanzha-demo.pk3`。

| 目录 | 内容 | 是否入库 |
|---|---|---|
| `maps/` | **生成物**：UDMF 文本装进 WAD lump（FZ01-03，命名空间 `ZDoomTranslated`）。源是 `tools/gen_maps.py`，不要手改 | 否 |
| `zscript/` | ZScript 生产脚本，include `fz_defs` / `fz_weapons` / `fz_gates` / `fz_hud` / `fz_actors` 五个 | 是 |
| `fonts/` | **生成物**：Fusion Pixel 12px 的 8 套预着色图集，由 `gen_font.py` 生成 | 否 |
| `graphics/` | HUD 底板、标题图、中文主菜单补丁（`M_*.png`） | 是 |
| `language/` | LANGUAGE 覆盖：拾取物与门的提示文案 | 是 |
| `mapinfo/` | MAPINFO：`statusbarclass`、`eventhandlers`、`doomednums`、章节链 | 是 |
| `menudef/` | 目前只有说明。主菜单靠 `graphics/M_*.png` 覆盖原版补丁，不打进 PK3 | 是 |
| `acs/` | 预留，当前无 ACS 脚本 | — |
| `sprites/` `sounds/` | 敌人与拾取物的自制精灵；玩家手持武器不覆盖（`PISG*` / `SHTG*` 走 IWAD），地面拾取 `PISTA0` / `SHOTA0` 是自制版。`sounds/` 已有 12 个自制音效（武器 2、拾取 4、门禁/警报 3、菜单 3） | — |
| `sndinfo/` | SNDINFO：逻辑音名 → `sounds/*.wav` 的映射；并覆盖 `menu/cursor` 等引擎菜单音。打包成 PK3 根目录的 `SNDINFO` | 是 |

打包命令：

```powershell
python tools\build.py      # -> build/fanzha-demo.pk3（缺地图/字体会自动生成）
```

地图 WAD 不进 PK3，而是作为松散文件放在 `build/maps/`：引擎 5.0.3 对 PK3 内
`maps/*.wad` 的全名查找不可靠。

硬约束（改动前先看这条）：地图是 **UDMF 文本装进 WAD lump**（`FZ01` 空标记 +
`TEXTMAP` + `ENDMAP`），命名空间固定 `ZDoomTranslated`——引擎靠它把 UDMF 编号
翻译成 Doom 内部号，写成 `zdoom` 命名空间会让门的 special 全部对不上。
别把地图改成 PK3 里的散装 `maps/xxx.map`：5.0.3 上那条路径启动即崩。
纹理名必须 NUL 填充且存在于 IWAD；自定义 ednum 必须 < 32768。
详细踩坑见根目录 README 的「已踩过的坑」。
