# Help & Reference

Quick answers first, then a reference for every window.

## FAQ

**Does this modify my game?** Never by itself. Edits are saved as
copies of the originals, and exports go to a folder you choose.
The only way a change reaches the game is you copying an exported
module into `<game>\modules\` — which you can always undo by
restoring your backup.

**Why did my save say "refused"?** The editor checks every save
against the original game data and refuses anything it cannot verify
(a name that's already taken, an item that doesn't exist, a value that
doesn't fit the field). The message says exactly what to fix — nothing
was written.

**Why is this thing read-only?** Some data types aren't editable yet
in the beta: NPC/door *placements*, names and descriptions, item
damage properties, scripts, triggers/doors/encounters/cameras. The UI
tells you when you've hit one.

**How do I open the in-game console?** `EnableCheats=1` under
`[Game Options]` in `swkotor.ini`, then press `` ` `` in game and type
blind (e.g. `warp danm13`).

## Marker colors

| Color | Meaning |
|---|---|
| Blue | waypoint |
| Yellow | sound |
| Green | store |
| White | ground item |
| Purple | placed object (pending) |
| Red | placed NPC (pending) |

## Level Editor panel

- **Import Level** — imports the typed module (auto-detects its area,
  loads the plug-in and shaders, styles markers).
- **Detect** — re-binds the panel to a level already in the scene.
- Family tabs — every editable marker; select to see properties.
  Position/bearing edits are written on export.
- **Add + tab** — palette of placeable templates; *Place* drops one
  into the viewport as a pending marker; **Export With Adds** writes
  it.
- **Check Changes** — dry-run export showing the exact bytes that
  would change. **Reset Sel. / Reset All** undo edits to source
  values.
- **Export Patched Module** — the real export, to your output folder.
- Display toggles: *Marker size*, *Retained FX markers*, *Live floor*,
  *Walkmeshes* (teal overlay, hidden by default).

## Asset Browser

- Left: categories (People / Objects / Markers). Top: search.
- Cards show thumbnails; *group duplicates* merges same-model
  variants into one card with a variant picker.
- **Place** — drop the selected template into the imported level.
- **Edit Asset** / right-click — open it in the Template Editor.
- **Rescan** rebuilds the catalog; **Refresh Previews** regenerates
  thumbnails (runs outside Maya; safe to keep working).

## Level Outliner

Searchable list of everything placed in the level. Selecting a row
selects it in the viewport. Right-click for Edit Asset / Edit
Properties. Folders are for your own organization — display only.

## Template Editor

Opens from any right-click > Edit Template, browser card, or the
KotOR menu.

- Header shows how many placements share this template — your edits
  are stored in a copy, so none of them change unless you point one
  at it.
- **Properties tab** — the full decoded template, read-only.
- **Edit Fields tab** — every editable field with a filter box.
  Numbers get typed ranges; text fields take plain text.
- **Loot / Inventory tab** — container loot or creature inventory.
  Add (browse or type), remove, per-item stats via right-click.
  For creatures, *Dropable* makes added items lootable from remains.
- **Save as Fork + Repoint** — apply staged edits to a copy and make
  the chosen placed record use it.
- **Save as New Template...** — save the edited copy under a new name
  without touching any placement; it appears in the Asset Browser
  after you deploy and Rescan.

## Item Browser

Every item the game can resolve (566 in a typical install), searchable
by name or resref, with descriptions and stats. **Add to Loot** stages
the selected item into the open Template Editor; the Stats box stages
Cost/StackSize/Charges edits.

## Troubleshooting

| Symptom | Fix |
|---|---|
| KotOR menu missing | Re-run the install snippet from the README |
| Import Level fails immediately | Check the install path; the folder must contain `chitin.key` |
| Detect finds nothing | There's no imported level in the scene — use Import Level |
| Thumbnails are placeholder cubes | Press **Refresh Previews** in the Asset Browser and wait for the batch to finish |
| Save refused: "resref already exists" | Pick a different new-template name |
| Save refused: "plugin is older" | Restart Maya so the current plug-in build loads |
| Placed NPC isn't interactive in game | Known beta limitation — added NPCs render but don't respond yet |
| Game shows old data after deploy | Make sure you copied the exported module over the right file, and that no leftover test module shadows it |
| Want the game back to stock | Restore your backed-up module files |
