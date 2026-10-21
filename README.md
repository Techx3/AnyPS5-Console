# AnyPS5 Console

A console-style launcher for [AnyPS5](https://github.com/boykopovar/AnyPS5): pick your user, browse your PS5 and PC games with a controller, and play. Games are converted with AnyPS5 on first launch and run fullscreen on top of the console.

Personal project by Larimar Studios. It is not affiliated with Sony Interactive Entertainment or with the AnyPS5 project.

## Download

From [Releases](../../releases):

- `AnyPS5Console-Setup-<version>.exe`: installer, no administrator rights needed. Optional task: download the build tools (Git + MinGW-w64 GCC 15.2.0) for the Repository version and forks.
- `AnyPS5Console-<version>-portable.zip`: unzip and run `AnyPS5Console.exe`. Data stays in the `data` folder next to it.

The installed version keeps its data in `%LOCALAPPDATA%\AnyPS5Console`.

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
