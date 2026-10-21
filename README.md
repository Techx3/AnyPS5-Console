# AnyPS5 Console

A console-style launcher for [AnyPS5](https://github.com/boykopovar/AnyPS5): pick your user, browse your PS5 and PC games with a controller, and play. Games are converted with AnyPS5 on first launch and run fullscreen on top of the console.

Personal project by Larimar Studios. It is not affiliated with Sony Interactive Entertainment or with the AnyPS5 project.

## Download

From [Releases](../../releases):

- `AnyPS5Console-Setup-<version>.exe`: installer, no administrator rights needed. Optional task: download the build tools (Git + MinGW-w64 GCC 15.2.0) for the Repository version and forks.
- `AnyPS5Console-<version>-portable.zip`: unzip and run `AnyPS5Console.exe`. Data stays in the `data` folder next to it.

The installed version keeps its data in `%LOCALAPPDATA%\AnyPS5Console`.

## Getting started

1. **Install.** Run `AnyPS5Console-Setup-<version>.exe` (or unzip the portable zip and open `AnyPS5Console.exe`). Windows SmartScreen may warn because the executable is not signed: choose *More info* > *Run anyway*.
2. **Create your user.** After the boot animation, pick *New user*, type a name with the on-screen keyboard (or your keyboard) and press *Done*. Every user has its own saves.
3. **Choose your PS5 games folder.** *Menu* (Start / M) > *Settings* > *PS5 games folder*. Each game is a folder with `eboot.bin` (decrypted ELF or SELF dump), `sce_sys/` and `sce_module/`. Subfolders are scanned up to 4 levels deep.
4. **Install an AnyPS5 version.** *Menu* > *Updates*:
   - *Install the stable version*: downloads the latest AnyPS5 release. Nothing else is needed. This is the recommended start.
   - *Update from the repository and build*: clones `boykopovar/AnyPS5` and builds it. Needs the build tools (*Install build tools*, about 350 MB, or the installer option).
   - *Add fork (GitHub link)*: any fork or branch, built the same way.
   - *Use version*: switches between the installed ones.
5. **Play.** Select a game and press A. The first launch converts it (a few seconds to a few minutes) and checks the system functions it needs; if something is missing you see the report and can still try with *Play anyway*. The game opens fullscreen on top of the console and you return when you close it.
6. **PC games (optional).** Steam and Epic Games libraries are detected automatically. Add your own folders or `.exe` files in *Settings* > *PC games*. Press down on the home screen to switch to the PC row.
7. **Language.** *Settings* > *Language* changes the console; *Game language* follows it or can be set to any of the 31 PS5 languages.

### Where things are

| What | Installer | Portable |
|---|---|---|
| Settings, users, saves | `%LOCALAPPDATA%\AnyPS5Console` | `data\` next to the `.exe` |
| Converted games | `...\cache\<version>\<title ID>-<hash>` | same, under `data\` |
| Last game log | `last_run.log` in the converted game folder (*Options* > *Open converted folder*) | |
| Function report | `audit.txt` in the converted game folder | |
| Crash report of the console | `crash.log` in the data folder | |

## Guía rápida (Español)

1. Ejecuta el instalador (o descomprime el zip portable y abre `AnyPS5Console.exe`). Si Windows SmartScreen avisa: *Más información* > *Ejecutar de todas formas*.
2. Crea tu usuario en "¿Quién está usando el control?" > *Nuevo usuario*. Cada usuario tiene sus propios saves.
3. *Menú* (Start / M) > *Ajustes* > *Idioma* para poner la consola en español, y *Carpeta de juegos PS5* para elegir dónde están tus dumps.
4. *Menú* > *Actualizaciones* > *Instalar la versión estable* (recomendado). Para compilar la versión Repositorio o un fork, instala antes las herramientas de compilación desde la misma pantalla.
5. Elige un juego y pulsa A. La primera vez se convierte y se revisan sus funciones; luego abre en pantalla completa y vuelves a la consola al cerrarlo.
6. Juegos de PC: Steam y Epic se detectan solos; tus carpetas o `.exe` se añaden en *Ajustes* > *Juegos PC*. Pulsa abajo en el inicio para ver esa fila.

## Features

- Boot sequence, user selection and creation; saves are kept per user.
- PS5 games (decrypted dumps) and PC games (Steam, Epic Games, your own folders and executables) in two rows.
- AnyPS5 versions: Stable (latest release, no build needed), Repository (`main`, built locally) and any fork by GitHub link. Update notices for each one.
- Check of the system functions a game needs before it starts (`tools/import_audit.py` from AnyPS5).
- Fullscreen games with aspect ratio kept, ultrawide included.
- Languages: English, 中文, हिन्दी, Español, Français, العربية. The game language follows the console language or can be set separately.

## Requirements

- Windows 10/11 x64 with a Vulkan GPU driver.
- Stable version: nothing else.
- Repository version and forks: Git, CMake, Ninja and MinGW-w64 GCC 15.2.0 (WinLibs `x86_64-ucrt-posix-seh`). The console can download them (Updates > Install build tools).

## Controls

| Controller | Keyboard | Action |
|---|---|---|
| A | Enter | Play / select |
| B | Esc | Back |
| Y | Tab | Options |
| X | F5 | Reload games |
| Start / Back | M | Menu |
| D-pad / stick | Arrows | Move |
| | F11 | Toggle fullscreen |

## Run from source

```
pip install -r requirements.txt
python src/main.py
```

Data goes to `data/` next to `src/`.

## Build

GitHub Actions (`.github/workflows/build.yml`) builds the executable with PyInstaller, the portable zip and the Inno Setup installer on every push. Pushing a tag `vX.Y.Z` publishes them as a release.

## License

GPL-2.0, like AnyPS5.
