// part B of fz_defs (split for bisect)
// Push a message onto the player's banner queue (play scope).
class FZUtilB : Object play
{
	static void PushMsg(Actor pl, int id, int life)
	{
		if (pl == null || pl.player == null) return;
		name slot;
		if (pl.FindInventory("FZMsg1") == null) slot = 'FZMsg1';
		else if (pl.FindInventory("FZMsg2") == null) slot = 'FZMsg2';
		else if (pl.FindInventory("FZMsg3") == null) slot = 'FZMsg3';
		else return;
		let m = FZMsgItemBase(Spawn(slot));
		if (m == null) return;
		m.MsgId = id;
		m.Life = life;
		m.AttachToOwner(pl);
	}
}


// ------------------------------------------------------- choice gate ------

// A holographic scam terminal. Walk into it to open the choice menu.
// args[0] = gate id (11..32), args[1] = done flag.
// Uses a placeholder sprite until the Blender pipeline lands.
class FZChoiceGate : Inventory
{
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

	override bool TryPickup(in out Actor toucher)
	{
		if (args[1] == 1) return false;
		if (toucher == null || toucher.player == null) return false;
		if (toucher.CountInventory("FZGateLock") > 0) return false;

		let lock = FZGateLock(Spawn("FZGateLock"));
		if (lock != null)
		{
			lock.GateId = args[0];
			lock.AttachToOwner(toucher);
		}
		return false;
	}
}

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

	override bool TryPickup(in out Actor toucher)
	{
		if (toucher == null || toucher.player == null) return false;
		if (toucher.CountInventory("FZEvidence") >= 3) return false;
		toucher.GiveInventory("FZEvidence", 1);
		toucher.GiveInventory("RedCard", 1);
		FZUtil.PushMsg(toucher, 901, 210);
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
		FZUtil.PushMsg(toucher, 903, 260);
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
			if (playeringame[i] && players[i].mo != null) FZUtil.PushMsg(players[i].mo, id, 340);
		}
		mTimer = 300;
	}

	private int NextBriefId()
	{
		switch (level.mapname)
		{
			case 'E1M1': return ++mLine <= 3 ? 101 + mLine - 1 : 0;
			case 'E1M2': return ++mLine <= 3 ? 201 + mLine - 1 : 0;
			case 'E1M3': return ++mLine <= 3 ? 301 + mLine - 1 : 0;
		}
		return 0;
	}
}
