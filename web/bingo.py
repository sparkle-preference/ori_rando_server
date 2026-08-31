"""Bingo board URLs, shared before the bingo routes themselves move.

The create/reroll modal opens on these parameters, so a board matches the seed
it came from. Presets and the generator both hand a freshly rolled game here.
"""


def bingo_board_url(game, params, disc=None, team_max=None):
    url = "/bingo/board?game_id=%s&fromGen=1&seed=%s&bingoLines=%s" % (
        game.key.id(), params.seed, params.bingo_lines)
    # the create modal opens on these, so a board matches the seed it came from
    url += "&bingoGoal=%s&bingoSquares=%s&bingoDiff=%s" % (
        params.bingo_goal, params.bingo_squares, params.bingo_diff)
    if params.bingo_meta:
        url += "&bingoMeta=1"
    # a caller's disc wins even when it is an explicit off, so a reroll keeps it
    disc = params.bingo_disc if disc is None else disc
    if disc:
        url += "&disc=%s" % disc
    if team_max:
        url += "&teamMax=%s" % team_max
    return url
