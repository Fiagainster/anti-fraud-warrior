# 反诈战士

基于 Doom 引擎（UZDoom 5.0.3 + Freedoom）的公安反诈宣传游戏。
**当前状态：三章演示可玩，已出交付包** —— 刷单深渊 / 装备黑市 / 警服幻影。

## 交付包

```
dist/fanzha-demo-v0.1.zip        ← 发给别人玩这个（37 MB）
dist/fanzha-demo-v0.1/           ← 解压即玩的目录
  run.bat                        ← 双击启动
  README.txt                     ← 玩家说明（操作/流程/许可）
```

包内自带引擎、IWAD、地图、配置与许可文件，**不依赖本仓库**。
打包命令：`python tools\make_dist.py`（会先重生成地图与 PK3）。

## 团队协作（开发入口）

新同学从 **[docs/协作/README.md](docs/协作/README.md)** 开始：

```powershell
python tools\doctor.py                 # 环境自检（缺什么会告诉你）
python toolsetch_vendor.py status    # 校验引擎/IWAD/字体（大文件不入库）
python toolsuild.py                  # 缺地图/字体会自动生成
python toolsz_ctl.py check           # 编译预检
```

- 角色手册：美术 / 地图 / 程序 / 剧情 / 音频（`docs/协作/角色-*.md`）
- 仓库与分支、资源命名、构建验收、授权与 AI 合规：`docs/协作/`
- 系统结构与"新增一章要动哪些文件"：`docs/架构与扩展.md`

## 本仓库内一键游玩

```powershell
python tools\build.py   # 打包（已预构建，可直接跳过）
run.bat                 # 双击启动
```

游戏内：走近闪烁的**数据终端**自动弹出抉择菜单（↑↓ 选择，回车确认），
集齐 3 件证据链（HUD 右下出现红字「红卡」）后到审判门按 E：门升起并保持敞
开，走进去击败幕后主谋，走到出口（绿色开关墙前的小间）即结算本章。
出口后是标准的关卡结算页（击杀/物品/时间），**按回车进入下一章**。
**ESC 需要按住约 2 秒**才能稳定打开主菜单（UZDoom 的按键重复机制会吞短按，
已实测确认；配置文件里已写入 `Escape=menu_main`）。

## 三章内容

| 章 | 骗术 | 抉择点 | Boss |
|---|---|---|---|
| 第一章：刷单深渊 | 刷单返利 | 垫付 299？共享屏幕？ | 群主"闪电哥" |
| 第二章：装备黑市 | 游戏交易诈骗 | 微信直转？钓鱼链接？ | 黑市商人"暗影" |
| 第三章：警服幻影 | 冒充公检法 | 安全账户？协查 APP？ | 影子会长 |

选错抉择会扣警惕值并引来妖魔伏击，选对得防骗盾 +10 与证据 +1。
证据链（红卡）到手后 HUD 右下会显示红字「红卡」；审判门需要它才能打开。
章节衔接走引擎标准流程：出口 → 结算页 → 回车 → 下一章（第三章结束回标题）。
抉择菜单中**正确选项固定为第一项**（教学演示，单按回车即正确作答）。

## 自动化接管（我自己玩 + 验证用的回路）

```powershell
python tools\fz_ctl.py check    # 只做脚本编译预检（无窗口、无弹窗）
python tools\fz_ctl.py tour     # 第一章全程：走位/证据/两道抉择门
python tools\fz_ctl.py gate     # 只到第一道终端并作答
python tools\fz_ctl.py menu     # 只展示抉择菜单（不作答，拍排版）
python tools\fz_ctl.py esc      # ESC 主菜单开合（长按 2 秒）
python tools\fz_ctl.py full     # 三章马拉松（战斗/过场/切换）
```

组成：
- `tools/fz_ctl.py` —— 编排：构建 → 预检 → 启动 → 驱动 → 截图 → 断言
- `tools/winbot.py` —— 真实键鼠注入（SendInput 扫描码）+ 窗口截图（DPI 感知，
  按 **进程 PID** 锁定本脚本启动的窗口，绝不误操作玩家自己的窗口）
- `tools/testhooks/bot/` —— 引擎内路线机器人（真实物理走位、卡点/实体探针、
  菜单内自动作答 cvar）+ 引擎截图

预检用 `-errorlog` 的 batchrun 模式：脚本/MAPINFO 编译错误直接打印并退出
（返回码 1337），**不会弹出阻塞式错误窗口**。最近一次 `tour` 为 **9/9 通过**。

## 截图

![第一章 HUD](docs/images/chapter1-hud.png)

![抉择菜单](docs/images/chapter1-gate.png)

## 目录

| 目录 | 用途 |
|---|---|
| `game/` | PK3 工程：ZScript、原生格式地图、字体、图形、语言表 |
| `config/` | 随包配置（绑定/分辨率/语言），**源文件**，勿手写精简版 |
| `assets_src/` | 美术/音频/手工地图**源文件**（LFS），含 CREDITS 登记 |
| `tools/` | 地图/字体生成、构建、打包、测试、环境自检 |
| `tools/testhooks/` | 自动化测试钩子（与正式内容隔离） |
| `vendor/` | UZDoom/Freedoom/字体；只提交 `manifest.json`，用 `fetch_vendor.py` 导入 |
| `source/` | 参考源码：1997 DOOM、UZDoom trunk、Freedoom、字体 |
| `dist/` | 交付包（zip + 解压目录） |
| `docs/` | 方案、剧情设定稿、验收清单、截图 |

## 已踩过的坑（重要留档）

1. **.bat 不能写中文**（cmd 用 GBK 解析，UTF-8 中文破坏解析）。
2. **模糊根因**：Windows 125% DPI 全屏被 DWM 拉伸 + 默认纹理过滤。
   对策：窗口模式 + `gl_texture_filter 0`；截图工具必须声明 DPI 感知。
3. **主菜单是图片补丁**（M_NGAME 等），语言表翻不到 → 中文 PNG 覆盖。
4. **调色板 translation 压暗真彩字体** → HUD 用预着色字体 + CR_UNTRANSLATED。
5. **ZScript 作用域**：EventHandler 默认 play，UiTick 是 ui，跨域赋值 =
   "Expression must be a modifiable value"。ui 侧状态用 `ui` 字段。
6. **顶层自由函数不存在**：函数必须挂在类里（static play 方法）。
7. **struct 赋值/返回未实现** → 用 primitive switch 函数替代 struct 传值。
8. **地图必须打成 PWAD 磁盘文件**（PK3 内 maps/*.wad 全名查找在 5.0.3 不可靠）。
9. **WAD 目录条目顺序**：filepos 在前、size 在后，写反 = 加载即崩。
10. **纹理/扁平名必须 NUL 填充**（空格填充 → 查不到 → 棋盘格）。
11. **THINGS 的 type 按有符号 16 位读**：ednum > 32767 变负数，物件被当
    "Unknown type" 丢弃（自定义编号请用 3920-3932 这类 <32768 的值）。
12. **THINGS 的 options 位 16 = 仅多人**：写成 7|16 会让单机下所有物品消失。
13. **`level.CreateActorIterator(0)` 是空迭代器**（源码里 id==0 直接返回 null）；
    要遍历实体请给 TID 或用 `ThinkerIterator.Create('Actor')`。
14. **矩形房间边界只能画一次**：重复调用 rect_walls 会把先前留的门洞重新封死
    （表现为"空气墙"）；所有 gap 必须一次给全。
15. **凹室必须在主房间之外**、与主房间共享边线；扇区空间重叠会毁掉 BSP。
16. **自定义 -config 会清空默认绑定**：引擎先 `C_SetDefaultBindings()` 再
    `UnbindAll()`，配置文件里没写的键全部失效（我们曾因此丢掉 ESC 和 ` 键）。
    正式配置必须包含完整绑定；本作已加 `Escape=menu_main`、`` `=toggleconsole ``。
17. **ESC 要长按约 2 秒**（短按被按键重复机制吞掉）。
18. **截图/按键必须按 PID 锁定自己启动的窗口**：否则会抓到玩家自己的
    uzdoom 窗口，把按键打进玩家游戏里。
19. **`-logfile` 偶发不落盘**；自动化以引擎内截图 + stdout 重定向为准。
20. **门的三个坑**：special 26/27/28 是蓝/黄/红 **DR**（会自动关上），
    31/32/33 才是对应的 **D1**（开一次常开）；门面图形必须放在 sidedef 的
    **upper** 纹理（放 middle 会透明，看起来像空气墙）；双面门扇线**不能**
    带 ML_BLOCKING(1)，否则门开了也永远走不过去。
21. **Vulkan 管线缓存损坏**（强杀进程残留）→ 随机 Access Violation；
    删除 `%LOCALAPPDATA%\doom\uzdoom\vulkanpipelinecache` 即愈。

## 已知待办

- [ ] 敌人/武器 sprite 仍为 Freedoom 占位素材（Blender 8 方向渲染是下一步）
- [ ] 抉择菜单的鼠标点击（当前键盘 ↑↓/回车）
- [ ] 章节结算页的过场节奏（背景图已生成 FZBKGRD1-3）
- [ ] 配音（台词见 docs/剧情.md）
- [ ] 选项子菜单的个别英文残留（引擎语言表补翻）

## 下一步

1. 用交付包做一轮真实玩家试玩（重点：抉择文案是否好读、难度曲线）。
2. Blender 8 方向敌人 sprite 批量渲染并替换。
3. 三章时长与难度按试玩反馈调整。
