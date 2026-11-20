// Test-only hook, Run B: force the main menu open from UiTick (proven to
// work) and capture it once enough UI ticks have elapsed. The launcher caps
// the framerate at 35 so tick counts translate to wall time deterministically
// (900 ticks ~ 26s, well past map load).

class FZSmokeMenuHandler : EventHandler
{
	ui int uticks;

	override void UiTick()
	{
		Menu.SetMenu('MainMenu');
		uticks++;
		if (uticks == 900)
		{
			LevelLocals.MakeScreenShot();
		}
	}
}
