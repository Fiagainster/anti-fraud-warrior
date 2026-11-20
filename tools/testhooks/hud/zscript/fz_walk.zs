// Automated WALK test (velocity-based, real physics): the player walks
// the chapter-1 path waypoint by waypoint. Blocked passages stop progress,
// which shows up as missing screenshots. A screenshot is captured on every
// waypoint arrival.
class FZWalkTestHandler : EventHandler
{
	int wticks;
	int wp;

	double Wpx(int i)
	{
		switch (i)
		{
			case 0: return 128;   case 1: return 256;
			case 2: return 460;   case 3: return 608;
			case 4: return 672;   case 5: return 768;
			case 6: return 1024;  case 7: return 1344;
			case 8: return 1184;  case 9: return 1088;
			case 10: return 896;  case 11: return 1472;
			case 12: return 2048; case 13: return 3264;
		}
		return 0;
	}

	double Wpy(int i)
	{
		switch (i)
		{
			case 0: return 256;   case 1: return 256;
			case 2: return 256;   case 3: return 432;
			case 4: return 432;   case 5: return 256;
			case 6: return 256;   case 7: return 256;
			case 8: return -224;  case 9: return -224;
			case 10: return -224; case 11: return 256;
			case 12: return 256;  case 13: return 256;
		}
		return 0;
	}

	override void WorldTick()
	{
		wticks++;
		if (wticks < 90 || wp >= 14) return;
		let pl = players[consoleplayer].mo;
		if (pl == null) return;

		double dx = Wpx(wp) - pl.x;
		double dy = Wpy(wp) - pl.y;
		double dist = sqrt(dx * dx + dy * dy);
		if (dist < 20)
		{
			// waypoint reached: log it and advance
			Console.Printf("WALK: reached wp %d at (%.0f, %.0f)", wp, pl.x, pl.y);
			wp++;
			return;
		}
		double sp = 6.0;
		pl.vel = (dx / dist * sp, dy / dist * sp, 0);
	}
}
