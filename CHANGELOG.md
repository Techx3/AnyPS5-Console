# Changelog

Release notes for AnyPS5 Console. The section of each version is the description of its GitHub release.

## Unreleased

**Per game**
- Compatibility icon on every cover: *Works*, *Boots* or *Doesn't load*, from your last session or, before playing, from the function check.
- Game profiles: AnyPS5 version, `APS5_*` variables and extra relinker arguments for one game only.
- Trophies: list of the game's trophies with icons, grade and unlock date, per user. Trophy count on the home screen.
- *View in the compatibility list* opens the game on the public page.

**Compatibility settings**
- *Game profile > Compatibility settings*: switch AnyPS5 options per game to work around a known problem (trails or uncleared images, depth, compression keys, frame order, PlayGo data) diagnostic logs (audio, color compression, frame dumps) and performance (overlay at start, GPU and driver time). Only the options your AnyPS5 version has are listed, each with a short explanation.
- On/off settings show *Sí/No* even when "on" is a value other than 1 (*Draw without a queue* showed 0).
- *Shaders* settings: precompile the shaders recorded in earlier sessions on all cores instead of half, and remember up to 4096 pipelines instead of 1024 (both off by default; AnyPS5 already precompiles what earlier sessions used).
- Settings recommended for a game (★) are applied automatically. Crash Bandicoot 4 renders correctly with them (`APS5_KEYS_FILL_CLEAR=1`).
- Compatibility reports include the settings the game ran with, and the list shows them. Sessions with diagnostic settings (logs, frame dumps) are marked and don't rate the game.
- Fewer repeated reports: a session that ends normally and is shorter than a result already reported for the same AnyPS5 version, game version and settings is not sent (crashes always are), and closing a game before its window appears sends nothing.
- A failed conversion now reports the relinker's own error lines, not only "the relinker failed".
- Games without a title ID (a folder with no `sce_sys/param.json`, such as `app0` or `source`) are no longer reported; the title ID is also read from the parent folder of an `app0` dump.

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
- When a game crashes, the error screen shows the exit code in hex with its meaning (for example `0xC0000409 (forced abort)`) and the cause from AnyPS5's log (for example `AGC graphics: storage texture has no committed guest pages`).
- Dumps without PlayGo data (for example Crash Bandicoot 4): when AnyPS5 stops asking for `APS5_PLAYGO_UNLISTED_CHUNKS`, the console sets it for that game (`installed`, or `absent` for titles that need it) and tells you to play again.
- The button hints at the bottom show keyboard keys (Enter, Esc, Tab, F5, M) while you use the keyboard, and controller buttons again when you use the controller.
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
