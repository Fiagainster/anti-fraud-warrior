// fz_actors.zs - 自制角色（当前是占位美术）
//
// 只换皮不换脑子：新类继承原版怪物，AI、掉落、寻路全部沿用，只覆盖 States
// 里的精灵名。这样"美术替换"和"战斗行为"解耦，任何一方的改动都不会把另一
// 方弄坏。
//
// 美术规则（tools/gen_sprites.py check 会强制）：
//   * 精灵名 4 字符，帧字母 A-Z，旋转号 0 = 单面朝向玩家
//   * 画布 48x64，脚画在底边（PNG 默认偏移是"水平居中、底边落地"）
//   * 弹道/枪口帧要加 Bright，否则跟着房间亮度变暗
//
// 现在 FZFR（刷手）用 FZShill 这个名字先替换 ZombieMan 做管线验证，
// 正式设定见 docs/角色美术设计.md。

class FZShill : ZombieMan replaces ZombieMan
{
	Default
	{
		Health 32;
		Speed 8;
		PainChance 190;
		BloodColor "50 55 45";
		Obituary "%o 被刷手拖着一起刷单了。";
	}

	States
	{
	Spawn:
		FZFR A 10 A_Look;
		Loop;
	See:
		FZFR A 4 A_Chase;
		FZFR B 4 A_Chase;
		FZFR C 4 A_Chase;
		FZFR D 4 A_Chase;
		Loop;
	Missile:
		FZFR E 8 A_FaceTarget;
		FZFR F 8 A_PosAttack;
		Goto See;
	Melee:
		FZFR E 8 A_FaceTarget;
		FZFR F 8 A_PosAttack;
		Goto See;
	Pain:
		FZFR G 3 A_Pain;
		Goto See;
	Death:
		FZFR H 5 A_Scream;
		FZFR I 5 A_NoBlocking;
		FZFR J -1;
		Stop;
	}
}
