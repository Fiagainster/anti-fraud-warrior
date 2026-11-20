// 反诈战士 · status bar
// Live stats row + objective + message banner. All CJK text uses the
// pre-colored fzfont families (palette translations darken truecolor glyphs).
// Also watches for FZGateLock (set by choice-gate pickups in play scope) and
// opens the choice menu from the ui side — the only scope-clean way to push
// a custom menu object.

class FZStatusBar : BaseStatusBar
{
	HUDFont mWhite;
	HUDFont mRed;
	HUDFont mBlue;
	HUDFont mGold;
	HUDFont mGreen;
	HUDFont mCyan;
	HUDFont mYellow;
	HUDFont mGray;

	override void Init()
	{
		Super.Init();
		SetSize(48, 320, 200);

		Font f0 = "fzfont";
		Font f1 = "fzfont_red";
		Font f2 = "fzfont_blue";
		Font f3 = "fzfont_gold";
		Font f4 = "fzfont_green";
		Font f5 = "fzfont_cyan";
		Font f6 = "fzfont_yellow";
		Font f7 = "fzfont_gray";
		mWhite = HUDFont.Create(f0, 0, Mono_Off, 1, 1);
		mRed = HUDFont.Create(f1, 0, Mono_Off, 1, 1);
		mBlue = HUDFont.Create(f2, 0, Mono_Off, 1, 1);
		mGold = HUDFont.Create(f3, 0, Mono_Off, 1, 1);
		mGreen = HUDFont.Create(f4, 0, Mono_Off, 1, 1);
		mCyan = HUDFont.Create(f5, 0, Mono_Off, 1, 1);
		mYellow = HUDFont.Create(f6, 0, Mono_Off, 1, 1);
		mGray = HUDFont.Create(f7, 0, Mono_Off, 1, 1);

		Console.Printf("FZ HUD: ready, canPrintCN=%s", f0.CanPrint("反诈战士") ? "yes" : "no");
	}

	// -- helpers -----------------------------------------------------------

	private int StageCount()
	{
		let mo = CPlayer == null ? null : CPlayer.mo;
		if (mo == null) return 0;
		int s = 0;
		if (mo.CountInv("FZStage1") > 0) s = 1;
		if (mo.CountInv("FZStage2") > 0) s = 2;
		if (mo.CountInv("FZStage3") > 0) s = 3;
		return s;
	}

	private String ObjectiveText()
	{
		int s = StageCount();
		if (level.mapname == "FZ01")
		{
			if (s == 0) return "调查刷单群";
			if (s == 1) return "识破共享屏幕陷阱";
			if (s == 2) return "击败群主闪电哥";
		}
		else if (level.mapname == "FZ02")
		{
			if (s == 0) return "潜入游戏黑市";
			if (s == 1) return "识破钓鱼链接";
			if (s == 2) return "击败暗影商人";
		}
		else if (level.mapname == "FZ03")
		{
			if (s == 0) return "接听恐吓来电";
			if (s == 1) return "识破协查APP";
			if (s == 2) return "擒获影子会长";
		}
		return "前往出口结案";
	}

	// -- gate menu opener (ui side) ----------------------------------------

	private void CheckGateMenu()
	{
		let mo = CPlayer == null ? null : CPlayer.mo;
		if (mo == null) return;
		if (Menu.GetCurrentMenu() != null) return;
		if (mo.CountInv("FZGateCool") > 0) return;

		let lock = FZGateLock(mo.FindInventory("FZGateLock"));
		if (lock == null) return;

		let m = new("FZChoiceMenu");
		m.Setup(lock.GateId);
		m.ActivateMenu();
	}

	// -- message banner -----------------------------------------------------

	private void DrawMessages()
	{
		let mo = CPlayer == null ? null : CPlayer.mo;
		if (mo == null) return;

		// message slots expire independently; show the freshest one
		// (largest remaining Life) rather than whichever slot comes first.
		int mid = 0;
		int bestLife = -1;
		for (let inv = mo.Inv; inv != null; inv = inv.Inv)
		{
			let msg = FZMsgItemBase(inv);
			if (msg != null && msg.Amount > 0 && msg.Life > bestLife)
			{
				bestLife = msg.Life;
				mid = msg.MsgId;
			}
		}
		if (mid == 0) return;

		String text = FZGateData.MsgText(mid);
		if (text == "") return;

		Font f = "fzfont";
		let lines = f.BreakLines(text, 300);
		int h = f.GetHeight() + 3;
		int boxh = lines.Count() * h + 10;
		int top = 152 - boxh - 3;

		DrawImage("FZBKPT", (8, top), DI_ITEM_LEFT_TOP, 0.72, (304, boxh));
		double y = top + 5;
		for (int i = 0; i < lines.Count(); i++)
		{
			int lw = lines.StringWidth(i);
			DrawString(mWhite, lines.StringAt(i), (160 - lw / 2.0, y), 0, Font.CR_UNTRANSLATED);
			y += h;
		}
	}

	// -- main draw -----------------------------------------------------------

	override void Draw(int state, double TicFrac)
	{
		// The gate lock must be checked even while other menus are open —
		// otherwise the choice menu can never push itself.
		CheckGateMenu();

		if (Menu.GetCurrentMenu() != null) return;

		Super.Draw(state, TicFrac);

		if (state == HUD_StatusBar)
		{
			// legacy status bar canvases are 4:3-centred: on widescreen the
			// side margins would show the world. Fill them with the panel
			// colour and carry the green rules across the full width.
			int sw = int(screen.GetWidth());
			int sh = int(screen.GetHeight());
			int top = int(GetTopOfStatusBar());
			screen.Dim(0xff0a0d12, 1.0, 0, top, sw, sh - top);
			screen.Dim(0xff00c878, 1.0, 0, top, sw, max(2, sh / 300));
			screen.Dim(0xff007a4d, 1.0, 0, sh - max(2, sh / 360), sw,
				max(2, sh / 360));
		}

		// force the 320x200 virtual space: without forceScaled, images are
		// drawn in screen pixels while strings use virtual units, which
		// leaves the panel narrower than the text row (world shows through).
		BeginStatusBar(true, 320, 200);

		DrawMessages();

		let mo = CPlayer == null ? null : CPlayer.mo;
		if (mo == null) return;

		if (state == HUD_StatusBar)
		{
			DrawImage("FZPANEL", (0, 152), DI_ITEM_LEFT_TOP);

			DrawString(mGreen, "反诈战士", (6, 155), DI_NOSHADOW, Font.CR_UNTRANSLATED);
			DrawString(mRed, String.Format("警惕值 %d", CPlayer.health), (80, 155), DI_NOSHADOW, Font.CR_UNTRANSLATED);
			DrawString(mBlue, String.Format("防骗盾 %d", GetArmorAmount()), (176, 155), DI_NOSHADOW, Font.CR_UNTRANSLATED);
						int ev = mo.CountInv("FZEvidence");
			if (ev > 3) ev = 3;
			DrawString(mGold, String.Format("证据 %d/3", ev), (256, 155), DI_NOSHADOW, Font.CR_UNTRANSLATED);

			DrawString(mWhite, String.Format("进度 %d/3", StageCount()), (6, 174), DI_NOSHADOW, Font.CR_UNTRANSLATED);
			DrawString(mCyan, ObjectiveText(), (80, 174), DI_NOSHADOW, Font.CR_UNTRANSLATED);
			// key indicator: the trial-door key is granted silently, so
			// players kept asking "where is the key?"
			if (mo.CountInv("RedCard") > 0)
				DrawString(mRed, "红卡", (206, 174), DI_NOSHADOW, Font.CR_UNTRANSLATED);
			DrawString(mYellow, "96110", (282, 174), DI_NOSHADOW, Font.CR_UNTRANSLATED);
		}
	}
}
