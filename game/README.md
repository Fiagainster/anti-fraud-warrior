# game/ — PK3 工程

这是「反诈战士」的主工程，最终打包成 `build/fanzha-demo.pk3`。

| 目录 | 内容 |
|---|---|
| `maps/` | UDMF 地图（UDB 编辑） |
| `zscript/` | ZScript：HUD、武器、敌人、事件、抉择门 |
| `acs/` | ACS 关卡脚本 |
| `fonts/` | 从 Fusion Pixel 生成的 Unicode PNG 字体 |
| `sprites/` | 敌人/武器/道具 sprite（PNG） |
| `sounds/` | 音效与配音（OGG） |
| `language/` | 中文文案、LANGUAGE 覆盖 |
| `mapinfo/` | MAPINFO、关卡顺序、结算定义 |
| `menudef/` | 主菜单/设置菜单定义 |

打包命令（后续实现）：

```powershell
tools\build.ps1
```
