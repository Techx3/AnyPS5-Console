# Changelog

Release notes for AnyPS5 Console. The section of each version is the description of its GitHub release.

## Unreleased

**Per game**
- Compatibility icon on every cover: *Works*, *Boots* or *Doesn't load*, from your last session or, before playing, from the function check.
- Game profiles: AnyPS5 version, `APS5_*` variables and extra relinker arguments for one game only.
- Trophies: list of the game's trophies with icons, grade and unlock date, per user. Trophy count on the home screen.
- *View in the compatibility list* opens the game on the public page.

**AnyPS5 pull requests**
- The console tells you when an open AnyPS5 PR implements functions your games are missing (*Menu > PRs for your games* and on each game). The compatibility page links those PRs in *Most needed functions*.

**Saves and space**
- Export and import a user's saves and trophies as a zip (previous data is backed up first).
- Automatic save backup to a synced folder (OneDrive, Google Drive) after every session, and restore on another PC.
- *Free up space*: delete converted games of old versions, removed games, versions not in use, or all. Saves are never deleted.

**Home screen**
- The selected game's theme music plays (`snd0.at9`, ATRAC9 decoded with LibAtrac9), with the background music lowered.
- Animated game backgrounds with a crossfade between games. Both can be turned off in *Settings*.

**Other**
- Game modules shipped beside `eboot.bin` (for example Castlevania Dominus Collection, Minecraft) are converted with the game; before, they were reported as missing libraries.
- The function check recognizes game modules by their own module name (for example `dra01.prx` is `libdra01`), as AnyPS5 does: Castlevania Dominus Collection no longer shows 22 missing functions and 5 missing libraries.
- Games go fullscreen with AnyPS5's own F11 toggle, so official AnyPS5 builds work without patches (borderless window as fallback).
- Sets `ANYPS5_FULLSCREEN` and `ANYPS5_USER_NAME` (proposed to AnyPS5) so games open fullscreen directly and show the console user's name.
- Experimental Linux / Steam Deck AppImage (builds AnyPS5 main or forks locally).
- Settings and lists no longer draw over the top bar when scrolled.

## v1.1.6

**First run**
- The console asks whether AnyPS5 is already installed. Pick its folder and it is detected (official main, a fork with its branch, or a stable release), or install Stable, official main or a fork. Playing without AnyPS5 asks again.

**AnyPS5 versions**
- Existing AnyPS5 folders are detected automatically and updated only from their own source; local commits and existing `build/` folders are kept and never deleted.
- *Settings > AnyPS5 version* lists every installed version with its state.
- *Updates > Update all* updates every installed version with changes. Updates and builds run in the background with progress in the top bar, a log view and cancel.
- Several forks supported, each with its own update.

**Compatibility list** ([techx3.github.io/AnyPS5-Compat](https://techx3.github.io/AnyPS5-Compat/))
- Game sessions are reported automatically, no account needed (turn off in *Settings > Compatibility reports*).
- Screenshots of the game window at 2 and 10 minutes.
- Error lines from the whole log are included, not only the last lines.
- A session that ends in a crash is never *Playable*; crashes show their reason (for example `0xC0000005 access violation`).
- Results from forks or modified builds are labeled *not tested on main/release*.
- Missing AnyPS5 builds or tools are no longer reported as *Does not convert*.

**Other**
- Sharper display on high resolutions and Windows display scaling.
- Self-update understands tags like `v.1.1.4`; running from source no longer offers the self-update.
- Wider menus so long options are not cut.
