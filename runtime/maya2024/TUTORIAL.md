# Tutorial — your first editing session

This walkthrough takes about 20 minutes and ends with you looting a
chest *you* stocked, inside the real game. It uses Dantooine's Jedi
Enclave (module `danm13`), but any module works.

## 0. One-time setup

Follow the Installation steps in the [README](../README.md): load the
`kotorImporterV114` plug-in and install the **KotOR** menu. Also enable
the game's console for testing: in `swkotor.ini` under
`[Game Options]`, add `EnableCheats=1`.

## 1. Import a level

1. **KotOR menu > Level Editor...**
2. Check *KotOR install* points at your game folder.
3. Type `danm13` in *Module* (or use the pick list), press
   **Import Level**.
4. After a couple of minutes the Enclave courtyard appears, and the
   panel lists every editable marker.

## 2. Getting around

- Colored cubes are the level's markers: **blue** = waypoints,
  **yellow** = sounds, **green** = stores, **white** = ground items.
  (Placed objects you add later: **purple** = containers/placeables,
  **red** = NPCs.) The *Marker size* slider scales them.
- Clicking any part of an NPC or a marker cube selects the whole
  thing, and the panel jumps to it.
- **KotOR menu > Level Outliner...** shows everything placed in the
  level as a searchable list.
- **Right-click** any KotOR object in the viewport: the top of Maya's
  menu gains *Edit Template* (and *Edit Properties* for markers).

## 3. Move something and export

1. Click a blue waypoint cube. The panel shows its X/Y/Z and bearing.
2. Change X by +1, or just drag the marker with Maya's Move tool.
3. Press **Check Changes** — the panel shows *exactly* which bytes of
   the module would change (here: one position field).
4. Press **Export Patched Module**. A patched `danm13.rim` lands in
   your output folder. Nothing in the game has changed yet.

## 4. Test it in the game

1. **Back up the original**: copy
   `<game>\modules\danm13.rim` somewhere safe.
2. Copy your exported `danm13.rim` over it.
3. Launch the game, load any save, press `` ` `` and type
   `warp danm13` (the console is invisible — type blind).
4. Done testing? Copy your backup back. The game is exactly as it was.

## 5. Place a chest

1. **KotOR menu > Asset Browser...** Pick *Objects > Containers*,
   select a footlocker (thumbnails included), press **Place**.
2. Click a floor spot in the viewport — a preview chest lands there.
   Fine-tune with the Move tool.
3. In the Level Editor panel, press **Export With Adds**. The packed
   module now contains your chest. Deploy and warp as in step 4 —
   the chest is there, opens, and is lootable.

## 6. Stock the chest

1. Right-click your chest (or any container) > **Edit 'name'
   Template**. The Template Editor opens.
2. **Loot tab** > **Browse Items...** — every item in the game, with
   real names. Search "blaster", select one, **Add to Loot**.
3. Want it pricier? Select the item row, edit **Cost / StackSize /
   Charges** in the Stats box, press **Stage Stat Edit**.
4. Back in the Template Editor, pick which placed chest to change in
   *Placed record*, press **Save as Fork + Repoint**. Your changes are
   stored in a *copy* of the template; the original stays untouched.
5. Deploy the exported module and loot your work in game.

## 7. Give an NPC droppable loot

Right-click an NPC > **Edit Template** > **Inventory / Drops** tab.
Add an item, leave *Dropable* checked, save. In game, that NPC's
remains now carry the item. (Works even for creatures that normally
carry nothing.)

## 8. Change fields, or make a new template

- **Edit Fields tab**: every editable property of the template —
  locks, HP, tags, stats — with a filter box. Change values, save.
- **Save as New Template...** saves your edited version under a brand
  new name *without* touching any placed object. After deploying,
  press **Rescan** in the Asset Browser and your creation is in the
  library, placeable like anything else.

## 9. Where things live

| What | Where |
|---|---|
| Exported modules | your chosen output folder |
| Template Editor saves | `work\w8_ui_out\` |
| Thumbnails | `work\asset_thumbs\` (Refresh Previews regenerates) |

**Golden rule:** back up any module file before overwriting it, and
restore backups when you finish testing.
