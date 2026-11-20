# 贡献指南（简版）

完整手册在 `docs/协作/README.md`，这里只列硬性要求。

## 提交前

```powershell
python tools\doctor.py
python tools\fz_ctl.py check
```

改动涉及玩法/地图/MAPINFO 时，再跑 `python tools\fz_ctl.py tour`（门/出口相关加 `door`/`exit`）。

## 不要提交

- `vendor/`（只提交 `vendor/manifest.json`）
- `build/`、`dist/`、`source/`
- `game/maps/*.wad`、`game/fonts/`（生成物）
- 任何密钥、代理地址、本机绝对路径

## 命名与分层

- 代码/脚本英文命名，玩家可见文本中文。
- 新素材进 `assets_src/` 并在 `assets_src/CREDITS.md` 登记。
- 新 DoomEd 编号先登记到 `docs/协作/资源与命名规范.md`。

## PR

使用 `.github/PULL_REQUEST_TEMPLATE.md`，附截图/回归结果；至少 1 人 Review。
