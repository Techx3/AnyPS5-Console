import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths  # noqa: E402

VERSION = paths.VERSION


def install_tools_cli():
    import updater
    log = paths.DATA / "install-tools.log"
    with open(log, "w", encoding="utf-8") as f:
        try:
            status = updater.install_tools(paths.TOOLS, lambda m: (f.write(m + "\n"), f.flush()))
            f.write(f"OK {status}\n")
            return 0
        except Exception as e:
            f.write(f"FAIL {e}\n")
            return 1


def main():
    if "--install-tools" in sys.argv:
        return install_tools_cli()
    if "--version" in sys.argv:
        print(VERSION)
        return 0
    try:
        import console
        console.Console().run()
        return 0
    except Exception:
        (paths.DATA / "crash.log").write_text(traceback.format_exc(), "utf-8")
        raise


if __name__ == "__main__":
    sys.exit(main())
