import React from 'react';
import {Container, Button, Collapse, Row, Col, Card, CardTitle, CardHeader, CardSubtitle, CardText, CardBody} from 'reactstrap';
import {Helmet} from 'react-helmet';

import {get_param, stuff_by_type} from "./common.js"
import SiteBar from "./SiteBar.js"

const GUIDES = ["install", "gen_seed", "get_tracker", "bonus_pickups", "starter_seeds", "differences", "gotchas"];
const counts = {
  "standard": { "RB|0": 3, "RB|1": 3, "RB|6": "3/5*", "RB|9": 1, "RB|10": 1, "RB|11": 1, "RB|12": "1/5*", "RB|13": 3, "RB|15": 3, "RB|17": "5**", "RB|19": "5**", "RB|21": "5**"},
  "bonus": { "RB|31": 1, "RB|32": 1, "RB|33": 3, "RB|36": 1, "RB|6": 5, "RB|12": 5, "RB|101": "*", "RB|102": "*", "RB|103": "*", "RB|104": "**", "RB|105": "**", "RB|106": "*", "RB|107": "*", "RB|109": "*", "RB|110": "*"},
}
const buttonHolder="mt-0 pt-0 pb-0 mb-0 text-center border-none"
export default class HelpAndGuides extends React.Component {
    getGlossaryCardContent = () => {
        let normal = []
        let bonus = []
//      let plandoOnly = []
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
                <Row className="border-left border-right"><Col className="text-center"><small>*: extra copies of this item are added if the "More Bonus Pickups" Variation is enabled.</small></Col></Row>
                <Row className="border-left border-right border-bottom"><Col className="text-center"><small>**: Only in seeds generated with KeyMode set to Shards.</small></Col></Row>
                <CardText className="text-center mt-3">
                <h5>The following items are only present when using the More Bonus Pickups Variation.</h5>
                </CardText>
                <Row className="border">
                <Col className="text-center" xs="3">Pickup Name</Col>
                <Col className="border-left border-right text-center" xs="8">Description</Col>
                <Col className="text-center" xs="1">#</Col>
                </Row>
                {bonus}
                <Row className="border-left border-right"><Col className="text-center"><small>*: 4 bonus skills are chosen at random for each Extra Bonus Pickups seed.</small></Col></Row>
                <Row className="border-left border-right border-bottom"><Col className="text-center"><small>**: Only one Teleport bonus skill will be in any given Extra Bonus Pickups seed.</small></Col></Row>

            </Collapse>
            </CardBody>
        </Card>
        )
    }
    getInstallSteamCardContent = () => {
        return (<Card className="w-100 mt-2" id="install">
            <CardBody>
                <div className={buttonHolder}>
                <Button color="primary" active={this.state.open["install"]} onClick={this.toggleOpen("install")}>
                    Installing the Randomizer (Steam/GOG)
                </Button>
                </div>
                <Collapse isOpen={this.state.open["install"]}>
                <CardText>
                    Installing the randomizer into your existing copy of the game is the easiest way to get started. It will allow you to continue
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
                            Once the generation finishes, click the Download Seed button to get your seed file. It should download with the name "randomizer.dat".
                            <ul>
                            <li><small>
                                Tip: You can also open a live-updating map that can help you keep track of reachable pickups by clicking "Open Tracking Map". If you get stuck or have a second monitor,
                                this can be very helpful!
                            </small></li>
                            </ul>
                        </li>
                        <li>
                            Move your randomizer.dat file to the same folder OriDE.exe is in. (See the installation guide for more details on how to find this folder)
                        </li>
                        <li>
                            You're all set! Launch the game and start a new save file to begin playing your seed.
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
                        Download the tracker {" "}<a target="_blank" rel="noopener noreferrer" href="/">here</a>.
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
                Need help? click the link to the seed below, then follow the instructions (step 4 onward) from the seedgen guide above. Be sure to check out the tracking map if you get stuck!
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
                        <li>Hint (highlight to view): <span style={{color: "#fff"}}>Remember to turn in your mapstones!</span></li>
                    </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/OddOpeningsOne/download?tracking=1">Odd Openings One</a>
                        <ul><li>Sometimes getting out of Glades can be a puzzle. See if you can solve this one! (Remember to check the tracking map if you get stuck)</li>
                        <li>Hint (highlight to view): <span style={{color: "#fff"}}>Check out the stompable peg near the Blackroot Spirit Well, in the rolling boulder area.</span></li>
                        </ul>
                    </li>
                    <li>
                        <a target="_blank" rel="noopener noreferrer" href="/plando/eiko/OddOpeningsTwo/download?tracking=1">Odd Openings Two</a>
                        <ul><li>Same idea as Odd Openings One. Find your way out of Glades!</li>
                        <li>Hint (highlight to view): <span style={{color: "#fff"}}>Be sure to pay attention what gets unlocked on the tracking map when you pick up skills <i>and teleporters</i>.</span></li>
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
                        <li>Hint 1 (highlight to view): <span style={{color: "#fff"}}>There are several ways into Sorrow. For this seed, you can use either the teleporter or Glide+Wind... once you find them!</span></li>
                        <li>Hint 2 (If 1 wasn't enough): <span style={{color: "#fff"}}>The dungeons (Ginso Tree, Forlorn Ruins, and Mount Horu) are full of pickups! Give them a search if you get stuck. </span></li>
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
                        The energy cost of the Grenade (light burst) skill has been removed.
                    </li>
                    <li>
                        The energy cost of the Charge Flame skill has been reduced to 1/2; it drops to 0 after leveling Charge Flame Efficiency in the blue ability tree.
                    </li>
                    <li>
                        You can use the Return To Start (bound to alt+R by default, rebindable using RandomizerRebindings.txt) keybinding to return to the spawn location in Sunken Glades at any time, similar to the "save and quit" functionality from the ALttP randomizer.
                    </li>
                    <li>
                        The Kuro cutscene in Hollow Grove always plays the first time you go there (In Open World, it will instead never play.)
                    </li>
                    <li>
                        The Valley killplane is always active, instead of being active as soon as you get stomp. (In Open World, it is instead never active.)
                    </li>
                    <li>
                        First-time pickup animations and Sein's dialog boxes are disabled, just like they would be in the base game with the UI toggled off.
                    </li>
                    <li>
                        In addition to the normal pickup locations, you can find pickups by:
                        <ul>
                            <li>
                                Destroying petrified (blue) plants (These now show up on the minimap as exp orbs if the Map Markers ability is unlocked)
                            </li>
                            <li>
                                Unlocking maps by turning in mapstones (9 pickups, 1 per map)
                            </li>
                            <li>
                                Finishing rooms in mount horu (8 pickups, 1 per room)
                            </li>
                        </ul>
                    </li>
                    <li>
                        There are new pickups not found in the base game, including teleporter unlocks and several bonus pickups. Check out the Bonus Item Glossary guide below to learn more about them.
                    </li>
                    <li>
                        The purple tree has been changed substantially: see the <a href="https://docs.google.com/document/d/1tprqq7mUJMGcgAA0TM-O5FeOklzz4dOReB0Nru3QlsI#bookmark=cax9k3:1me" target="_blank" rel="noopener noreferrer">patch notes</a> for a full summary.
                    </li>
                    <li>
                        The UI transparency is increased while performing a "Save Anywhere" glitch.
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
                        There is a known softlock that can happen if the Ginso Escape cutscene is not skipped. To avoid it, skip the cutscene as soon as you get the pickup text for the "Clean Water" pickup slot.
                        </li>
                        <li>
                        Do not Alt+R out of any room with a temporary lock (Ginso miniboss 1, Grotto Miniboss, Outer Swamp Spitter puzzle area) with the door still closed. You may softlock if you do.
                        </li>
                        <li>
                        Do not Alt+R out of the fronkey fight after Sein unless you have already picked up the exp orb below Sein. You may softlock if you do.
                        </li>
                    </ul>
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
        {this.getInstallSteamCardContent()}
        {this.getGenSeedCardContent()}
        {this.getStarterSeedsCardContent()}
        {this.getTrackerCardContent()}
        {this.getGotchasCardContent()}
        {this.getDifferencesCardContent()}
        {this.getGlossaryCardContent()}
      </Container>
    );
  };
}
