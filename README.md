# AnyPS5 Console

A console-style launcher for [AnyPS5](https://github.com/boykopovar/AnyPS5): pick your user, browse your PS5 and PC games with a controller, and play. Games are converted with AnyPS5 on first launch and run fullscreen on top of the console.

Personal project by Larimar Studios. It is not affiliated with Sony Interactive Entertainment or with the AnyPS5 project.

## Download

From [Releases](../../releases):

- `AnyPS5Console-Setup-<version>.exe`: installer, no administrator rights needed. Optional task: download the build tools (Git + MinGW-w64 GCC 15.2.0) for the Repository version and forks.
- `AnyPS5Console-<version>-portable.zip`: unzip and run `AnyPS5Console.exe`. Data stays in the `data` folder next to it.
- `AnyPS5Console-<version>-x86_64.AppImage` (experimental): Linux desktop and Steam Deck. `chmod +x` and run. AnyPS5 releases only ship Windows binaries, so on Linux the console builds AnyPS5 main or a fork (install `git cmake ninja-build gcc g++` with your package manager). Data in `~/.local/share/AnyPS5Console`.

The installed version keeps its data in `%LOCALAPPDATA%\AnyPS5Console`. The console updates itself from *Menu* > *Updates* when a new release is out.

## Getting started

1. **Install.** Run `AnyPS5Console-Setup-<version>.exe` (or unzip the portable zip and open `AnyPS5Console.exe`). Windows SmartScreen may warn because the executable is not signed: choose *More info* > *Run anyway*.
2. **Create your user.** After the boot animation, pick *New user*, type a name with the on-screen keyboard (or your keyboard) and press *Done*. Every user has its own saves.
3. **Set up AnyPS5.** The first time you reach the home screen the console asks *Do you have AnyPS5 installed on this PC?*
   - **Yes, choose its folder:** the console detects what it is (official main, a fork with its branch, or a stable release) and selects it.
   - **No, install it now:** choose **Stable** (recommended, nothing to build), **Official main** (built on your PC) or **a fork** (GitHub link). Build tools are downloaded first when needed. It installs in the background.
   - Without AnyPS5 the console asks again when you try to play.
4. **Choose your PS5 games folder.** *Menu* (Start / M) > *Settings* > *PS5 games folder*. Each game is a folder with `eboot.bin` (decrypted ELF or SELF dump), `sce_sys/` and `sce_module/`. Subfolders are scanned up to 4 levels deep.
5. **Play.** Select a game and press A. The first launch converts it (a few seconds to a few minutes) and checks the system functions it needs; if something is missing you see the report and can still try with *Play anyway*. The game opens fullscreen on top of the console and you return when you close it. While playing, the controller Guide button opens a quick menu (return to the game or close it).
6. **PC games (optional).** Steam and Epic Games libraries are detected automatically. Add your own folders or `.exe` files in *Settings* > *PC games*. Press down on the home screen to switch to the PC row.
7. **Language.** *Settings* > *Language* changes the console; *Game language* follows it or can be set to any of the 31 PS5 languages.

## AnyPS5 versions and updates

You can have several AnyPS5 versions installed and choose which one to play with in *Settings* > *AnyPS5 version* (the list shows each one with its state). Converted games are kept per version.

| Version | Where it comes from | How it updates |
|---|---|---|
| Stable | Latest [AnyPS5 release](https://github.com/boykopovar/AnyPS5/releases) (relinker `.exe` + libraries) | Downloads the new release, nothing to build |
| Repository (main) | `boykopovar/AnyPS5` main | Merges main and builds |
| Fork | Any GitHub fork and branch | Merges that fork and builds |

*Menu* > *Updates*:

- **Update all (N)**: updates every installed version that has changes, one after another. Versions you never installed are skipped.
- **Use my existing AnyPS5**: pick the folder of an AnyPS5 you already have; it is detected and updated only from its own source (main from `boykopovar/AnyPS5`, a fork from its own repository). Your local commits and your `build/` folder are kept, and the console never deletes your folder.
- **Add fork (GitHub link)**: `https://github.com/user/AnyPS5` or `.../tree/branch`. The same fork with two branches counts as two versions.
- **Install build tools**: Git + MinGW-w64 GCC 15.2.0 (about 350 MB), needed for main and forks.

Updates and builds run in the background: the top bar shows the progress, *Updates* > *View progress* shows the log, and you can keep playing with any version that is not being updated. A build after an update takes a few minutes; the first build of a version takes longer.

## Compatibility list

Every game session is reported to **[AnyPS5 Compatibility](https://techx3.github.io/AnyPS5-Compat/)**, a public list of how each game runs with AnyPS5. Its data lives in [Techx3/AnyPS5-Compat](https://github.com/Techx3/AnyPS5-Compat).

**How it works**

1. When a game ends (or fails to convert), the console builds a report and sends it. No account is needed.
2. The first report of a game opens an issue titled `[TITLE_ID] Name` in AnyPS5-Compat; later reports are comments on the same issue. One game = one entry, whatever AnyPS5 version or tester sent it.
3. A GitHub Action reads all reports, labels each issue with its status and rebuilds the page about a minute later.
4. A report is only sent when something changed for that game (status, AnyPS5 version, missing functions, screenshots), so playing the same game again does not flood the list.

**Status**

| Status | Meaning |
|---|---|
| Does not convert | AnyPS5 failed to convert the game |
| Does not boot | No game window appeared |
| Boots | Game window, under 2 minutes |
| In game | 2 to 10 minutes, or longer but it crashed |
| Playable | 10 minutes or more in one session without crashing |

A session that ends in a crash is never *Playable*; the page shows it as crashed with its exit code (for example `0xC0000005 (access violation)`). Closing the game yourself is not a crash. Missing AnyPS5 builds or tools on the PC are not reported as *Does not convert*. A result reported on a fork or on main with local changes, but not on official AnyPS5 (stable or main), is tagged **not tested on main/release** (or shows the best official result), so it is clear it was not confirmed there.

**What a report contains**

- Game: title ID, name and version.
- AnyPS5: version in use (channel and commit or release tag) and console version.
- Session: minutes played, exit code, whether you closed it, time until the window appeared.
- System functions the game needs that AnyPS5 is missing (from the function check), and where it stops.
- Log: the error lines of the whole log plus its last lines.
- Screenshots of the game window only (not the desktop) at 2 and 10 minutes.
- Windows version and GPU name, and an anonymous random ID per installation to count testers.

Paths and user names are removed from the log before sending.

**The page** lists every game with its current status, best result and AnyPS5 version, with search and filters. Open a game to see the crash reason, missing functions, log errors and screenshots. *Most needed functions* ranks the functions missing for the most games: a good place to start when implementing functions for AnyPS5 pull requests.

**Turning it off:** *Settings* > *Compatibility reports* > *Turn off reports*. *Sign with my GitHub account* (optional) sends the reports under your GitHub user.

**On each cover** an icon shows how the game did on your PC: green ✓ *Works* (10+ minutes without crashing), amber − *Boots*, red ✕ *Doesn't load*. Before the first session it comes from the function check (*Probably doesn't load* when functions are missing).

**AnyPS5 pull requests for your games:** the console checks every hour which open [AnyPS5 pull requests](https://github.com/boykopovar/AnyPS5/pulls) implement functions your games are missing and tells you (*Menu* > *PRs for your games*, or *Options* on a game).

## Per game

*Options* (Y) on a game:

- **Game profile**: AnyPS5 version used for that game, `APS5_*` environment variables (for example `APS5_FULLSCREEN=0`) and extra relinker arguments. Only that game is affected; changing the arguments reconverts it next time.
- **Trophies**: the trophies AnyPS5 records for the current user, with icons, grade and unlock date (from the game's `sce_sys/trophy2` package).
- **View in the compatibility list**, **PRs that would help it**, **System functions**.

The home screen plays the game's own theme (`sce_sys/snd0.at9`, decoded with [LibAtrac9](native/libatrac9)) when you stay on a game, and its art moves slowly in the background. Both can be turned off in *Settings*.

## Saves and space

- Saves and trophies are kept per user. *Y* on a user: **Export saves and trophies (zip)** and **Import** (what was there is backed up first in `users\<id>\backups`).
- *Settings* > **Save backup to a synced folder**: pick your OneDrive or Google Drive folder and every game session copies that user's saves there (`AnyPS5 Console\<user id>`). *Restore from the backup folder* on the user brings them back on another PC.
- *Settings* > **Free up space**: deletes converted games of versions you no longer have, of games no longer in your folder, of versions you are not using, or all. Saves are never deleted; a game is converted again when you play it.

## Where things are

| What | Installer | Portable |
|---|---|---|
| Settings, users, saves | `%LOCALAPPDATA%\AnyPS5Console` | `data\` next to the `.exe` |
| Converted games | `...\cache\<version>\<title ID>` | same, under `data\` |
| Last game log | `last_run.log` in the converted game folder (*Options* > *Open converted folder*) | |
| Function report | `audit.txt` in the converted game folder | |
| Reports not sent yet | `compat\pending\` in the data folder | |
| Saves and trophies per user | `users\<id>\saves`, `users\<id>\trophies` in the data folder | |
| Crash report of the console | `crash.log` in the data folder | |

## Guía rápida (Español)

1. Ejecuta el instalador (o descomprime el zip portable y abre `AnyPS5Console.exe`). Si Windows SmartScreen avisa: *Más información* > *Ejecutar de todas formas*.
2. Crea tu usuario en "¿Quién está usando el control?" > *Nuevo usuario*. Cada usuario tiene sus propios saves.
3. La primera vez la consola pregunta si ya tienes AnyPS5: elige su carpeta (detecta si es main, un fork o la estable) o instala uno: **Estable** (recomendada), **Main oficial** o **un fork**.
4. *Menú* (Start / M) > *Ajustes* > *Idioma* para poner la consola en español, y *Carpeta de juegos PS5* para elegir dónde están tus dumps.
5. Elige un juego y pulsa A. La primera vez se convierte y se revisan sus funciones; luego abre en pantalla completa y vuelves a la consola al cerrarlo. El botón Guide abre el menú rápido durante el juego.
6. *Ajustes* > *Versión de AnyPS5* para cambiar entre las versiones instaladas. *Actualizaciones* > *Actualizar todo* actualiza todas en segundo plano.
7. Juegos de PC: Steam y Epic se detectan solos; tus carpetas o `.exe` se añaden en *Ajustes* > *Juegos PC*.
8. *Y* sobre un juego: **Perfil del juego** (versión de AnyPS5, variables `APS5_*`, argumentos del relinker solo para ese juego), **Trofeos**, PRs que le ayudarían. *Y* sobre un usuario: exportar o importar sus saves. *Ajustes*: copia de saves en OneDrive/Google Drive y **Liberar espacio**.
9. Cada partida se reporta a la [lista de compatibilidad](https://techx3.github.io/AnyPS5-Compat/): estado, versión de AnyPS5, funciones que faltan, errores del log y capturas a los 2 y 10 minutos, sin rutas ni nombres de usuario. Se desactiva en *Ajustes* > *Reportes de compatibilidad*.

## Features

- Boot sequence, user selection and creation; saves, playtime, favorites and avatar per user.
- PS5 games (decrypted dumps) and PC games (Steam, Epic Games, your own folders and executables) in two rows, with search and sort (recent, A–Z, most played).
- AnyPS5 versions: Stable, Repository (main) and any number of forks, existing installs detected, background updates.
- Check of the system functions a game needs before it starts (`tools/import_audit.py` from AnyPS5).
- Compatibility reports to the public list, with screenshots.
- Fullscreen games with aspect ratio kept, ultrawide included; quick menu with the Guide button.
- Languages: English, 中文, हिन्दी, Español, Français, العربية. The game language follows the console language or can be set separately.
- Compatibility icon on each cover, AnyPS5 pull requests that help your games.
- Game profiles, trophies per user, save export/import and synced backup, free-space cleanup.
- Game theme music (ATRAC9) and animated backgrounds.
- Self-update, background music (can be turned off). Experimental Linux / Steam Deck AppImage.

## Requirements

- Windows 10/11 x64 with a Vulkan GPU driver (or Linux x86_64 for the experimental AppImage).
- Stable version: nothing else.
- Repository version and forks: Git, CMake, Ninja and MinGW-w64 GCC 15.2.0 (WinLibs `x86_64-ucrt-posix-seh`). The console can download them. An existing build of your own (any generator or compiler) is reused.

## Controls

| Controller | Keyboard | Action |
|---|---|---|
| A | Enter | Play / select |
| B | Esc | Back / cancel |
| Y | Tab | Options |
| X | F5 | Reload games |
| Start / Back | M | Menu |
| Guide (in game) | | Quick menu |
| D-pad / stick | Arrows | Move |
| | F11 | Toggle fullscreen |

## Run from source

```
pip install -r requirements.txt
python src/main.py
```

Data goes to `data/` next to `src/`.

## Build

GitHub Actions (`.github/workflows/build.yml`) builds the executable with PyInstaller, the portable zip, the Inno Setup installer and the Linux AppImage on every push. `native/atrac9.dll` is LibAtrac9 built with `x86_64-w64-mingw32-gcc` (see `native/libatrac9`). Pushing a tag `vX.Y.Z` publishes them as a release.

## License

GPL-2.0, like AnyPS5.
