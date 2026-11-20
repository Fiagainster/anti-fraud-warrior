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
	bool bossKilled;
	// sidestep burst: a monster standing in a 64-unit doorway blocks the
	// straight line for ever (the bot has no path finder), so after a stuck
	// report it walks diagonally for a moment and slips past.
	int sideTicks;
	double sideDir;
	int stuckSameWp;
	int stuckWpIdx;

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
		bossKilled = false;
		stuckSameWp = 0;
		stuckWpIdx = -1;
		sideTicks = 0;
		retries = 0;
		// a level restart (death without a save) re-arms the route, so the
		// one-shot markers must be cleared or later chapters stay silent
		routeDone = false;
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

		// test seam: real invulnerability for the chapters that run WITH
		// monsters. Clamping health only survives chip damage - a point
		// blank shotgun blast (7 pellets) or a baron swipe still takes the
		// bot from 100 to dead in one tic, which restarts the chapter and
		// throws the waypoint bookkeeping away. Refreshed every second so
		// the 30 s powerup can never lapse.
		CVar god = CVar.FindCVar("fz_bot_god");
		if (god != null && god.GetInt() == 1 && (wticks % 35) == 0)
			pl.GiveInventory("PowerInvulnerable", 1);

		// test seam: keep the guns fed. The map economy is two shell boxes
		// for the whole chapter; firing non-stop at every blocker empties it
		// half way and the bot then welds itself to a monster standing in a
		// 64 unit doorway (it cannot kill what it cannot shoot, and it has
		// no path finder to walk around). Topped up once a second.
		CVar am = CVar.FindCVar("fz_bot_ammo");
		if (am != null && am.GetInt() == 1 && (wticks % 35) == 0)
		{
			pl.GiveInventory("Shell", 24);
			pl.GiveInventory("Clip", 40);
		}

		CVar combat = CVar.FindCVar("fz_bot_combat");
		if (combat != null && combat.GetInt() == 1) BotCombat(pl);

		// test seam: drop the chapter boss as soon as the bot is inside the
		// boss room, so WorldThingDied -> FZMasterProof -> FZStage3 gets
		// exercised deterministically. This is the same damage path a player
		// shotgun would take (no console command, no aim dependence).
		CVar kb = CVar.FindCVar("fz_bot_killboss");
		if (kb != null && kb.GetInt() == 1 && !bossKilled && wp >= 23)
		{
			ThinkerIterator bi = ThinkerIterator.Create('BaronOfHell');
			for (let b = Actor(bi.Next()); b != null; b = Actor(bi.Next()))
			{
				if (b.health <= 0) continue;
				b.DamageMobj(b, pl, 100000, 'Normal');
				bossKilled = true;
				Console.Printf("FZBOT: boss downed at (%.0f, %.0f)", b.Pos.X, b.Pos.Y);
			}
		}

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
			// one shot only: this branch is reached on every following tic,
			// and MakeScreenShot() per tic produced hundreds of truncated
			// (unreadable) PNGs.
			if (!routeDone)
			{
				routeDone = true;
				Console.Printf("FZBOT: TIMEOUT at (%.0f, %.0f) wp=%d", pl.Pos.X, pl.Pos.Y, wp);
				LevelLocals.MakeScreenShot();
			}
			return;
		}

		double dx = Wpx(wp) - pl.Pos.X;
		double dy = Wpy(wp) - pl.Pos.Y;
		double dist = sqrt(dx * dx + dy * dy);
		if (dist < 20)
		{
			Console.Printf("FZBOT: reached wp %d (%.0f, %.0f) ev=%d red=%d st1=%d st2=%d st3=%d",
				wp, pl.Pos.X, pl.Pos.Y, pl.CountInv("FZEvidence"),
				pl.CountInv("RedCard"), pl.CountInv("FZStage1"),
				pl.CountInv("FZStage2"), pl.CountInv("FZStage3"));
			LevelLocals.MakeScreenShot();
			wp++;
			stuckTicks = 0;
			lastX = pl.Pos.X;
			lastY = pl.Pos.Y;
			// test seam: skip the three evidence alcoves (negative test -
			// with no evidence at all the trial door must stay locked)
			CVar sk = CVar.FindCVar("fz_bot_skip_evidence");
			if (sk != null && sk.GetInt() == 1 && wp == 7) wp = 16;
			return;
		}
		// test seam: a wrong answer must not soft-lock the chapter. Walk back
		// to gate A's terminal and touch it again - the menu re-arms once the
		// 4 s per-terminal cooldown is out - paired with fz_autoanswer 3
		// (wrong on the first visit, correct on the return visit).
		CVar rt = CVar.FindCVar("fz_bot_retry");
		if (rt != null && rt.GetInt() == 1 && retries < 4
			&& wp >= 5 && pl.CountInv("FZStage1") < 1)
		{
			retries++;
			wp = 3;
			Console.Printf("FZBOT: retry gate A (#%d)", retries);
			return;
		}
		double sp = 5.0;
		double vx = dx / dist * sp;
		double vy = dy / dist * sp;
		if (sideTicks > 0)
		{
			sideTicks--;
			vx += -dy / dist * sp * sideDir;
			vy += dx / dist * sp * sideDir;
		}
		pl.vel = (vx, vy, pl.vel.z);

		stuckTicks++;
		if (stuckTicks >= 35)
		{
			if (abs(pl.Pos.X - lastX) < 4 && abs(pl.Pos.Y - lastY) < 4)
			{
				Console.Printf("FZBOT: stuck at (%.0f, %.0f) -> wp %d", pl.Pos.X, pl.Pos.Y, wp);
				if (stuckTicks == 35) NearbyProbe(pl);
				sideTicks = 28;
				sideDir = (random(0, 1) == 0) ? -1.0 : 1.0;
				// Three strikes on the same waypoint: the bot was shoved off
				// the approach line. The evidence alcove mouths are offset 32
				// units west of the alcove centre (mouth 1216..1280, crate at
				// 1280), so once a monster pushes the bot back into the
				// corridor the straight line to the crate runs into the wall
				// and no amount of sidestepping fixes it. Step back to the
				// previous waypoint - always the mouth - and re-enter.
				if (stuckWpIdx == wp) stuckSameWp++;
				else { stuckWpIdx = wp; stuckSameWp = 1; }
				if (stuckSameWp >= 3 && wp > 0)
				{
					wp--;
					stuckSameWp = 0;
					Console.Printf("FZBOT: backtrack to wp %d", wp);
				}
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
	ui int mWrongOnceId;
	int retries;

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
			// fz_autoanswer 1 = option A (correct in all six gates)
			// fz_autoanswer 2 = option B on purpose: the negative test that
			// the choice gates really veto the trial door
			// fz_autoanswer 3 = wrong the first time this gate is touched,
			// correct on the return visit. Pairs with fz_bot_retry to prove a
			// wrong answer costs time, not the chapter.
			int mode = a.GetInt();
			if (mode == 3)
			{
				// gate A (id ends in 1) is answered wrong on its first visit
				// and correct on the return visit; gate B is answered
				// correctly straight away, so the chapter can still be
				// finished once gate A is retried.
				if (cm.mGateId % 10 == 1 && cm.mGateId != mWrongOnceId)
				{
					mWrongOnceId = cm.mGateId;
					mode = 2;
				}
				else mode = 1;
			}
			if (mode == 2) m.MenuEvent(Menu.MKEY_Down, false);
			m.MenuEvent(Menu.MKEY_Enter, false);
		}
	}


}
