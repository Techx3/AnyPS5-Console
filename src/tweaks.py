"""Compatibility toggles: AnyPS5 environment variables a player can switch per game when a title shows a known
problem, with the values recommended for titles where one is known to help."""
from pathlib import Path

# values: the settings the toggle cycles through after "off"; group orders the menu.
TWEAKS = [
    {"var": "APS5_KEYS_FILL_CLEAR", "values": ["1"], "group": "Gráficos",
     "label": "Limpiar superficies al instante",
     "help": "Para imagen con estelas o restos de cuadros anteriores. Puede romper otros juegos."},
    {"var": "APS5_NO_PENDING_HTILE_FILLS", "values": ["1"], "group": "Gráficos",
     "label": "Leer la profundidad tal cual",
     "help": "Para objetos que se ven a través de otros o fondos que no se borran."},
    {"var": "APS5_CPU_DCC_KEYS", "values": ["1"], "group": "Gráficos",
     "label": "Claves de compresión en la CPU",
     "help": "Para bloques o colores corruptos en superficies comprimidas. Más lento."},
    {"var": "APS5_EXACT_DRAW_WRITES", "values": ["1"], "group": "Gráficos",
     "label": "Escrituras de dibujo exactas",
     "help": "Para texturas que muestran el contenido de otra superficie."},
    {"var": "APS5_IMAGE_TABLE_STRICT", "values": ["1"], "group": "Gráficos",
     "label": "Tablas de texturas estrictas",
     "help": "Para objetos con la textura de otro objeto."},
    {"var": "APS5_CPU_FLIP_IN_ORDER", "values": ["1"], "group": "Gráficos",
     "label": "Presentar los cuadros en orden",
     "help": "Para parpadeos o cuadros que saltan."},
    {"var": "APS5_PIPELINED_DRAWS", "values": ["0"], "group": "Estabilidad",
     "label": "Dibujar sin cola",
     "help": "Para cierres o cuelgues gráficos al azar. Más lento."},
    {"var": "APS5_PLAYGO_UNLISTED_CHUNKS", "values": ["installed", "absent"], "group": "Sistema",
     "label": "Datos PlayGo faltantes",
     "help": "Copias sin playgo-chunk.dat. installed sirve para casi todos; absent si se queda sin memoria al iniciar."},
    {"var": "APS5_TRACE_AUDIOOUT2", "values": ["1"], "group": "Diagnóstico",
     "label": "Registrar la salida de audio",
     "help": "Anota en el log los canales de audio del juego. El log crece rápido."},
    {"var": "APS5_TRACE_AJM", "values": ["1"], "group": "Diagnóstico",
     "label": "Registrar el decodificador de audio",
     "help": "Anota en el log cada trabajo del decodificador Ajm."},
    {"var": "APS5_TRACE_DCC_KEYS", "values": ["1"], "group": "Diagnóstico",
     "label": "Registrar la compresión de color",
     "help": "Anota en el log las limpiezas y lecturas de claves DCC."},
    {"var": "APS5_DUMP_FRAMES", "values": ["60"], "group": "Diagnóstico",
     "label": "Guardar los primeros 60 cuadros",
     "help": "Guarda imágenes de los cuadros en la carpeta convertida del juego."},
]

# Title ID -> {variable: value} that a title is known to need with current AnyPS5.
KNOWN = {
    # Crash Bandicoot 4 (PPSA02433) needed APS5_KEYS_FILL_CLEAR=1 until AnyPS5 main of 2026-10-22 fixed the key-fill path.
}

OFF = ""  # profile value that switches a recommended toggle off


def available(root):
    """Toggles the AnyPS5 at `root` documents (all of them when its variable list can't be read)."""
    try:
        text = (Path(root) / "docs" / "dev" / "ENVIRONMENT.md").read_text("utf-8", "replace")
    except (OSError, TypeError):
        return list(TWEAKS)
    return [t for t in TWEAKS if f"`{t['var']}`" in text]


def recommended(title_id):
    return dict(KNOWN.get((title_id or "").split("-")[0].upper(), {}))


def effective_env(profile_env, title_id):
    """Recommended values overridden by the profile; a profile value of OFF removes the variable."""
    env = recommended(title_id)
    env.update(profile_env or {})
    return env


def state(tweak, profile_env, title_id):
    """(current value or OFF, recommended value or None)."""
    rec = recommended(title_id).get(tweak["var"])
    value = (profile_env or {}).get(tweak["var"], rec if rec is not None else OFF)
    return value, rec


def cycle(tweak, profile_env, title_id):
    """The profile env after moving the toggle to its next value."""
    env = dict(profile_env or {})
    value, rec = state(tweak, env, title_id)
    order = [OFF] + tweak["values"]
    nxt = order[(order.index(value) + 1) % len(order)] if value in order else OFF
    if nxt == (rec if rec is not None else OFF):
        env.pop(tweak["var"], None)
    else:
        env[tweak["var"]] = nxt
    return env
