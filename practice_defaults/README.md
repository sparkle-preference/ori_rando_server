Default practice segments. Every .bfrp here is offered to players; the game downloads the ones they don't have into their practice folder at launch. The file name is the segment's name.

- A player who deletes or renames one never gets it again.
- Changing a file here doesn't update the copies players already have, with one exception: demo ghosts. To replace one, put the old demo's SHA-1 in `retired_demos.txt` and ship the new demo. A client newer than 5.0.1 whose copy still holds that exact demo takes the new one at launch; a demo the player made stays.
- Names can't contain dots. `test/practice_defaults_test.py` checks every file.
- The game lists defaults after the player's own segments. `order.txt` (optional) sets their order: one name per line, then any it leaves out alphabetically.
