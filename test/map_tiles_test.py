"""The map's tile host serves nothing past TILE_MAX_ZOOM, and Leaflet's default
lets a TileLayer zoom to 18, so an uncapped layer goes black two wheel clicks in.
Every map page has to cap its layer at the shared constant.

Run from the repo root:  python3 -m unittest test.map_tiles_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "map", "src")


def read(name):
    with io.open(os.path.join(SRC, name), encoding="utf-8") as f:
        return f.read()


class MapTilesTestCase(unittest.TestCase):
    def test_every_tile_layer_stops_at_the_hosted_zoom(self):
        pages = [n for n in os.listdir(SRC) if n.endswith(".js") and "<TileLayer" in read(n)]
        self.assertTrue(pages, "no page renders a TileLayer any more")
        for name in pages:
            for layer in re.findall(r"<TileLayer[^>]*>", read(name)):
                self.assertIn("maxNativeZoom={TILE_MAX_ZOOM}", layer, name)
                self.assertIn("maxZoom={TILE_MAX_ZOOM", layer, name)
            self.assertIn("TILE_MAX_ZOOM", re.search(r"import \{[^}]*\} from './shared_map.js'", read(name)).group(0), name)

    def test_the_crs_and_the_layers_share_one_number(self):
        shared = read("shared_map.js")
        self.assertIn("const TILE_MAX_ZOOM = 7;", shared)
        self.assertIn("let maxZoom = TILE_MAX_ZOOM;", shared)


if __name__ == "__main__":
    unittest.main()
