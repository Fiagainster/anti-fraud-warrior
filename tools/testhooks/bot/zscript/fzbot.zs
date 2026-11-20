// fzbot.zs - automation robot hook (test-only, ships in fz-bot.pk3)
//
// Drives the player along the full chapter route with real physics, so
// walls, gaps, pickups and terminals are exercised exactly as a player
// would hit them. Controlled from OUTSIDE via user cvars (+set fz_bot 1):
//   fz_bot          1 = route bot on
//   fz_bot_stop     N = halt once waypoint index >= N (-1/0 = full route)
//   fz_bot_timeout  seconds until the bot gives up (default 150)
//   fz_bot_combat   1 = auto-aim at the nearest living monster
// Waypoint arrival, stuck spots and route completion are printed to the
// log ("FZBOT: ..." lines) and captured as engine screenshots. The world
// pauses whenever a menu is up, so the bot naturally waits while the
// outside driver (tools/winbot.py) answers gate menus / intermissions.

class FZBotEvents : EventHandler
{
	int wticks;
	int wp;
	int stuckTicks;
	double lastX;
	double lastY;
	bool armed;
	bool routeDone;

	// ---- route waypoints (identical layout in all three chapters) ------
	// 0 spawn, 1 brief east, 2 corridor, 3 gateA terminal touch, 4 back,
	// 5 shotgun, 6 arena center, 7-15 evidence loop, 16 a1 east,
	// 17 c2, 18 gateB terminal touch, 19 back, 20 a2 entry, 21 a2 center,
	// 22 trial door face (waits for outside USE), 23 boss room,
	// 24 boss center, 25 exit nook, 26 exit switch face.
	double Wpx(int i)
	{
		switch (i)
		{
			case 0: return 128;   case 1: return 460;
			case 2: return 640;   case 3: return 640;
			case 4: return 640;   case 5: return 780;
			case 6: return 1088;  case 7: return 864;
			case 8: return 896;   case 9: return 864;
			case 10: return 1056; case 11: return 1088;
			case 12: return 1056; case 13: return 1248;
			case 14: return 1280; case 15: return 1248;
			case 16: return 1440; case 17: return 1584;
			case 18: return 1600; case 19: return 1600;
			case 20: return 1728; case 21: return 2208;
			case 22: return 2384; case 23: return 2512;
			case 24: return 2880; case 25: return 3180;
			case 26: return 3308;
		}
		return 0;
	}

	double Wpy(int i)
	{
		switch (i)
		{
			case 0: return 256;   case 1: return 256;
			case 2: return 256;   case 3: return 470;
			case 4: return 256;   case 5: return 256;
			case 6: return 256;   case 7: return -32;
			case 8: return -128;  case 9: return -32;
			case 10: return -32;  case 11: return -128;
			case 12: return -32;  case 13: return -32;
			case 14: return -128; case 15: return -32;
			case 16: return 256;  case 17: return 256;
			case 18: return 486;  case 19: return 256;
			case 20: return 256;  case 21: return 256;
			case 22: return 256;  case 23: return 256;
			case 24: return 256;  case 25: return 256;
			case 26: return 256;
		}
		return 0;
	}

	int WpCount() { return 27; }

	override void WorldLoaded(WorldEvent e)
	{
		wticks = 0;
		wp = 0;
		stuckTicks = 0;
		armed = true;
		lastX = -1e9;
		lastY = -1e9;
		Console.Printf("FZBOT: route armed on %s", level.mapname);
		SpawnProbe();
	}

	// counts the custom gameplay things this chapter must have spawned.
	// NOTE: CreateActorIterator(0) is EMPTY in UZDoom (FActorIterator
	// returns null for id 0) - always iterate a real TID.
	int CountTid(int tid)
	{
		int n = 0;
		ActorIterator it = level.CreateActorIterator(tid);
		for (let a = it.Next(); a != null; a = it.Next()) n++;
		return n;
	}

	void SpawnProbe()
	{
		int gates, evidence, brief;
		ThinkerIterator it = ThinkerIterator.Create('Actor');
		for (let a = Actor(it.Next()); a != null; a = Actor(it.Next()))
		{
			name cn = a.GetClassName();
			if (cn == 'FZGate11' || cn == 'FZGate12' || cn == 'FZGate21'
				|| cn == 'FZGate22' || cn == 'FZGate31' || cn == 'FZGate32') gates++;
			else if (cn == 'FZEvidencePickup') evidence++;
			else if (cn == 'FZBriefingActor') brief++;
		}
		Console.Printf("FZBOT: spawns gates=%d evidence=%d brief=%d",
			gates, evidence, brief);
	}

	// names every custom actor within 160 units (stuck diagnosis)
	void NearbyProbe(Actor pl)
	{
		for (int tid = 3942; tid <= 3944; tid++)
		{
			ActorIterator it = level.CreateActorIterator(tid);
			for (let a = it.Next(); a != null; a = it.Next())
			{
				double dx = a.Pos.X - pl.Pos.X;
				double dy = a.Pos.Y - pl.Pos.Y;
				if (dx * dx + dy * dy > 160 * 160) continue;
				Console.Printf("FZBOT: nearby %s at (%.0f, %.0f) z %.0f",
					a.GetClassName(), a.Pos.X, a.Pos.Y, a.Pos.Z);
			}
		}
	}

	override void WorldTick()
	{
		if (!armed) return;
		wticks++;

		CVar b = CVar.FindCVar("fz_bot");
		if (b == null || b.GetInt() == 0) return;

		let pl = players[consoleplayer].mo;
		if (pl == null) return;

		// test seam: the bot must not die mid-route (real players dodge)
		if (pl.health < 100) pl.health = 100;

		CVar combat = CVar.FindCVar("fz_bot_combat");
		if (combat != null && combat.GetInt() == 1) BotCombat(pl);

		int stopWp = -1;
		CVar sc = CVar.FindCVar("fz_bot_stop");
		if (sc != null && sc.GetInt() > 0) stopWp = sc.GetInt();
		if (stopWp >= 0 && wp >= stopWp)
		{
			if (!routeDone)
			{
				routeDone = true;
				Console.Printf("FZBOT: stop at wp %d pos (%.0f, %.0f)", wp, pl.Pos.X, pl.Pos.Y);
				LevelLocals.MakeScreenShot();
			}
			return;
		}

		if (wp >= WpCount())
		{
			if (!routeDone)
			{
				routeDone = true;
				Console.Printf("FZBOT: ROUTE DONE at (%.0f, %.0f)", pl.Pos.X, pl.Pos.Y);
				LevelLocals.MakeScreenShot();
			}
			return;
		}

		CVar t = CVar.FindCVar("fz_bot_timeout");
		int lim = (t != null && t.GetInt() > 0) ? t.GetInt() * 35 : 150 * 35;
		if (wticks > lim)
		{
			routeDone = true;
			Console.Printf("FZBOT: TIMEOUT at (%.0f, %.0f) wp=%d", pl.Pos.X, pl.Pos.Y, wp);
			LevelLocals.MakeScreenShot();
			return;
		}

		double dx = Wpx(wp) - pl.Pos.X;
		double dy = Wpy(wp) - pl.Pos.Y;
		double dist = sqrt(dx * dx + dy * dy);
		if (dist < 20)
		{
			Console.Printf("FZBOT: reached wp %d (%.0f, %.0f) ev=%d red=%d st1=%d st2=%d",
				wp, pl.Pos.X, pl.Pos.Y, pl.CountInv("FZEvidence"),
				pl.CountInv("RedCard"), pl.CountInv("FZStage1"),
				pl.CountInv("FZStage2"));
			LevelLocals.MakeScreenShot();
			wp++;
			stuckTicks = 0;
			lastX = pl.Pos.X;
			lastY = pl.Pos.Y;
			return;
		}
		double sp = 5.0;
		pl.vel = (dx / dist * sp, dy / dist * sp, pl.vel.z);

		stuckTicks++;
		if (stuckTicks >= 35)
		{
			if (abs(pl.Pos.X - lastX) < 4 && abs(pl.Pos.Y - lastY) < 4)
			{
				Console.Printf("FZBOT: stuck at (%.0f, %.0f) -> wp %d", pl.Pos.X, pl.Pos.Y, wp);
				if (stuckTicks == 35) NearbyProbe(pl);
			}
			lastX = pl.Pos.X;
			lastY = pl.Pos.Y;
			stuckTicks = 0;
		}
	}

	void BotCombat(Actor pl)
	{
		Actor best = null;
		double bd = 1e12;
		// ThinkerIterator is the only all-actor walk in this engine
		ThinkerIterator it = ThinkerIterator.Create('Actor');
		for (let a = Actor(it.Next()); a != null; a = Actor(it.Next()))
		{
			if (!a.bIsMonster || a.health <= 0) continue;
			double dx = a.Pos.X - pl.Pos.X;
			double dy = a.Pos.Y - pl.Pos.Y;
			double d = dx * dx + dy * dy;
			if (d < bd) { bd = d; best = a; }
		}
		if (best != null && bd < 512 * 512)
		{
			pl.angle = atan2(best.Pos.Y - pl.Pos.Y, best.Pos.X - pl.Pos.X);
		}
	}
	// The choice menu pauses the world before the next WorldTick, so menu
	// state is observed from the UI side. One "menu open" log per instance
	// (for screenshots), and an optional in-engine answer that works no
	// matter which window owns the OS keyboard focus.
	ui bool mMenuLogged;
	ui int mAnswerTicks;

	override void UiTick()
	{
		Menu m = Menu.GetCurrentMenu();
		if (m == null)
		{
			mMenuLogged = false;
			mAnswerTicks = 0;
			return;
		}
		let cm = FZChoiceMenu(m);
		if (cm == null) return;

		if (!mMenuLogged)
		{
			mMenuLogged = true;
			Console.Printf("FZ: gate menu open");
		}

		CVar a = CVar.FindCVar("fz_autoanswer");
		if (a == null || a.GetInt() == 0) return;
		mAnswerTicks++;
		if (mAnswerTicks == 15)
		{
			// option A is the correct answer in all six gates
			m.MenuEvent(Menu.MKEY_Enter, false);
		}
	}


}
