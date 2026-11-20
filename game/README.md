# game/ — PK3 工程

这是「反诈战士」的主工程，最终打包成 `build/fanzha-demo.pk3`。

| 目录 | 内容 | 是否入库 |
|---|---|---|
| `maps/` | **生成物**：vanilla 二进制 PWAD（FZ01-03）。源是 `tools/gen_maps.py`，不要手改 | 否 |
| `zscript/` | ZScript 生产脚本，只 include `fz_defs` / `fz_gates` / `fz_hud` 三个 | 是 |
| `fonts/` | **生成物**：Fusion Pixel 12px 的 8 套预着色图集，由 `gen_font.py` 生成 | 否 |
| `graphics/` | HUD 底板、标题图、中文主菜单补丁（`M_*.png`） | 是 |
| `language/` | LANGUAGE 覆盖：拾取物与门的提示文案 | 是 |
| `mapinfo/` | MAPINFO：`statusbarclass`、`eventhandlers`、`doomednums`、章节链 | 是 |
| `menudef/` | 目前只有说明。主菜单靠 `graphics/M_*.png` 覆盖原版补丁，不打进 PK3 | 是 |
| `acs/` | 预留，当前无 ACS 脚本 | — |
| `sprites/` `sounds/` | 预留，当前敌人/武器仍用 IWAD 占位素材 | — |

打包命令：

```powershell
python tools\build.py      # -> build/fanzha-demo.pk3（缺地图/字体会自动生成）
```

地图 WAD 不进 PK3，而是作为松散文件放在 `build/maps/`：引擎 5.0.3 对 PK3 内
`maps/*.wad` 的全名查找不可靠。

硬约束（改动前先看这条）：地图必须是 **vanilla 二进制格式**，UDMF 在 UZDoom
5.0.3 会崩；纹理名必须 NUL 填充且存在于 IWAD；自定义 ednum 必须 < 32768。
详细踩坑见根目录 README 的「已踩过的坑」。
