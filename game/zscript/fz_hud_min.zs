// Dependency-free minimal HUD used for bisect tests. NOT included by the
// production zscript.txt.
class FZStatusBar : BaseStatusBar
{
	HUDFont mWhite;

	override void Init()
	{
		Super.Init();
		SetSize(48, 320, 200);
		Font f0 = "fzfont";
		mWhite = HUDFont.Create(f0, f0.GetCharWidth("0"), Mono_CellLeft, 1, 1);
		Console.Printf("FZ HUD MIN: ready");
	}

	override void Draw(int state, double TicFrac)
	{
		if (Menu.GetCurrentMenu() != null) return;
		Super.Draw(state, TicFrac);
		if (state == HUD_StatusBar)
		{
			BeginStatusBar();
			DrawImage("FZPANEL", (0, 152), DI_ITEM_LEFT_TOP);
			DrawString(mWhite, "反诈战士", (6, 155), DI_NOSHADOW, Font.CR_UNTRANSLATED);
		}
	}
}
