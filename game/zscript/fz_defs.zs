// 反诈战士 · gameplay definitions
// Custom inventory tokens, message carriers, and the interactive
// choice-gate / evidence actors. Menu + outcomes live in fz_gates.zs.

// ---------------------------------------------------------------- tokens --

class FZStage1 : Inventory
{
	Default { Inventory.MaxAmount 1; }
}

class FZStage2 : Inventory
{
	Default { Inventory.MaxAmount 1; }
}

class FZStage3 : Inventory
{
	Default { Inventory.MaxAmount 1; }
}

// Held while a choice menu is open; the HUD (ui scope) watches for it and
// pushes FZChoiceMenu. Outcomes take it away again and hand out FZGateCool
// so the same touch does not instantly re-open the menu.
class FZEvidence : Inventory
{
	Default { Inventory.MaxAmount 3; }
}

class FZGateLock : Inventory
{
	int GateId;
	Default { Inventory.MaxAmount 1; }
}

class FZGateCool : Inventory
{
	Default { Inventory.MaxAmount 1; }
}

// ------------------------------------------------------------ messages --

// Message carrier attached to the player. The HUD (ui scope) reads MsgId and
// draws the matching text; the item destroys itself when Life runs out.
// Three slots are enough because the banner only ever shows one line group.
class FZMsgItemBase : Inventory abstract
{
	int MsgId;
	int Life;

	Default
	{
		Inventory.MaxAmount 1;
		Height 0;
		Radius 0;
		RenderStyle "None";
		+INVENTORY.UNDROPPABLE
	}

	override void Tick()
	{
		Super.Tick();
		if (Life > 0)
		{
			Life--;
			// Destroy(), not "Amount = 0": the engine only removes an
			// inventory item whose amount hit zero when it goes through
			// DepleteOrDestroy, and a bare Amount=0 leaves a zero-count
			// item behind. FZMsgItemBase.Push() looks for a free slot with
			// FindInventory, which still found those ghosts - so after the
			// three briefing lines every later banner (识破/正确/红卡)
			// silently never appeared again.
			if (Life <= 0) Destroy();
		}
	}

	// Push a message onto the player's banner queue (play scope).
	static void Push(Actor pl, int id, int life)
	{
		if (pl == null || pl.player == null) return;
		name slot;
		if (pl.FindInventory("FZMsg1") == null) slot = 'FZMsg1';
		else if (pl.FindInventory("FZMsg2") == null) slot = 'FZMsg2';
		else if (pl.FindInventory("FZMsg3") == null) slot = 'FZMsg3';
		else return;
		let m = FZMsgItemBase(Actor.Spawn(slot));
		if (m == null) return;
		m.MsgId = id;
		m.Life = life;
		m.AttachToOwner(pl);
	}
}

class FZMsg1 : FZMsgItemBase {}
class FZMsg2 : FZMsgItemBase {}
class FZMsg3 : FZMsgItemBase {}

// --------------------------------------------------------- evidence -------

// Single source of truth for "a piece of evidence was just obtained".
//
// The trial door only ever checks the RedCard, so the card has to appear
// exactly when the chain is complete - handing it out on the first correct
// choice (as the demo used to) opened the door while the HUD still read
// 1/3, contradicting both the banner text and the README.
class FZEvidenceChain : Object play
{
	// 红卡 = 结案资格，两个条件缺一不可：
	//   1) 证据链 3 件（三个证据箱正好凑满，全捡齐才行）；
	//   2) 本章两道抉择都答对（FZStage1 + FZStage2）。
	//
	// 第 2 条是这次改的重点：原来只要凑满 3 件证据就发红卡，而三个证据箱
	// 自己就能凑满，于是"两题全答错、只捡箱子"照样能开门——抉择对开门没有
	// 任何否决权，反诈题白答。现在证据箱只负责"凑数"，答题才决定"能不能结案"。
	//
	// 不会卡关：答错时 FZGateTerminal 不置 done（只有答对或已持有该题进度
	// 才置），冷却 4 秒后走开再靠近就会重新弹菜单，代价是掉警惕值 + 伏击。
	// 所以"答错"只是暂时开不了门，永远有重答这条路。
	static void Grant(Actor pl, int amount = 1)
	{
		if (pl == null || pl.player == null) return;
		pl.GiveInventory("FZEvidence", amount); // MaxAmount 3，超出的自动吞掉
		if (pl.CountInv("RedCard") > 0) return;
		if (pl.CountInv("FZEvidence") < 3) return;
		if (pl.CountInv("FZStage1") < 1 || pl.CountInv("FZStage2") < 1)
		{
			// 证据齐了但还有题没答对：明确告诉玩家回去重答，别让人以为是 bug
			FZMsgItemBase.Push(pl, 905, 320);
			return;
		}
		pl.GiveInventory("RedCard", 1);
		FZMsgItemBase.Push(pl, 904, 320);
	}
}

// ------------------------------------------------------- choice gate ------

// Holographic scam terminals. Walk into one to open its choice menu.
// One class per gate (vanilla-format maps have no thing args), each carrying
// its gate id via a virtual method.
class FZGateTerminal : Inventory abstract
{
	bool done;
	// Per-terminal cooldown in tics. The player-level FZGateCool token is a
	// one-shot (the next touch eats it), which is useless while the player
	// stands inside the terminal: the very next tic opens the menu again.
	// After a wrong answer that turned into "forced to answer again and
	// again until you drop dead, then the chapter restarts".
	int mCool;

	override void Tick()
	{
		Super.Tick();
		if (mCool > 0) mCool--;
	}

	void StartCool(int ticks)
	{
		mCool = ticks;
	}

	// 4 seconds (35 tics per second) before the same terminal may pop its
	// menu again. Long enough that standing still lets you read the banner.
	static int CoolTics()
	{
		return 140;
	}

	Default
	{
		Inventory.MaxAmount 1;
		Height 48;
		Radius 16;
		RenderStyle "Translucent";
		Alpha 0.85;
		+INVENTORY.UNDROPPABLE
	}
	States
	{
	Spawn:
		FZGT A -1 Bright;
		Stop;
	}

	virtual int GateId() const { return 11; }

	override void PostBeginPlay()
	{
		Super.PostBeginPlay();
		ChangeTid(3942); // shared gate tid: lets play code find terminals
	}

	override bool TryPickup(in out Actor toucher)
	{
		if (done || mCool > 0) return false;
		if (toucher == null || toucher.player == null) return false;
		// Already answered this gate? Its stage token is already carried.
		// Gate ids end in 1/2 (11/12, 21/22, 31/32), i.e. "first/second
		// gate of this chapter", and FZPlayEvents.WorldLoaded clears the
		// tokens on every map load - so this check is per chapter and can
		// never be satisfied by the previous chapter's progress.
		name need = (GateId() % 10 == 1) ? 'FZStage1' : 'FZStage2';
		if (toucher.CountInv(need) > 0) { done = true; return false; }
		if (toucher.CountInv("FZGateLock") > 0) return false;
		if (toucher.CountInv("FZGateCool") > 0)
		{
			toucher.TakeInventory("FZGateCool", 1);
			return false;
		}

		let lock = FZGateLock(Actor.Spawn("FZGateLock"));
		if (lock != null)
		{
			lock.GateId = GateId();
			lock.AttachToOwner(toucher);
		}
		return false;
	}
}

class FZGate11 : FZGateTerminal { override int GateId() const { return 11; } }
class FZGate12 : FZGateTerminal { override int GateId() const { return 12; } }
class FZGate21 : FZGateTerminal { override int GateId() const { return 21; } }
class FZGate22 : FZGateTerminal { override int GateId() const { return 22; } }
class FZGate31 : FZGateTerminal { override int GateId() const { return 31; } }
class FZGate32 : FZGateTerminal { override int GateId() const { return 32; } }

// --------------------------------------------------------- pickups ------

// Evidence crate: gives evidence count + the RedCard "证据链" key that opens
// the trial gate. Sprite is a placeholder drawn by tools/gen_props.py; the
// final art replaces art/sprites/FZEV/A.png and keeps the same name.
class FZEvidencePickup : Inventory
{
	Default
	{
		Height 16;
		Radius 12;
		+FLOORCLIP
		+INVENTORY.UNDROPPABLE
	}
	States
	{
	Spawn:
		FZEV A -1 Bright;
		Stop;
	}

	override void PostBeginPlay()
	{
		Super.PostBeginPlay();
		ChangeTid(3943);
	}

	override bool TryPickup(in out Actor toucher)
	{
		if (toucher == null || toucher.player == null) return false;
		if (toucher.CountInv("FZEvidence") >= 3) return false;
		FZEvidenceChain.Grant(toucher);
		FZMsgItemBase.Push(toucher, 901, 210);
		GoAwayAndDie();
		return true;
	}
}

// Dropped by the chapter boss; completes the stage.
class FZMasterProof : Inventory
{
	Default
	{
		Height 16;
		Radius 12;
		+FLOORCLIP
		+INVENTORY.UNDROPPABLE
	}
	States
	{
	Spawn:
		FZPF A -1 Bright;
		Stop;
	}

	override bool TryPickup(in out Actor toucher)
	{
		if (toucher == null || toucher.player == null) return false;
		toucher.GiveInventory("FZStage3", 1);
		FZMsgItemBase.Push(toucher, 903, 260);
		GoAwayAndDie();
		return true;
	}
}

// -------------------------------------------------------- briefing ------

// Invisible map actor that streams the chapter briefing as banner messages.
class FZBriefingActor : Actor
{
	int mLine;
	int mTimer;

	Default
	{
		Height 1;
		Radius 1;
		RenderStyle "None";
		+NOGRAVITY
		+NOBLOCKMAP
		+INVISIBLE
	}

	override void PostBeginPlay()
	{
		Super.PostBeginPlay();
		ChangeTid(3944);
		mTimer = 45;
	}

	override void Tick()
	{
		Super.Tick();
		if (--mTimer > 0) return;
		int id = NextBriefId();
		if (id <= 0)
		{
			Destroy();
			return;
		}
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (playeringame[i] && players[i].mo != null) FZMsgItemBase.Push(players[i].mo, id, 340);
		}
		mTimer = 300;
	}

	private int NextBriefId()
	{
		int base = 0;
		if (level.mapname == "FZ01") base = 100;
		else if (level.mapname == "FZ02") base = 200;
		else if (level.mapname == "FZ03") base = 300;
		if (base == 0) return 0;
		mLine++;
		if (mLine <= 3) return base + mLine;
		return 0;
	}
}
