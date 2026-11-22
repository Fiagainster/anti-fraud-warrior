// 玩家手感调参：武器伤害与弹药供给。
//
// 原则和 fz_actors.zs 一样——换皮不换脑子，只改数字：
//   * 枪械类沿用 Freedoom 的精灵帧（PISG / SHTG），只重写 Fire 状态里的
//     A_FireBullets 伤害，动画节奏与原版一致。
//   * 弹药拾取物直接改 Inventory.Amount，地图里的 Clip / Shell 都是同一批
//     类名，replaces 之后生成时自动换成新数值。
// 2026-11-22 首版：试玩反馈"太难"，伤害约 ×2，拾取量 ×2，出生自带 100 发
// 手枪弹 + 16 发霰弹。

class FZPistol : Pistol replaces Pistol
{
	States
	{
	Fire:
		PISG A 4;
		PISG B 6 A_FireBullets(5.6, 0, 1, 12, "BulletPuff");
		PISG C 4;
		PISG B 5 A_ReFire;
		Goto Ready;
	}
}

class FZShotgun : Shotgun replaces Shotgun
{
	States
	{
	Fire:
		SHTG A 3;
		SHTG A 7 A_FireBullets(5.6, 0, 7, 9, "BulletPuff");
		SHTG B 5;
		SHTG C 5;
		SHTG D 4;
		SHTG C 5;
		SHTG B 5;
		SHTG A 3;
		SHTG A 7 A_Refire;
		Goto Ready;
	}
}

// ---------------------------------------------------------------- 弹药
class FZClip : Clip replaces Clip
{
	Default
	{
		Inventory.Amount 20;
	}
}

class FZClipBox : ClipBox replaces ClipBox
{
	Default
	{
		Inventory.Amount 100;
	}
}

class FZShell : Shell replaces Shell
{
	Default
	{
		Inventory.Amount 8;
	}
}

class FZShellBox : ShellBox replaces ShellBox
{
	Default
	{
		Inventory.Amount 40;
	}
}

// 出生补给：在 DoomPlayer 自带的 Fist / Pistol / Clip 50 之上追加。
// Player.StartItem 在子类里是累加的，不会覆盖父类那几条。
class FZPlayer : DoomPlayer replaces DoomPlayer
{
	Default
	{
		Player.StartItem "Clip", 50;
		Player.StartItem "Shell", 16;
	}
}
