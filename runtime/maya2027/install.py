"""KotOR Level Editor (beta) - installer.

Drag this file into the Maya 2027 viewport to install.

It copies the toolkit into your Maya user folder, registers it so the
plug-in appears in the Plug-in Manager, and adds a KotOR menu and shelf
button. It never touches your game installation.
"""

import os
import shutil
import sys

PACKAGE_NAME = "KotorLevelEditor"
PACKAGE_VERSION = "1.0.0"
MAYA_VERSION = "2027"
PLUGIN_FILE = "kotorImporterV114.mll"
UI_MODULES = (
    "kotor_importer_ui_v114",
    "kotor_level_editor_w6",
    "kotor_asset_browser_w7",
    "kotor_outliner_w7",
    "kotor_template_inspector_w8",
    "kotor_item_picker_w8",
)
DOC_FILES = ("README.md", "TUTORIAL.md", "HELP.md", "LICENSE")

SHELF_ANNOTATION = "KotOR Level Editor"
SHELF_COMMAND = ("import kotor_importer_ui_v114 as kui\n"
                 "kui.install_menu()\nkui.show()")

USER_SETUP = '''"""KotOR Level Editor: adds the KotOR menu at startup."""
import maya.utils


def _kotor_menu():
    try:
        import kotor_importer_ui_v114 as kui
        kui.install_menu()
    except Exception:
        pass


maya.utils.executeDeferred(_kotor_menu)
'''

_ran = {"done": False}


def _source_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return ""


def _add_shelf_button(cmds, mel):
    try:
        top = mel.eval("$kotorInstTmp=$gShelfTopLevel")
        current = top + "|" + cmds.tabLayout(top, query=True,
                                             selectTab=True)
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
        pass  # convenience only; the menu still works


def install():
    if _ran["done"]:
        return
    _ran["done"] = True

    import maya.cmds as cmds
    import maya.mel as mel

    source = _source_dir()
    plug_src = os.path.join(source, "plug-ins")
    script_src = os.path.join(source, "scripts")
    if not os.path.isfile(os.path.join(plug_src, PLUGIN_FILE)):
        cmds.confirmDialog(
            title="KotOR Level Editor",
            message="Please keep install.py inside the unzipped folder "
                    "(next to the plug-ins and scripts folders) and drag "
                    "it into the viewport again.",
            button=["OK"], icon="critical")
        return

    running = cmds.about(version=True)
    if MAYA_VERSION not in str(running):
        choice = cmds.confirmDialog(
            title="KotOR Level Editor",
            message="This package is built for Maya %s but you are "
                    "running Maya %s.\n\nThe plug-in will not load. "
                    "Download the package for your Maya version."
                    % (MAYA_VERSION, running),
            button=["Install anyway", "Cancel"],
            defaultButton="Cancel", cancelButton="Cancel",
            dismissString="Cancel", icon="warning")
        if choice != "Install anyway":
            return

    missing = [name for name in UI_MODULES
               if not os.path.isfile(os.path.join(script_src,
                                                  name + ".pyc"))]
    if missing:
        cmds.confirmDialog(
            title="KotOR Level Editor",
            message="This package is incomplete - %d file(s) missing:"
                    "\n\n%s\n\nPlease re-download and unzip it again."
                    % (len(missing), "\n".join(missing)),
            button=["OK"], icon="critical")
        return

    user_dir = cmds.internalVar(userAppDir=True)
    dest = os.path.join(user_dir, PACKAGE_NAME)
    if os.path.isdir(dest):
        choice = cmds.confirmDialog(
            title="KotOR Level Editor",
            message="The editor is already installed.\n\nUpdate the "
                    "installed files?",
            button=["Update", "Cancel"], defaultButton="Update",
            cancelButton="Cancel", dismissString="Cancel",
            icon="question")
        if choice != "Update":
            return

    plug_dir = os.path.join(dest, "plug-ins")
    scripts_dir = os.path.join(dest, "scripts")
    modules_dir = os.path.join(user_dir, "modules")
    try:
        for folder in (plug_dir, scripts_dir, modules_dir):
            if not os.path.isdir(folder):
                os.makedirs(folder)
        for name in sorted(os.listdir(plug_src)):
            shutil.copy2(os.path.join(plug_src, name),
                         os.path.join(plug_dir, name))
        for name in sorted(os.listdir(script_src)):
            shutil.copy2(os.path.join(script_src, name),
                         os.path.join(scripts_dir, name))
        with open(os.path.join(scripts_dir, "userSetup.py"),
                  "w") as handle:
            handle.write(USER_SETUP)
        for name in DOC_FILES:
            doc = os.path.join(source, name)
            if os.path.isfile(doc):
                shutil.copy2(doc, os.path.join(dest, name))
        mod_text = "+ %s %s %s\nplug-ins: plug-ins\nscripts: scripts\n" \
            % (PACKAGE_NAME, PACKAGE_VERSION, dest.replace("\\", "/"))
        with open(os.path.join(modules_dir, PACKAGE_NAME + ".mod"),
                  "w") as handle:
            handle.write(mod_text)
    except (OSError, shutil.Error) as exc:
        cmds.confirmDialog(
            title="KotOR Level Editor",
            message="Install failed:\n%s\n\nIf an older copy is in use, "
                    "restart Maya and drag install.py again." % exc,
            button=["OK"], icon="critical")
        return

    plugin_path = os.path.join(plug_dir, PLUGIN_FILE).replace("\\", "/")
    cmds.optionVar(stringValue=("kotorUI114_pluginPath", plugin_path))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    _add_shelf_button(cmds, mel)

    opened = True
    try:
        import kotor_importer_ui_v114 as kui
        kui.install_menu()
    except Exception:
        opened = False

    extra = "" if opened else ("\n\nRestart Maya, then use the KotOR "
                               "menu.")
    cmds.confirmDialog(
        title="KotOR Level Editor installed",
        message="Installed to:\n%s\n\nAdded: the KotOR menu, a shelf "
                "button, and a Plug-in Manager entry.\n\nOpen "
                "KotOR > Level Editor..., set your game folder, type a "
                "module name (try danm13) and press Import Level.\n\n"
                "See TUTORIAL.md for a guided first session.%s"
                % (dest, extra),
        button=["OK"], icon="information")


def onMayaDroppedPythonFile(*_args):
    install()


if __name__ == "__main__":
    try:
        import maya.cmds  # noqa: F401
    except ImportError:
        print("Open Maya %s and drag install.py into the viewport."
              % MAYA_VERSION)
    else:
        install()
