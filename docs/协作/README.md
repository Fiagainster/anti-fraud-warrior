# 团队协作手册 · 入口

欢迎加入《反诈战士》。这是一款基于 UZDoom 的中文反诈 FPS，目标受众是学生与社区群众。
**先读这一页，再按你的角色进对应手册。**

## 30 分钟上手

```powershell
git clone https://github.com/Fiagainster/anti-fraud-warrior.git
cd 反诈战士
git lfs install                 # 如需拉取美术/音频源文件

python tools\doctor.py          # 环境自检（缺什么会告诉你）
# 首次需要导入引擎/IWAD/字体（大文件不入库）：
python tools\fetch_vendor.py import --uzdoom <UZDoom目录> --freedoom <freedoom1.wad> --font <字体ttf>

python tools\build.py           # 打包 game/ -> build/fanzha-demo.pk3
run.bat                         # 游玩（窗口 1280x720）
python tools\fz_ctl.py check    # 脚本编译预检（改代码后必跑）
python tools\fz_ctl.py tour     # 第一章自动化回归（预期 9/9）
```

## 角色手册

| 角色 | 手册 | 你主要交付什么 |
|---|---|---|
| 美术 | [角色-美术.md](角色-美术.md) | 手工像素画（Pixelorama）为主：道具图标、UI、贴图；敌人 8 方向 sprite 走 Blender |
| 关卡 / 地图 | [角色-地图.md](角色-地图.md) | 地图生成器参数（当前）；手工 WAD 仅新开章时用 |
| 程序 | [角色-程序.md](角色-程序.md) | ZScript 系统、HUD、菜单、工具链 |
| 剧情 / 文案 | [角色-剧情文案.md](角色-剧情文案.md) | 章节剧情、抉择文案、识破知识点、卷宗 |
| 音频 | [角色-音频.md](角色-音频.md) | 音效、BGM、配音 |
| 测试 / 发布 | [构建与验收.md](构建与验收.md) | 回归、打包、发布检查 |

公共规范（所有人都要读）：

- [仓库与分支规范.md](仓库与分支规范.md)
- [资源与命名规范.md](资源与命名规范.md)
- [素材授权与AI合规.md](素材授权与AI合规.md)
- [../架构与扩展.md](../架构与扩展.md)（系统结构 + 新增章节步骤）

## 项目分层（一句话版）

```
引擎/底座   vendor/      UZDoom + Freedoom + 字体（不入库，按清单导入）
内容源码    game/        ZScript / MAPINFO / 语言表 / 字体图集 / 图形
源素材      assets_src/  Pixelorama / Blender 源文件、贴图源、音频源（LFS）
工具链      tools/       地图生成、字体生成、打包、测试、发布
文档        docs/        方案、剧情、验收、协作手册
产物        build/ dist/ 构建与交付（不入库）
```

## 网络

若 `github.com` 直连不稳定：给 git 配代理
（`git config --global http.proxy http://127.0.0.1:<端口>`），或改用 `gh`（走 `api.github.com`）。下载引擎/IWAD 同理。

本机实测可用的写法是**只对这一次命令挂代理**，不改全局配置：

```powershell
git -c http.proxy=http://127.0.0.1:7893 push
```

两个坑：一是环境里可能有别的代理变量（`http_proxy`/`https_proxy`）指着另一个端口，
报错会是 `CONNECT tunnel failed, response 502`，那不是"网断了"而是走错了口；
二是 `github.com` 和 `api.github.com` 的封锁策略不一定一致——出现过
`api.github.com` 通、`github.com` 不通的情况，那时用 `tools/publish_api.py` 走 `gh api`。
先分头测一遍再决定用哪条：

```powershell
curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 -x http://127.0.0.1:7893 https://github.com/
curl -s -o /dev/null -w "%{http_code}\n" --max-time 12 https://api.github.com/
```

两条都 200 才能走 git push；只有后一条通就走 `gh`。`000` 是没通。

## 沟通与节奏

- 任务用 Issue 描述（模板见 `.github/ISSUE_TEMPLATE/`），PR 关联 Issue。
- 每周一次 30 分钟同步：本周交付、阻塞、需要谁配合。
- 任何"看起来能跑但没过 `fz_ctl check`"的代码不合并。
- 剧情/文案涉及公安宣传口径与 96110，发布前需按 `素材授权与AI合规.md` 走审校。
