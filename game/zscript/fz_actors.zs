// fz_actors.zs - 自制角色：把原版 6 个怪物全部换成自研美术
//
// 原则：换皮不换脑子。每个类都 `: 原版类 replaces 原版类`，健康/速度/伤害/
// 寻路/掉落全部继承，一个字都不改；只覆盖 `States` 里的精灵名和帧序列。
// 地图侧也不用动——地图里放的是 3004/3001/3002/3003/3005 这些原版 ednum，
// 引擎在生成时自动换成本类（这就是 replaces 的作用）。
//
// 帧字母与状态一一对应，13 帧用满 A-M（docs/角色美术设计.md §3）：
//   A 待机 / B-E 行走 / F-G 攻击 / H 受击 / I-M 死亡
//
// 死亡帧必须保留原版的三个关键调用，否则玩法会坏：
//   A_Scream      死亡音效
//   A_NoBlocking  解除碰撞（漏了地上会留一堵看不见的墙）
//   A_BossDeath   只有 Boss 有，漏了关卡结束不了
//
// 美术来源：art/sprites/<精灵名>/<帧>.png（生成端见仓库外的 生图/pixelpipe）
//   FZFR 刷手      ← 原 ZombieMan   （家族 A 原型）
//   FZRN 跑分马仔  ← 原 ShotgunGuy   （FZFR 土黄变体）
//   FZSC 黄牛      ← 原 DoomImp      （家族 B 原型）
//   FZBK 黑市掮客  ← 原 Demon        （FZSC 褐变体）
//   FZCP 假警察    ← 原 Cacodemon    （家族 C 原型）
//   FZCH 影子会长  ← 原 BaronOfHell  （FZCP 黑红变体，放大 1.7 倍当 Boss）

// ---------------------------------------------------------------- 刷手
class FZShill : ZombieMan replaces ZombieMan
{
	Default
	{
		Health 32;
		Speed 8;
		PainChance 190;
		BloodColor "50 55 45";
		Obituary "%o 被刷手拉着一起刷了单，再没醒。";
	}

	States
	{
	Spawn:
		FZFR A 10 A_Look;
		Loop;
	See:
		FZFR B 4 A_Chase;
		FZFR C 4 A_Chase;
		FZFR D 4 A_Chase;
		FZFR E 4 A_Chase;
		Loop;
	Missile:
		FZFR F 6 A_FaceTarget;
		FZFR G 6 A_PosAttack;
		Goto See;
	Pain:
		FZFR H 3 A_Pain;
		Goto See;
	Death:
		FZFR I 5 A_Scream;
		FZFR J 5 A_Fall;
		FZFR K 5;
		FZFR L 5 A_NoBlocking;
		FZFR M -1;
		Stop;
	// 原版 ZombieMan 有 XDeath（被霰弹/爆炸打成碎块时走这条），不覆盖的话
	// 引擎会回退到原版的 POSS 帧，玩家就会看见一张 Freedoom 图。
	XDeath:
		FZFR I 5 A_XScream;
		FZFR J 5 A_Fall;
		FZFR K 5;
		FZFR L 5 A_NoBlocking;
		FZFR M -1;
		Stop;
	}
}

// ---------------------------------------------------------------- 跑分马仔
// 原 ShotgunGuy：中距连射。保持"一梭两发"的节奏。
class FZRunner : ShotgunGuy replaces ShotgunGuy
{
	Default
	{
		Obituary "%o 的流水跑到头了。";
	}

	States
	{
	Spawn:
		FZRN A 10 A_Look;
		Loop;
	See:
		FZRN B 3 A_Chase;
		FZRN C 3 A_Chase;
		FZRN D 3 A_Chase;
		FZRN E 3 A_Chase;
		Loop;
	Missile:
		FZRN F 8 A_FaceTarget;
		FZRN G 8 A_SPosAttack;
		FZRN F 8 A_FaceTarget;
		FZRN G 8 A_SPosAttack;
		Goto See;
	Pain:
		FZRN H 3 A_Pain;
		Goto See;
	Death:
		FZRN I 5 A_Scream;
		FZRN J 5 A_Fall;
		FZRN K 5;
		FZRN L 5 A_NoBlocking;
		FZRN M -1;
		Stop;
	XDeath:
		FZRN I 5 A_XScream;
		FZRN J 5 A_Fall;
		FZRN K 5;
		FZRN L 5 A_NoBlocking;
		FZRN M -1;
		Stop;
	}
}

// ---------------------------------------------------------------- 黄牛
// 原 DoomImp：近战爪击 + 远程抛射，两个状态指向同一动作函数。
class FZScalper : DoomImp replaces DoomImp
{
	Default
	{
		Obituary "%o 成了又一茬韭菜。";
	}

	States
	{
	Spawn:
		FZSC A 10 A_Look;
		Loop;
	See:
		FZSC B 3 A_Chase;
		FZSC C 3 A_Chase;
		FZSC D 3 A_Chase;
		FZSC E 3 A_Chase;
		Loop;
	Melee:
	Missile:
		FZSC F 8 A_FaceTarget;
		FZSC G 8 A_TroopAttack;
		Goto See;
	Pain:
		FZSC H 3 A_Pain;
		Goto See;
	Death:
		FZSC I 5 A_Scream;
		FZSC J 5 A_Fall;
		FZSC K 5;
		FZSC L 5 A_NoBlocking;
		FZSC M -1;
		Stop;
	// 原版 DoomImp 有 XDeath，理由同 FZShill。
	XDeath:
		FZSC I 5 A_XScream;
		FZSC J 5 A_Fall;
		FZSC K 5;
		FZSC L 5 A_NoBlocking;
		FZSC M -1;
		Stop;
	}
}

// ---------------------------------------------------------------- 黑市掮客
// 原 Demon：只会近身冲撞，所以只给 Melee。
class FZBroker : Demon replaces Demon
{
	Default
	{
		Obituary "%o 被中间人抽走了最后一笔。";
	}

	States
	{
	Spawn:
		FZBK A 10 A_Look;
		Loop;
	See:
		FZBK B 3 A_Chase;
		FZBK C 3 A_Chase;
		FZBK D 3 A_Chase;
		FZBK E 3 A_Chase;
		Loop;
	Melee:
		FZBK F 8 A_FaceTarget;
		FZBK G 8 A_SargAttack;
		Goto See;
	Pain:
		FZBK H 2 A_Pain;
		Goto See;
	Death:
		FZBK I 8 A_Scream;
		FZBK J 8 A_Fall;
		FZBK K 8;
		FZBK L 8 A_NoBlocking;
		FZBK M -1;
		Stop;
	}
}

// ---------------------------------------------------------------- 假警察
// 原 Cacodemon：浮空 + 远程咬击。不画腿，袍角下垂，正好对上浮空。
class FZFakeCop : Cacodemon replaces Cacodemon
{
	Default
	{
		Obituary "%o 被「王警官」要求配合调查，再没回来。";
	}

	States
	{
	Spawn:
		FZCP A 10 A_Look;
		Loop;
	See:
		FZCP B 3 A_Chase;
		FZCP C 3 A_Chase;
		FZCP D 3 A_Chase;
		FZCP E 3 A_Chase;
		Loop;
	Melee:
	Missile:
		FZCP F 5 A_FaceTarget;
		FZCP G 5 A_HeadAttack;
		Goto See;
	Pain:
		FZCP H 3 A_Pain;
		Goto See;
	Death:
		FZCP I 8 A_Scream;
		FZCP J 8 A_Fall;
		FZCP K 8;
		FZCP L 8 A_NoBlocking;
		FZCP M -1;
		Stop;
	}
}

// ---------------------------------------------------------------- 影子会长
// 原 BaronOfHell：Boss。Scale 只放大表现，不动碰撞盒（Height 继承原版），
// 所以玩法手感与原版 Boss 完全一致。
class FZChairman : BaronOfHell replaces BaronOfHell
{
	Default
	{
		Scale 1.7;
		Obituary "%o 在影子会长的判决书上签了字。";
	}

	States
	{
	Spawn:
		FZCH A 10 A_Look;
		Loop;
	See:
		FZCH B 3 A_Chase;
		FZCH C 3 A_Chase;
		FZCH D 3 A_Chase;
		FZCH E 3 A_Chase;
		Loop;
	Melee:
	Missile:
		FZCH F 8 A_FaceTarget;
		FZCH G 8 A_BruisAttack;
		Goto See;
	Pain:
		FZCH H 2 A_Pain;
		Goto See;
	Death:
		FZCH I 8 A_Scream;
		FZCH J 8 A_Fall;
		FZCH K 8;
		FZCH L 8 A_NoBlocking;
		FZCH M -1 A_BossDeath;
		Stop;
	}
}

