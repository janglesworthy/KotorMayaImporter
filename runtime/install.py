"""KotOR Maya Importer (V114) - installer.

Drag this file into the Maya 2024 viewport to install.

What it does:
  * copies the importer into your Maya user folder
    (Documents/maya/2024/KotorMayaImporterV114),
  * registers it with Maya so the plug-in appears in the Plug-in Manager,
  * adds a "KotOR" menu and a "KotOR" shelf button,
  * opens the importer window.

It does not touch your game installation, and it only writes inside your
Maya user folder.
"""

import os
import shutil
import sys

PACKAGE_NAME = "KotorMayaImporterV114"
PACKAGE_VERSION = "114.0"
PLUGIN_FILE = "kotorImporterV114.mll"
UI_FILE = "kotor_importer_ui_v114.py"
DOC_FILES = ("README.md", "HELP.html")
EFFECT_FILES = (
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

SHELF_ANNOTATION = "KotOR Importer V114"
SHELF_COMMAND = "import kotor_importer_ui_v114 as kui\nkui.show()"

USER_SETUP = '''"""KotOR Maya Importer (V114): adds the KotOR menu at startup."""
import maya.utils


def _kotor_importer_menu():
    try:
        import kotor_importer_ui_v114 as kui
        kui.install_menu()
    except Exception:
        pass


maya.utils.executeDeferred(_kotor_importer_menu)
'''

_ran = {"done": False}


def _source_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return ""


def _add_shelf_button(cmds, mel):
    """Add a KotOR button to the current shelf (skips if already there)."""
    try:
        top = mel.eval("$kotorInstTmp=$gShelfTopLevel")
        current = top + "|" + cmds.tabLayout(top, query=True, selectTab=True)
        for child in cmds.shelfLayout(current, query=True,
                                      childArray=True) or []:
            try:
                if cmds.shelfButton(child, query=True,
                                    annotation=True) == SHELF_ANNOTATION:
                    return
            except RuntimeError:
                continue
        cmds.shelfButton(parent=current, label="KotOR",
                         imageOverlayLabel="KotOR",
                         image="pythonFamily.png",
                         sourceType="python", command=SHELF_COMMAND,
                         annotation=SHELF_ANNOTATION)
    except Exception:
        pass  # the shelf button is a convenience; the menu still works


def install():
    if _ran["done"]:
        return
    _ran["done"] = True

    import maya.cmds as cmds
    import maya.mel as mel

    source = _source_dir()
    if not source or not os.path.isfile(os.path.join(source, PLUGIN_FILE)):
        cmds.confirmDialog(
            title="KotOR Maya Importer",
            message="Please keep install.py inside the unzipped folder, "
                    "next to %s, and drag it into the viewport again."
                    % PLUGIN_FILE,
            button=["OK"], icon="critical")
        return

    missing = [name for name in (PLUGIN_FILE, UI_FILE) + EFFECT_FILES
               if not os.path.isfile(os.path.join(source, name))]
    if missing:
        cmds.confirmDialog(
            title="KotOR Maya Importer",
            message="This package is incomplete - %d file(s) missing:\n\n%s"
                    "\n\nPlease re-download and unzip it again."
                    % (len(missing), "\n".join(missing)),
            button=["OK"], icon="critical")
        return

    user_dir = cmds.internalVar(userAppDir=True)  # Documents/maya/2024/
    dest = os.path.join(user_dir, PACKAGE_NAME)
    if os.path.isdir(dest):
        choice = cmds.confirmDialog(
            title="KotOR Maya Importer",
            message="The importer is already installed.\n\nUpdate the "
                    "installed files?",
            button=["Update", "Cancel"], defaultButton="Update",
            cancelButton="Cancel", dismissString="Cancel", icon="question")
        if choice != "Update":
            return

    plug_dir = os.path.join(dest, "plug-ins")
    scripts_dir = os.path.join(dest, "scripts")
    modules_dir = os.path.join(user_dir, "modules")
    try:
        for folder in (plug_dir, scripts_dir, modules_dir):
            if not os.path.isdir(folder):
                os.makedirs(folder)
        for name in (PLUGIN_FILE,) + EFFECT_FILES:
            shutil.copy2(os.path.join(source, name),
                         os.path.join(plug_dir, name))
        shutil.copy2(os.path.join(source, UI_FILE),
                     os.path.join(scripts_dir, UI_FILE))
        with open(os.path.join(scripts_dir, "userSetup.py"), "w") as handle:
            handle.write(USER_SETUP)
        for name in DOC_FILES:
            doc = os.path.join(source, name)
            if os.path.isfile(doc):
                shutil.copy2(doc, os.path.join(dest, name))
        mod_text = "+ %s %s %s\nplug-ins: plug-ins\nscripts: scripts\n" % (
            PACKAGE_NAME, PACKAGE_VERSION, dest.replace("\\", "/"))
        with open(os.path.join(modules_dir, PACKAGE_NAME + ".mod"),
                  "w") as handle:
            handle.write(mod_text)
    except (OSError, shutil.Error) as exc:
        cmds.confirmDialog(
            title="KotOR Maya Importer",
            message="Install failed:\n%s\n\nIf an older copy is currently "
                    "in use, restart Maya and drag install.py again." % exc,
            button=["OK"], icon="critical")
        return

    # Point the importer window at the installed plug-in so its Load button
    # works with no browsing.
    plugin_path = os.path.join(plug_dir, PLUGIN_FILE).replace("\\", "/")
    cmds.optionVar(stringValue=("kotorUI114_pluginPath", plugin_path))

    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    _add_shelf_button(cmds, mel)

    opened = True
    try:
        import kotor_importer_ui_v114 as kui
        kui.install_menu()
        kui.show()
    except Exception:
        opened = False

    extra = "" if opened else ("\n\nOpen the window from the KotOR menu "
                               "after restarting Maya.")
    cmds.confirmDialog(
        title="KotOR Maya Importer installed",
        message="Installed to:\n%s\n\nAdded: the KotOR menu, a KotOR shelf "
                "button, and a Plug-in Manager entry.\n\nNext, in the "
                "window's Setup section:\n1. Press Load.\n2. Set 'KotOR "
                "install' to your game folder. The importer manages its "
                "derived-file cache automatically.%s" % (dest, extra),
        button=["OK"], icon="information")


def onMayaDroppedPythonFile(*_args):
    install()


if __name__ == "__main__":
    try:
        import maya.cmds  # noqa: F401
    except ImportError:
        print("Open Maya 2024 and drag install.py into the viewport to "
              "install.")
    else:
        install()
