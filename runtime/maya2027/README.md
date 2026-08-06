# KotOR Level Editor for Maya — Beta

Import *Star Wars: Knights of the Old Republic* levels into Autodesk
Maya, browse every asset in the game with thumbnails, place objects and
NPCs, edit containers, loot, and character stats, and export patched
modules you can play immediately.

This toolkit **never touches your game installation or the original
game data**. Every edit is saved as a *copy* of the original asset,
every export goes to an output folder you choose, and putting a change
into the game is always a manual file copy that you make (and can undo
by restoring your backup).

New here? Start with the **[Tutorial](docs/TUTORIAL.md)**. Stuck? See
**[Help](docs/HELP.md)**.

## Requirements

- Windows 10/11
- Autodesk Maya 2024
- A local *Knights of the Old Republic* installation (GOG or Steam)

## Installation

1. Open Maya's **Plug-in Manager** (Windows > Settings/Preferences)
   and load `build\starter-body-importer\Release\kotorImporterV114.mll`
   from this package. Tick *Auto load*.
2. In the Script Editor (Python tab), run — with `<package>` replaced
   by this folder's path:

   ```python
   import sys; sys.path.insert(0, r"<package>\ui")
   import kotor_importer_ui_v114 as kui; kui.install_menu()
   ```

3. A **KotOR** menu appears in Maya's main menu bar. Everything is
   launched from there.

## The tools

| Window | What it does |
|---|---|
| **Level Editor** | Import a module, see every placed marker, move waypoints/sounds/stores/items, place new objects, export patched modules |
| **Asset Browser** | Every template in the game, organized and searchable, with thumbnails rendered from your own install; drag assets into the level |
| **Level Outliner** | Flat list of everything placed in the imported level, with search and folders |
| **Template Editor** | Tabbed editor for any asset: properties, editable fields, loot/inventory; save as a copy or as a brand-new template |
| **Item Browser** | Every item in the game with real names, descriptions, and editable stats |

Right-clicking a KotOR object in the viewport adds KotOR entries to
Maya's normal right-click menu.

## Safety model

- Originals are never modified: edits always produce a **copy** of the
  template under a new name, and only the placement you choose points
  at the copy.
- Exports are written to your chosen output folder, never into the
  game.
- Before testing an edit in game, back up the module file you are
  replacing. The tutorial walks through this.

## Known limitations (beta)

- NPCs *added* to a level appear in game but are not yet interactive
  (retail NPCs, and edits to them, are unaffected).
- Placement editing covers waypoints, sounds, stores, and ground
  items; NPC and door placements are shown read-only.
- Item/creature names, item damage properties, scripts, and dialogue
  are not editable yet.
- Triggers, doors, encounters, and cameras are display-only.
- KotOR 1 only.

## Feedback

This is a beta. If something is confusing, broken, or missing, please
report it with: what you clicked, what you expected, what happened,
and (if relevant) the module you were editing.

---

Developer documentation (file formats, design contracts, verification
protocol) lives in [`docs/`](docs/), starting with
`docs/WRITE_PATH_DESIGN.md` and `docs/CPP_PLUGIN_OPERATORS_MANUAL.md`.
