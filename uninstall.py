"""KotOR Maya Importer (V114) - uninstaller.

Drag this file into the Maya 2024 viewport to remove the importer.

It removes the KotOR menu, the shelf button, the saved settings, and the
installed files from your Maya user folder. Your game installation, your
scenes, and the managed import cache are not touched.
"""

import os
import shutil

PACKAGE_NAME = "KotorMayaImporterV114"
PLUGIN_NAME = "kotorImporterV114"
WINDOW_NAME = "kotorImporterV114WC"
MENU_NAME = "kotorImporterV114Menu"
SHELF_ANNOTATION = "KotOR Importer V114"
OPTION_VARS = ("kotorUI114_installRoot", "kotorUI114_outputBase",
               "kotorUI114_pluginPath")

_ran = {"done": False}


def uninstall():
    if _ran["done"]:
        return
    _ran["done"] = True

    import maya.cmds as cmds
    import maya.mel as mel

    # Unload the plug-in first. If the current scene still uses it, ask for
    # a clean scene instead of forcing anything.
    try:
        if cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
            try:
                cmds.unloadPlugin(PLUGIN_NAME)
            except RuntimeError:
                cmds.confirmDialog(
                    title="KotOR Maya Importer",
                    message="The current scene still uses the importer's "
                            "materials, so it can't be removed yet.\n\n"
                            "Save your work, start a new scene (File > "
                            "New Scene), then drag uninstall.py again.",
                    button=["OK"], icon="warning")
                return
    except RuntimeError:
        pass

    # Close the window and remove the menu.
    if cmds.workspaceControl(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)

    # Remove KotOR shelf buttons from every shelf.
    try:
        top = mel.eval("$kotorUninstTmp=$gShelfTopLevel")
        for tab in cmds.tabLayout(top, query=True, childArray=True) or []:
            shelf = top + "|" + tab
            for child in cmds.shelfLayout(shelf, query=True,
                                          childArray=True) or []:
                try:
                    if cmds.shelfButton(child, query=True,
                                        annotation=True) == SHELF_ANNOTATION:
                        cmds.deleteUI(child)
                except RuntimeError:
                    continue
    except Exception:
        pass

    # Forget the saved settings.
    for var in OPTION_VARS:
        if cmds.optionVar(exists=var):
            cmds.optionVar(remove=var)

    # Delete the installed files.
    user_dir = cmds.internalVar(userAppDir=True)
    dest = os.path.join(user_dir, PACKAGE_NAME)
    mod_file = os.path.join(user_dir, "modules", PACKAGE_NAME + ".mod")
    leftovers = []
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
        if os.path.isdir(dest):
            leftovers.append(dest)
    if os.path.isfile(mod_file):
        try:
            os.remove(mod_file)
        except OSError:
            leftovers.append(mod_file)

    if leftovers:
        message = ("Almost done. Maya is still holding on to:\n\n%s\n\n"
                   "Restart Maya, then delete it by hand."
                   % "\n".join(leftovers))
    else:
        message = ("The KotOR Maya Importer has been removed.\n\nYour "
                   "scenes and managed import cache were not touched. Note that "
                   "previously saved scenes need the importer installed to "
                   "display their materials.")
    cmds.confirmDialog(title="KotOR Maya Importer", message=message,
                       button=["OK"], icon="information")


def onMayaDroppedPythonFile(*_args):
    uninstall()


if __name__ == "__main__":
    try:
        import maya.cmds  # noqa: F401
    except ImportError:
        print("Open Maya 2024 and drag uninstall.py into the viewport to "
              "uninstall.")
    else:
        uninstall()
