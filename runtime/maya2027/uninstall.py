"""KotOR Level Editor - uninstaller.

Drag this file into the Maya viewport to remove the editor.

It removes the KotOR menu, the shelf button, the module registration
and the installed files from your Maya user folder. It does not touch
your game installation, and it leaves anything you exported alone.
"""

import os
import shutil
import sys

PACKAGE_NAME = "KotorLevelEditor"
LEGACY_PACKAGE = "KotorMayaImporterV114"
PLUGIN_NAME = "kotorImporterV114"
SHELF_ANNOTATIONS = ("KotOR Level Editor", "KotOR Importer V114")
OPTION_VARS = ("kotorUI114_pluginPath", "kotorW6_installRoot",
               "kotorW6_outputBase")
MENUS = ("kotorLevelEditorW6Menu", "kotorImporterMenu")

_ran = {"done": False}


def _remove_shelf_buttons(cmds, mel):
    try:
        top = mel.eval("$kotorUninstTmp=$gShelfTopLevel")
        for tab in cmds.tabLayout(top, query=True, childArray=True) or []:
            shelf = top + "|" + tab
            for child in cmds.shelfLayout(shelf, query=True,
                                          childArray=True) or []:
                try:
                    note = cmds.shelfButton(child, query=True,
                                            annotation=True)
                except RuntimeError:
                    continue
                if note in SHELF_ANNOTATIONS:
                    try:
                        cmds.deleteUI(child)
                    except RuntimeError:
                        pass
    except Exception:
        pass


def uninstall():
    if _ran["done"]:
        return
    _ran["done"] = True

    import maya.cmds as cmds
    import maya.mel as mel

    choice = cmds.confirmDialog(
        title="KotOR Level Editor",
        message="Remove the KotOR Level Editor from Maya?\n\nYour game "
                "installation and anything you exported are not "
                "touched.",
        button=["Remove", "Cancel"], defaultButton="Remove",
        cancelButton="Cancel", dismissString="Cancel", icon="question")
    if choice != "Remove":
        return

    # Close tool windows so nothing holds the files open.
    for module in ("kotor_template_inspector_w8", "kotor_item_picker_w8",
                   "kotor_asset_browser_w7", "kotor_outliner_w7",
                   "kotor_level_editor_w6"):
        mod = sys.modules.get(module)
        if mod is None:
            continue
        try:
            window = getattr(mod, "_STATE", {}).get("window")
            if window is not None:
                window.close()
        except Exception:
            pass
        try:
            ws = getattr(mod, "WS", "")
            if ws and cmds.workspaceControl(ws, exists=True):
                cmds.deleteUI(ws)
        except Exception:
            pass

    for menu in MENUS:
        try:
            if cmds.menu(menu, exists=True):
                cmds.deleteUI(menu)
        except Exception:
            pass
    _remove_shelf_buttons(cmds, mel)

    unloaded = True
    try:
        if cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
            cmds.file(new=True, force=True)
            cmds.unloadPlugin(PLUGIN_NAME)
    except Exception:
        unloaded = False

    for name in OPTION_VARS:
        try:
            if cmds.optionVar(exists=name):
                cmds.optionVar(remove=name)
        except Exception:
            pass

    user_dir = cmds.internalVar(userAppDir=True)
    removed, kept = [], []
    for package in (PACKAGE_NAME, LEGACY_PACKAGE):
        target = os.path.join(user_dir, package)
        mod_file = os.path.join(user_dir, "modules", package + ".mod")
        for path in (mod_file, target):
            if not os.path.exists(path):
                continue
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                removed.append(path)
            except OSError:
                kept.append(path)

    if kept:
        message = ("Partly removed.\n\nThese files are still in use:\n"
                   "%s\n\nRestart Maya and drag uninstall.py again."
                   % "\n".join(kept))
        icon = "warning"
    elif removed:
        message = ("Removed:\n%s\n\nRestart Maya to finish clearing the "
                   "menu." % "\n".join(removed))
        icon = "information"
    else:
        message = "Nothing to remove - no installed copy was found."
        icon = "information"
    if not unloaded:
        message += ("\n\nThe plug-in could not be unloaded; it will be "
                    "gone after a restart.")
    cmds.confirmDialog(title="KotOR Level Editor", message=message,
                       button=["OK"], icon=icon)


def onMayaDroppedPythonFile(*_args):
    uninstall()


if __name__ == "__main__":
    try:
        import maya.cmds  # noqa: F401
    except ImportError:
        print("Open Maya and drag uninstall.py into the viewport.")
    else:
        uninstall()
