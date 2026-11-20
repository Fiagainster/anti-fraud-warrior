// Automated-test hook: captures the gameplay HUD, then forces the
// chapter-1 choice menu open and captures it. Verifies the full core loop.
class FZSmokeHUDHandler : EventHandler
{
	int wticks;
	ui int uticks;

	override void WorldTick()
	{
		wticks++;
		if (wticks == 90)
		{
			LevelLocals.MakeScreenShot();
		}
		if (wticks == 120)
		{
			let pl = players[consoleplayer].mo;
			if (pl != null)
			{
				let lock = FZGateLock(Actor.Spawn("FZGateLock"));
				if (lock != null)
				{
					lock.GateId = 11;
					lock.AttachToOwner(pl);
				}
			}
		}
	}

	override void UiTick()
	{
		uticks++;
		if (uticks == 400)
		{
			LevelLocals.MakeScreenShot();
		}
	}
}
