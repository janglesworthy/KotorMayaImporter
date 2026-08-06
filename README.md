# KotOR Level Editor for Maya

**KotOR Level Editor** is a compiled **Star Wars: Knights of the Old
Republic** toolkit for **Autodesk Maya 2024 and 2027**. It imports
characters, props, animations and complete Odyssey-engine levels — and
now *edits* them: place objects and NPCs, change container loot,
creature inventories, item stats and template fields, and export
patched modules you can play.

The toolkit reads your own installed copy of the game. No game data is
included here, and **your game installation is never modified**. Edits
are saved as a *copy* of the original asset, exports go to a folder you
choose, and installing a change into the game is always a manual file
copy you make yourself.

## Download

Get the package for your Maya version from the
[latest release](https://github.com/janglesworthy/KotorMayaImporter/releases/latest):

| Package | For |
|---|---|
| `KotorLevelEditor-1.0.0-beta-Maya2024.zip` | Autodesk Maya 2024 (Python 3.10) |
| `KotorLevelEditor-1.0.0-beta-Maya2027.zip` | Autodesk Maya 2027 (Python 3.13) |

This repository is a compiled-only distribution; C++ source code is not
included. The `runtime/maya2024` and `runtime/maya2027` folders contain
the same application files as the release packages.

## Install

1. Unzip anywhere.
2. Drag **install.py** into the Maya viewport.
3. A **KotOR** menu and shelf button appear. Start with
   **KotOR > Level Editor...**

`TUTORIAL.md` in the package walks through a full first session in
about 20 minutes, ending with you looting a chest you stocked, inside
the game. Drag **uninstall.py** into the viewport to remove everything.

## The tools

| Window | What it does |
|---|---|
| **Level Editor** | Import a module, see every placed marker, move waypoints/sounds/stores/items, place new objects and NPCs, export patched modules |
| **Asset Browser** | Every template in the game, searchable, with 2,400+ rendered thumbnails; place assets into the level |
| **Level Outliner** | Flat, searchable list of everything placed in the imported level |
| **Template Editor** | Tabbed editor for any asset: properties, editable fields, loot/inventory; save as a copy or as a brand-new template |
| **Item Browser** | Every item in the game with real names, descriptions and editable stats |

KotOR entries also appear inside Maya's own right-click menu.

## Importing

- **Characters** — any player body with a head, weapons in either hand,
  a mask or goggles, and exact game textures. Skin weights and skeleton
  intact.
- **NPCs, creatures and droids** — browse every creature by name and
  import one with its full equipment, exactly as the game defines it.
- **Standalone props** — static geometry with no fabricated rig. If the
  installation itself lacks an authored texture, the exact geometry
  still imports with source diffuse colour and an explicit warning.
- **Animations** — list a model's clips, inspect them, or bake one as
  Maya keyframes at 30 fps and play it back.
- **Complete levels** — rooms with baked lightmaps, doors, placeables,
  creatures, grass, water, particle effects, lights, cameras, sounds
  and more, including the swoop/minigame maps and all 20 STUNT modules.
- **Working-axis toggle** — switch Maya between Y-up and KotOR Z-up
  without rewriting scene nodes.

## Editing

- **Placement** — move waypoints, sounds, stores and ground items;
  place any template from the browser with a click-to-drop preview.
- **Container loot** — add and remove items, browse the game's full
  item library by real name, edit per-item Cost/StackSize/Charges.
- **Creature inventory and drops** — give an NPC items that can be
  looted from its remains, even if it normally carries nothing.
- **Template fields** — an editable, filterable form of every supported
  field (locks, DCs, HP, tags, stats — 53 fields on a container, 60 on
  a creature).
- **Save as New Template** — save your edited version under a new name
  without touching any placed object; it then appears in the Asset
  Browser as a placeable library entry.
- **Check Changes** — a dry-run export showing exactly which bytes a
  real export would alter, before you write anything.

## How edits stay safe

Every write is verified byte-for-byte before anything is saved, and the
release is gated by independent checkers that re-derive the expected
bytes from the original game data:

| Area | Checks |
|---|---|
| Container loot editing | 37 |
| Item stat editing | 42 |
| Field editing + save-as-new-template | 19 |
| Creature inventory / drops | 39 |

The Maya 2024 and Maya 2027 builds are also proven to produce
**byte-identical output** from identical inputs.

## Supported KotOR 1 data

| Category | Working formats and content |
|---|---|
| Game archives and indexes | `KEY`, `BIF`, `RIM`, `ERF` |
| Models and animation | Binary `MDL`/`MDX`: meshes, skeletons, skin weights, clips and events, room models, equipment, lights, emitters, dangly meshes, AABB trees, lightsaber data |
| Textures and materials | `TPC`, `TGA`, `TXI`: diffuse, alpha, lightmaps, environment maps, bump/bumpy-shiny, water, grass, additive, punch-through, animated sequences |
| Game tables and names | `2DA`, `TLK` |
| Level layout and visibility | `LYT`, `VIS`, `WOK` |
| Level and object records | `IFO`, `ARE`, `GIT`, `UTC`, `UTP`, `UTD`, `UTI`, `UTS`, `UTW`, `UTT`, `UTE`, `UTM` |
| Audio | WAV and KotOR's packaged MPEG-compressed streams, as Maya audio nodes |

Writing covers area records (`GIT`) and object templates (`UTP`, `UTC`,
`UTI` and the other placement families) packaged into module `RIM`
containers. Geometry, scripts, dialogue and game tables are read-only.

## Requirements

- Windows 10 or 11, 64-bit
- Autodesk Maya 2024 **or** 2027
- A legally installed copy of **Star Wars: Knights of the Old
  Republic** (GOG, Steam, or disc)

KotOR II is not supported.

## Beta limitations

- NPCs *added* to a level render in game but are not yet interactive.
  Retail NPCs, and edits to them, are unaffected.
- Placement editing covers waypoints, sounds, stores and ground items;
  NPC and door placements are shown read-only.
- Item and creature names, item damage properties, scripts and dialogue
  are not editable yet.
- Triggers, doors, encounters and cameras are display-only.

## Help

`HELP.md` in the package has an FAQ, a per-window reference and a
troubleshooting table. `TUTORIAL.md` is the guided first session.

## Legal

- This package contains **no game assets**. It reads only from your own
  legally installed copy of the game.
- Textures and audio written to the managed cache are derived from your
  copy of the game, for your personal use — do not redistribute them.
- Fan-made tool. Not affiliated with, endorsed by, or supported by
  Lucasfilm, Disney, BioWare, Aspyr, or Autodesk. All trademarks belong
  to their respective owners.
- Provided free of charge, as-is, without warranty of any kind.
