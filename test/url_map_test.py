"""Every URL and method the service answers.

This is a move-detector, not a spec: the point is that shuffling routes between
modules changes nothing a client can see. It pins rules and methods and NOT
endpoint names, because a route joining a blueprint is renamed by design
(bingo_board -> bingo.bingo_board) while its URL must not move.

Adding or removing a route fails this. That is the intent -- update EXPECTED in
the same commit, so the diff shows the URL surface changing.

HEAD and OPTIONS are dropped: Flask derives both, so they carry no signal.

Run from the repo root:  python3 -m unittest test.url_map_test -v
"""
import inspect
import unittest

import main

EXPECTED = [
    "GET /",
    "GET /activeGames/",
    "GET /activeGames/<hours>/",
    "GET /app",
    "GET /apworld",
    "GET /authorize",
    "GET /beta/claim/<secret>",
    "GET /bingo/bingothon/<int:game_id>/player/<int:player_id>",
    "GET /bingo/board",
    "GET /bingo/from_game/<int:game_id>",
    "GET /bingo/game/<int:game_id>/add/<int:player_id>",
    "GET /bingo/game/<int:game_id>/fetch",
    "GET /bingo/game/<int:game_id>/remove/<int:player_id>",
    "GET /bingo/game/<int:game_id>/reroll",
    "GET /bingo/game/<int:game_id>/reroll_board",
    "GET /bingo/game/<int:game_id>/seed/<int:player_id>",
    "GET /bingo/game/<int:game_id>/start",
    "GET /bingo/new",
    "GET /bingo/spectate",
    "GET /bingo/spectate/<name>",
    "GET /bingo/userboard/<name>/",
    "GET /bingo/userboard/<name>/fetch/<game_id>",
    "GET /cache/clear",
    "GET /clean/",
    "GET /discord",
    "GET /discord/dev",
    "GET /dll",
    "GET /dll/beta",
    "GET /faq",
    "GET /flags",
    "GET /game/<int:game_id>",
    "GET /game/<int:game_id>/delete/",
    "GET /game/<int:game_id>/history/",
    "GET /game/<int:game_id>/player/<pid>/remove/",
    "GET /game/<int:game_id>/players/",
    "GET /generator/apworld",
    "GET /generator/apyaml/<params_id>/<int:world_id>",
    "GET /generator/apyamls/<params_id>",
    "GET /generator/aux_spoiler/<params_id>",
    "GET /generator/json",
    "GET /generator/metadata/<param_id>",
    "GET /generator/metadata/<param_id>/<int:game_id>",
    "GET /generator/seed/<params_id>",
    "GET /generator/spoiler/<params_id>",
    "GET /league/rules",
    "GET /logichelper",
    "GET /login",
    "GET /logout",
    "GET /myGames",
    "GET /myPresets",
    "GET /netcode/areas",
    "GET /netcode/game/<int:game_id>/ap/status",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/callback/<path:signal>",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/complete",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>/",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/goals",
    "GET /netcode/game/<int:game_id>/player/<int:player_id>/ws",
    "GET /oidc_callback",
    "GET /patchnotes",
    "GET /patchnotes.json",
    "GET /patchnotes.xml",
    "GET /patchnotes/<version>",
    "GET /patchnotes/announce",
    "GET /pickupandlocinfo",
    "GET /plando/<author_name>",
    "GET /plando/<author_name>/<seed_name>/",
    "GET /plando/<author_name>/<seed_name>/download",
    "GET /plando/<author_name>/<seed_name>/spoiler",
    "GET /plando/<seed_name>/delete",
    "GET /plando/<seed_name>/edit",
    "GET /plando/<seed_name>/hideToggle",
    "GET /plando/<seed_name>/rename/<new_name>",
    "GET /plando/fillgen",
    "GET /plandos",
    "GET /preset/<owner_name>/<name>",
    "GET /preset/<owner_name>/<name>/roll",
    "GET /preset/latest",
    "GET /preset/list",
    "GET /preset/mine/<name>/delete",
    "GET /preset/mine/<name>/hideToggle",
    "GET /quickstart",
    "GET /rebinds",
    "GET /reroll",
    "GET /reset/<int:game_id>",
    "GET /theme/toggle",
    "GET /tracker",
    "GET /tracker/game/<int:game_id>/",
    "GET /tracker/game/<int:game_id>/<int:player_id>/items",
    "GET /tracker/game/<int:game_id>/fetch/gamedata",
    "GET /tracker/game/<int:game_id>/fetch/items/<int:player_id>",
    "GET /tracker/game/<int:game_id>/fetch/player/<int:player_id>/seed",
    "GET /tracker/game/<int:game_id>/fetch/update",
    "GET /tracker/game/<int:game_id>/items",
    "GET /tracker/game/<int:game_id>/map",
    "GET /tracker/spectate/<name>",
    "GET /transfer/<int:game_id>/<int:player_id>",
    "GET /trickglossary",
    "GET /trickrepo",
    "GET /user/settings",
    "GET /user/settings/name-free",
    "GET /vanilla",
    "GET /version",
    "GET /version/beta",
    "GET /version/json",
    "GET /version/latest",
    "GET /version/minimum",
    "GET,POST /generator/build",
    "POST /netcode/game/<int:game_id>/ap/connect",
    "POST /netcode/game/<int:game_id>/ap/disconnect",
    "POST /netcode/game/<int:game_id>/player/<int:player_id>/bingo",
    "POST /netcode/game/<int:game_id>/player/<int:player_id>/connect",
    "POST /netcode/game/<int:game_id>/player/<int:player_id>/setSeed",
    "POST /netcode/game/<int:game_id>/player/<int:player_id>/tick",
    "POST /netcode/game/<int:game_id>/player/<int:player_id>/tick/",
    "POST /plando/<seed_name>/upload",
    "POST /plando/reachable",
    "POST /preset/delete",
    "POST /preset/edit",
    "POST /preset/save",
    "POST /user/settings/update",
]


def live_rules():
    out = []
    for rule in main.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        methods = ",".join(sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")))
        out.append("%s %s" % (methods, rule.rule))
    return sorted(out)


class UrlMapTestCase(unittest.TestCase):
    def test_url_surface_is_unchanged(self):
        live = live_rules()
        added = [r for r in live if r not in EXPECTED]
        gone = [r for r in EXPECTED if r not in live]
        self.assertEqual(
            (added, gone), ([], []),
            "URL surface moved.%snew: %s%sgone: %s%s"
            "If you meant it, update EXPECTED. If you were moving routes between "
            "modules, you did not mean it." % (chr(10), added, chr(10), gone, chr(10)))

    def test_every_handler_accepts_exactly_its_url_variables(self):
        """Flask hands a view the rule's variables as keyword arguments, so a
        handler whose signature disagrees is a 500 on every request to it.

        This is what catches a decorator binding to the wrong function: inserting
        a def directly beneath an existing @route steals it, the URL stays
        registered, and nothing else notices. /reroll spent a week that way.
        """
        for rule in main.app.url_map.iter_rules():
            fn = main.app.view_functions.get(rule.endpoint)
            if fn is None or rule.endpoint == "static":
                continue
            # flask_sock injects the connection; it is not a URL variable
            injected = {"conn"} if rule.endpoint.startswith("__flask_sock.") else set()
            params = list(inspect.signature(fn).parameters.values())
            takes_kwargs = any(p.kind is p.VAR_KEYWORD for p in params)
            named = {p.name for p in params
                     if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
            required = {p.name for p in params
                        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
                        and p.default is p.empty} - injected
            args = set(rule.arguments)

            if not takes_kwargs:
                self.assertFalse(args - named,
                                 "%s: the URL supplies %s, %s does not accept it"
                                 % (rule, sorted(args - named), rule.endpoint))
            self.assertFalse(required - args,
                             "%s: %s requires %s, which the URL never supplies"
                             % (rule, rule.endpoint, sorted(required - args)))

    def test_every_rule_is_reachable_by_name(self):
        """A blueprint split renames endpoints; url_for must still resolve each."""
        for rule in main.app.url_map.iter_rules():
            self.assertTrue(main.app.view_functions.get(rule.endpoint),
                            "no view function for %s" % rule.endpoint)


if __name__ == "__main__":
    unittest.main()
