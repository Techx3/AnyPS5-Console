# Changelog

Release notes for AnyPS5 Console. The section of each version is the description of its GitHub release.

## Unreleased

_No changes yet._

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
