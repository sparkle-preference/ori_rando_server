import React from 'react';
import {Container, Button, Collapse, Row, Col, Card, CardTitle, CardHeader, CardSubtitle, CardText, CardBody} from 'reactstrap';
import {Helmet} from 'react-helmet';

import {get_param, get_flag, stuff_by_type} from "./common.js"
import SiteBar from "./SiteBar.js"

const GUIDES = ["install", "install_manual", "app", "gen_seed", "get_tracker", "bonus_pickups", "starter_seeds", "differences", "gotchas", "bingo_userboard", "practice", "archipelago"];
// userboard url params, as read by Bingo.js's constructor
const USERBOARD_PARAMS = [
  ["playerList", "off", "Show the player list (scores, teams, timer) beside the board."],
  ["eventLog", "off", "Show the event log: a running feed of squares gained, lost, and bingos completed."],
  ["listWidth", "300", "Width of the player list, in pixels. Only matters with playerList on."],
  ["listHeight", "400", "Height of the player list, in pixels. Only matters with playerList on."],
  ["logWidth", "500", "Width of the event log, in pixels. Only matters with eventLog on."],
  ["logHeight", "200", "Height of the event log, in pixels. Only matters with eventLog on."],
  ["dark", "your profile setting", "Force the dark theme on, whatever your profile says."],
  ["textSize*", "1.5vh", "Bingo goal text size. Increase slowly - anything above 1.8vh can easily overflow."],
  ["hideFooter*", "off", "Hide the square footers that show which players have completed that square."],
  ["hideLabels*", "off", "hide the row, column, and diagonal labels that normally surround the board."]
];
const counts = {
  "standard": { "RB|0": 3, "RB|1": 3, "RB|6": "3/5*", "RB|9": 1, "RB|10": 1, "RB|11": 1, "RB|12": "1/5*", "RB|13": 3, "RB|15": 3, "RB|17": "5**", "RB|19": "5**", "RB|21": "5**"},
  "bonus": { "RB|31": 1, "RB|32": 1, "RB|33": 3, "RB|36": 1, "RB|6": 5, "RB|12": 5, "RB|101": "*", "RB|102": "*", "RB|103": "*", "RB|104": "**", "RB|105": "**", "RB|106": "*", "RB|107": "*", "RB|109": "*", "RB|110": "*", "RB|111": "***", "RB|113": "***"},
}
const buttonHolder="mt-0 pt-0 pb-0 mb-0 text-center border-none"
// spoiler-tagged hint: the label toggles it. (It used to be white-on-white,
// which only hid anything in light mode.)
class Hint extends React.Component {
    state = {shown: false}
    toggle = (e) => {
        e.preventDefault()
        this.setState(prev => ({shown: !prev.shown}))
    }
    render = () => {
        let {label, children} = this.props
        let {shown} = this.state
        return (
            <li>
                <a href="#" onClick={this.toggle}>{label || "Hint"}</a>
                {shown ? <span> (hide): {children}</span> : <span> (show)</span>}
            </li>
        )
    }
}
export default class HelpAndGuides extends React.Component {
    getGlossaryCardContent = () => {
        let normal = []
        let bonus = []
        stuff_by_type["Upgrades"].forEach(upgrade_data => {
        let {label, value, desc} = upgrade_data;
        if(counts["standard"].hasOwnProperty(value)) {
            let count = counts["standard"][value];
            normal.push((
            <Row className="border">
                <Col className="align-self-center text-center" xs="3">{label}</Col>
                <Col className="border-left border-right" xs="8"><small>{desc}</small></Col>
                <Col className="text-center align-self-center" xs="1">{count}</Col>
            </Row>
            ))
        } else if(counts["bonus"].hasOwnProperty(value)) {
            let count = counts["bonus"][value];
            bonus.push((
            <Row className="border">
                <Col className="align-self-center text-center" xs="3">{label}</Col>
                <Col className="border-left border-right" xs="8"><small>{desc}</small></Col>
                <Col className="text-center align-self-center" xs="1">{count}</Col>
            </Row>
            ))
        }
        })
        return (
        <Card className="w-100 mt-2" id="bonus_pickups">
            <CardBody>
            <CardTitle className={buttonHolder}>
                <Button color="primary" active={this.state.open["bonus_pickups"]} onClick={this.toggleOpen("bonus_pickups")}>
                Bonus Item Glossary
                </Button>
            </CardTitle>
            <Collapse isOpen={this.state.open["bonus_pickups"]}>
                <CardText>
                The Ori randomizer contains some totally-new items not found in the base game. Ever wondered what exactly an Attack Upgrade does? Wonder no more!
                </CardText>
                <CardText className="text-center">
                <h5>The following items are  present in all normal seeds.</h5>
                </CardText>
                <Row className="border">
                <Col className="text-center" xs="3">Pickup Name</Col>
                <Col className="border-left border-right text-center" xs="8">Description</Col>
                <Col className="text-center" xs="1">#</Col>
                </Row>
                {normal}
                <Row className="border-left border-right"><Col className="text-center"><small>*: extra copies of this item are added if the "Bonus Pickups" item pool preset is selected.</small></Col></Row>
                <Row className="border-left border-right border-bottom"><Col className="text-center"><small>**: Only in seeds generated with KeyMode set to Shards.</small></Col></Row>
                <CardText className="text-center mt-3">
                <h5>The following items are only present when using the Bonus Pickups item pool preset (or a custom one).</h5>
                </CardText>
                <Row className="border">
                <Col className="text-center" xs="3">Pickup Name</Col>
                <Col className="border-left border-right text-center" xs="8">Description</Col>
                <Col className="text-center" xs="1">#</Col>
                </Row>
                {bonus}
                <Row className="border-left border-right"><Col className="text-center"><small>*: 4 bonus skills are chosen at random in seeds using the Bonus Pickups item pool preset.</small></Col></Row>
                <Row className="border-left border-right"><Col className="text-center"><small>**: At most 1 Teleport bonus skill will be in seeds using the Bonus Pickups item pool preset.</small></Col></Row>
                <Row className="border-left border-right border-bottom"><Col className="text-center"><small>***: Rare bonus skills (10% chance of seeing one in seeds using the Bonus Pickups item pool preset)</small></Col></Row>

            </Collapse>
            </CardBody>
        </Card>
        )
    }
    getInstallCardContent = () => {
        return (<Card className="w-100 mt-2" id="install">
            <CardBody>
                <div className={buttonHolder}>
                    <Button color="primary" active={this.state.open["install"]} onClick={this.toggleOpen("install")}>
                        Installing the Randomizer
                    </Button>
                </div>
                <Collapse isOpen={this.state.open["install"]}>
                    <CardText>
                        The recommended way to install the randomizer is via the Ori DE Rando App (described below).<br/>
                        Note that the app is fully optional (though convenient), and currently only available for Windows.
                        If you wish (or need) to install the randomizer manually, the instructions can be found <a href="/faq?g=install_manual">here</a>
                    </CardText>
                    <CardText className="border">
                        <small>Compatibility Note: The Ori randomizer is only compatible with Ori and the Blind Forest: Definitive Edition (Ori DE) for the PC.
                            It is not compatible the Windows Store version of Ori DE, as the Windows Store has anti-tampering features that prevent the mod from working.</small>
                    </CardText>
                    <CardText>
                        Installation steps:
                        <ol>
                            <li>
                                Download the Rando App from <a target="_blank" href="/app">here</a>.
                            </li>
                            <li>
                                Start the app and install the randomizer. Further features of the app are described <a href="/faq?g=app">here</a>.
                            </li>
                            <li>
                                If the game installation directory can not be found automatically, you will need to select it manually.
                                Typical install locations are:
                                <small><ul><li>
                                    Steam: Your Ori install will be inside your steam install at <code>.../Steam/steamapps/common/Ori DE</code> You can also right click on the game in your Steam library, click properties, then open the "Local Files" tab and click the "Browse Local Files..." button.
                                </li><li>
                                    GOG:  Your Ori install will be inside your GOG install at <code>...GOG Games/Ori and The Blind Forest - Definitive Edition</code> You can also right click on the game in your GOG library, click "Manage Installation" and then "Show folder".
                                </li></ul></small>
                            </li>
                            <li>
                                Installation complete! All you need now to start playing is a seed; either grab one from the Starter Seed check out the guide below to generate your own!
                            </li>
                        </ol>
                    </CardText>
                    <CardText>
                        To play the original game again, simply select "Vanilla" from the version selector in the app.
                    </CardText>
                    {get_flag("ap_flag") ? (
                        <CardText>
                            Playing in an Archipelago session? You will also want{" "}<a target="_blank" rel="noopener noreferrer" href="/apworld">oride.apworld</a>{" "}
                            in your Archipelago install's custom_worlds folder. Only the person generating the session needs it; the rest is <a href="/faq?g=archipelago">here</a>.
                        </CardText>
                    ) : null}
                </Collapse>
            </CardBody>
        </Card>)
    }
    getInstallManualCardContent = () => {
        return (<Card className="w-100 mt-2" id="install_manual">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["install_manual"]} onClick={this.toggleOpen("install_manual")}>
                    Installing the Randomizer (Manual)
                </Button>
                </div>
                <Collapse isOpen={this.state.open["install_manual"]}>
                <CardText>
                    Outside of using the app, installing the randomizer into your existing copy of the game is the easiest way to get started. It will allow you to continue
                    accruing Steam playtime hours and achievements, but will require a bit of work to switch between the regular game and the Randomizer.
                </CardText>
                <CardText className="border">
                    <small>Compatibility Note: The Ori randomizer is only compatible with Ori and the Blind Forest: Definitive Edition (Ori DE) for the PC. 
                        It is not compatible the Windows Store version of Ori DE, as the Windows Store has anti-tampering features that prevent the mod from working.</small>
                </CardText>
                <CardText>
                    Installation steps:
                    <ol>
                    <li>
                        Open the folder where your copy of Ori DE is installed. You'll need to get back here later, so consider making a
                        shortcut or pinning this folder to Quick Access.
                        <small><ul><li>
                            Steam: Your Ori install will be inside your steam install at <code>.../Steam/steamapps/common/Ori DE</code> You can also right click on the game in your Steam library, click properties, then open the "Local Files" tab and click the "Browse Local Files..." button.
                        </li><li>
                            GOG:  Your Ori install will be inside your GOG install at <code>...GOG Games/Ori and The Blind Forest - Definitive Edition</code> You can also right click on the game in your GOG library, click "Manage Installation" and then "Show folder".
                        </li></ul></small>
                    </li>
                    <li>
                        From the Ori folder, navigate to oriDE_Data/Managed. Look for a file named "Assembly-CSharp.dll". To install the randomizer, we will be replacing this file, so create a
                        backup first, either by renaming it to something like Assembly-CSharp-Vanilla.dll, or moving it into a different folder.
                    </li>
                    <li>
                        Download the Randomizer version of Assembly-Csharp.dll{" "}<a target="_blank" rel="noopener noreferrer" href="/dll">here</a>, and move it into the oriDE_Data/Managed folder.
                    </li>
                    <li>
                        Installation complete! All you need now to start playing is a seed; either grab one from the Starter Seed check out the guide below to generate your own!
                    </li>
                    </ol>
                </CardText>
                <CardText>
                    To play the original game again, simply replace your Assembly-CSharp.dll file with the backup you made. If you didn't
                    make one or can't find it, someone in the{" "}<a target="_blank" rel="noopener noreferrer" href="/discord">ori discord</a>{" "}can get you a copy.
                </CardText>
                {get_flag("ap_flag") ? (
                <CardText>
                    Playing in an Archipelago session? You will also want{" "}<a target="_blank" rel="noopener noreferrer" href="/apworld">oride.apworld</a>{" "}
                    in your Archipelago install's custom_worlds folder. Only the person generating the session needs it; the seed page walks you through the rest.
                </CardText>
                ) : null}
                </Collapse>
            </CardBody>
            </Card>)
    }
    getAppCardContent = () => {
        return (<Card className="w-100 mt-2" id="app">
            <CardBody>
                <div className={buttonHolder}>
                    <Button color="primary" active={this.state.open["app"]} onClick={this.toggleOpen("app")}>
                        Rando App
                    </Button>
                </div>
                <Collapse isOpen={this.state.open["app"]}>
                    <CardText>
                        The Randomizer App is a small standalone app to make working with the randomizer more convenient.
                        You can download it <a target="_blank" href="/app">here</a>.
                    </CardText>
                    <CardText className="border">
                        Note: The Rando app is fully optional and currently only available for Windows.
                    </CardText>
                    <CardText>
                        The major features are:
                        <ul>
                            <li>Installing and updating the randomizer</li>
                            <li>Automatically keeping the randomizer up-to date (by selecting the version "Latest")</li>
                            <li>Easily switch between rando versions and vanilla</li>
                            <li>Quickly play seeds by clicking the "Play" button on seed pages</li>
                            <li>Play seeds by dragging & dropping them onto the app (either desktop icon or app window)</li>
                            <li>Automatically archiving old seeds and stats</li>
                            <li>Quick access to game folders and settings files (keybinds, rando settings, etc.)</li>
                        </ul>
                    </CardText>
                </Collapse>
            </CardBody>
        </Card>)
    }
    getGenSeedCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="gen_seed">
                <CardBody>
                    <div className={buttonHolder}>
                    <Button color="primary" active={this.state.open["gen_seed"]} onClick={this.toggleOpen("gen_seed")}>
                        Generating your first seed
                    </Button>
                    </div>
                    <Collapse isOpen={this.state.open["gen_seed"]}>
                    <CardText>
                        In order to play the Ori randomizer, you need a <i>seed file</i>, which specifies the randomized placement of the items. Each randomized playthrough of the game will require a different
                        seed. This guide will walk you through the process of generating and downloading your first seed.
                    </CardText>
                    <CardText>
                        To generate a good beginner seed:
                        <ol>
                        <li>
                            Open the{" "}<a target="_blank" rel="noopener noreferrer" href="/">seed generator page</a>.
                        </li>
                        <li>
                            Change the Logic Mode (in the top-left) from "Standard" to "Casual". The default settings for the other options are
                            fine. If you want, you can give your seed a name using the text box at the bottom.
                            <ul><li><small>
                                <i>Curious about the available options? Check out the built-in help system! Mouse over anything in the UI to learn more about it.</i>
                            </small></li></ul>
                        </li>
                        <li>
                            Click the Generate Seed button to have the server begin generating your seed. It may take a few seconds.
                        </li>
                        <li>
                            Once the generation finishes:
                            <p>
                            If you're using the <a target="_blank" href="/faq?g=app">Rando App</a>:
                            <ul>
                                <li>
                                    Click the Play button to start the game with your seed. Start a new save file and begin playing.
                                    <ul>
                                        <li><small>
                                            Tip: If you get stuck, open the in-game map. It's revealed from the start, and the In Logic
                                            filter shows every pickup you can currently reach.
                                        </small></li>
                                    </ul>
                                </li>
                            </ul>
                            </p>
                            <p>
                            If you aren't using the Rando App:
                            <ol>
                                <li>
                                    Click the Download Seed button to get your seed file. It should download with the name "randomizer.bfr".
                                    <ul>
                                        <li><small>
                                            Tip: If you get stuck, open the in-game map. It's revealed from the start, and the In Logic
                                            filter shows every pickup you can currently reach.
                                        </small></li>
                                    </ul>
                                </li>
                                <li>
                                    Move your randomizer.bfr file to the same folder OriDE.exe is in. (See the installation guide for more details on how to find this folder)
                                </li>
                                <li>
                                    You're all set! Launch the game and start a new save file to begin playing your seed.
                                </li>
                            </ol>
                            </p>
                        </li>
                        </ol>
                    </CardText>
                    </Collapse>
                </CardBody>
            </Card>
        )
    }
    getTrackerCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="get_tracker">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["get_tracker"]} onClick={this.toggleOpen("get_tracker")}>
                    Get the item tracker
                </Button>
                </div>
                <Collapse isOpen={this.state.open["get_tracker"]}>
                <CardText>
                    The item tracker is a helper utility for Ori randomizer players. While completely optional, it can be very useful for keeping track of what items you have.
                </CardText>
                <CardText>
                    To install the tracker:
                    <ol>
                    <li>
                        Download the tracker {" "}<a target="_blank" rel="noopener noreferrer" href="/tracker">here</a>.
                    </li>
                    <li>
                        Extract the files to wherever you would like.
                    </li>
                    <li>
                        After extraction, start the tracker by running OriDETracker.exe. You may wish to make a shortcut if you would like.
                        <ul>
                        <li><small>
                            (Windows may complain or attempt to prevent you from opening the tracker. This is normal)
                        </small></li>
                        </ul>
                    </li>
                    <li>
                        Right click on the tracker and click the Auto-Update button. This will let the tracker automatically update the items you have. 
                    </li>
                        <ul>
                        <li><small>
                            You can also open up the settings window to change the size of the tracker and what kinds of things it tracks.
                        </small></li>
                        </ul>
                    <li>
                        You're all set! Start playing. 
                    </li>
                    </ol>
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }
    getStarterSeedsCardContent = () => {
        return (
        <Card className="w-100 mt-2" id="starter_seeds">
          <CardBody>
            <div className={buttonHolder}>
              <Button color="primary" active={this.state.open["starter_seeds"]} onClick={this.toggleOpen("starter_seeds")}>
                Starter Seeds
              </Button>
            </div>
            <Collapse isOpen={this.state.open["starter_seeds"]}>
            <CardText>
                These seeds have been picked out as decent seeds for learning the Ori randomizer. If you're not sure where to begin, try them out in order. 
            </CardText>
            <CardText><i>
                Need help? click the link to the seed below, then follow the instructions (step 4 onward) from the seedgen guide above. Be sure to check the in-game map if you get stuck!
            </i></CardText>
            <CardText>
                <ol>
                    <li>
                    <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/MyFirstRandoSeed/download?tracking=1">My First Rando Seed</a>
                    <ul><li>A good starter seed. Nothing too tricky required!</li></ul>
                    </li>
                    <li>
                    <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/IntroToClimbStart/download?tracking=1">Intro to Climb Start</a>
                    <ul><li>You won't always start the game with Wall Jump. This seed will require you to navigate the early game using Climb as your form of wall interaction.</li>
                        <Hint>Remember to turn in your mapstones!</Hint>
                    </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/OddOpeningsOne/download?tracking=1">Odd Openings One</a>
                        <ul><li>Sometimes getting out of Glades can be a puzzle. See if you can solve this one! (Remember to check the in-game map if you get stuck)</li>
                        <Hint>Check out the stompable peg near the Blackroot Spirit Well, in the rolling boulder area.</Hint>
                        </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/OddOpeningsTwo/download?tracking=1">Odd Openings Two</a>
                        <ul><li>Same idea as Odd Openings One. Find your way out of Glades!</li>
                        <Hint>Be sure to pay attention to what gets unlocked on the in-game map when you pick up skills <i>and teleporters</i>.</Hint>
                        </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/IntroToBashGrenade/download?tracking=1">Intro To Bash Grenade</a>
                        <ul><li>In the Randomizer, the Grenade (light burst) skill costs no energy, which makes it a very powerful (but somewhat tricky!) method of movement when combined with Bash.</li>
                        <li>Note: Bash+Grenade movement is more difficult when using a controller. Don't worry if it takes you longer to figure out how to get around!</li>
                        <li>Note: You can't bash off of grenades that were thrown while moving, either on the ground or in the air. However, you can (usually) bash off grenades thrown while holding still with climb.</li>
                        </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/TrickyCleanupOne/download?tracking=1">Tricky Cleanup One</a>
                        <ul><li>In some seeds, the biggest challenge can be reaching a specific area. For this seed, that area is Sorrow: figure out how to get up to the Charge Jump tree so that you can finish this seed!</li>
                        <Hint label="Hint 1">There are several ways into Sorrow. For this seed, you can use either the teleporter or Glide+Wind... once you find them!</Hint>
                        <Hint label="Hint 2">The dungeons (Ginso Tree, Forlorn Ruins, and Mount Horu) are full of pickups! Give them a search if you get stuck.</Hint>
                        </ul>
                    </li>
                </ol>
            </CardText>
            </Collapse>
          </CardBody>
        </Card>
        )
    }
    getDifferencesCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="differences">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["differences"]} onClick={this.toggleOpen("differences")}>
                    Rando-Specific features
                </Button>
                </div>
                <Collapse isOpen={this.state.open["differences"]}>
                <CardText>
                    The Ori Randomizer includes a number of gameplay changes from the base game. The most important ones are documented here.
                    <ul>
                    <li>
                        The energy cost of the Grenade (Light Burst) skill has been removed.
                    </li>
                    <li>
                        The energy cost of the Charge Flame skill has been reduced to 1/2; it drops to 0 after leveling Charge Flame Efficiency in the blue ability tree.
                    </li>
                    <li>
                        In addition to the normal pickup locations, you can find pickups by:
                        <ul>
                            <li>
                                Destroying petrified (blue) plants (These now show up on the minimap)
                            </li>
                            <li>
                                Unlocking maps by turning in mapstones (9 pickups, 1 per map)
                            </li>
                            <li>
                                Finishing rooms in Mount Horu (8 pickups, 1 per room)
                            </li>
                        </ul>
                    </li>
                    <li>
                        You can use the Warp keybinding (bound to alt+R by default, rebindable using RandomizerRebindings.txt) to teleport to a Spirit Well at any time, to prevent logical softlocks.
                        <ul>
                            <li>
                                The Sunken Glades Spirit Well is automatically granted to the player upon picking up Sein/Spirit Flame - you can Warp back to Glades to skip fighting the three fronkeys (jumping enemies) that spawn after picking it up.
                            </li>
                        </ul>
                    </li>
                    <li>
                        You start the game with one energy instead of zero.
                    </li>
                    <li>
                        The wall that slowly opens and closes in Blackroot (Below the dash tree, blocking access to the Spirit Well area) is permanently open.
                    </li>
                    <li>
                        The Kuro cutscene in Hollow Grove always plays the first time you go there (In Open World, it will instead never play).
                    </li>
                    <li>
                        The Valley killplane is always active, instead of being active as soon as you get stomp. (In Open World, it is instead never active).
                    </li>
                    <li>
                        First-time pickup animations and Sein's dialog boxes are disabled, just like they would be in the base game with the UI toggled off.
                    </li>
                    <li>
                        There are new pickups not found in the base game, including teleporter unlocks and several bonus pickups. Check out the Bonus Item Glossary guide below to learn more about them.
                    </li>
                    <li>
                        The purple tree has been changed substantially: see the <a href="/patchnotes#3.0" target="_blank" rel="noopener noreferrer">patch notes</a> for details.
                    </li>
                    <li>
                        The UI transparency is increased while performing a "Save Anywhere" glitch. The amount of transparency is configurable in the RandomizerSettings.txt file.
                    </li>
                </ul>
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }

    getUserboardCardContent = () => {
        let user = this.state.user || "YourName"
        let paramRows = USERBOARD_PARAMS.map(([name, def, desc]) => (
            <Row className="border" key={name}>
                <Col className="align-self-center text-center" xs="3"><code>{name}</code></Col>
                <Col className="border-left border-right" xs="6"><small>{desc}</small></Col>
                <Col className="text-center align-self-center" xs="3"><small>{def}</small></Col>
            </Row>
        ))
        return (
            <Card className="w-100 mt-2" id="bingo_userboard">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["bingo_userboard"]} onClick={this.toggleOpen("bingo_userboard")}>
                    Bingo Userboard (for streaming)
                </Button>
                </div>
                <Collapse isOpen={this.state.open["bingo_userboard"]}>
                <CardText>
                    The <b>userboard</b> is a stripped-down view of your bingo board, built to be dropped straight into a streaming layout.
                    It removes the header, buttons, and padding, displaying just the board by default (the player list and event log can be added back in; see below for more info).
                </CardText>
                <CardText>
                    Userboards automatically show the last bingo game you most recently joined and update live when you join new games.
                </CardText>
                <CardText className="border p-2">
                    Your userboard link is:{" "}<a target="_blank" rel="noopener noreferrer" href={`/bingo/userboard/${user}/`}><code>{`${window.location.host}/bingo/userboard/${user}/`}</code></a>
                    {!this.state.user ? (<div><small><i>(Userboards only work while logged in - the above link is a placeholder.)</i></small></div>) : null}
                </CardText>
                <CardText>
                    To add it to OBS:
                    <ol>
                    <li>Add a <b>Browser</b> source to your scene.</li>
                    <li>Paste your userboard link into the URL field.</li>
                    <li>Set the width and height. The board alone is roughly 700&times;700 - add more space for the player list and/or event log if necessary.</li>
                    <li>(Optional) add url params below as desired to customize.</li>
                    </ol>
                </CardText>
                <CardText className="text-center mt-3">
                <h5>URL options</h5>
                </CardText>
                <CardText>
                    Everything is off by default. Add options to the end of your link with <code>?</code> before the first one and <code>&amp;</code> between the rest.
                </CardText>
                <Row className="border">
                    <Col className="text-center" xs="3">Option</Col>
                    <Col className="border-left border-right text-center" xs="6">What it does</Col>
                    <Col className="text-center" xs="3">Default</Col>
                </Row>
                {paramRows}
                <CardText className="mt-3"><div><small><i>(textSize, hideLabels, and hideFooter work on the normal bingo page too.)</i></small></div>
                </CardText>

                <CardText className="mt-3">
                    Examples:
                    <ul>
                    <li>
                        Board plus a player list:{" "}
                        <code>{`/bingo/userboard/${user}/?playerList`}</code>
                    </li>
                    <li>
                        Board, player list, and a wide short event log:{" "}
                        <code>{`/bingo/userboard/${user}/?playerList&eventLog&logWidth=700&logHeight=120`}</code>
                    </li>
                    <li>
                        Narrow player list for a vertical layout:{" "}
                        <code>{`/bingo/userboard/${user}/?playerList&listWidth=180&listHeight=600`}</code>
                    </li>
                    </ul>
                </CardText>
                <CardText className="text-center mt-3">
                <h5>Common questions</h5>
                </CardText>
                <CardText>
                    <ul>
                    <li>
                        <b>I added an option and nothing changed.</b> The options are read once when the page loads. Refresh the browser source
                        (in OBS: right click the source &rarr; Refresh, or reopen its properties and hit OK) after editing the URL.
                    </li>
                    <li>
                        <b>How do I turn an option back off?</b> Delete it from the URL. Writing <code>eventLog=false</code> will <i>not</i> work &mdash;
                        the page only checks whether the option is present, so any value at all (even "false") turns it on.
                    </li>
                    <li>
                        <b>Which player is highlighted?</b> The one matching the preferred player number on your{" "}<a href="/">profile</a>. That player
                        also sorts to the top of the player list.
                    </li>
                    <li>
                        <b>Can I point it at one specific game?</b> Not with a userboard link &mdash; it always follows your latest bingo game by design.
                        For a fixed game, use the spectator link from that game's board page instead.
                    </li>
                    <li>
                        <b>It says it can't find any bingo games.</b> The link uses your site username and only finds games you've actually joined.
                        Join the game first, then the userboard will pick it up.
                    </li>
                    <li>
                        <b>Can I restyle it?</b> Light/dark follows your profile (or <code>dark</code> above). Beyond that, OBS browser sources accept
                        custom CSS, which works fine here &mdash; the board is ordinary HTML.
                    </li>
                    </ul>
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }

    getGotchasCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="gotchas">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["gotchas"]} onClick={this.toggleOpen("gotchas")}>
                    Important Tips/Known Issues
                </Button>
                </div>
                <Collapse isOpen={this.state.open["gotchas"]}>
                <CardText>
                    <ul>
                        <li>
                        The blue tree is by far the most valuable use of ability points, followed by the purple tree. It is not advised to spend more than 2 or 3 points in the red tree.
                        </li>
                        <li>
                        In the Clues keymode, the borders between zones are not always obvious. Check out <a target="_blank" rel="noopener noreferrer" href="https://i.imgur.com/lHgbqmI.jpg">this map</a> to see exactly which pickup is considered to be in which zone!
                        </li>
                        <li>
                        Do not Warp out of any room with a temporary lock (Ginso miniboss 1, Grotto Miniboss, Outer Swamp Spitter puzzle area) with the door still closed. You may softlock if you do.
                        </li>
                        <li>
                        Do not Warp out of the fronkey fight after Sein unless you have already picked up the exp orb below Sein. You may softlock if you do.
                        </li>
                    </ul>
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }

    getArchipelagoCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="archipelago">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["archipelago"]} onClick={this.toggleOpen("archipelago")}>
                    Archipelago
                </Button>
                </div>
                <Collapse isOpen={this.state.open["archipelago"]}>
                <CardText>
                    <a target="_blank" rel="noopener noreferrer" href="https://archipelago.gg">Archipelago</a> is a multi-game randomizer: your skills and upgrades are
                    scattered across everyone's games, and theirs across yours. An Ori rando seed can be part of one.
                </CardText>
                <CardText>
                    Only the person running the Archipelago session installs anything extra. Everyone else plays from a normal seed file and never opens an Archipelago client &mdash;
                    this website connects to the room on their behalf.
                </CardText>
                <CardText>
                    Setup:
                    <ol>
                        <li>
                            Generate a seed with Archipelago turned on, in the Multiplayer tab. Pick the Export Categories while you're there: those are the items that go
                            into the Archipelago pool. Everything else stays an ordinary Ori multiworld item.
                        </li>
                        <li>
                            Put <a target="_blank" rel="noopener noreferrer" href="/apworld">oride.apworld</a> in your Archipelago install's <code>custom_worlds</code> folder,
                            replacing any older copy. Don't rename it &mdash; Archipelago takes the world's name from the file name.
                        </li>
                        <li>
                            On the seed page, hit Get YAMLs and drop the file in Archipelago's <code>Players</code> folder. One file covers every Ori world.
                        </li>
                        <li>
                            Generate the session in Archipelago and host the room. An archipelago.gg room always works; a self-hosted room has to be reachable from the internet.
                        </li>
                        <li>
                            Back on the seed page, enter the room's host and port and hit Connect.
                        </li>
                        <li>
                            Wait for every world to report its item names, then download the seeds and hand them out.
                        </li>
                        <li>
                            Ori players drop their randomizer.bfr in the game folder and play as usual.
                        </li>
                    </ol>
                </CardText>
                <CardText>
                    <ul>
                        <li>
                            <b>A seed I downloaded says "AP Item #12".</b> It was downloaded before the room was connected. Download it again now and the real names are in it.
                        </li>
                        <li>
                            <b>Do I have to keep the site open?</b> No. The connection lives on the server; the seed page is just where you start and check it.
                        </li>
                        <li>
                            <b>Can I use the Bingo goal?</b> Yes. Your board number is your Archipelago world, and winning the board completes it.
                        </li>
                        <li>
                            <b>Hints cost a lot.</b> Hint prices are an Archipelago room setting, the same for every game in the session. Ori worlds are large, so budget accordingly.
                        </li>
                        <li>
                            <b>Death Link?</b> It's a checkbox at generation, and part of the seed &mdash; it can't be turned on or off afterwards.
                        </li>
                    </ul>
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }

    getPracticeCardContent = () => {
        return (
            <Card className="w-100 mt-2" id="practice">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["practice"]} onClick={this.toggleOpen("practice")}>
                    Practice Mode
                </Button>
                </div>
                <Collapse isOpen={this.state.open["practice"]}>
                <CardText>
                    Practice mode runs one stretch of the game over and over against a clock. A segment is a save file plus rules: where the run ends, what you start with,
                    and boxes drawn in the world. PRACTICE on the title menu lists yours.
                </CardText>
                <CardText>
                    To make one, get to the spot you want to practice in a normal game and press Alt+S. Then pick it from the practice menu and start it.
                </CardText>
                <CardText>
                    <b>Boxes.</b> Pause a running segment and choose EDIT PRACTICE SEGMENT: the world freezes and you draw boxes with the mouse.
                    1-4 pick the tool, Z undoes, X deletes the box under the cursor, WASD pans, Enter saves and restarts the attempt.
                    <ul>
                        <li><b>Goal</b> ends the run.</li>
                        <li><b>Kill</b> kills Ori, so you can practice past a checkpoint without walking back.</li>
                        <li><b>Item</b> hands you a pickup, or a message to read as a reminder.</li>
                        <li><b>Solid</b> is a block you can stand on, climb and wall jump off.</li>
                    </ul>
                </CardText>
                <CardText>
                    <b>The editor page.</b> Press 5 in the box editor and the rest opens in your browser, on a map of the world: the name, the end condition,
                    item boxes, shuffle groups, variants and ghosts. Save to game and a running attempt picks up the new rules immediately.
                </CardText>
                <CardText>
                    <b>Ending a run.</b> Any combination of a goal box, skills or events held, a pickup count and locations collected &mdash; every part you set has to hold at once.
                    Finishing shows your time against your best and your average, plus the run's deaths, quits and time spent in menus.
                </CardText>
                <CardText>
                    <b>Ghosts.</b> A ghost of an earlier attempt runs alongside you. Each segment keeps your fastest and your most recent, plus one you pin at the finish screen.
                </CardText>
                <CardText>
                    <b>Variants.</b> One segment, several loadouts: a variant brings its own starting items, boxes, history and ghosts, and shares the start and the ending.
                    Practice the same room with Charge Jump and with Double Jump and each keeps its own best time.
                </CardText>
                <CardText>
                    <b>Shuffle groups.</b> Scatter a set of pickups over a set of spots, redrawn every attempt &mdash; three keystones over five locations, in a different three each time.
                </CardText>
                <CardText>
                    Segments are <code>.bfrp</code> files in the practice folder next to the game. They're safe to copy, rename and send to someone else.
                    <code>RandomizerSettings.txt</code> has the folder, which ghost to race, and whether the timer shows.
                </CardText>
                </Collapse>
            </CardBody>
            </Card>
        )
    }


      constructor(props) {
        super(props);
        let open = {}
        let user = get_param("user");
        GUIDES.forEach(name => {open[name] = false})
        this.state = {user: user, open: open};
    }
    componentDidMount() {
        let url = new URL(window.document.location.href);
        let start_open = url.searchParams.get("g") || "install";
        console.log(start_open, GUIDES.includes(start_open))
        if(GUIDES.includes(start_open))
            this.toggleOpen(start_open)()
    }
    
    toggleOpen = (section) => () => this.setState(prev => {
        prev.open[section] = !(prev.open[section] || false)
        return {open: prev.open}
    }, () => {
        if(this.state.open[section]) {
            let target = document.getElementById(section)
            if(target)
            {
                setTimeout(() => 
                    window.scrollTo({
                        top: target.offsetTop,
                        behavior: "smooth"
                    }), 300) 
            }
        }
    })
        
  render = () => {
    return (
      <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75 border">
        <Helmet>
          <style>{"body { background-color: white, text-color: black}"}</style>
        </Helmet>
        <SiteBar user={this.state.user}/>
        <Card className="w-100">
          <CardBody>
            <CardHeader tag="h2" className="mb-2 text-center">
              Help and Guides
            </CardHeader>
            <CardSubtitle tag="h5" className="pt-3 text-center pb-4">
              Looking for help with the randomizer? You've come to the right place!
            </CardSubtitle>
            <CardText>
              Check out the guides below to learn more about the randomizer.
            </CardText>
            <CardText className="text-center">
              <Button color="success" href="/discord">
                Join the Ori Discord
              </Button>
            </CardText>
            <CardText>
              This page is still under construction! If you have any questions or need more help, please join the discord; it's the fastest and easiest way to get help.
            </CardText>
          </CardBody>
        </Card>
        {this.getInstallCardContent()}
        {this.getInstallManualCardContent()}
        {this.getAppCardContent()}
        {this.getGenSeedCardContent()}
        {this.getStarterSeedsCardContent()}
        {this.getTrackerCardContent()}
        {this.getUserboardCardContent()}
        {this.getPracticeCardContent()}
        {get_flag("ap_flag") ? this.getArchipelagoCardContent() : null}
        {this.getGotchasCardContent()}
        {this.getDifferencesCardContent()}
        {this.getGlossaryCardContent()}
      </Container>
    );
  };
}
