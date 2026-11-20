# 源素材目录（assets_src）

这里放**可编辑的源文件**，游戏实际使用的资源由工具生成/导入到 `game/`。

```
pixelorama/ Pixelorama 源文件（.pxo）：道具图标、UI、贴图、手绘 sprite
blender/    Blender 源文件（敌人、武器、徽标、道具）
textures/   墙面/地面/天花源图（krita/psd/aseprite）
ui/         HUD/标题/菜单/结算页源文件
audio/      音效/配音/BGM 源文件
maps_src/   手工地图源文件（Ultimate Doom Builder）
CREDITS.md  所有外部/AI 素材的来源与授权登记
```

美术主线是**手工像素画（Pixelorama）**，Blender 只负责敌人/武器的 8 方向
sprite 渲染。所以 `pixelorama/` 是这套流程里最先会被填满的目录。

## 当前状态（2026-11-20）

**上面这些子目录目前都是空的。** 现有美术全部由脚本生成（`tools/gen_*.py`），
敌人/武器/道具仍在用 Freedoom 占位素材，所以 `CREDITS.md` 里还没有素材条目。
补齐美术是本项目最大的缺口，见根目录 README「已知待办」。

手绘产物的接线步骤（sprite 命名、`States` 改动、碰撞体调整）见
`docs/协作/角色-美术.md`——**画完不接线，游戏里看不到**。

## 规则

- 大文件走 Git LFS：`.gitattributes` 已声明 `.blend/.psd/.kra/.aseprite/.pxo/.wav/.ogg`
  等过滤器，但**新克隆必须先执行 `git lfs install`**，否则这些文件会被当普通
  二进制提交，之后无法追溯。当前仓库尚未启用 LFS（`git lfs ls-files` 为空）。
- 命名全小写+下划线，不带中文；导出给引擎的资源名遵守 8 字符大写限制。
- 每个外部素材必须在 `CREDITS.md` 登记：来源、作者、许可证、AI 参与情况
  （AI 参与还必须写工具/模型、日期、提示词摘要、人工修改程度）。
- 导入游戏的流程与验收见 `docs/协作/角色-美术.md`、`docs/协作/角色-音频.md`。
