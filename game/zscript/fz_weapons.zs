// 玩家手感调参：武器伤害、弹药供给与开火音效。
//
// 原则和 fz_actors.zs 一样——换皮不换脑子，只改数字：
//   * 枪械类沿用 Freedoom 的精灵帧（PISG / SHTG），只重写 Fire 状态里的
//     A_FireBullets 伤害，动画节奏与原版一致。
//   * 开火音效走 sndinfo/SNDINFO 里登记的 fz/pistol、fz/shotgun。
//   * 弹药拾取物直接改 Inventory.Amount，地图里的 Clip / Shell 都是同一批
//     类名，replaces 之后生成时自动换成新数值。
// 2026-11-22 首版：试玩反馈"太难"，伤害约 ×2，拾取量 ×2，出生自带 100 发
// 手枪弹 + 16 发霰弹。

class FZPistol : Pistol replaces Pistol
{
	Default
	{
		Inventory.PickupMessage "拾取了【证据链】手枪！";
	}

	States
	{
	Fire:
		PISG A 4;
		PISG B 6
			{
				A_PlaySound("fz/pistol", CHAN_WEAPON);
				A_FireBullets(5.6, 0, 1, 12, "BulletPuff");
			}
		PISG C 4;
		PISG B 5 A_ReFire;
		Goto Ready;
	}
}

class FZShotgun : Shotgun replaces Shotgun
{
	Default
	{
		Inventory.PickupMessage "拾取了【反诈喇叭】！";
	}

	States
	{
	Fire:
		SHTG A 3;
		SHTG A 7
			{
				A_PlaySound("fz/shotgun", CHAN_WEAPON);
				A_FireBullets(5.6, 0, 7, 9, "BulletPuff");
			}
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
// 拾取提示写在 actor 上：Freedoom 的 DEHACKED 把 GOTxxx 全改成了英文，
// LANGUAGE 覆盖不了，所以每个可拾取物都自带一条中文提示。
class FZClip : Clip replaces Clip
{
	Default
	{
		Inventory.Amount 20;
		Inventory.PickupSound "fz/ammo";
		Inventory.PickupMessage "拾取了一盒【线索】！";
	}
}

class FZClipBox : ClipBox replaces ClipBox
{
	Default
	{
		Inventory.Amount 100;
		Inventory.PickupSound "fz/ammo";
		Inventory.PickupMessage "拾取了一箱【线索】！";
	}
}

class FZShell : Shell replaces Shell
{
	Default
	{
		Inventory.Amount 8;
		Inventory.PickupSound "fz/ammo";
		Inventory.PickupMessage "拾取了一盒【话术弹】！";
	}
}

class FZShellBox : ShellBox replaces ShellBox
{
	Default
	{
		Inventory.Amount 40;
		Inventory.PickupSound "fz/ammo";
		Inventory.PickupMessage "拾取了一堆【话术弹】！";
	}
}

// ---------------------------------------------------------------- 医疗
// 地图里的 2011/2012 是原版 Stimpack / Medikit，替换后只改拾取音。
class FZStimpack : Stimpack replaces Stimpack
{
	Default
	{
		Inventory.PickupSound "fz/health";
		Inventory.PickupMessage "喝了一罐【警惕能量】！";
	}
}

class FZMedikit : Medikit replaces Medikit
{
	Default
	{
		Inventory.PickupSound "fz/health";
		Inventory.PickupMessage "打开【防骗急救包】！警惕值回满";
	}
}

// 防骗盾 / 证据链：原版类是 GreenArmor / ArmorBonus / RedCard，
// 只为了改拾取提示而替换，数值与行为全部继承。
class FZArmorBonus : ArmorBonus replaces ArmorBonus
{
	Default
	{
		Inventory.PickupMessage "防骗盾 +1";
	}
}

class FZGreenArmor : GreenArmor replaces GreenArmor
{
	Default
	{
		Inventory.PickupMessage "拾取了【防骗盾】！话术攻击被吸收";
	}
}

class FZRedCard : RedCard replaces RedCard
{
	Default
	{
		Inventory.PickupMessage "拾取了【证据链】！审判门已解锁";
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

