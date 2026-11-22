# tools/

全部脚本用标准库为主，只有生成图片的脚本需要 Pillow
（`python -m pip install pillow`）。`fz_ctl.py check` 不需要 Pillow。

## 构建与交付

| 脚本 | 作用 |
|---|---|
| `build.py` | 打包 `game/` → `build/fanzha-demo.pk3`；缺地图/字体会自动生成 |
| `make_dist.py` | 出交付包 `dist/fanzha-demo-v0.1{.zip,/}`（会先重跑地图与打包） |
| `doctor.py` | 环境自检：Python/Pillow/vendor/配置绑定/内容文件，缺什么给什么命令 |
| `fetch_vendor.py` | `status` 校验 vendor 完整性；`import` 从本地官方文件导入引擎/IWAD/字体（只校验本次导入项） |
| `publish_api.py` | 备用发布通道：`github.com` 直连不通、但 `api.github.com` 可达时，用 `gh api` 逐 blob 上传当前 HEAD |

## 内容生成（源即生成器，产物不入库）

| 脚本 | 产物 |
|---|---|
| `gen_sfx.py` | `sfx_preview/` 预听包（武器 / 拾取 / 门禁 / 菜单），纯 numpy 合成，无外部素材；选定后手工拷进 `game/sounds/` |
| `gen_maps.py` | `game/maps/FZ01-03.wad`（vanilla 二进制 PWAD），并对照 IWAD 校验纹理名 |
| `gen_font.py` | `game/fonts/fzfont*`（305 字 × 8 色预着色图集） |
| `gen_menu_patches.py` | `game/graphics/M_*.png`（中文主菜单按钮） |
| `gen_panel.py` | `game/graphics/FZPANEL.png`（HUD 底栏 320×48） |
| `gen_titlepic.py` | `game/graphics/TITLEPIC.png` |
| `gen_intermission.py` | `game/graphics/FZBKGRD1-3.png`（章节卷宗背景，预留） |

## 检查

| 脚本 | 作用 |
|---|---|
| `ci_static.py` | CI 用的静态检查：include 存在性、MAPINFO 地图链、doomednums 类、字体引用、run.bat 纯 ASCII、绝对路径泄漏 |
| `check_charset.py` | 校对字体字符集与脚本里出现的汉字是否一致 |

## 测试（两套，分工明确）

| 脚本 | 定位 |
|---|---|
| `fz_ctl.py` | **主回归入口**。构建 → `-errorlog` 编译预检 → 启动 → 引擎内路线机器人走位 → 真实键鼠处理门/过场 → 截图与日志断言。场景：`check/boot/tour/gate/menu/door/exit/esc/full` |
| `winbot.py` | 底层驱动库：SendInput 扫描码注入、按 PID 锁窗口、DPI 感知截图 |
| `test_smoke.py` | **legacy**：早期像素级冒烟（引擎内截图 + 逐色比对）。硬编码 26s 等待、依赖已不存在的 `t.cfg`，只在新机首次验证渲染时用；日常回归请用 `fz_ctl.py` |
| `udmf_bisect.py` | 历史排查脚本（UDMF 崩溃二分定位），保留作档案，勿用于新流程 |
| `testhooks/` | 引擎内测试钩子（bot / hud / menu 三套），与正式内容隔离，只进测试 PK3 |

## 常用序列

```powershell
python tools\doctor.py            # 环境自检
python tools\fetch_vendor.py status
python tools\build.py
run.bat
python tools\fz_ctl.py check      # 改脚本后必跑
python tools\fz_ctl.py tour       # 第一章回归（预期 9/9）
python tools\make_dist.py         # 出包
```
