# menudef/

当前主菜单**不在这里定义**。我们用 `game/graphics/M_*.png` 覆盖原版菜单补丁：

- `M_DOOM` — 标题「反诈战士」
- `M_NGAME` — 开始行动
- `M_OPTION` — 设置
- `M_LOADG` — 读取进度
- `M_SAVEG` — 保存进度
- `M_RDTHIS` — 操作说明
- `M_QUITG` — 退出

这样保留 Doom 原生的菜单布局、骷髅光标、快捷键和鼠标区域。生成脚本：`tools/gen_menu_patches.py`。

如果以后要做完全自定义的菜单（例如案件选择、知识库入口），再在这里放 `menudef.txt`，并在 `tools/build.py` 里把它打包成 `MENUDEF`。
