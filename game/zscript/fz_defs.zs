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
// draws the matching text; the item expires itself by zeroing Amount.
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
			if (Life <= 0) Amount = 0;
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

// ------------------------------------------------------- choice gate ------

// Holographic scam terminals. Walk into one to open its choice menu.
// One class per gate (vanilla-format maps have no thing args), each carrying
// its gate id via a virtual method.
class FZGateTerminal : Inventory abstract
{
	bool done;

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
		ARM1 A -1 Bright;
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
		if (done) return false;
		if (toucher == null || toucher.player == null) return false;
		// already answered this gate? its stage token is already carried
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
// the trial gate. Sprite is a placeholder (backpack) until Blender art lands.
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
		BPAK A -1 Bright;
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
		toucher.GiveInventory("FZEvidence", 1);
		toucher.GiveInventory("RedCard", 1);
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
		BKEY A -1 Bright;
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
