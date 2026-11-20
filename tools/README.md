# tools/

| 脚本 | 作用 |
|---|---|
| `gen_font.py` | 从 Fusion Pixel 12px TTF 生成 GZDoom Unicode PNG 字体（305 字 × 8 色） |
| `gen_menu_patches.py` | 生成中文主菜单补丁 `M_DOOM`、`M_NGAME` 等 |
| `gen_panel.py` | 生成 HUD 底栏面板 `FZPANEL.png`（320×48） |
| `build.py` | 打包 `game/` 为 `build/fanzha-demo.pk3` |
| `test_smoke.py` | **自动化冒烟测试**（发布前必跑） |
| `testhooks/` | 测试专用钩子（HUD 截图 / 强制菜单），与正式内容隔离 |

## 自动化测试

```powershell
python tools\test_smoke.py
```

流程：构建游戏包 → 构建两个测试钩子包（`fz-testhooks-hud.pk3` / `fz-testhooks-menu.pk3`）→ 两次确定性引擎运行 → 引擎自动截图 → 校验日志（无 ZScript 错误、字体加载、地图加载）→ 逐色比对预着色字形像素 → 输出 PASS/FAIL 汇总，非零退出码表示失败。

设计要点：

- 截图走引擎内部 framebuffer（`enablescriptscreenshot` + ZScript `LevelLocals.MakeScreenShot`），不受窗口/DPI/截屏 API 影响，像素断言是确定性的。
- Run A 在 `WorldTick` t=90 截 HUD（`-nomonsters` 保证世界稳定）。
- Run B 锁 `vid_maxfps 35`，UiTick 每帧无条件 `Menu.SetMenu('MainMenu')`（标题屏阶段为无害 no-op），UI tick 900（≈26s，肯定已过地图加载）时截图。
- 断言颜色来自 `gen_font.py` / `gen_menu_patches.py` 烘焙的精确 RGB，容差 ±40。

## 资产再生成

```powershell
python tools\gen_font.py          # 改了 CHARSET 后重新生成字体
python tools\gen_menu_patches.py  # 改了菜单文案后重新生成补丁
python tools\gen_panel.py         # 改了 HUD 布局后重新生成面板
python tools\build.py             # 打包
python tools\test_smoke.py        # 验证
```
