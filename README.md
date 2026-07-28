# KotOR Maya Importer (V114)

Import characters, standalone props, animations, and complete levels from **Star Wars: Knights
of the Old Republic** into **Autodesk Maya 2024**.

The importer reads your own installed copy of the game directly. Nothing from
the game is included in this package, and the tool never writes to your game
folder.

## Download

Download the ready-to-install package from the
[latest GitHub release](https://github.com/janglesworthy/KotorMayaImporter/releases/latest).
This repository is a compiled-only distribution; C++ source code is not
included. The `runtime` folder contains the same application files as the
release package.

## Features

- **Characters** — import any player body with a head, weapons in either
  hand, a mask or goggles, and an exact game texture. Skin weights and the
  skeleton come across intact.
- **NPCs, creatures, and droids** — browse every creature in the game by
  name (per level, or all at once) and import one with its full equipment,
  exactly as the game defines it.
- **Standalone props** — the separate Prop tab lists installed models that
  are not character bodies or heads. Props import as static geometry with no
  fabricated rig or animation. If the retail installation itself lacks an
  authored texture, the exact geometry still imports with source diffuse
  color and an explicit warning listing the missing resrefs. No replacement
  or copied game asset is invented.
- **Animations** — list every animation clip a model can play, inspect clip
  details, or use **Import + Play** to bake the selected clip as regular
  Maya keyframes at 30 fps and start continuous timeline playback. When a
  character is already active, the successful animated import replaces it
  instead of creating an overlapping copy. Use **Bind Pose** to stop
  playback and restore the active imported character.
- **Working-axis toggle** — switch Maya globally between its normal Y-up
  convention and KotOR Z-up without rewriting imported scene nodes.
- **Complete levels** — import a whole level in a couple of clicks: rooms
  with baked lightmaps, doors, placeables, creatures, grass, water,
  particle effects, lights, cameras, sounds, and more. A successful import
  clears stale viewport isolation and frames the ordinary room core, so huge
  authored sky shells cannot leave the level offscreen or reduced to a dot.
- **K1 swoop/minigame maps** — Taris, Tatooine, and Manaan retain their
  installed LYT track hooks, obstacle placements, rendered obstacle models,
  and hidden source collision volumes. No game assets are bundled.
- **K1 cinematic/STUNT maps** — authored no-model rooms, native reference
  nodes, source-only emitters, sky textures, optional WOK data, lightmap
  warnings, additive displays, and partially transparent placeables are
  retained without fabricated replacements. All 20 installed STUNT modules
  are supported.
- **Show in scene toggles** — show or hide parts of an imported level
  (NPCs, waypoints, lights, particle FX, water, and so on) with checkboxes
  or one-click presets.
- **Safe by design** — import-only. The tool never modifies your KotOR
  installation.

## Supported KotOR 1 data

The importer reads these formats directly from the selected game installation:

| Category | Working formats and content |
|---|---|
| Game archives and indexes | `KEY`, `BIF`, `RIM`, and `ERF` |
| Models and animation | Binary `MDL` and `MDX`, including meshes, skeletons, skin weights, animation clips and events, room models, equipment, native lights, emitters, dangly meshes, AABB trees, and lightsaber data |
| Textures and materials | `TPC`, `TGA`, and `TXI`, including diffuse textures, alpha, lightmaps, environment maps, bump/bumpy-shiny materials, water, grass, additive materials, punch-through materials, and animated texture sequences |
| Game tables and names | `2DA` and `TLK` |
| Level layout and visibility | `LYT`, `VIS`, and `WOK` |
| Level and object records | `IFO`, `ARE`, `GIT`, `UTC`, `UTP`, `UTD`, `UTI`, `UTS`, `UTW`, `UTT`, `UTE`, and `UTM` |
| Audio | WAV audio and KotOR's packaged MPEG-compressed sound streams, imported as Maya audio nodes |

The output is a native Maya scene: polygon meshes, joints, skin clusters,
keyframes, cameras, lights, audio nodes, organized transforms, and Viewport 2.0
materials. This release does not export or write game files.

## Requirements

- Windows 10 or 11, 64-bit
- Autodesk Maya 2024
- A legally installed copy of **Star Wars: Knights of the Old Republic**
  (GOG, Steam, or disc)

KotOR II is not supported.

## Installation

1. Unzip this package anywhere.
2. Open Maya 2024.
3. Drag **install.py** from the unzipped folder into the Maya viewport.

That's it. The installer copies everything into your Maya user folder, adds
a **KotOR** menu to the main menu bar and a **KotOR** button to the current
shelf, and opens the importer window.

### First-time setup (once)

In the window's **Setup** section:

1. Press **Load** — the plug-in loads and finds its shader files
   automatically.
2. Set **KotOR install** to your game folder — the one that contains
   `chitin.key` and `swkotor.exe` (for example
   `C:/GOG Games/Star Wars - KotOR`).

These are remembered between Maya sessions. There is no Export folder
setting: the importer automatically keeps decoded textures, audio, and logs
in `Documents/maya/KotorMayaImporterCache/V114`. **Open Import Cache** in the
Result panel reveals the exact folder used by the last import.

The **Global up axis** button in Setup toggles **Maya Y-up** and
**KotOR Z-up**. It changes Maya's working grid and views; it does not rotate
existing objects.

### Manual installation

If drag-and-drop doesn't work for you:

1. Copy the unzipped folder to
   `Documents/maya/2024/KotorMayaImporterV114`.
2. Inside that copy, make two subfolders: `plug-ins` (move the `.mll` and
   all `.ogsfx` files into it — they must stay together) and `scripts`
   (move `kotor_importer_ui_v114.py` into it).
3. Create a text file `Documents/maya/2024/modules/KotorMayaImporterV114.mod`
   containing (adjust the path to yours):

   ```
   + KotorMayaImporterV114 114.0 C:/Users/YOU/Documents/maya/2024/KotorMayaImporterV114
   plug-ins: plug-ins
   scripts: scripts
   ```

4. Restart Maya, then run in the Script Editor (Python):

   ```python
   import kotor_importer_ui_v114 as kui
   kui.install_menu()
   kui.show()
   ```

## Uninstalling

Drag **uninstall.py** into the Maya viewport. It removes the menu, the shelf
button, the saved settings, and the installed files. (If the game importer
was used in the current scene, save your work and start a new scene first.)

## Help

Open **HELP.html** in any web browser for the full user guide, including a
tour of every field, the safety dialogs you may see, troubleshooting, and an
FAQ.

## Legal

- This package contains **no game assets**. It reads only from your own
  legally installed copy of the game.
- Textures and audio that the importer writes to its managed cache are
  derived from your copy of the game. They are for your personal use — do
  not redistribute them.
- This is a fan-made tool. It is not affiliated with, endorsed by, or
  supported by Lucasfilm, Disney, BioWare, Aspyr, or Autodesk. All
  trademarks are the property of their respective owners.
- Provided free of charge, as-is, without warranty of any kind.

## Package contents

| File | Purpose |
|---|---|
| `install.py` | Drag into Maya to install |
| `uninstall.py` | Drag into Maya to remove |
| `README.md` | This file |
| `HELP.html` | Full user guide |
| `kotorImporterV114.mll` | The importer plug-in (Maya 2024, 64-bit) |
| `*.ogsfx` (16 files) | Viewport shaders — keep beside the `.mll` |
| `kotor_importer_ui_v114.py` | The importer window |
