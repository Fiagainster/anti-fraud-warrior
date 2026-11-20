# 素材来源与授权登记

每个外部素材 / AI 参与文件都登记一行。自制素材也请注明"自制"。
发布前由负责人复核。

| 文件/目录 | 类型 | 来源 | 作者/工具 | 许可证 | AI 参与 | 备注 |
|---|---|---|---|---|---|---|
| `vendor/uzdoom-5.0.3/*` | 引擎 | github.com/UZDoom/UZDoom | UZDoom Team | GPL-3.0 | 无 | 未修改源码 |
| `vendor/freedoom-0.13.0/freedoom1.wad` | IWAD/贴图/音效 | freedoom.github.io | Freedoom Team | BSD-3-Clause | 无 | 保留 COPYING/CREDITS |
| `vendor/fusion-pixel-2026.11.10/*.ttf` | 字体 | github.com/TakWolf/fusion-pixel-font | TakWolf | OFL-1.1 | 无 | 预着色图集由 gen_font.py 生成 |
| `tools/blender/emblem_render.py` | 脚本 | 自制 | 本项目 | GPL-3.0 | 无 | Blender 无头渲染示例 |
| `game/graphics/*.png` | UI 图 | 自制（脚本生成） | 本项目 | CC BY-NC-SA 4.0* | 无 | gen_titlepic/gen_panel 等生成 |
| `game/zscript/*`, `tools/*` | 代码 | 自制 | 本项目 | GPL-3.0 | 无 | |
| `docs/剧情.md` 等 | 文案 | 自制 | 本项目 | CC BY-NC-SA 4.0* | 无 | 发布前需宣传口径审校 |

\* 内容授权待单位确认，确认后请更新此表与根目录 `LICENSE`。

## 模板（新增素材时复制）

```
| 文件名 | 类型 | 来源 | 作者/工具 | 许可证 | AI 参与 | 备注 |
| assets_src/blender/enemy_scammer.blend | 3D 源文件 | 自制 | 张三 | CC BY-NC-SA 4.0 | 无 | |
| assets_src/textures/wall_office.png | 贴图 | AI 辅助 | SDXL / 2026-11-20 | 自制 | 是（提示词见下） | 人工修整 60% |
```

AI 登记需额外写明：模型名、日期、提示词摘要、人工修改内容。
