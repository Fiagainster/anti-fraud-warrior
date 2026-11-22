// 反诈战士 · choice gates
// Gate data (ui), the choice menu (ui), and play-side outcomes.
// Scope map: play (gate pickup) -> HUD notices lock (ui) -> FZChoiceMenu
// -> SendNetworkEvent (clearscope) -> FZPlayEvents.NetworkProcess (play).

// ------------------------------------------------------------ gate data --

class FZGateDef : Object ui
{
	String title;
	String scenario;
	String optA;
	String optB;
	int correct; // 0 = A, 1 = B
}

class FZGateData ui
{
	// All fzfont-drawn text lives here; keep lines short enough to wrap well.
	static FZGateDef Get(int id)
	{
		let d = new("FZGateDef");
		switch (id)
		{
			case 11:
				d.title = "刷单深渊 · 抉择一";
				d.scenario = "群主“闪电哥”发来消息：\n新手单 29 元立返 35，已到账。\n现在有个大单：垫付 299，\n十分钟后返 380。\n“兄弟，错过这村没这店。”";
				d.optA = "拒绝垫付，举报该群";
				d.optB = "垫付 299 元，抢下大单";
				d.correct = 0;
				break;
			case 12:
				d.title = "刷单深渊 · 抉择二";
				d.scenario = "“客服”来电称系统卡单，\n要求下载某会议 APP，\n并打开屏幕共享，\n“由专员指导你完成返款”。";
				d.optA = "挂断电话，拉黑举报";
				d.optB = "下载 APP，共享屏幕";
				d.correct = 0;
				break;
			case 21:
				d.title = "装备黑市 · 抉择一";
				d.scenario = "卖家报价：传说皮肤 80 元。\n“平台要抽成 15%，\n加我微信直接转，\n再便宜你 50，秒发货。”";
				d.optA = "只走官方担保交易";
				d.optB = "加微信，直接转账";
				d.correct = 0;
				break;
			case 22:
				d.title = "装备黑市 · 抉择二";
				d.scenario = "群里弹出链接：\n“周年庆 3 折皮肤礼包”，\n点击后要求输入游戏\n账号和密码“验证资格”。";
				d.optA = "识破钓鱼，直接退出";
				d.optB = "输入账号密码";
				d.correct = 0;
				break;
			case 31:
				d.title = "警服幻影 · 抉择一";
				d.scenario = "“王警官”来电：你涉嫌洗钱，\n案件代号 0927，\n“把生活费转入安全账户，\n配合资金清查，\n否则立刻网上追逃”。";
				d.optA = "挂断，拨打 96110 核实";
				d.optB = "转账到安全账户";
				d.correct = 0;
				break;
			case 32:
				d.title = "警服幻影 · 抉择二";
				d.scenario = "对方发来“公安协查 APP”，\n要求下载并共享屏幕取证，\n“案件涉密，禁止告诉\n任何人，包括家人。”";
				d.optA = "识破话术，告诉家人";
				d.optB = "下载 APP，配合取证";
				d.correct = 0;
				break;
			default:
				d.title = "未知抉择";
				d.scenario = "";
				d.optA = "确认";
				d.optB = "取消";
				d.correct = 0;
				break;
		}
		return d;
	}

	// Banner texts shown by the HUD. ids are global.
	static String MsgText(int id)
	{
		switch (id)
		{
			case 101: return "【简报】大学生小陈被拉进“闪电赚钱群”，\n动动手指日赚三百？潜入骗局网络空间，\n净化妖魔，收集证据！";
			case 102: return "【提示】走近闪烁的“数据终端”触发抉择，\n选错会掉警惕值并引来妖魔伏击，\n但走开再回来可以重新作答。";
			case 103: return "【提示】集齐 3 件证据、并答对两道抉择，\n审判门才会打开；击败幕后主谋才能结案。";
			case 201: return "【简报】小陈的室友想买 3 折“内部价”皮肤，\n进了黑市交易群。潜入黑市空间，\n揪出暗影商人！";
			case 202: return "【提示】黑市里诱惑更多，站稳脚跟：\n远离一切脱离平台的交易。\n答错可以走开再回来重答，不会被锁死。";
			case 203: return "【提示】钓鱼链接最爱伪装“官方活动”，\n任何索要账号密码的活动都是假的。";
			case 301: return "【简报】“王警官”来电恐吓小陈：\n涉案要判刑！潜入幻影空间，\n拆穿假警察的真面目！";
			case 302: return "【提示】记住：公检法不会电话办案，\n更没有“安全账户”。\n答错可以走开再回来重答，不会被锁死。";
			case 303: return "【提示】“案件保密，不许告诉家人”\n是骗子的心虚——告诉家人就是反诈！";
			case 901: return "获得一件证据碎片！集齐 3 件可开启审判门。";
			case 902: return "幕后主谋已倒下！拾取掉落的\n【主谋证据】，前往出口结案。";
			case 903: return "结案！主谋已伏法，前往出口开关。";
			case 904: return "【证据链完整】审判门已解锁，\n走到红锁门前按 E 进入。";
			case 905: return "【提示】证据链已齐，但还有抉择没答对——\n回到闪烁终端重新作答，审判门才会开。";
			case 111: return "【识破】凡是让你先垫资的刷单都是诈骗——\n先给甜头后宰客，垫付的钱有去无回！";
			case 121: return "【识破】共享屏幕=把银行卡密码拱手送人！\n卡单、解冻、激活全是话术。";
			case 211: return "【识破】脱离平台私下交易=放弃一切保障，\n转账瞬间对方立刻拉黑跑路。";
			case 221: return "【识破】低价皮肤是诱饵，\n索要账号密码的“官方活动”都是钓鱼！";
			case 311: return "【识破】公检法不设“安全账户”，\n凡是要求转账的都是诈骗！";
			case 321: return "【识破】真警察绝不会电话要求下载 APP、\n共享屏幕“取证”！";
			case 112: return "【正确】拒绝垫付！刷单返利是骗局，\n防骗盾+1，获得证据碎片。";
			case 122: return "【正确】拉黑举报！不给骗子共享屏幕，\n防骗盾+1，获得证据碎片。";
			case 212: return "【正确】坚持官方平台！担保交易才安全，\n防骗盾+1，获得证据碎片。";
			case 222: return "【正确】不输密码！钓鱼链接无处遁形，\n防骗盾+1，获得证据碎片。";
			case 312: return "【正确】拨 96110 核实！假警察当场露馅，\n防骗盾+1，获得证据碎片。";
			case 322: return "【正确】告诉家人！反诈第一步就是别保密，\n防骗盾+1，获得证据碎片。";
		}
		return "";
	}
}

// ------------------------------------------------------------- menu -----

class FZChoiceMenu : Menu
{
	int mGateId;
	int mSelection;
	bool mCommitted;
	FZGateDef mDef;
	BrokenLines mScenario;
	Font mFont;

	// The canvas cannot be the classic 320x200 here. The CJK atlas is 16 px
	// tall, so title(32) + 5 scenario lines + 2 options + hint need ~190
	// units, while a 320-wide canvas only yields ~172 on a 16:9 window -
	// the hint line got clipped by the window edge. Widening the canvas to
	// 400 shrinks the glyphs relative to the frame and leaves room for
	// every row, with the height derived from the real aspect ratio.
	private int MenuW() { return 400; }

	void Setup(int gid)
	{
		Init(Menu.GetCurrentMenu());
		mGateId = gid;
		mSelection = 0;
		mCommitted = false;
		mFont = "fzfont";
		mDef = FZGateData.Get(gid);
		mScenario = mFont.BreakLines(mDef.scenario, MenuW() - 40);
	}

	private int VirtualHeight()
	{
		int sw = int(screen.GetWidth());
		int sh = int(screen.GetHeight());
		if (sw <= 0 || sh <= 0) return 250;
		int vh = int(MenuW() * double(sh) / double(sw));
		if (vh < 160) vh = 160;
		if (vh > 330) vh = 330;
		return vh;
	}

	private void DrawVText(Font f, int color, double x, double y, String s,
		double scale = 1.0, int vh = 250)
	{
		// No DTA_KeepRatio: it would force the canvas back to a fixed 4:3
		// ratio and let the bottom overflow again. 400 x vh already
		// matches the window aspect, so the mapping stays 1:1.
		screen.DrawText(f, color, x, y, s,
			DTA_VirtualWidth, MenuW(), DTA_VirtualHeight, vh,
			DTA_ScaleX, scale, DTA_ScaleY, scale);
	}

	override void Drawer()
	{
		screen.Dim(0, 0.78, 0, 0, screen.GetWidth(), screen.GetHeight());

		int vh = VirtualHeight();
		int fh = mFont.GetHeight();
		double cx = MenuW() / 2.0;

		// Bottom-up: the hint owns the last row with a safe margin, the two
		// options sit directly above it, and the scenario gets what is left.
		double hintY = vh - fh - 10;
		double optBlock = (fh + 6) * 2;
		double y = 8;

		int tw = mFont.StringWidth(mDef.title);
		DrawVText(mFont, Font.CR_UNTRANSLATED, cx - tw, y, mDef.title, 2.0, vh);
		y += fh * 2 + 8;

		int c = mScenario.Count();
		double bodyAvail = hintY - optBlock - 8 - y;
		double lineh = fh + 2;
		if (c > 0 && c * lineh > bodyAvail)
			lineh = max(fh - 2, int(bodyAvail / c));
		for (int i = 0; i < c; i++)
		{
			int lw = mScenario.StringWidth(i);
			DrawVText(mFont, Font.CR_UNTRANSLATED, cx - lw / 2.0, y,
				mScenario.StringAt(i), 1.0, vh);
			y += lineh;
		}

		y = hintY - optBlock;
		for (int i = 0; i < 2; i++)
		{
			bool sel = (mSelection == i);
			String opt = (i == 0) ? mDef.optA : mDef.optB;
			Font f;
			if (sel) f = "fzfont_green";
			else f = "fzfont_gray";
			int cw = mFont.StringWidth(opt);
			double ox = cx - cw / 2.0 - 20;
			DrawVText(f, Font.CR_UNTRANSLATED, ox, y, opt, 1.0, vh);
			if (sel && (Menu.MenuTime() % 8) < 6)
			{
				DrawVText(mFont, Font.CR_UNTRANSLATED, ox - 18, y, ">", 1.0, vh);
			}
			y += fh + 6;
		}

		String hint = "[↑/↓] 选择   [回车] 确认";
		int hw = mFont.StringWidth(hint);
		DrawVText(mFont, Font.CR_UNTRANSLATED, cx - hw / 2.0, hintY, hint, 1.0, vh);
	}

	private void Commit(int choice)
	{
		if (mCommitted) return;
		mCommitted = true;
		EventHandler.SendNetworkEvent('FZGateChoice', mGateId, choice);
		Close();
	}

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		switch (mkey)
		{
			case MKEY_Up:
			case MKEY_Left:
				mSelection = 1 - mSelection;
				MenuSound("menu/cursor");
				return true;
			case MKEY_Down:
			case MKEY_Right:
				mSelection = 1 - mSelection;
				MenuSound("menu/cursor");
				return true;
			case MKEY_Enter:
				MenuSound("menu/choose");
				Commit(mSelection);
				return true;
			case MKEY_Back:
				MenuSound("menu/backup");
				Commit(-1);
				return true;
		}
		return Super.MenuEvent(mkey, fromcontroller);
	}

	override bool MouseEvent(int type, int x, int y)
	{
		return Super.MouseEvent(type, x, y);
	}
}

// ------------------------------------------------------ play outcomes --

class FZPlayEvents : EventHandler
{
	// gate outcome config as primitive-returning helpers (struct assignment
	// is not implemented in the current ZScript compiler)
	private int GateCorrect(int gid)
	{
		// option A (index 0) is the correct answer for every gate; see
		// FZGateData.Get. The two must stay in sync.
		switch (gid)
		{
			case 11: case 12: case 21: case 22: case 31: case 32: return 0;
		}
		return 0;
	}

	private int GateDmg(int gid)
	{
		switch (gid)
		{
			// chapter 3's fake police come down harder on a wrong answer
			case 31: case 32: return 30;
			case 11: case 12: case 21: case 22: return 25;
		}
		return 25;
	}

	private name GateAmb(int gid)
	{
		// Must be our own classes, not the IWAD names: Ambush() spawns with
		// NO_REPLACE (we do not want the map's corpse/replacement bookkeeping),
		// and a raw 'DoomImp' would then appear with the original Freedoom look.
		switch (gid)
		{
			case 11: return 'FZShill';
			case 12: return 'FZRunner';
			case 21: return 'FZScalper';
			case 22: return 'FZScalper';
			case 31: return 'FZRunner';
			case 32: return 'FZFakeCop';
		}
		return 'FZShill';
	}

	private int GateAmbCount(int gid)
	{
		switch (gid)
		{
			case 11: return 3;
			case 12: return 2;
			case 21: return 3;
			case 22: return 4;
			case 31: return 3;
			case 32: return 2;
		}
		return 3;
	}

	private int GateMsgWrong(int gid)
	{
		switch (gid)
		{
			case 11: return 111;
			case 12: return 121;
			case 21: return 211;
			case 22: return 221;
			case 31: return 311;
			case 32: return 321;
		}
		return 0;
	}

	private int GateMsgRight(int gid)
	{
		switch (gid)
		{
			case 11: return 112;
			case 12: return 122;
			case 21: return 212;
			case 22: return 222;
			case 31: return 312;
			case 32: return 322;
		}
		return 0;
	}

	private name GateStage(int gid)
	{
		switch (gid)
		{
			case 11: case 21: case 31: return 'FZStage1';
			case 12: case 22: case 32: return 'FZStage2';
		}
		return 'FZStage1';
	}

	// ----------------------------------------------------------- chapter --

	// Per-chapter state reset.
	//
	// A player keeps its whole inventory when travelling to the next map
	// (that is how Doom hands weapons and keys down), and our tokens ride
	// along with it. Chapter 2 therefore used to start holding chapter 1's
	// FZStage1/FZStage2, its 3 evidence pieces and its RedCard, which broke
	// the flow both ways:
	//   * FZGateTerminal saw "this gate's stage token is already carried"
	//     and closed itself without ever showing a menu -> no evidence,
	//   * the trial door was already unlocked (or, once the evidence count
	//     was stale at 3 while the card was gone, stayed locked forever
	//     because the crates refuse to hand out a 4th piece).
	// Everything chapter-scoped is cleared here, so each map starts from
	// zero and the door has to be earned again.
	//
	// Safe for savegames: the engine skips WorldLoaded for non-static
	// handlers when restoring a save (src/events.cpp), so a mid-chapter load
	// keeps the inventory the save was made with.
	private static void ClearChapterState(Actor mo)
	{
		mo.TakeInventory("FZEvidence", 3);
		mo.TakeInventory("RedCard", 1);
		mo.TakeInventory("FZStage1", 1);
		mo.TakeInventory("FZStage2", 1);
		mo.TakeInventory("FZStage3", 1);
		mo.TakeInventory("FZGateLock", 1);
		mo.TakeInventory("FZGateCool", 1);
		// stale banners must not survive the chapter change either
		mo.TakeInventory("FZMsg1", 1);
		mo.TakeInventory("FZMsg2", 1);
		mo.TakeInventory("FZMsg3", 1);
	}

	override void WorldLoaded(WorldEvent e)
	{
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || players[i].mo == null) continue;
			let mo = players[i].mo;
			ClearChapterState(mo);
			CVar dbg = CVar.FindCVar("fz_bot");
			if (dbg != null && dbg.GetInt() == 1)
				Console.Printf("FZDBG: chapter reset %s ev=%d red=%d st1=%d st2=%d st3=%d",
					level.mapname, mo.CountInv("FZEvidence"),
					mo.CountInv("RedCard"), mo.CountInv("FZStage1"),
					mo.CountInv("FZStage2"), mo.CountInv("FZStage3"));
		}
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == 'FZGateChoice') GateChoice(e.Player, e.Args[0], e.Args[1]);
	}

	private void GateChoice(int pnum, int gid, int choice)
	{
		if (pnum < 0 || pnum >= MAXPLAYERS) return;
		let pl = players[pnum].mo;
		if (pl == null) return;

		// always release the lock so other gates can trigger, and cool the
		// terminal down so standing inside it doesn't instantly re-open
		pl.TakeInventory("FZGateLock", 1);
		pl.GiveInventory("FZGateCool", 1);

		// test seam: only prints when the automation cvar exists
		CVar dbg = CVar.FindCVar("fz_bot");
		if (dbg != null && dbg.GetInt() == 1)
			Console.Printf("FZDBG: gate %d choice %d ev=%d", gid, choice,
				pl.CountInv("FZEvidence"));

		if (choice < 0) return; // walked away, may retry (cool clears on next touch)

		if (choice == GateCorrect(gid))
		{
			pl.GiveInventory(GateStage(gid), 1);
			pl.GiveInventory("ArmorBonus", 10); // 防骗盾 +10
			FZMsgItemBase.Push(pl, GateMsgRight(gid), 300);
			// Granted last so the "chain complete" banner (904) wins over
			// the per-choice banner when this happens to be the third piece.
			FZEvidenceChain.Grant(pl);
		}
		else
		{
			pl.DamageMobj(null, null, GateDmg(gid), 'FZFraud');
			Ambush(pl, gid);
			FZMsgItemBase.Push(pl, GateMsgWrong(gid), 340);
		}

		// Per-terminal bookkeeping, both branches: a correct answer retires
		// the terminal (done), and every answer puts it on cooldown so a
		// player standing inside it is not force-fed the menu again a tic
		// later (that used to chain-damage players to death and restart the
		// chapter). Walk out and back in to retry after mCool ticks.
		// Terminals share tid 3942; tid 0 is an empty iterator - never use it.
		let it = level.CreateActorIterator(3942);
		for (let a = it.Next(); a != null; a = it.Next())
		{
			let g = FZGateTerminal(a);
			if (g == null || g.GateId() != gid) continue;
			if (choice == GateCorrect(gid)) g.done = true;
			g.StartCool(FZGateTerminal.CoolTics());
		}
	}

	private void Ambush(Actor pl, int gid)
	{
		name t = GateAmb(gid);
		int count = GateAmbCount(gid);
		int baseang = random(0, 255);
		for (int i = 0; i < count; i++)
		{
			double dist = 128 + random(0, 48);
			double ang = baseang * 1.40625 + i * (360.0 / count);
			Vector3 pos = pl.Vec3Angle(dist, ang, 8.0);
			Actor.Spawn(t, pos, NO_REPLACE);
		}
	}

	override void WorldThingDied(WorldEvent e)
	{
		if (e.Thing == null) return;
		// 章节 Boss 被打倒：掉主谋证据。
		// 怪物已换成自制类（fz_actors.zs 里 FZChairman replaces BaronOfHell），
		// 类名不再叫 BaronOfHell，所以两个名字都要认；只删掉旧的判断会让
		// 结局永远不触发。
		name cls = e.Thing.GetClassName();
		if (cls != 'BaronOfHell' && cls != 'FZChairman') return;
		// chapter boss downed: drop the master proof
		Actor.Spawn("FZMasterProof", e.Thing.Pos, NO_REPLACE);
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (playeringame[i] && players[i].mo != null) FZMsgItemBase.Push(players[i].mo, 902, 280);
		}
	}

	override void PlayerDied(PlayerEvent e)
	{
		// make sure a stuck lock can't wedge the gate system after respawn
		if (players[e.PlayerNumber].mo != null) players[e.PlayerNumber].mo.TakeInventory("FZGateLock", 1);
	}
}
