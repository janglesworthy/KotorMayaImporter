"""KotOR Maya importer (V114) - the importer window.

Maya-native (maya.cmds) front end for the kotorImporterV114 plug-in.

The plug-in owns every import decision. This module only:
  * collects operator input,
  * validates it against the manual's documented rules before invoking,
  * invokes the three public V114 commands,
  * presents returned summaries, logs, and derived-output locations.

Usage:
    import kotor_importer_ui_v114 as kui
    kui.show()          # open the dockable window
    kui.install_menu()  # optional: adds a "KotOR" menu to Maya's main menu bar

The window is a floating/dockable workspace control. It is rebuilt by show()
and is not retained across Maya sessions; reopen it from the KotOR menu or a
shelf button running the two lines above.
"""

import os
import re
import struct

import maya.cmds as cmds
import maya.mel as mel

# ---------------------------------------------------------------------------
# Contract constants (CPP_PLUGIN_OPERATORS_MANUAL.md)
# ---------------------------------------------------------------------------

PLUGIN = "kotorImporterV114"
PLUGIN_VERSION = "114.0.0"

CMD_CHARACTER = "kotorStarterPlayerImportV114"
CMD_ANIMLIB = "kotorAnimationLibraryV114"
CMD_LEVEL = "kotorLevelImportV114"

OPAQUE_EFFECT = "kotor_character_opaque.ogsfx"
ENVMAP_EFFECT = "kotor_character_envmap.ogsfx"

# Full required runtime bundle (manual section 3). The two named above are
# passed explicitly; the rest are resolved as siblings beside the plug-in.
BUNDLE_EFFECTS = (
    "kotor_character_opaque.ogsfx",
    "kotor_character_envmap.ogsfx",
    "kotor_character_alpha.ogsfx",
    "kotor_character_envmap_alpha.ogsfx",
    "kotor_character_selfillum.ogsfx",
    "kotor_character_envmap_selfillum.ogsfx",
    "kotor_character_alpha_depthwrite.ogsfx",
    "kotor_single_emitter_world_z.ogsfx",
    "kotor_emitter_v85.ogsfx",
    "kotor_bumpy_shiny_v90.ogsfx",
    "kotor_light_flare_v92.ogsfx",
    "kotor_room_lightmapped.ogsfx",
    "kotor_water_exact.ogsfx",
    "kotor_grass_native.ogsfx",
    "kotor_punchthrough.ogsfx",
    "kotor_additive.ogsfx",
)

CHARACTER_LOG = "starter_body_import.log"
CHARACTER_PHASE_LOG = "starter_body_import_phase.log"
LEVEL_LOG = "level_import.log"
CACHE_FOLDER = "KotorMayaImporterCache/V114"

CHARACTER_ROOT_PREFIX = "KOTOR_STARTER_PLAYER_"
PROP_ROOT_PREFIX = "KOTOR_PROP_"
LEVEL_ROOT_PREFIX = "KOTOR_LEVEL_"

# Resource-table type ids, used only to LIST names (areas, creature
# templates, models, textures) so pickers can offer real choices. The UI
# never extracts or converts a game resource; the plug-in does all real
# reading at import.
RESTYPE_TGA = 3
RESTYPE_MDL = 2002
RESTYPE_TWO_DA = 2017
RESTYPE_ARE = 2012
RESTYPE_GIT = 2023
RESTYPE_TPC = 3007

TEXTURE_PACK = "TexturePacks/swpc_tex_tpa.erf"

# ---------------------------------------------------------------------------
# Level display options.
#
# The level command always imports the complete level (it has no partial
# flags, and the manual's fail-closed rules forbid the UI faking one). These
# options SHOW/HIDE parts of the imported level: applied automatically right
# after an import, and re-appliable at any time. Nothing is deleted.
#
# Group toggles map to the root's standard child groups; the last three find
# their targets by the plug-in's own shader/light node types.
# ---------------------------------------------------------------------------

LEVEL_GROUPS = (
    # label, checkbox key, root child-group suffixes, default
    ("Rooms", "dispRooms", ("ROOMS", "RACE_TRACK", "RACE_OBSTACLES"), True),
    ("Doors & placeables", "dispStatics", ("STATICS",), True),
    ("NPCs / creatures", "dispActors", ("ACTORS",), True),
    ("Grass", "dispGrass", ("GRASS",), True),
    ("Waypoints", "dispWaypoints", ("WAYPOINTS",), False),
    ("Stores & items", "dispStores", ("STORES", "ITEMS"), False),
    ("Triggers & encounters", "dispTriggers", ("TRIGGERS", "ENCOUNTERS"),
     False),
    ("Cameras", "dispCameras", ("CAMERAS",), False),
    ("Sounds", "dispSounds", ("SOUNDS",), False),
    ("Source collision (audit)", "dispWok",
     ("WOK_SOURCE", "RACE_OBSTACLE_AABB_SOURCE"), False),
)

SHADER_TOGGLES = (
    # label, checkbox key, node type ("__lights__" = Maya lights), default
    ("Lights", "dispLights", "__lights__", True),
    ("Particle FX", "dispFx", "kotorEmitterShaderCppV85", True),
    ("Water", "dispWater", "kotorWaterShaderCppV79", True),
)

AREA_ONLY_KEYS = frozenset(
    ("dispRooms", "dispGrass", "dispLights", "dispFx", "dispWater"))

# ---------------------------------------------------------------------------
# UI constants / state
# ---------------------------------------------------------------------------

WS = "kotorImporterV114WC"
MENU = "kotorImporterV114Menu"
PICK_WIN = "kotorImporterV114PickWin"

OPT_INSTALL = "kotorUI114_installRoot"
OPT_PLUGIN = "kotorUI114_pluginPath"

LABEL_W = 104   # left label column width
BROWSE_W = 30   # "..." button width

UI = {}                                  # widget path registry
STATE = {"last_outdir": "", "last_log": "",
         "src_module": "", "src_area": "", "src_creature": ""}

# Name caches (per install root / archive path) so browse is instant after
# the first use.
_KEY_CACHE = {"root": None, "types": {}}
_ERF_CACHE = {"path": None, "types": {}}
_MODEL_KIND_CACHE = {
    "root": None, "characters": (), "heads": (), "props": ()}

DEFAULT_CAMERAS = frozenset(("persp", "top", "front", "side"))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _norm(path):
    """Forward-slash normalized path (manual section 6)."""
    return path.strip().replace("\\", "/").rstrip("/")


def _optvar(key, default=""):
    if cmds.optionVar(exists=key):
        return cmds.optionVar(query=key)
    return default


def _save_optvar(key, value):
    cmds.optionVar(stringValue=(key, value))


def _text(name):
    return cmds.textField(UI[name], query=True, text=True).strip()


def _set_text(name, value):
    cmds.textField(UI[name], edit=True, text=value)


def _sanitize_label(label):
    return re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_")


def _install_root():
    return _norm(_text("installField"))


def _output_base():
    """Persistent UI-managed cache; never a required operator setting."""
    return _norm(os.path.join(cmds.internalVar(userAppDir=True),
                              CACHE_FOLDER))


def _error(message, title="KotOR importer"):
    cmds.confirmDialog(title=title, message=message, button=["OK"], icon="critical")


def _info(message, title="KotOR importer"):
    cmds.confirmDialog(title=title, message=message, button=["OK"], icon="information")


def _warning(message, title="KotOR importer warning"):
    cmds.confirmDialog(title=title, message=message, button=["OK"], icon="warning")


def _confirm(message, yes="Continue", title="KotOR importer"):
    choice = cmds.confirmDialog(
        title=title, message=message, button=[yes, "Cancel"],
        defaultButton=yes, cancelButton="Cancel", dismissString="Cancel",
        icon="warning")
    return choice == yes


# ---------------------------------------------------------------------------
# Plug-in status and shader auto-resolution
#
# The 16 .ogsfx shader files live beside kotorImporterV114.mll, so the
# loaded plug-in's own location IS the shader location. No shader field.
# ---------------------------------------------------------------------------

def _plugin_loaded():
    try:
        return bool(cmds.pluginInfo(PLUGIN, query=True, loaded=True))
    except RuntimeError:
        return False


def _plugin_path():
    if not _plugin_loaded():
        return ""
    try:
        return _norm(cmds.pluginInfo(PLUGIN, query=True, path=True) or "")
    except RuntimeError:
        return ""


def _effects_dir():
    path = _plugin_path()
    return _norm(os.path.dirname(path)) if path else ""


def _shader_paths():
    effects = _effects_dir()
    return (effects + "/" + OPAQUE_EFFECT, effects + "/" + ENVMAP_EFFECT)


def _missing_bundle_effects():
    effects = _effects_dir()
    if not effects:
        return []
    return [name for name in BUNDLE_EFFECTS
            if not os.path.isfile(os.path.join(effects, name))]


def _conflicting_plugins():
    loaded = cmds.pluginInfo(query=True, listPlugins=True) or []
    return [p for p in loaded
            if p.lower().startswith("kotorimporter") and p != PLUGIN]


def _refresh_plugin_status(*_):
    conflicts = _conflicting_plugins()
    if conflicts:
        msg = "CONFLICT: %s loaded. Clear the scene and unload it first." % (
            ", ".join(conflicts))
    elif _plugin_loaded():
        version = cmds.pluginInfo(PLUGIN, query=True, version=True)
        missing = _missing_bundle_effects()
        if version != PLUGIN_VERSION:
            msg = "Loaded (%s) - expected %s" % (version, PLUGIN_VERSION)
        elif not missing:
            msg = "Loaded (%s), shaders found" % version
        else:
            msg = "Loaded (%s), %d shader file(s) missing" % (
                version, len(missing))
    else:
        msg = "Not loaded"
    cmds.text(UI["pluginStatus"], edit=True, label=msg)
    return msg


def _load_plugin(*_):
    conflicts = _conflicting_plugins()
    if conflicts:
        _error("Another importer version is loaded: %s\n\n"
               "Only one KotOR importer version may be loaded. Start a new "
               "scene, unload it (Plug-in Manager), then load V114."
               % ", ".join(conflicts))
        return
    if _plugin_loaded():
        _refresh_plugin_status()
        return

    path = ""
    remembered = _optvar(OPT_PLUGIN)
    if remembered and os.path.isfile(remembered):
        path = remembered
    if not path:
        picked = cmds.fileDialog2(
            fileMode=1, caption="Locate %s.mll" % PLUGIN,
            fileFilter="Maya plug-in (*.mll)")
        if not picked:
            return
        path = _norm(picked[0])

    try:
        cmds.loadPlugin(path, quiet=True)
    except RuntimeError as exc:
        _save_optvar(OPT_PLUGIN, "")  # forget a bad path; next click browses
        _error("Plug-in failed to load:\n%s\n\nCheck: Maya 2024 x64, the "
               ".ogsfx files beside the .mll, the file not blocked by "
               "Windows, no older importer version loaded." % exc)
        _refresh_plugin_status()
        return
    _save_optvar(OPT_PLUGIN, _plugin_path() or path)
    _refresh_plugin_status()


# ---------------------------------------------------------------------------
# Setup persistence and validation
# ---------------------------------------------------------------------------

def _save_setup(*_):
    _save_optvar(OPT_INSTALL, _text("installField"))


def _browse_into(field, caption):
    start = _norm(_text(field)) or None
    kwargs = {"fileMode": 3, "caption": caption}
    if start and os.path.isdir(start):
        kwargs["startingDirectory"] = start
    picked = cmds.fileDialog2(**kwargs)
    if picked:
        _set_text(field, _norm(picked[0]))
        _save_setup()


def _setup_errors():
    """Blocking problems shared by every command invocation."""
    problems = []
    install = _install_root()
    if not install:
        problems.append("Set the KotOR installation folder.")
    elif not os.path.isfile(os.path.join(install, "chitin.key")):
        problems.append("That folder has no chitin.key - point at the game "
                        "root (e.g. C:/GOG Games/Star Wars - KotOR), not "
                        "data/, modules/, or the executable.")
    return problems


def _shader_errors():
    if not _plugin_loaded():
        return []  # _plugin_errors already blocks on this
    opaque, envmap = _shader_paths()
    if os.path.isfile(opaque) and os.path.isfile(envmap):
        return []
    return ["The character shader files (%s, %s) are not beside the loaded "
            "plug-in:\n%s\n\nKeep the .mll and its 16 .ogsfx files in one "
            "folder." % (OPAQUE_EFFECT, ENVMAP_EFFECT, _effects_dir())]


def _plugin_errors():
    problems = []
    conflicts = _conflicting_plugins()
    if conflicts:
        problems.append("Unload the other importer version first: %s."
                        % ", ".join(conflicts))
    if not _plugin_loaded():
        problems.append("Load %s first (Setup > Load)." % PLUGIN)
    elif cmds.pluginInfo(PLUGIN, query=True, version=True) != PLUGIN_VERSION:
        problems.append("Loaded plug-in version is not %s." % PLUGIN_VERSION)
    return problems


# ---------------------------------------------------------------------------
# Internal derived-file cache: deterministic and invisible to normal setup
# ---------------------------------------------------------------------------

def _resolve_output_dir(label):
    """Return reusable managed-cache subfolder <base>/<label>."""
    base = _output_base()
    target = base + "/" + _sanitize_label(label).lower()
    if not os.path.isdir(target):
        try:
            os.makedirs(target)
        except OSError as exc:
            _error("Could not create the importer cache:\n%s\n%s"
                   % (target, exc))
            return ""
    return target


def _output_errors():
    """Compatibility stub: cache location is automatic and never blocks."""
    return []


# ---------------------------------------------------------------------------
# Global Maya working-axis control
# ---------------------------------------------------------------------------

def _current_up_axis():
    try:
        return str(cmds.upAxis(query=True, axis=True) or "y").lower()
    except RuntimeError:
        return "y"


def _up_axis_button_label():
    if _current_up_axis() == "z":
        return "KotOR Z-up  |  switch to Maya Y-up"
    return "Maya Y-up  |  switch to KotOR Z-up"


def _refresh_up_axis_button():
    control = UI.get("upAxisButton")
    if control and cmds.control(control, exists=True):
        cmds.button(control, edit=True, label=_up_axis_button_label())


def _toggle_up_axis(*_):
    """Toggle Maya's global working up axis; never rotate scene objects."""
    target = "y" if _current_up_axis() == "z" else "z"
    try:
        cmds.play(state=False)
        cmds.upAxis(axis=target, rotateView=True)
    except RuntimeError as exc:
        _error("Could not switch Maya's global up axis:\n%s" % exc)
        return
    _refresh_up_axis_button()


# ---------------------------------------------------------------------------
# Result panel
# ---------------------------------------------------------------------------

def _show_result(title, body, outdir="", log_name=""):
    STATE["last_outdir"] = outdir
    STATE["last_log"] = (outdir + "/" + log_name) if (outdir and log_name) else ""
    cmds.scrollField(UI["resultField"], edit=True,
                     text="%s\n%s\n%s" % (title, "-" * len(title), body))
    cmds.button(UI["openDirBtn"], edit=True, enable=bool(outdir))
    cmds.button(UI["openLogBtn"], edit=True, enable=bool(STATE["last_log"]))


def _format_summary(raw):
    parts = [p.strip() for p in str(raw).split(";") if p.strip()]
    return "\n".join(parts) if parts else str(raw)


def _summary_value(raw, key, default=""):
    prefix = str(key) + "="
    for part in str(raw).split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix):]
    return default


def _open_path(path):
    if not path:
        return
    if not os.path.exists(path):
        _error("Path does not exist yet:\n%s" % path)
        return
    if hasattr(os, "startfile"):
        os.startfile(path)  # Windows; V114 is Windows-only.


def _open_last_dir(*_):
    _open_path(STATE["last_outdir"])


def _open_last_log(*_):
    _open_path(STATE["last_log"])


def _run_command(fn, kwargs):
    cmds.waitCursor(state=True)
    try:
        return True, fn(**kwargs)
    except Exception as exc:  # the command raises RuntimeError on failure
        return False, str(exc)
    finally:
        cmds.waitCursor(state=False)


def _refresh_vp2_after_import():
    """Make newly connected KotOR shader/file graphs visible immediately."""
    cmds.dgdirty(allPlugs=True)
    try:
        cmds.ogs(reset=True)
    except RuntimeError:
        # VP2 may be unavailable in batch/headless Maya; the DG refresh still
        # preserves a valid imported scene and the next viewport draw updates it.
        pass
    cmds.refresh(force=True)


def _matching_roots(prefix):
    """Include Maya's numeric suffix when a requested root name exists."""
    return [root for root in (cmds.ls(assemblies=True) or [])
            if root.startswith(prefix) and re.search(r"_ROOT\d*$", root)]


def _character_roots():
    return _matching_roots(CHARACTER_ROOT_PREFIX)


def _prop_roots():
    return _matching_roots(PROP_ROOT_PREFIX)


def _count_roots(prefix):
    return len(_matching_roots(prefix))


# ---------------------------------------------------------------------------
# List picker window with live filter (clips, levels, creatures)
# ---------------------------------------------------------------------------

def _pick_from_list(title, items, on_pick, initial_filter=""):
    if cmds.window(PICK_WIN, exists=True):
        cmds.deleteUI(PICK_WIN)
    win = cmds.window(PICK_WIN, title=title, widthHeight=(340, 470),
                      sizeable=True)
    form = cmds.formLayout(parent=win)
    filter_field = cmds.textField(parent=form,
                                  placeholderText="type to filter",
                                  annotation="Filters the list as you type. "
                                             "Edit or clear the suggestion "
                                             "to widen the search.")
    tsl = cmds.textScrollList(parent=form, allowMultiSelection=False)

    def _refilter(*_):
        query = cmds.textField(filter_field, query=True,
                               text=True).strip().lower()
        cmds.textScrollList(tsl, edit=True, removeAll=True)
        keep = [i for i in items if query in i.lower()] if query else items
        if keep:
            cmds.textScrollList(tsl, edit=True, append=keep)

    cmds.textField(filter_field, edit=True, textChangedCommand=_refilter)
    if initial_filter:
        cmds.textField(filter_field, edit=True, text=initial_filter)
    _refilter()

    def _ok(*_):
        selected = cmds.textScrollList(tsl, query=True, selectItem=True)
        if selected:
            cmds.deleteUI(win)
            on_pick(selected[0])

    def _cancel(*_):
        cmds.deleteUI(win)

    cmds.textScrollList(tsl, edit=True, doubleClickCommand=_ok)
    ok_btn = cmds.button(parent=form, label="Select", command=_ok)
    cancel_btn = cmds.button(parent=form, label="Cancel", command=_cancel)
    cmds.formLayout(
        form, edit=True,
        attachForm=[(filter_field, "top", 6), (filter_field, "left", 6),
                    (filter_field, "right", 6),
                    (tsl, "left", 6), (tsl, "right", 6),
                    (ok_btn, "left", 6), (ok_btn, "bottom", 6),
                    (cancel_btn, "right", 6), (cancel_btn, "bottom", 6)],
        attachControl=[(tsl, "top", 6, filter_field),
                       (tsl, "bottom", 6, ok_btn)],
        attachPosition=[(ok_btn, "right", 3, 50),
                        (cancel_btn, "left", 3, 50)])
    cmds.showWindow(win)


# ---------------------------------------------------------------------------
# Level / area / creature discovery
#
# Reads only resource NAME tables (RIM directory, GIT creature template
# names) so pickers can offer real choices. Nothing is extracted or
# converted; the plug-in does all real reading at import time.
# ---------------------------------------------------------------------------

def _rim_entries(rim_path):
    """[(resref, type_id, offset, size)] from a .rim's directory table."""
    try:
        with open(rim_path, "rb") as handle:
            header = handle.read(20)
            if len(header) < 20 or header[:4] != b"RIM ":
                return []
            count, table_offset = struct.unpack_from("<II", header, 12)
            if count <= 0 or count > 200000:
                return []
            handle.seek(table_offset)
            table = handle.read(32 * count)
    except (OSError, ValueError, struct.error):
        return []
    entries = []
    for i in range(count):
        entry = table[i * 32:(i + 1) * 32]
        if len(entry) < 32:
            break
        name = entry[:16].split(b"\0", 1)[0].decode(
            "ascii", "ignore").strip().lower()
        try:
            rtype, _index, offset, size = struct.unpack_from("<4I", entry, 16)
        except struct.error:
            break
        if name:
            entries.append((name, rtype, offset, size))
    return entries


def _rim_read(rim_path, offset, size):
    try:
        with open(rim_path, "rb") as handle:
            handle.seek(offset)
            return handle.read(size)
    except OSError:
        return b""


def _key_resrefs(type_ids):
    """All resource names of the given types from chitin.key's index."""
    install = _install_root()
    if not install:
        return []
    if _KEY_CACHE["root"] != install:
        types = {}
        path = os.path.join(install, "chitin.key")
        try:
            with open(path, "rb") as handle:
                data = handle.read()
            if data[:4] == b"KEY ":
                _bifs, key_count, _file_off, key_off = struct.unpack_from(
                    "<4I", data, 8)
                if 0 < key_count <= 500000:
                    for i in range(key_count):
                        base = key_off + i * 22
                        entry = data[base:base + 22]
                        if len(entry) < 22:
                            break
                        name = entry[:16].split(b"\0", 1)[0].decode(
                            "ascii", "ignore").strip().lower()
                        rtype = struct.unpack_from("<H", entry, 16)[0]
                        if name:
                            types.setdefault(rtype, set()).add(name)
        except (OSError, ValueError, struct.error):
            types = {}
        _KEY_CACHE["root"] = install
        _KEY_CACHE["types"] = {t: sorted(s) for t, s in types.items()}
    out = set()
    for type_id in type_ids:
        out.update(_KEY_CACHE["types"].get(type_id, []))
    return sorted(out)


def _override_resource(resref, extension):
    """Read one exact flat Override resource without scanning game archives."""
    folder = os.path.join(_install_root(), "Override")
    if not os.path.isdir(folder):
        return b""
    wanted = (resref + "." + extension).casefold()
    try:
        for name in os.listdir(folder):
            if name.casefold() != wanted:
                continue
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                with open(path, "rb") as handle:
                    return handle.read()
    except OSError:
        return b""
    return b""


def _key_bif_resource(resref, resource_type, extension):
    """Resolve one exact Override/KEY/BIF resource from the installation."""
    override = _override_resource(resref, extension)
    if override:
        return override
    install = _install_root()
    key_path = os.path.join(install, "chitin.key")
    try:
        with open(key_path, "rb") as handle:
            key = handle.read()
        if len(key) < 28 or key[:4] != b"KEY ":
            raise ValueError("invalid chitin.key header")
        bif_count, key_count, bif_table, key_table = struct.unpack_from(
            "<4I", key, 8)
        if bif_count <= 0 or bif_count > 100000:
            raise ValueError("invalid KEY BIF count")
        if key_count <= 0 or key_count > 500000:
            raise ValueError("invalid KEY resource count")
        if bif_table + bif_count * 12 > len(key):
            raise ValueError("truncated KEY BIF table")
        if key_table + key_count * 22 > len(key):
            raise ValueError("truncated KEY resource table")

        wanted = resref.casefold()
        packed_id = None
        for index in range(key_count):
            entry = key_table + index * 22
            name = key[entry:entry + 16].split(b"\0", 1)[0].decode(
                "ascii", "ignore").strip().casefold()
            kind = struct.unpack_from("<H", key, entry + 16)[0]
            if name == wanted and kind == resource_type:
                packed_id = struct.unpack_from("<I", key, entry + 18)[0]
                break
        if packed_id is None:
            return b""

        bif_index = packed_id >> 20
        resource_id = packed_id & 0xFFFFF
        if bif_index >= bif_count:
            raise ValueError("KEY resource references an invalid BIF index")
        bif_entry = bif_table + bif_index * 12
        name_offset = struct.unpack_from("<I", key, bif_entry + 4)[0]
        name_size = struct.unpack_from("<H", key, bif_entry + 8)[0]
        if name_offset + name_size > len(key):
            raise ValueError("truncated KEY BIF path")
        relative = key[name_offset:name_offset + name_size].split(
            b"\0", 1)[0].decode("latin-1").replace("\\", "/")
        bif_path = os.path.join(install, *relative.split("/"))
        if not os.path.isfile(bif_path):
            bif_path = os.path.join(install, "data", os.path.basename(relative))

        with open(bif_path, "rb") as handle:
            header = handle.read(20)
            if len(header) < 20 or header[:4] != b"BIFF":
                raise ValueError("invalid BIF header")
            resource_count = struct.unpack_from("<I", header, 8)[0]
            resource_table = struct.unpack_from("<I", header, 16)[0]
            if resource_count <= 0 or resource_count > 10000000:
                raise ValueError("invalid BIF resource count")
            handle.seek(resource_table)
            table = handle.read(resource_count * 16)
            if len(table) != resource_count * 16:
                raise ValueError("truncated BIF resource table")
            selected = None
            for index in range(resource_count):
                entry = struct.unpack_from("<4I", table, index * 16)
                if entry[0] == resource_id:
                    selected = entry
                    break
            if selected is None and resource_id < resource_count:
                selected = struct.unpack_from(
                    "<4I", table, resource_id * 16)
            if selected is None or selected[3] != resource_type:
                raise ValueError("BIF resource id/type mismatch")
            handle.seek(selected[1])
            payload = handle.read(selected[2])
            if len(payload) != selected[2]:
                raise ValueError("truncated BIF resource payload")
            return payload
    except (OSError, ValueError, struct.error):
        return b""


def _binary_twoda_rows(data, label):
    """Return source-authored rows from one bounded retail 2DA V2.b table."""
    if not data.startswith(b"2DA V2.b\n"):
        raise ValueError("%s is not a binary 2DA V2.b table" % label)
    position = 9
    header_end = data.find(b"\0", position)
    if header_end < 0:
        raise ValueError("%s has no terminated header row" % label)
    headers = [value.decode("latin-1").casefold()
               for value in data[position:header_end].split(b"\t") if value]
    position = header_end + 1
    if not headers or position + 4 > len(data):
        raise ValueError("%s has no bounded columns/row count" % label)
    row_count = struct.unpack_from("<I", data, position)[0]
    position += 4
    cell_count = row_count * len(headers)
    if cell_count > 16000000:
        raise ValueError("%s has an implausible cell count" % label)
    for _ in range(row_count):
        end = data.find(b"\t", position)
        if end < 0:
            raise ValueError("%s has an unterminated row label" % label)
        position = end + 1
    offset_size = cell_count * 2
    if position + offset_size + 2 > len(data):
        raise ValueError("%s has a truncated cell-offset table" % label)
    offsets = struct.unpack_from("<%dH" % cell_count, data, position)
    position += offset_size
    string_size = struct.unpack_from("<H", data, position)[0]
    position += 2
    if position + string_size > len(data):
        raise ValueError("%s has a truncated string table" % label)
    strings = data[position:position + string_size]

    def value_at(offset):
        if offset >= len(strings):
            raise ValueError("%s cell offset is outside its string table" % label)
        end = strings.find(b"\0", offset)
        if end < 0:
            raise ValueError("%s has an unterminated cell" % label)
        return strings[offset:end].decode("latin-1").strip().casefold()

    return [
        {header: value_at(offsets[row * len(headers) + column])
         for column, header in enumerate(headers)}
        for row in range(row_count)
    ]


def _model_kind_names():
    """Classify installed MDLs from retail appearance/head source tables."""
    install = _install_root()
    if _MODEL_KIND_CACHE["root"] == install:
        return _MODEL_KIND_CACHE
    appearance_data = _key_bif_resource(
        "appearance", RESTYPE_TWO_DA, "2da")
    heads_data = _key_bif_resource("heads", RESTYPE_TWO_DA, "2da")
    if not appearance_data or not heads_data:
        raise ValueError(
            "Couldn't resolve appearance.2da and heads.2da from this install.")
    appearance_rows = _binary_twoda_rows(appearance_data, "appearance.2da")
    head_rows = _binary_twoda_rows(heads_data, "heads.2da")
    characters = set()
    for row in appearance_rows:
        for column, value in row.items():
            if column == "race" or re.fullmatch(r"model[a-z]", column):
                if value and value != "****":
                    characters.add(value)
    heads = {
        row.get("head", "") for row in head_rows
        if row.get("head", "") not in ("", "****")}
    installed = set(_installed_model_names())
    _MODEL_KIND_CACHE.update({
        "root": install,
        "characters": tuple(sorted(characters & installed)),
        "heads": tuple(sorted(heads & installed)),
        "props": tuple(sorted(installed - characters - heads)),
    })
    return _MODEL_KIND_CACHE


def _erf_resrefs(erf_path, type_ids):
    """All resource names of the given types from an ERF's key list."""
    if not os.path.isfile(erf_path):
        return []
    if _ERF_CACHE["path"] != erf_path:
        types = {}
        try:
            with open(erf_path, "rb") as handle:
                header = handle.read(32)
                if len(header) == 32 and header[:4] == b"ERF ":
                    entry_count, _loc_off, key_off = struct.unpack_from(
                        "<3I", header, 16)
                    if 0 < entry_count <= 500000:
                        handle.seek(key_off)
                        table = handle.read(24 * entry_count)
                        for i in range(entry_count):
                            entry = table[i * 24:(i + 1) * 24]
                            if len(entry) < 24:
                                break
                            name = entry[:16].split(b"\0", 1)[0].decode(
                                "ascii", "ignore").strip().lower()
                            rtype = struct.unpack_from("<H", entry, 20)[0]
                            if name:
                                types.setdefault(rtype, set()).add(name)
        except (OSError, ValueError, struct.error):
            types = {}
        _ERF_CACHE["path"] = erf_path
        _ERF_CACHE["types"] = {t: sorted(s) for t, s in types.items()}
    out = set()
    for type_id in type_ids:
        out.update(_ERF_CACHE["types"].get(type_id, []))
    return sorted(out)


def _installed_model_names():
    """Every model name available from Override or the KEY/BIF index."""
    names = set(_key_resrefs((RESTYPE_MDL,)))
    folder = os.path.join(_install_root(), "Override")
    if os.path.isdir(folder):
        try:
            names.update(
                os.path.splitext(name)[0].casefold()
                for name in os.listdir(folder)
                if name.casefold().endswith(".mdl") and
                os.path.isfile(os.path.join(folder, name)))
        except OSError:
            pass
    return sorted(names)


def _installed_texture_names():
    """Texture names: the high-quality pack plus KEY-indexed TGA/TPC."""
    names = set(_erf_resrefs(
        os.path.join(_install_root(), *TEXTURE_PACK.split("/")),
        (RESTYPE_TPC, RESTYPE_TGA)))
    names.update(_key_resrefs((RESTYPE_TPC, RESTYPE_TGA)))
    return sorted(names)


def _pick_model_into(field_key, title, seed=""):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    names = _installed_model_names()
    if not names:
        _error("Couldn't read the model index (chitin.key).")
        return
    _pick_from_list(title, names,
                    lambda name: _set_text(field_key, name),
                    initial_filter=seed)


def _pick_model_kind_into(field_key, title, kind):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    try:
        names = list(_model_kind_names()[kind])
    except ValueError as exc:
        _error(str(exc))
        return
    if not names:
        _error("No %s models were resolved from the installed source tables."
               % kind)
        return
    _pick_from_list(title, names,
                    lambda name: _set_text(field_key, name))


def _pick_character_model_into(field_key="modelField"):
    _pick_model_kind_into(field_key, "Character body / race models",
                          "characters")


def _pick_prop_model_into(field_key="propModelField"):
    _pick_model_kind_into(field_key, "Props / standalone models", "props")


def _pick_head_model_into(field_key="headField"):
    _pick_model_kind_into(field_key, "Character heads", "heads")


def _pick_texture_into(field_key, title, seed=""):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    names = _installed_texture_names()
    if not names:
        _error("Couldn't read the texture index (%s / chitin.key)."
               % TEXTURE_PACK)
        return
    _pick_from_list(title, names,
                    lambda name: _set_text(field_key, name),
                    initial_filter=seed)


def _installed_modules():
    modules_dir = os.path.join(_install_root(), "modules")
    if not os.path.isdir(modules_dir):
        return []
    return sorted({
        os.path.splitext(f)[0]
        for f in os.listdir(modules_dir)
        if f.lower().endswith(".rim") and not f.lower().endswith("_s.rim")})


def _module_rims(module):
    modules_dir = os.path.join(_install_root(), "modules")
    return [p for p in (os.path.join(modules_dir, module + ".rim"),
                        os.path.join(modules_dir, module + "_s.rim"))
            if os.path.isfile(p)]


def _module_areas(module):
    if not _install_root() or not module:
        return []
    for path in _module_rims(module):
        names = sorted({name for (name, rtype, _o, _s) in _rim_entries(path)
                        if rtype == RESTYPE_ARE})
        if not names:
            names = sorted({name for (name, rtype, _o, _s)
                            in _rim_entries(path) if rtype == RESTYPE_GIT})
        if names:
            return names
    return []


def _gff_creature_templates(git_bytes):
    """[(index, template_resref)] from a GIT's creature list."""
    try:
        if len(git_bytes) < 56 or git_bytes[4:8] != b"V3.2":
            return []
        (s_off, s_cnt, f_off, _f_cnt, l_off, _l_cnt, fd_off, _fd_cnt,
         fi_off, _fi_cnt, li_off, _li_cnt) = struct.unpack_from(
            "<12I", git_bytes, 8)

        def struct_fields(struct_idx):
            if struct_idx >= s_cnt:
                return []
            _stype, dod, fcount = struct.unpack_from(
                "<3I", git_bytes, s_off + struct_idx * 12)
            if fcount == 0:
                return []
            if fcount == 1:
                return [dod]
            return list(struct.unpack_from("<%dI" % fcount, git_bytes,
                                           fi_off + dod))

        def field(field_idx):
            ftype, label_idx, dod = struct.unpack_from(
                "<3I", git_bytes, f_off + field_idx * 12)
            lbase = l_off + label_idx * 16
            label = git_bytes[lbase:lbase + 16].split(b"\0", 1)[0].decode(
                "ascii", "ignore")
            return ftype, label, dod

        for field_idx in struct_fields(0):
            ftype, label, dod = field(field_idx)
            if ftype == 15 and label == "Creature List":
                base = li_off + dod
                size = struct.unpack_from("<I", git_bytes, base)[0]
                struct_idxs = struct.unpack_from("<%dI" % size, git_bytes,
                                                 base + 4)
                out = []
                for i, sidx in enumerate(struct_idxs):
                    template = ""
                    for cfi in struct_fields(sidx):
                        cftype, clabel, cdod = field(cfi)
                        if cftype == 11 and clabel == "TemplateResRef":
                            fb = fd_off + cdod
                            length = git_bytes[fb]
                            template = git_bytes[fb + 1:fb + 1 + length]\
                                .decode("ascii", "ignore").strip().lower()
                            break
                    out.append((i, template or "(unknown)"))
                return out
        return []
    except (struct.error, IndexError, ValueError):
        return []


def _module_creatures(module):
    """[(area, index, template)] for every area in the module."""
    if not _install_root() or not module:
        return []
    for path in _module_rims(module):
        out = []
        for (name, rtype, offset, size) in _rim_entries(path):
            if rtype == RESTYPE_GIT and size:
                for idx, template in _gff_creature_templates(
                        _rim_read(path, offset, size)):
                    out.append((name, idx, template))
        if out:
            return out
    return []


def _fill_area_from_module(module, area_key, quiet=False):
    areas = _module_areas(module)
    if len(areas) == 1:
        _set_text(area_key, areas[0])
    elif len(areas) > 1:
        _pick_from_list("Areas in %s" % module, areas,
                        lambda area: _set_text(area_key, area))
    elif not quiet:
        _info("Couldn't read area names from '%s' - type the area name "
              "manually." % module)


def _pick_installed_module(module_key, area_key):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    names = _installed_modules()
    if not names:
        _error("No .rim levels found under modules/ in the installation.")
        return

    def picked(name):
        _set_text(module_key, name)
        _fill_area_from_module(name, area_key, quiet=True)

    _pick_from_list("Installed levels", names, picked)


def _pick_area(module_key, area_key):
    module = _text(module_key)
    if not module:
        _info("Pick a level (module) first.")
        return
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    _fill_area_from_module(module, area_key, quiet=False)


# ---------------------------------------------------------------------------
# NPC / creature browsing (Character tab, creature mode)
# ---------------------------------------------------------------------------

def _pick_creature_module(*_):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    names = _installed_modules()
    if not names:
        _error("No .rim levels found under modules/ in the installation.")
        return

    def picked(name):
        _set_text("srcModuleField", name)
        _set_text("srcCreatureField", "")
        areas = _module_areas(name)
        STATE["src_module"] = name
        STATE["src_area"] = areas[0] if len(areas) == 1 else ""
        STATE["src_creature"] = ""

    _pick_from_list("Installed levels", names, picked)


def _pick_creature(*_):
    problems = _setup_errors()
    if problems:
        _error("\n\n".join(problems))
        return
    module = _text("srcModuleField")

    cmds.waitCursor(state=True)
    try:
        if module:
            rows = [(module, area, idx, template)
                    for (area, idx, template) in _module_creatures(module)]
            title = "NPCs / creatures in %s" % module
        else:
            rows = []
            for name in _installed_modules():
                rows.extend((name, area, idx, template)
                            for (area, idx, template)
                            in _module_creatures(name))
            title = "All NPCs / creatures"
    finally:
        cmds.waitCursor(state=False)

    if not rows:
        _info("No creatures found%s."
              % ((" in '%s'" % module) if module else ""))
        return

    lookup = {}
    items = []
    for (mod, area, idx, template) in rows:
        if module:
            display = "%d: %s" % (idx, template)
        else:
            display = "%s   %d: %s" % (mod, idx, template)
        if display in lookup:  # same index in a multi-area module
            display = "%s  (%s)" % (display, area)
        lookup[display] = (mod, area, idx, template)
        items.append(display)

    def picked(display):
        mod, area, idx, template = lookup[display]
        _set_text("srcModuleField", mod)
        _set_text("srcCreatureField", "%d: %s" % (idx, template))
        STATE["src_module"] = mod
        STATE["src_area"] = area
        STATE["src_creature"] = template

    _pick_from_list(title, items, picked)


def _creature_index():
    text = _text("srcCreatureField")
    if not text:
        return None
    token = text.split()[0].rstrip(":")
    try:
        return int(token)
    except ValueError:
        return None


def _resolve_creature_area(module):
    """Area for the selected creature, from the pick or the module itself."""
    if module and STATE.get("src_module") == module and STATE.get("src_area"):
        return STATE["src_area"]
    areas = _module_areas(module)
    return areas[0] if len(areas) == 1 else ""


# ---------------------------------------------------------------------------
# Character tab logic
# ---------------------------------------------------------------------------

def _character_mode():
    """1 = manual model, 2 = NPC / creature."""
    return cmds.radioButtonGrp(UI["charMode"], query=True, select=True)


def _sync_character_mode(*_):
    manual = _character_mode() == 1
    cmds.frameLayout(UI["manualFrame"], edit=True, manage=manual)
    cmds.frameLayout(UI["sourceFrame"], edit=True, manage=not manual)
    _sync_animation_enable()


def _static_checked():
    return False


def _sync_animation_enable(*_):
    static = _character_mode() == 1 and _static_checked()
    cmds.rowLayout(UI["animRow"], edit=True, enable=not static)


def _auto_label():
    if _character_mode() == 1:
        model = _text("modelField")
        head = _text("headField")
        label = model + ("_" + head if head else "")
    else:
        module = _text("srcModuleField")
        template = ""
        if STATE.get("src_module") == module:
            template = STATE.get("src_creature", "")
        if template and template != "(unknown)":
            label = template
        else:
            index = _creature_index()
            label = "%s_CREATURE_%s" % (
                module, index if index is not None else "X")
    return _sanitize_label(label).upper()


def _choose_animation(*_):
    if _character_mode() == 2:
        _info("In creature mode the body model comes from the game data, so "
              "the UI can't list its clips here. Type the exact clip name, "
              "or look up clips for a known model in the Animations tab.")
        return
    problems = _setup_errors() + _plugin_errors()
    model = _text("modelField")
    if not model:
        problems.append("Enter a model name first - clips are listed per "
                        "model.")
    if problems:
        _error("\n\n".join(problems))
        return
    ok, result = _run_command(
        getattr(cmds, CMD_ANIMLIB),
        {"installation": _install_root(), "model": model})
    if not ok:
        _error("Clip listing failed:\n%s" % result)
        return
    clips = result or []
    if not clips:
        _info("No clips found for '%s'." % model)
        return
    _pick_from_list("Clips: %s" % model, clips,
                    lambda clip: _set_text("animField", clip))


def _import_character(*_, play_after_import=False, replace_existing=False):
    manual = _character_mode() == 1
    problems = _setup_errors() + _shader_errors() + _plugin_errors()

    src_module = ""
    src_area = ""
    src_index = None
    if manual:
        if not _text("modelField"):
            problems.append("Model is required in manual mode.")
        else:
            try:
                character_models = _model_kind_names()["characters"]
                if _text("modelField").casefold() not in character_models:
                    problems.append(
                        "'%s' is not referenced as a character body/race in "
                        "appearance.2da. Use the Prop tab for standalone "
                        "models." % _text("modelField"))
            except ValueError as exc:
                problems.append(str(exc))
        if _text("headEquipField") and not _text("headField"):
            problems.append("A mask/goggles model needs an external Head "
                            "with a GoggleHook - fill the Head field too.")
    else:
        src_module = _text("srcModuleField")
        src_index = _creature_index()
        if not src_module:
            problems.append("Pick the level (module) the creature lives in, "
                            "or leave it empty and browse all creatures "
                            "with the Creature ... button.")
        if src_index is None:
            problems.append("Pick a creature with the ... button (or type "
                            "its number).")
        if src_module:
            src_area = _resolve_creature_area(src_module)
            if not src_area:
                problems.append("Couldn't work out which area of '%s' the "
                                "creature is in - pick it with the ... "
                                "button." % src_module)

    label = _text("labelField") or _auto_label()
    if not label:
        problems.append("Enter a label (or fill the fields it derives from).")

    if problems:
        _error("\n\n".join(problems), title="Cannot import")
        return False

    _set_text("labelField", label)

    missing = _missing_bundle_effects()
    missing = [m for m in missing if m not in (OPAQUE_EFFECT, ENVMAP_EFFECT)]
    if missing and not _confirm(
            "Shader set beside the plug-in is incomplete (%d missing):\n"
            "%s\n\nSome materials will fail. Import anyway?"
            % (len(missing), "\n".join(missing)), yes="Import Anyway"):
        return False

    replacement_root = ""
    replacement_matrix = None
    before_character_roots = set(_character_roots())
    if replace_existing and before_character_roots:
        replacement_root = _active_character_root()
        if not replacement_root:
            return False
        replacement_matrix = cmds.xform(
            replacement_root, query=True, worldSpace=True, matrix=True)

    outdir = _resolve_output_dir(label)
    if not outdir:
        return False

    opaque, envmap = _shader_paths()
    kwargs = {
        "installation": _install_root(),
        "appearance": label,
        "textureDirectory": outdir,
        "shaderPath": opaque,
        "envShaderPath": envmap,
    }
    if manual:
        kwargs["model"] = _text("modelField")
        for field, flag in (("headField", "head"),
                            ("bodyTexField", "bodyTexture"),
                            ("rhandField", "rightHandModel"),
                            ("lhandField", "leftHandModel"),
                            ("headEquipField", "headEquipmentModel")):
            value = _text(field)
            if value:
                kwargs[flag] = value
        if _static_checked():
            kwargs["static"] = True
        else:
            animation = _text("animField")
            if animation:
                kwargs["animation"] = animation
    else:
        kwargs["sourceModule"] = src_module
        kwargs["sourceArea"] = src_area
        kwargs["sourceCreatureIndex"] = src_index
        animation = _text("animField")
        if animation:
            kwargs["animation"] = animation

    ok, result = _run_command(getattr(cmds, CMD_CHARACTER), kwargs)
    if not ok:
        _show_result(
            "CHARACTER IMPORT FAILED",
            "%s\n\nThe command is non-undoable; clear this scene before "
            "retrying.\nCheck %s and %s in the import cache."
            % (result, CHARACTER_PHASE_LOG, CHARACTER_LOG),
            outdir, CHARACTER_PHASE_LOG)
        _error("Import failed - see the Result panel.")
        return False

    replacement_message = ""
    if replacement_root:
        created_roots = sorted(
            set(_character_roots()) - before_character_roots)
        if len(created_roots) != 1:
            _show_result(
                "CHARACTER IMPORT NEEDS ATTENTION",
                "The compiled import succeeded, but the UI found %d new "
                "character roots instead of one. The previous character "
                "was preserved; select the candidate you want manually."
                % len(created_roots),
                outdir, CHARACTER_LOG)
            _error("The new animated candidate could not be identified "
                   "safely. The previous character was not removed.")
            return False
        new_root = created_roots[0]
        old_name = replacement_root.rsplit("|", 1)[-1]
        cmds.delete(replacement_root)
        new_root = cmds.rename(new_root, old_name)
        if replacement_matrix:
            cmds.xform(new_root, worldSpace=True, matrix=replacement_matrix)
        cmds.select(new_root, replace=True)
        replacement_message = (
            "Replaced %s only after the animated import completed."
            % old_name)

    roots = _count_roots(CHARACTER_ROOT_PREFIX)
    body = "%s\n\nImported character roots now in scene: %d" % (
        _format_summary(result), roots)
    if replacement_message:
        body += "\n\n" + replacement_message
    if play_after_import:
        played, playback_message = _start_timeline_playback()
        body += "\n\n" + playback_message
    _refresh_vp2_after_import()
    _show_result("CHARACTER IMPORT OK", body, outdir, CHARACTER_LOG)
    return True


def _import_prop(*_):
    problems = _setup_errors() + _shader_errors() + _plugin_errors()
    model = _text("propModelField")
    if not model:
        problems.append("Select a standalone prop model.")
    else:
        try:
            prop_models = _model_kind_names()["props"]
            if model.casefold() not in prop_models:
                problems.append(
                    "'%s' is an appearance-backed character component. "
                    "Use the Character tab instead." % model)
        except ValueError as exc:
            problems.append(str(exc))
    label = _text("propLabelField") or model
    if not label:
        problems.append("Enter a prop label.")
    if problems:
        _error("\n\n".join(problems), title="Cannot import prop")
        return False

    _set_text("propLabelField", label)
    outdir = _resolve_output_dir(label)
    if not outdir:
        return False
    opaque, envmap = _shader_paths()
    before = set(_prop_roots())
    ok, result = _run_command(
        getattr(cmds, CMD_CHARACTER),
        {
            "installation": _install_root(),
            "model": model,
            "appearance": label,
            "textureDirectory": outdir,
            "shaderPath": opaque,
            "envShaderPath": envmap,
            "prop": True,
        })
    if not ok:
        _show_result(
            "PROP IMPORT FAILED",
            "%s\n\nFor any later-stage failure, clear only the failed prop "
            "root before retrying.\n"
            "Check %s and %s in the import cache."
            % (result, CHARACTER_PHASE_LOG, CHARACTER_LOG),
            outdir, CHARACTER_PHASE_LOG)
        _error("Prop import failed - see the Result panel.")
        return False

    created = sorted(set(_prop_roots()) - before)
    if len(created) != 1:
        _show_result(
            "PROP IMPORT NEEDS ATTENTION",
            "The compiled import succeeded, but the UI found %d new prop "
            "roots instead of one." % len(created),
            outdir, CHARACTER_LOG)
        _error("The new prop candidate could not be identified safely.")
        return False
    cmds.select(created[0], replace=True)
    _refresh_vp2_after_import()
    warning_count = int(_summary_value(result, "warningCount", "0") or 0)
    missing_count = int(
        _summary_value(result, "retailIncompleteTextures", "0") or 0)
    missing_names = ""
    if cmds.attributeQuery("kotorMissingSourceTextures", node=created[0], exists=True):
        missing_names = cmds.getAttr(created[0] + ".kotorMissingSourceTextures") or ""
    if warning_count:
        body = (
            "%s\n\nImported prop roots now in scene: %d\n\n"
            "WARNING: this installed retail asset is incomplete. %d authored "
            "texture dependency/dependencies are absent: %s\n"
            "The model was imported with its source diffuse color and no "
            "invented or copied substitute texture."
            % (_format_summary(result), len(_prop_roots()), missing_count,
               missing_names or "(see import log)")
        )
        _show_result(
            "PROP IMPORTED - RETAIL ASSET INCOMPLETE",
            body, outdir, CHARACTER_LOG)
        _warning(
            "The prop imported, but the retail game data is missing %d "
            "authored texture dependency/dependencies:\n\n%s"
            % (missing_count, missing_names or "See the import log."),
            title="Retail asset incomplete")
        return True
    _show_result(
        "PROP IMPORT OK",
        "%s\n\nImported prop roots now in scene: %d"
        % (_format_summary(result), len(_prop_roots())),
        outdir, CHARACTER_LOG)
    return True


# ---------------------------------------------------------------------------
# Animations tab logic
# ---------------------------------------------------------------------------

def _anim_model():
    return _text("libModelField")


def _list_clips(*_):
    problems = _setup_errors() + _plugin_errors()
    if not _anim_model():
        problems.append("Enter a model name.")
    if problems:
        _error("\n\n".join(problems))
        return
    ok, result = _run_command(
        getattr(cmds, CMD_ANIMLIB),
        {"installation": _install_root(), "model": _anim_model()})
    if not ok:
        _error("Clip listing failed:\n%s" % result)
        return
    clips = result or []
    cmds.textScrollList(UI["clipList"], edit=True, removeAll=True)
    if clips:
        cmds.textScrollList(UI["clipList"], edit=True, append=clips)
    cmds.text(UI["clipCount"], edit=True,
              label="%d clip(s). Listing changes nothing in the scene."
              % len(clips))
    cmds.scrollField(UI["clipInfo"], edit=True, text="")


def _selected_clip():
    selected = cmds.textScrollList(UI["clipList"], query=True,
                                   selectItem=True)
    return selected[0] if selected else ""


def _start_timeline_playback():
    """Start Maya playback over the range configured by the C++ bake."""
    try:
        frame_start = float(cmds.playbackOptions(query=True, minTime=True))
        frame_end = float(cmds.playbackOptions(query=True, maxTime=True))
        if frame_end <= frame_start:
            return False, (
                "Animation imported, but Maya's playback range is empty "
                "(%s to %s)." % (frame_start, frame_end)
            )
        cmds.play(state=False)
        cmds.playbackOptions(
            loop="continuous", playbackSpeed=1.0, maxPlaybackSpeed=1.0)
        cmds.currentTime(frame_start, edit=True)
        cmds.play(forward=True)
        return True, "Playback started: frames %g to %g." % (
            frame_start, frame_end)
    except RuntimeError as exc:
        return False, "Animation imported, but playback could not start: %s" % exc


def _configure_selected_clip_for_character(switch_tab):
    """Copy the selected library model/clip to a non-static manual import."""
    clip = _selected_clip()
    if not clip:
        _info("Select a clip first.")
        return ""
    model = _anim_model()
    if not model:
        _info("Enter the animation model first.")
        return ""

    cmds.radioButtonGrp(UI["charMode"], edit=True, select=1)
    _sync_character_mode()
    _set_text("modelField", model)
    _sync_animation_enable()
    _set_text("animField", clip)
    if switch_tab:
        cmds.tabLayout(UI["tabs"], edit=True, selectTabIndex=1)
    return clip


def _inspect_clip(*_):
    clip = _selected_clip()
    if not clip:
        return
    ok, result = _run_command(
        getattr(cmds, CMD_ANIMLIB),
        {"installation": _install_root(), "model": _anim_model(),
         "animation": clip})
    if not ok:
        cmds.scrollField(UI["clipInfo"], edit=True,
                         text="Inspect failed:\n%s" % result)
        return
    rows = result or []
    pairs = list(zip(rows[0::2], rows[1::2]))
    cmds.scrollField(UI["clipInfo"], edit=True,
                     text="\n".join("%s: %s" % (k, v) for k, v in pairs))


def _show_clip_events(*_):
    clip = _selected_clip()
    if not clip:
        _info("Select a clip first.")
        return
    ok, result = _run_command(
        getattr(cmds, CMD_ANIMLIB),
        {"installation": _install_root(), "model": _anim_model(),
         "animation": clip, "events": True})
    if not ok:
        _error("Event query failed:\n%s" % result)
        return
    rows = result or []
    lines = []
    for i in range(0, len(rows) - 3, 4):
        lines.append("%ss  %s  (offset %s)\n    %s"
                     % (rows[i], rows[i + 1], rows[i + 2], rows[i + 3]))
    body = ("\n".join(lines) if lines
            else "No retained events for this clip.")
    _show_result("EVENTS: %s / %s" % (_anim_model(), clip),
                 body + "\n\nEvents are inspection data only; they are "
                 "never executed.")


def _apply_clip_to_character(*_):
    """Set the Character tab's animation. Replaces any previous choice."""
    clip = _configure_selected_clip_for_character(switch_tab=True)
    if not clip:
        return
    cmds.text(UI["clipCount"], edit=True,
              label="'%s' set on the Character tab. It bakes on the next "
                    "import." % clip)


def _import_selected_clip(*_):
    """Replace the active review character with the selected animated clip."""
    clip = _configure_selected_clip_for_character(switch_tab=False)
    if not clip:
        return
    cmds.text(UI["clipCount"], edit=True,
              label="Importing '%s'; playback starts after the bake." % clip)
    _import_character(play_after_import=True, replace_existing=True)


def _active_character_root():
    roots = _character_roots()
    if not roots:
        return ""
    selected = cmds.ls(selection=True, long=True) or []
    selected_roots = []
    for root in roots:
        long_names = cmds.ls(root, long=True) or []
        if not long_names:
            continue
        long_root = long_names[0]
        if any(item == long_root or item.startswith(long_root + "|")
               for item in selected):
            selected_roots.append(root)
    if len(selected_roots) == 1:
        return selected_roots[0]
    if len(roots) == 1:
        return roots[0]
    _error("More than one imported character root exists. Select exactly "
           "one root (or anything beneath it), then press Bind Pose again.")
    return ""


def _matrix16(value):
    if isinstance(value, (list, tuple)) and len(value) == 1:
        if isinstance(value[0], (list, tuple)):
            value = value[0]
    if isinstance(value, (list, tuple)) and len(value) == 16:
        return list(value)
    return None


def _restore_character_bind_pose(root):
    """Remove this root's joint curves and restore Maya's recorded bind pose."""
    joints = cmds.listRelatives(
        root, allDescendents=True, fullPath=True, type="joint") or []
    if not joints:
        return False, "%s contains no Maya joints to restore." % root
    joint_short = {joint.rsplit("|", 1)[-1] for joint in joints}

    poses = []
    posed_joint_names = set()
    for pose in cmds.ls(type="dagPose") or []:
        members = cmds.dagPose(pose, query=True, members=True) or []
        member_short = {member.rsplit("|", 1)[-1] for member in members}
        if joint_short.intersection(member_short):
            poses.append(pose)
            posed_joint_names.update(member_short)

    curves = set()
    curves_by_joint = {}
    for joint in joints:
        joint_curves = []
        for source in cmds.listConnections(
                joint, source=True, destination=False) or []:
            if "animCurve" in (cmds.nodeType(source, inherited=True) or []):
                curves.add(source)
                joint_curves.append(source)
        curves_by_joint[joint] = joint_curves

    bind_matrices = {}
    unsafe_unposed = []
    for joint in joints:
        short = joint.rsplit("|", 1)[-1]
        if short in posed_joint_names:
            continue
        matrix = _matrix16(cmds.getAttr(joint + ".bindPose"))
        if matrix is not None:
            bind_matrices[joint] = matrix
            continue
        varying = False
        for curve in curves_by_joint[joint]:
            values = cmds.keyframe(curve, query=True, valueChange=True) or []
            if values and max(values) - min(values) > 1.0e-8:
                varying = True
                break
        if varying:
            unsafe_unposed.append(short)
    if unsafe_unposed:
        return False, (
            "Exact bind pose is unavailable for these animated helper "
            "joints: %s. Reimport without an animation instead of guessing."
            % ", ".join(sorted(unsafe_unposed))
        )

    cmds.play(state=False)
    frame_start = cmds.playbackOptions(query=True, minTime=True)
    cmds.currentTime(frame_start, edit=True)
    if curves:
        cmds.delete(sorted(curves))

    for joint in sorted(bind_matrices, key=lambda value: value.count("|")):
        cmds.xform(joint, worldSpace=True, matrix=bind_matrices[joint])
    for pose in poses:
        cmds.dagPose(pose, restore=True)

    cmds.playbackOptions(animationStartTime=1, animationEndTime=2,
                         minTime=1, maxTime=2, loop="once")
    cmds.currentTime(1, edit=True)
    return True, (
        "%s restored to bind pose; removed %d joint animation curve(s) "
        "and restored %d Maya bind-pose record(s)."
        % (root, len(curves), len(poses))
    )


def _clear_character_animation(*_):
    root = _active_character_root()
    roots_exist = bool(_character_roots())
    if roots_exist and not root:
        return
    if root:
        ok, message = _restore_character_bind_pose(root)
        if not ok:
            _error(message, title="Cannot restore bind pose")
            return
        _show_result("BIND POSE RESTORED", message)
        label = "Current character restored to bind pose."
    else:
        label = "Animation cleared; next import is bind pose only."
    _set_text("animField", "")
    cmds.text(UI["clipCount"], edit=True, label=label)


# ---------------------------------------------------------------------------
# Level display options (show/hide parts of an imported level)
# ---------------------------------------------------------------------------

def _level_roots():
    return _matching_roots(LEVEL_ROOT_PREFIX)


def _level_room_focus_candidates(root):
    """Visible room transforms without giant sky-dome framing outliers."""
    root_longs = cmds.ls(root, long=True) or []
    if not root_longs:
        return []
    room_groups = [
        child for child in (cmds.listRelatives(
            root_longs[0], children=True, type="transform", fullPath=True) or [])
        if child.rsplit("|", 1)[-1].endswith("_ROOMS")
    ]
    if not room_groups:
        return []

    candidates = []
    for room in (cmds.listRelatives(
            room_groups[0], children=True, type="transform",
            fullPath=True) or []):
        visible_meshes = []
        for shape in (cmds.listRelatives(
                room, allDescendents=True, type="mesh",
                fullPath=True) or []):
            try:
                if cmds.getAttr(shape + ".intermediateObject"):
                    continue
                if not cmds.getAttr(shape + ".visibility"):
                    continue
            except (RuntimeError, ValueError):
                continue
            visible_meshes.append(shape)
        if not visible_meshes:
            continue
        try:
            bounds = cmds.exactWorldBoundingBox(visible_meshes)
        except RuntimeError:
            continue
        dimensions = [bounds[index + 3] - bounds[index]
                      for index in range(3)]
        if not all(0.0 < value < 1.0e19 for value in dimensions):
            continue
        diagonal = sum(value * value for value in dimensions) ** 0.5
        candidates.append((diagonal, room))

    if not candidates:
        return []
    candidates.sort(key=lambda item: (item[0], item[1].casefold()))
    median_diagonal = candidates[len(candidates) // 2][0]
    # A few cinematic rooms contain enormous authored sky/space shells. They
    # remain visible and imported, but must not reduce the playable room core
    # to a dot when Maya frames the new level.
    limit = median_diagonal * 4.0
    core = [room for diagonal, room in candidates if diagonal <= limit]
    return core or [candidates[len(candidates) // 2][1]]


def _reveal_and_frame_imported_level(root):
    """Clear stale isolate state and make a newly imported level visible."""
    panels = [
        panel for panel in (cmds.getPanel(visiblePanels=True) or [])
        if cmds.getPanel(typeOf=panel) == "modelPanel"
    ]
    if not panels:
        return
    for panel in panels:
        if cmds.isolateSelect(panel, query=True, state=True):
            cmds.isolateSelect(panel, state=False)
    panel = panels[0]
    cmds.modelEditor(
        panel, edit=True, displayTextures=True,
        displayAppearance="smoothShaded", useDefaultMaterial=False)
    targets = _level_room_focus_candidates(root) or [root]
    cmds.select(targets, replace=True)
    cmds.setFocus(panel)
    cmds.viewFit(all=False, animate=False, fitFactor=0.8)
    cmds.select(clear=True)


def _display_states():
    states = {}
    for _label, key, _target, _default in LEVEL_GROUPS + SHADER_TOGGLES:
        states[key] = cmds.checkBox(UI[key], query=True, value=True)
    return states


def _hidden_display_labels():
    states = _display_states()
    return [label for label, key, _t, _d in LEVEL_GROUPS + SHADER_TOGGLES
            if not states[key]]


def _set_visibility(node, state):
    try:
        cmds.setAttr(node + ".visibility", state)
    except RuntimeError:
        pass  # locked/connected - leave it alone


def _shader_shapes(root_long, node_type):
    """Long paths of shapes under root shaded by the given plug-in node."""
    shapes = set()
    try:
        nodes = cmds.ls(type=node_type) or []
    except RuntimeError:
        return []  # node type not registered (plug-in unloaded)
    for node in nodes:
        for engine in cmds.listConnections(node, type="shadingEngine") or []:
            for member in cmds.sets(engine, query=True) or []:
                base = member.split(".")[0]
                for long_path in cmds.ls(base, long=True) or []:
                    if long_path.startswith(root_long + "|"):
                        shapes.add(long_path)
    return sorted(shapes)


def _apply_level_display(root):
    states = _display_states()
    root_longs = cmds.ls(root, long=True) or []
    root_long = root_longs[0] if root_longs else "|" + root

    children = cmds.listRelatives(root_long, children=True,
                                  fullPath=True) or []
    for _label, key, suffixes, _default in LEVEL_GROUPS:
        for child in children:
            short = child.rsplit("|", 1)[-1]
            if any(short.endswith(suffix) for suffix in suffixes):
                _set_visibility(child, states[key])

    descendents = cmds.listRelatives(root_long, allDescendents=True,
                                     fullPath=True) or []
    for shape in cmds.ls(descendents, type="light", long=True) or []:
        _set_visibility(shape, states["dispLights"])

    for _label, key, node_type, _default in SHADER_TOGGLES:
        if node_type == "__lights__":
            continue
        for shape in _shader_shapes(root_long, node_type):
            _set_visibility(shape, states[key])


def _apply_display_clicked(*_):
    roots = _level_roots()
    if not roots:
        _info("No imported level in the scene yet. These options are "
              "applied automatically after the next level import.")
        return
    for root in roots:
        _apply_level_display(root)


def _display_preset(show_all):
    for _label, key, _target, _default in LEVEL_GROUPS + SHADER_TOGGLES:
        value = True if show_all else (key in AREA_ONLY_KEYS)
        cmds.checkBox(UI[key], edit=True, value=value)
    for root in _level_roots():
        _apply_level_display(root)


# ---------------------------------------------------------------------------
# Level tab logic
# ---------------------------------------------------------------------------

def _import_level(*_):
    problems = _setup_errors() + _shader_errors() + _plugin_errors()
    module = _text("moduleField")
    area = _text("areaField")
    if not module:
        problems.append("Pick a level (module) first.")
    if not area:
        problems.append("Pick or type the area name (use the ... button "
                        "next to Area).")
    if problems:
        _error("\n\n".join(problems), title="Cannot import")
        return

    missing = _missing_bundle_effects()
    if missing and not _confirm(
            "Shader set beside the plug-in is incomplete (%d missing):\n"
            "%s\n\nSome materials will fail. Import anyway?"
            % (len(missing), "\n".join(missing)), yes="Import Anyway"):
        return

    outdir = _resolve_output_dir(area)
    if not outdir:
        return

    opaque, envmap = _shader_paths()
    kwargs = {
        "installation": _install_root(),
        "module": module,
        "area": area,
        "textureDirectory": outdir,
        "shaderPath": opaque,
        "envShaderPath": envmap,
        "bakedLighting": cmds.checkBox(UI["bakedCheck"], query=True,
                                       value=True),
    }
    roots_before = set(_level_roots())
    ok, result = _run_command(getattr(cmds, CMD_LEVEL), kwargs)
    if not ok:
        _show_result(
            "LEVEL IMPORT FAILED",
            "%s\n\nThe command is non-undoable; clear this scene before "
            "retrying.\nCheck %s in the import cache."
            % (result, LEVEL_LOG),
            outdir, LEVEL_LOG)
        _error("Import failed - see the Result panel.")
        return

    roots_after = _level_roots()
    for root in roots_after:
        _apply_level_display(root)
    _refresh_vp2_after_import()
    created_roots = [root for root in roots_after if root not in roots_before]
    review_root = created_roots[-1] if created_roots else (
        roots_after[-1] if roots_after else "")
    if review_root:
        _reveal_and_frame_imported_level(review_root)
        _refresh_vp2_after_import()

    roots = _count_roots(LEVEL_ROOT_PREFIX)
    body = "%s\n\nImported level roots now in scene: %d" % (
        _format_summary(result), roots)
    hidden = _hidden_display_labels()
    if hidden:
        body += ("\n\nHidden by 'Show in scene' (still imported, tick + "
                 "Apply to reveal): %s" % ", ".join(hidden))
    warning_count = int(_summary_value(result, "warningCount", "0") or 0)
    if warning_count:
        body += (
            "\n\nSOURCE WARNINGS: the level still imported. Check the "
            "retainedLayoutEmitters and missingAuthoredLightmaps rows above, "
            "then open the log for exact source resrefs. No substitute asset "
            "was invented."
        )
    _show_result(
        "LEVEL IMPORTED WITH SOURCE WARNINGS" if warning_count
        else "LEVEL IMPORT OK",
        body, outdir, LEVEL_LOG)


# ---------------------------------------------------------------------------
# Layout builders
# ---------------------------------------------------------------------------

def _label_row(parent, label, field_key, placeholder="", annotation=""):
    row = cmds.rowLayout(parent=parent, numberOfColumns=2,
                         adjustableColumn=2,
                         columnWidth=[(1, LABEL_W)],
                         columnAlign=(1, "right"),
                         columnAttach=[(1, "right", 4), (2, "both", 0)])
    cmds.text(label=label, annotation=annotation)
    UI[field_key] = cmds.textField(placeholderText=placeholder,
                                   annotation=annotation)
    cmds.setParent(parent)
    return row


def _button_row(parent, label, field_key, placeholder, annotation,
                button_label, button_cb, button_width=BROWSE_W):
    row = cmds.rowLayout(parent=parent, numberOfColumns=3,
                         adjustableColumn=2,
                         columnWidth=[(1, LABEL_W), (3, button_width)],
                         columnAlign=(1, "right"),
                         columnAttach=[(1, "right", 4), (2, "both", 0),
                                       (3, "left", 4)])
    cmds.text(label=label, annotation=annotation)
    UI[field_key] = cmds.textField(placeholderText=placeholder,
                                   annotation=annotation)
    cmds.button(label=button_label, width=button_width, command=button_cb)
    cmds.setParent(parent)
    return row


def _path_row(parent, label, field_key, browse_cb, annotation=""):
    row = cmds.rowLayout(parent=parent, numberOfColumns=3,
                         adjustableColumn=2,
                         columnWidth=[(1, LABEL_W), (3, BROWSE_W)],
                         columnAlign=(1, "right"),
                         columnAttach=[(1, "right", 4), (2, "both", 0),
                                       (3, "left", 4)])
    cmds.text(label=label, annotation=annotation)
    UI[field_key] = cmds.textField(changeCommand=_save_setup,
                                   annotation=annotation)
    cmds.button(label="...", width=BROWSE_W, command=browse_cb,
                annotation="Browse")
    cmds.setParent(parent)
    return row


def _build_setup(parent):
    frame = cmds.frameLayout(parent=parent, label="Setup",
                             collapsable=True, marginWidth=6, marginHeight=4)
    col = cmds.columnLayout(parent=frame, adjustableColumn=True,
                            rowSpacing=4)

    cmds.rowLayout(parent=col, numberOfColumns=3, adjustableColumn=2,
                   columnWidth=[(1, LABEL_W), (3, 60)],
                   columnAlign=(1, "right"),
                   columnAttach=[(1, "right", 4), (2, "both", 0),
                                 (3, "left", 4)])
    cmds.text(label="Plug-in",
              annotation="The importer plug-in. Its shader files sit beside "
                         "the .mll and are found automatically when it "
                         "loads.")
    UI["pluginStatus"] = cmds.text(label="Not loaded", align="left")
    cmds.button(label="Load", width=60, command=_load_plugin,
                annotation="Load kotorImporterV114.mll (remembers the "
                           "location). Shaders load automatically from the "
                           "same folder.")
    cmds.setParent(col)

    _path_row(col, "KotOR install", "installField",
              lambda *_: _browse_into("installField",
                                      "KotOR 1 installation folder"),
              annotation="The game folder containing chitin.key. KotOR II "
                         "is not supported.")
    cmds.rowLayout(parent=col, numberOfColumns=2, adjustableColumn=2,
                   columnWidth=[(1, LABEL_W)],
                   columnAlign=(1, "right"),
                   columnAttach=[(1, "right", 4), (2, "both", 0)])
    cmds.text(label="Global up axis",
              annotation="Changes Maya's global working up axis and "
                         "rotates the views. Existing scene nodes and "
                         "source data are not rotated.")
    UI["upAxisButton"] = cmds.button(
        label=_up_axis_button_label(), command=_toggle_up_axis,
        annotation="Toggle Maya Y-up and KotOR Z-up globally. This changes "
                   "Maya's working axis and view orientation; it never "
                   "rewrites imported geometry or source transforms.")
    cmds.setParent(col)
    cmds.setParent(parent)


def _build_character_tab(tabs):
    tab = cmds.columnLayout(parent=tabs, adjustableColumn=True, rowSpacing=6,
                            columnAttach=("both", 2))

    UI["charMode"] = cmds.radioButtonGrp(
        parent=tab, numberOfRadioButtons=2,
        labelArray2=["Manual model", "NPC / creature"], select=1,
        columnWidth2=(130, 140),
        changeCommand=_sync_character_mode,
        annotation="Manual: pick body/head/equipment yourself. NPC / "
                   "creature: browse the game's NPCs, creatures, and "
                   "droids; everything about them comes from the game "
                   "data.")

    UI["manualFrame"] = cmds.frameLayout(
        parent=tab, label="Model and equipment", collapsable=False,
        marginWidth=6, marginHeight=4)
    manual_col = cmds.columnLayout(parent=UI["manualFrame"],
                                   adjustableColumn=True, rowSpacing=4)
    _button_row(manual_col, "Model", "modelField", "e.g. pmbfl",
                "Character body/race model. The browser is sourced from "
                "appearance.2da; standalone models belong in the Prop tab.",
                "...", lambda *_: _pick_character_model_into())
    _button_row(manual_col, "Head", "headField", "optional, e.g. pmhc04",
                "External head, attached via the body's headhook. Leave "
                "empty for models with a built-in head. Browse starts on "
                "male heads (pmh) - change the filter to pfh for female.",
                "...", lambda *_: _pick_head_model_into())
    _button_row(manual_col, "Body texture", "bodyTexField",
                "optional, e.g. pmbalb01",
                "Exact texture name - not a variation number. Browse "
                "starts filtered to the current model's name.",
                "...", lambda *_: _pick_texture_into(
                    "bodyTexField", "Textures", seed=_text("modelField")))
    _button_row(manual_col, "Right hand", "rhandField",
                "optional, e.g. w_lghtsbr_001",
                "Item model for the right hand. The body must have a rhand "
                "hook. Browse starts on weapons (w_).",
                "...", lambda *_: _pick_model_into(
                    "rhandField", "Right-hand items", seed="w_"))
    _button_row(manual_col, "Left hand", "lhandField", "optional",
                "Item model for the left hand. The body must have a lhand "
                "hook. Browse starts on weapons (w_).",
                "...", lambda *_: _pick_model_into(
                    "lhandField", "Left-hand items", seed="w_"))
    _button_row(manual_col, "Mask/goggles", "headEquipField",
                "optional, e.g. i_mask_001",
                "Head-slot item. Needs an external Head with a GoggleHook. "
                "Browse starts on masks (i_mask).",
                "...", lambda *_: _pick_model_into(
                    "headEquipField", "Masks / goggles", seed="i_mask"))
    cmds.setParent(tab)

    UI["sourceFrame"] = cmds.frameLayout(
        parent=tab, label="NPC / creature", collapsable=False,
        marginWidth=6, marginHeight=4)
    src_col = cmds.columnLayout(parent=UI["sourceFrame"],
                                adjustableColumn=True, rowSpacing=4)
    _button_row(src_col, "Level (module)", "srcModuleField",
                "optional - empty browses all levels",
                "The level the creature lives in. Leave empty and use the "
                "Creature ... button to browse every NPC, creature, and "
                "droid in the game.",
                "...", _pick_creature_module)
    _button_row(src_col, "Creature", "srcCreatureField",
                "browse with ...",
                "The creature to import. Browsing lists them by template "
                "name (n_ = NPC, c_ = creature, dr/d_ = droid).",
                "...", _pick_creature)
    cmds.setParent(tab)

    common = cmds.columnLayout(parent=tab, adjustableColumn=True,
                               rowSpacing=4)
    _label_row(common, "Label", "labelField", "auto from fields above",
               "Names the imported root and the export subfolder. Cosmetic "
               "only - it doesn't change what gets imported.")
    UI["animRow"] = cmds.rowLayout(
        parent=common, numberOfColumns=3, adjustableColumn=2,
        columnWidth=[(1, LABEL_W), (3, 74)],
        columnAlign=(1, "right"),
        columnAttach=[(1, "right", 4), (2, "both", 0), (3, "left", 4)])
    cmds.text(label="Animation")
    UI["animField"] = cmds.textField(
        placeholderText="optional - baked at import",
        annotation="One exact clip name, baked as Maya keys at 30 fps "
                   "during the import. Leave empty for bind pose.")
    cmds.button(label="Choose...", width=74, command=_choose_animation,
                annotation="List this model's clips and pick one.")
    cmds.setParent(common)

    cmds.text(parent=common, align="left",
              label="Not undoable. Runs in the current scene.",
              font="smallObliqueLabelFont")
    cmds.button(parent=common, label="Import Character", height=30,
                command=_import_character)
    cmds.setParent(tabs)
    return tab


def _build_prop_tab(tabs):
    tab = cmds.columnLayout(parent=tabs, adjustableColumn=True, rowSpacing=6,
                            columnAttach=("both", 2))
    frame = cmds.frameLayout(
        parent=tab, label="Props / standalone models", collapsable=False,
        marginWidth=6, marginHeight=4)
    col = cmds.columnLayout(parent=frame, adjustableColumn=True, rowSpacing=4)
    cmds.text(
        parent=col,
        label="Character bodies/heads are excluded; source textures are required.",
        align="left",
        annotation="The list is installed MDLs minus models referenced by "
                   "appearance.2da and heads.2da. Imports are static and "
                   "carry no fabricated character rig or animation. A prop "
                   "whose authored textures are absent from the installed "
                   "game is rejected without creating scene nodes.")
    _button_row(
        col, "Model", "propModelField", "e.g. plc_chair1",
        "Installed standalone model. The browser excludes source-authored "
        "character body/race and head components. The compiled importer "
        "requires every authored rendered texture to resolve from this "
        "KotOR installation.",
        "...", lambda *_: _pick_prop_model_into())
    _label_row(
        col, "Label", "propLabelField", "auto from model",
        "Names the KOTOR_PROP_<label>_ROOT created by the native importer.")
    cmds.button(
        parent=col, label="Import Prop / Standalone", height=30,
        command=_import_prop,
        annotation="Imports the exact installed model through the compiled "
                   "V114 prop path. No rig or animation is invented.")
    cmds.setParent(tab)
    return tab


def _build_animations_tab(tabs):
    tab = cmds.columnLayout(parent=tabs, adjustableColumn=True, rowSpacing=6,
                            columnAttach=("both", 2))

    cmds.rowLayout(parent=tab, numberOfColumns=4, adjustableColumn=2,
                   columnWidth=[(1, LABEL_W), (3, BROWSE_W), (4, 74)],
                   columnAlign=(1, "right"),
                   columnAttach=[(1, "right", 4), (2, "both", 0),
                                 (3, "left", 4), (4, "left", 4)])
    cmds.text(label="Model",
              annotation="Model whose clips to list (includes inherited "
                         "supermodel clips).")
    UI["libModelField"] = cmds.textField(
        placeholderText="e.g. pmbfl",
        annotation="Model whose clips to list (includes inherited "
                   "supermodel clips).")
    cmds.button(label="...", width=BROWSE_W,
                command=lambda *_: _pick_model_into("libModelField",
                                                    "Models"),
                annotation="Browse every model in the game.")
    cmds.button(label="List", width=74, command=_list_clips)
    cmds.setParent(tab)

    UI["clipCount"] = cmds.text(parent=tab, align="left",
                                label="Listing changes nothing in the "
                                      "scene.",
                                font="smallObliqueLabelFont")
    UI["clipList"] = cmds.textScrollList(parent=tab, height=190,
                                         allowMultiSelection=False,
                                         selectCommand=_inspect_clip)
    UI["clipInfo"] = cmds.scrollField(parent=tab, editable=False,
                                      wordWrap=False, height=110,
                                      text="Select a clip to see its "
                                           "details.")
    cmds.rowLayout(parent=tab, numberOfColumns=4, adjustableColumn=1,
                   columnWidth=[(2, 68), (3, 58), (4, 78)],
                   columnAttach=[(1, "both", 0), (2, "left", 4),
                                 (3, "left", 4), (4, "left", 4)])
    cmds.button(label="Import + Play", command=_import_selected_clip,
                annotation="Import this exact model and clip through the "
                           "compiled V114 command, then replace the active "
                           "imported character only after that import "
                           "succeeds and start continuous playback.")
    cmds.button(label="Set Only", width=68,
                command=_apply_clip_to_character,
                annotation="Copy this exact model and clip to the Character "
                           "tab without importing. It bakes on that tab's "
                           "next import.")
    cmds.button(label="Bind Pose", width=58,
                command=_clear_character_animation,
                annotation="Stop playback, remove only the selected/current "
                           "imported character's joint animation curves, "
                           "restore its recorded Maya bind pose, and clear "
                           "the Character tab's clip field.")
    cmds.button(label="Events", width=78, command=_show_clip_events,
                annotation="Show the clip's retained events in the Result "
                           "panel. Events are never executed.")
    cmds.setParent(tabs)
    return tab


def _build_level_tab(tabs):
    tab = cmds.columnLayout(parent=tabs, adjustableColumn=True, rowSpacing=6,
                            columnAttach=("both", 2))

    _button_row(tab, "Level (module)", "moduleField", "e.g. danm13",
                "The level's archive name in the game's modules folder "
                "(no .rim). Use ... to pick from the installed list.",
                "...", lambda *_: _pick_installed_module("moduleField",
                                                         "areaField"))
    _button_row(tab, "Area", "areaField", "picked automatically",
                "The area inside that level. Filled automatically when you "
                "pick a level; use ... to re-pick.",
                "...", lambda *_: _pick_area("moduleField", "areaField"))
    UI["bakedCheck"] = cmds.checkBox(
        parent=tab, label="Baked lighting (lightmaps)", value=True,
        annotation="On (default): rooms get their baked lightmaps. Off: "
                   "plain textures only. This is the importer's only "
                   "import-time option.")

    disp = cmds.frameLayout(parent=tab, label="Show in scene",
                            collapsable=True, marginWidth=6, marginHeight=4)
    disp_col = cmds.columnLayout(parent=disp, adjustableColumn=True,
                                 rowSpacing=4)
    cmds.text(parent=disp_col, align="left",
              label="The importer always brings in the complete level.\n"
                    "Unchecked parts are hidden (not skipped) and can be\n"
                    "shown again any time with Apply.",
              font="smallObliqueLabelFont")
    grid = cmds.rowColumnLayout(parent=disp_col, numberOfColumns=2,
                                columnWidth=[(1, 190), (2, 190)])
    for label, key, _target, default in LEVEL_GROUPS + SHADER_TOGGLES:
        UI[key] = cmds.checkBox(parent=grid, label=label, value=default)
    cmds.setParent(disp_col)
    cmds.rowLayout(parent=disp_col, numberOfColumns=3, adjustableColumn=3,
                   columnAttach=[(1, "both", 0), (2, "left", 4),
                                 (3, "left", 4)])
    cmds.button(label="Everything", width=90,
                command=lambda *_: _display_preset(True),
                annotation="Show every part of the level.")
    cmds.button(label="Area only", width=90,
                command=lambda *_: _display_preset(False),
                annotation="Just the environment: rooms, grass, lights, "
                           "particle FX, water.")
    cmds.button(label="Apply", command=_apply_display_clicked,
                annotation="Apply these show/hide choices to the imported "
                           "level in the scene.")
    cmds.setParent(tab)

    cmds.text(parent=tab, align="left",
              label="Not undoable. Sets the scene to 30 fps.",
              font="smallObliqueLabelFont")
    cmds.button(parent=tab, label="Import Full Level", height=30,
                command=_import_level)
    cmds.setParent(tabs)
    return tab


def _build_result(parent):
    frame = cmds.frameLayout(parent=parent, label="Result",
                             collapsable=True, marginWidth=6, marginHeight=4)
    col = cmds.columnLayout(parent=frame, adjustableColumn=True,
                            rowSpacing=4)
    UI["resultField"] = cmds.scrollField(
        parent=col, editable=False, wordWrap=False, height=150,
        text="No command run yet.")
    cmds.rowLayout(parent=col, numberOfColumns=2, adjustableColumn=1,
                   columnAttach=[(1, "both", 0), (2, "left", 4)])
    UI["openDirBtn"] = cmds.button(label="Open Import Cache", enable=False,
                                   command=_open_last_dir)
    UI["openLogBtn"] = cmds.button(label="Open Log", width=110, enable=False,
                                   command=_open_last_log)
    cmds.setParent(parent)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def show():
    """Build (or rebuild) and show the importer window."""
    UI.clear()
    if cmds.workspaceControl(WS, exists=True):
        cmds.deleteUI(WS)
    cmds.workspaceControl(WS, label="KotOR Importer V114", retain=False,
                          floating=True, initialWidth=440,
                          initialHeight=840)

    scroll = cmds.scrollLayout(parent=WS, childResizable=True)
    root = cmds.columnLayout(parent=scroll, adjustableColumn=True,
                             rowSpacing=6, columnAttach=("both", 4))

    _build_setup(root)

    UI["tabs"] = cmds.tabLayout(parent=root, innerMarginWidth=6,
                                innerMarginHeight=6)
    char_tab = _build_character_tab(UI["tabs"])
    prop_tab = _build_prop_tab(UI["tabs"])
    anim_tab = _build_animations_tab(UI["tabs"])
    level_tab = _build_level_tab(UI["tabs"])
    cmds.tabLayout(UI["tabs"], edit=True,
                   tabLabel=[(char_tab, "Character"),
                             (prop_tab, "Prop"),
                             (anim_tab, "Animations"),
                             (level_tab, "Level")])

    _build_result(root)

    install_root = _optvar(OPT_INSTALL) or _optvar(
        "kotorUI112_installRoot")
    _set_text("installField", install_root)
    if install_root and not _optvar(OPT_INSTALL):
        _save_optvar(OPT_INSTALL, install_root)
    _sync_character_mode()
    _refresh_plugin_status()


def install_menu():
    """Add a 'KotOR' menu to Maya's main menu bar."""
    main_window = mel.eval("$kotorUI114Tmp = $gMainWindow")
    if cmds.menu(MENU, exists=True):
        cmds.deleteUI(MENU)
    cmds.menu(MENU, label="KotOR", parent=main_window, tearOff=True)
    cmds.menuItem(parent=MENU, label="Importer V114...",
                  command=lambda *_: show())
