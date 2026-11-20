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
// pushes FZChoiceMenu. Outcomes take it away again.
class FZGateLock : Inventory
{
	int GateId;
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
}

class FZMsg1 : FZMsgItemBase {}
class FZMsg2 : FZMsgItemBase {}
class FZMsg3 : FZMsgItemBase {}

// Push a message onto the player's banner queue (play scope).
class FZUtil : Object play
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

