# 源素材目录（assets_src）

这里放**可编辑的源文件**，游戏实际使用的资源由工具生成/导入到 `game/`。

```
blender/    Blender 源文件（敌人、武器、徽标、道具）
textures/   墙面/地面/天花源图（krita/psd/aseprite）
ui/         HUD/标题/菜单/结算页源文件
audio/      音效/配音/BGM 源文件
maps_src/   手工地图源文件（Ultimate Doom Builder）
CREDITS.md  所有外部/AI 素材的来源与授权登记
```

规则：

- 大文件走 Git LFS（`.blend/.psd/.kra/.wav/.ogg/...`，见根目录 `.gitattributes`）。
- 命名全小写+下划线，不带中文；导出给引擎的资源名遵守 8 字符大写限制。
- 每个外部素材必须在 `CREDITS.md` 登记：来源、作者、许可证、AI 参与情况。
- 导入游戏的流程与验收见 `docs/协作/角色-美术.md`、`docs/协作/角色-音频.md`。
