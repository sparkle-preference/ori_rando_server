import json
import unittest
from urllib.parse import unquote

from mockclient.client import WsClient
from mockclient.seedfile import goal_shapes_from

# a board with two ActivateTeleporter cards (one well, a count of wells) folds them into one entry
LINE = "Goals:BreakPlants-7/ActivateTeleporter:COUNT,mangroveFalls/GetEvent:Sunstone,Water Vein/DrainSwamp:COUNT"


class GoalShapesTestCase(unittest.TestCase):
    def test_count_is_a_flag_beside_the_listed_subgoals(self):
        shapes = goal_shapes_from(LINE)
        self.assertEqual(shapes["ActivateTeleporter"], ("multi", ["mangroveFalls"], "count"))
        self.assertEqual(shapes["DrainSwamp"], ("multi", [], "count"))
        self.assertEqual(shapes["GetEvent"], ("multi", ["Sunstone", "Water Vein"], None))
        self.assertEqual(shapes["BreakPlants"], ("int", [], 7))


class PostTestCase(unittest.TestCase):
    def posted(self, name):
        client = WsClient("http://mock", "Sync1.1,Standard,Bingo|seed\n" + LINE + "\n")
        client.ws_open, client.version, frames = True, "4.9.13", []
        client.send_frame = frames.append
        client.complete_goal(name)
        client.post_bingo()
        body = frames[0].split("bingoData=", 1)[1].split("&version=")[0]
        return json.loads(unquote(body))[name]

    def test_a_merged_entry_completes_both_cards(self):
        # the well card reads its subgoal, the count card reads the total
        self.assertEqual(self.posted("ActivateTeleporter"), {"value": {"mangroveFalls": {"value": True}}, "total": 9999})

    def test_a_bare_count_posts_a_count(self):
        self.assertEqual(self.posted("DrainSwamp"), {"value": {}, "total": 9999})

    def test_a_list_posts_its_subgoals(self):
        self.assertEqual(self.posted("GetEvent"),
                         {"value": {"Sunstone": {"value": True}, "Water Vein": {"value": True}}, "total": 2})


if __name__ == "__main__":
    unittest.main()
