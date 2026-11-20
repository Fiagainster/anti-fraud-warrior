@echo off
setlocal
set ROOT=%~dp0

rem NOTE: keep this file pure ASCII. cmd.exe parses batch files in the
rem system codepage (GBK on Chinese Windows), so UTF-8 Chinese text here
rem corrupts the parser.

if not exist "%ROOT%build\fanzha-demo.pk3" (
  echo [Anti-Fraud Warrior] Missing build\fanzha-demo.pk3
  echo Run this first: python tools\build.py
  pause
  exit /b 1
)

"%ROOT%vendor\uzdoom-5.0.3\uzdoom.exe" -config "%ROOT%config\uzdoom.cfg" -iwad "%ROOT%vendor\freedoom-0.13.0\freedoom1.wad" -file "%ROOT%build\maps\FZ01.wad" -file "%ROOT%build\maps\FZ02.wad" -file "%ROOT%build\maps\FZ03.wad" -file "%ROOT%build\fanzha-demo.pk3" +set vid_fullscreen 0 +set vid_defwidth 1280 +set vid_defheight 720 +set language "zh-Hans" +set gl_texture_filter 0 %*
endlocal
