import React, {Fragment} from 'react';
import {Container, Button, Collapse, Row, Col, Card, CardTitle, CardHeader, CardSubtitle, CardText, CardBody} from 'reactstrap';
import {Helmet} from 'react-helmet';

import {get_param, stuff_by_type} from "./common.js"
import SiteBar from "./SiteBar.js"

const GUIDES = ["install", "gen_seed", "get_tracker", "bonus_pickups"];
const counts = {
  "standard": { "RB|0": 3, "RB|1": 3, "RB|6": "3/5*", "RB|9": 1, "RB|10": 1, "RB|11": 1, "RB|12": "1/5*", "RB|13": 3, "RB|15": 3, "RB|17": "5**", "RB|19": "5**", "RB|21": "5**"},
  "bonus": { "RB|31": 1, "RB|32": 1, "RB|33": 3, "RB|36": 1, "RB|6": 5, "RB|12": 5, "RB|101": "*", "RB|102": "*", "RB|103": "*", "RB|104": "**", "RB|105": "**", "RB|106": "*", "RB|107": "*"},
}

export default class HelpAndGuides extends React.Component {
  getGlossaryCardContent = () => {
    let normal = []
    let bonus = []
    let plandoOnly = []
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
          <CardTitle className=" text-center border-none">
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
                target.scrollIntoView()
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
        <Card className="w-100 mt-2" id="install">
          <CardBody>
            <CardTitle className=" text-center border-none">
              <Button color="primary" active={this.state.open["install"]} onClick={this.toggleOpen("install")}>
                Installing the Randomizer (Steam/GOG)
              </Button>
            </CardTitle>
            <Collapse isOpen={this.state.open["install"]}>
              <CardText>
                Installing the randomizer into your existing copy of the game is the easiest way to get started. It will allow you to continue
                accruing Steam playtime hours and achievements, but will require a bit of work to switch between the regular game and the Randomizer.
              </CardText>
              <CardText>
                Installation steps:
                <ol>
                  <li>
                    Open the folder where your copy of Ori DE is installed. You'll need to get back here later, so consider making a
                    shortcut or pinning this folder to Quick Access. From there, Navigate down to Ori DE/oriDE_Data/Managed
                    <small><ul><li>
                        Steam: Steam/steamapps/common/Ori DE. You can also right click on the game in your Steam library and click the "View local files" button on the options screen.
                      </li><li>
                        GOG: GOG Games/Ori and The Blind Forest - Definitive Edition/
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
                    Installation complete! All you need now to start playing is a seed, so check out the guide below to generate your own!
                  </li>
                </ol>
              </CardText>
              <CardText>
                To play the original game again, simply replace your Assembly-CSharp.dll file with the backup you made. If you didn't
                make one or can't find it, someone in the{" "}<a target="_blank" rel="noopener noreferrer" href="/discord">ori discord</a>{" "}can get you a copy.
              </CardText>
            </Collapse>
          </CardBody>
        </Card>
        <Card className="w-100 mt-2" id="gen_seed">
          <CardBody>
            <CardTitle className=" text-center border-none">
              <Button color="primary" active={this.state.open["gen_seed"]} onClick={this.toggleOpen("gen_seed")}>
                Generating your first seed
              </Button>
            </CardTitle>
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
                        Tip: You can also open a live-updating map that can help you keep track of reachable pickups by clicking Open Tracking Map. If you get stuck or have a second monitor,
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
        <Card className="w-100 mt-2" id="get_tracker">
          <CardBody>
            <CardTitle className=" text-center border-none">
              <Button color="primary" active={this.state.open["get_tracker"]} onClick={this.toggleOpen("get_tracker")}>
                Get the item tracker
              </Button>
            </CardTitle>
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
        {this.getGlossaryCardContent()}
      </Container>
    );
  };
}
