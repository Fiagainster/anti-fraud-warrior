# menudef/

`menudef.txt` 会被 `tools/build.py` 打包成 pk3 根目录的 `MENUDEF`。

它替换了两处：

1. **MainMenu** —— 保持原版布局，只把「开始行动」（`M_NGAME`）指向我们自己的
   `FZNewGameMenu`，不再进引擎的 PlayerclassMenu / SkillMenu；
2. **FZNewGameMenu** —— 五个中文难度项，用的是引擎自带的 `Startgame` 动作，
   参数直接是 skill 序号（0–4）。引擎在 `M_SetSpecialMenu` 里会
   `G_DeferedInitNew` + `M_ClearMenus`，所以选完就自动开局、自动关菜单。

主菜单其余项（设置 / 读档 / 存档 / 操作说明 / 退出）保持引擎默认的 `M_*` 贴图覆盖。

## 坑

- `Command` 项只在 **OptionMenu** 里合法；ListMenu 里写 `Command` 会报
  `Unknown keyword 'Command'`。而 OptionMenu 又不支持 `Position` / `LineSpacing`。
- `Font "fzfont"` 在 ListMenu 里能解析，但 fzfont 是给 HUD 的 320×200 画的，
  菜单里会挤成一团——用默认菜单字体即可，它本来就能渲染中文。
- 别再回头去改 skill 的名字：`skill` 块在我们 MAPINFO 里解析得比引擎的
  `mapinfo/doomcommon.txt` 早，永远是"追加"而不是"替换"；Freedoom 的 DEHACKED
  又只认 IWAD 里的那一份。菜单这条路才是对的。
