"""Pages that are a redirect or a template name, and nothing else.

A leftovers drawer on purpose: these have no family of their own, and a module
each would be worse than one honest pile.
"""
from flask import Blueprint, redirect, render_template

import util
from models import User
from util import INDEX_TEMPLATE, param_val, template_vals

bp = Blueprint("pages", __name__)


@bp.route('/logichelper') #  LogicHelper
def logic_helper():
        template_values = template_vals("LogicHelper", "Logic Helper", User.get())
        template_values.update({'is_spoiler': "True", 'pathmode': param_val('pathmode'), 'HC': param_val('HC'),
                           'EC': param_val('EC'), 'AC': param_val('AC'), 'KS': param_val('KS'),
                           'skills': param_val('skills'), 'tps': param_val('tps'), 'evs': param_val('evs')})
        return render_template(INDEX_TEMPLATE, **template_values)


@bp.route('/faq') #  Guides
def faqs_guides():
    template_values = template_vals("HelpAndGuides", "Help and Guides", User.get())
    return render_template(INDEX_TEMPLATE, **template_values)


@bp.route('/rebinds') # RebindingsEditor
def rebinding_tool():
    template_values = template_vals("RebindingsEditor", "Ori DERebindings Editor", User.get())
    return render_template(INDEX_TEMPLATE, **template_values)


@bp.route('/discord')
def discord_redirect():
    return redirect("https://discord.gg/TZfue9V")


@bp.route('/discord/dev')
def dev_discord_redirect():
    return redirect("https://discord.gg/sfUr8ra5P7")


@bp.route('/dll')
def dll():
    return redirect(util.DLL_URL % util.DLL_BRANCH)


@bp.route('/app')
def rando_app():
    return redirect("https://github.com/ori-community/bf-rando-installer/releases/latest/download/Ori.DE.Randomizer.exe")


@bp.route('/dll/beta')
def dll_beta():
    return redirect(util.DLL_URL % util.DLL_BETA_BRANCH)


@bp.route('/apworld')
def apworld():
    # short link for the discord, same shape as /dll; point it at a github
    # release once the item tables stop moving
    return redirect("/generator/apworld")


@bp.route('/league/rules')
def league_rules():
    return redirect("https://docs.google.com/document/d/1TDmDPb-zDFQ6gxw_RN-b4S9UxcDQu0ySuXfuWefLZ9c/edit?tab=t.0")


@bp.route('/trickglossary')       
def trickglossary():
    return redirect('https://docs.google.com/document/d/1vjDiXz8UPiIOtUVKPlgzjBn9lrCE4y95EwPt0WnQF_U/')


@bp.route('/trickrepo')           
def trickrepo():
    return redirect('https://www.youtube.com/channel/UCowq0m-wHdwi0vpG3jY1hFA')
