# 素材来源与授权登记

每个外部素材 / AI 参与文件都登记一行。自制素材也请注明"自制"。
发布前由负责人复核。

| 文件/目录 | 类型 | 来源 | 作者/工具 | 许可证 | AI 参与 | 备注 |
|---|---|---|---|---|---|---|
| `vendor/uzdoom-5.0.3/*` | 引擎 | github.com/UZDoom/UZDoom | UZDoom Team | GPL-3.0 | 无 | 未修改源码 |
| `vendor/freedoom-0.13.0/freedoom1.wad` | IWAD/贴图/音效 | freedoom.github.io | Freedoom Team | BSD-3-Clause | 无 | 保留 COPYING/CREDITS |
| `vendor/fusion-pixel-2026.11.10/*.ttf` | 字体 | github.com/TakWolf/fusion-pixel-font | TakWolf | OFL-1.1 | 无 | 预着色图集由 gen_font.py 生成 |
| `tools/blender/emblem_render.py` | 脚本 | 自制 | 本项目 | GPL-3.0 | 无 | Blender 无头渲染示例 |
| `game/graphics/*.png` | UI 图 | 自制（脚本生成） | 本项目 | CC BY-NC-SA 4.0* | 无 | gen_title/gen_panel 等生成 |
| `game/zscript/*`, `tools/*` | 代码 | 自制 | 本项目 | GPL-3.0 | 无 | |
| `game/music/title.ogg` | 音乐 | 自制（AI 辅助） | DSH Agent + anyaudio 0.4.2 / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 70 BPM D 小调，27.4s 整曲循环 |
| `game/music/ch1.ogg` | 音乐 | 自制（AI 辅助） | DSH Agent + anyaudio 0.4.2 / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 128 BPM A 小调，8 小节前奏 + 32 小节循环 |
| `game/music/ch2.ogg` | 音乐 | 自制（AI 辅助） | DSH Agent + anyaudio 0.4.2 / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 92 BPM E 小调，A16 + B16 |
| `game/music/ch3.ogg` | 音乐 | 自制（AI 辅助） | DSH Agent + anyaudio 0.4.2 / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 110 BPM C 小调，16 小节慢起 + 32 小节进行 |
| `game/music/boss.ogg` | 音乐 | 自制（AI 辅助） | DSH Agent + anyaudio 0.4.2 / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 140 BPM F 小调，8 小节进场 + 16 小节循环 |
| `art/title/cover.jpg`、`art/title/ending.jpg` | 插画源 | 自制（AI 生成） | Ark Seedream 5.0 `doubao-seedream-5-0-260128` / 2026-11-23 | CC BY-NC-SA 4.0* | 是 | 标题与终章插画底稿，提示词见下 |
| `game/graphics/TITLEPIC.png`、`FZENDPIC.png` | 标题 / 终章图 | 上述插画 + 脚本叠字 | 同左 + `tools/gen_title.py` | CC BY-NC-SA 4.0* | 是 | 中文标题、压暗、降色数由脚本完成 |
| `game/graphics/FZCRED1.png`、`FZCRED2.png`、`FZCASTBG.png` | 轮播页 / 巡礼底图 | 自制（纯脚本绘制） | 本项目 | CC BY-NC-SA 4.0* | 无 | `tools/gen_title.py` 生成，无 AI 插画 |
| `game/graphics/FZSELECT.png` | 难度菜单光标 | 自制（纯脚本绘制） | 本项目 | CC BY-NC-SA 4.0* | 无 | `tools/gen_menu_cursor.py` 画放大镜，16×16 放大 2 倍 |
| `docs/剧情.md` 等 | 文案 | 自制 | 本项目 | CC BY-NC-SA 4.0* | 无 | 发布前需宣传口径审校 |

\* 内容授权待单位确认，确认后请更新此表与根目录 `LICENSE`。

### 标题插画的 AI 登记

| 项 | 内容 |
|---|---|
| 模型 / 工具 | 火山方舟 Ark，Seedream 5.0（`doubao-seedream-5-0-260128`），2560×1440 |
| 日期 | 2026-11-23 |
| 提示词摘要 | 封面（第二版，采用）："像素风厚涂，深蓝黑数据空间，反诈特勤队队员背影（深色战术制服、反光条、臂章），面对一整面悬浮聊天窗口墙——刷单群/红包/转账/二维码的抽象图形，部分窗口伸出黑色的手与剪影，地面发光网格与数据碎片，冷蓝主调、青绿与品红点缀，上方留白给标题，不要文字/logo"；终章（第二版）："数据空间崩塌，聊天窗口碎裂成像素，六道妖魔剪影消散，三枚证据碎片聚拢，深蓝过渡到破晓青，上下留暗部给文字" |
| 人工修改 | 裁切为 16:9、左上/底部压暗、降色数到 56 色保住像素块面；中文标题、章节名、"按 ENTER"、96110、操作提示全部由 `tools/gen_title.py` 用 Fusion Pixel 字体叠加，未使用模型生成文字 |

### 音乐素材的 AI 登记

| 项 | 内容 |
|---|---|
| 模型 / 工具 | DeepSeek Harness Agent 编谱；anyaudio 0.4.2 用本地 SoundFont（GeneralUser GS，GeneralUser GS License v2.0）渲染成音频；ffmpeg 做循环折叠后的 OGG 封装 |
| 日期 | 2026-11-23 |
| 提示词摘要 | "按 docs/音频设计.md §4 的音乐 brief 做五首：标题+三章+Boss，工业暗黑底子、中国乐器点缀、能无缝循环、不抢枪声" |
| 人工修改 | 调式、BPM、配器、段落结构、循环点由人根据 brief 指定；逐轨电平按角色目标标定；接缝不干净的曲子用 30 ms 交叉淡化处理 |
| 版权说明 | 旋律、和声、编排全部为本次原创，未使用任何第三方采样或既有曲目的旋律；音源只在本机渲染，不随包分发 |

## 模板（新增素材时复制）

```
| 文件名 | 类型 | 来源 | 作者/工具 | 许可证 | AI 参与 | 备注 |
| assets_src/blender/enemy_scammer.blend | 3D 源文件 | 自制 | 张三 | CC BY-NC-SA 4.0 | 无 | |
| assets_src/textures/wall_office.png | 贴图 | AI 辅助 | SDXL / 2026-11-20 | 自制 | 是（提示词见下） | 人工修整 60% |
```

AI 登记需额外写明：模型名、日期、提示词摘要、人工修改内容。

