import React from 'react';
import {Container, Row, Col, Button, Collapse, Jumbotron} from 'reactstrap';
import {Helmet} from 'react-helmet';
import Select, { createFilter } from 'react-select';
import SiteBar from "./SiteBar.js"

const textStyle = {color: "black", textAlign: "center"}

const HelpSection = (name, isOpen, toggleOpen, inner) => (
    <Row>
    <Button active={isOpen} onClick={toggleOpen}>{name}</Button>
    <Collapse isOpen={isOpen}>
    {inner}
    </Collapse>
    </Row>
)

export default class HelpAndGuides extends React.Component {
  constructor(props) {
    super(props);
    this.state = {open: {"install": true}};
}
    toggleOpen = (section) => () => this.setState(prev => {
        prev.open[section] = !(prev.open[section] || false)
    })
    render = () => {
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <Helmet>
                    <style>{'body { background-color: white, text-color: black}'}</style>
                </Helmet>
                <SiteBar user={this.state.user}/>
                <Row className="p-1">
                <Jumbotron>
                    <h3 className="display-3">Help and Guides</h3>
                    <p className="lead">Looking for help with the randomizer? You've come to the right place! Click the buttons below to open each guide.</p>
                    <hr className="my-2" />
                    <p>If you have any questions or need more help, join the <a href="/discord">Ori discord</a> and ask there.</p>
                </Jumbotron>
                </Row>
                <Row>
                    <Button ref="install" active={this.state.open["install"]} onClick={this.toggleOpen("install")}>Installing the Randomizer (Steam/GOG)</Button>
                    <Collapse isOpen={isOpen}>
                            Installing the randomizer into your existing copy of the game is the easiest way to get started. It will allow you to continue accruing Steam playtime hours and achievements, but will require a bit of work to switch between the regular game and the Randomizer.
                        <ol>
                            <li>
                                Open the folder where your copy of Ori DE is installed. You'll need to get back here later, so consider making a shortcut or pinning this folder to Quick Access.
                                Ori DE folder wherever your Steam/GOG games are installed. Navigate down to Ori DE/oriDE_Data/Managed 
                                <ol><li>
                                    Steam: Steam/steamapps/common/Ori DE. You can also right click on the game in your Steam library and click "View local files"
                                </li><li>
                                    GOG: GOG Games/Ori and The Blind Forest - Definitive Edition/
                                </li></ol>
                            </li>
                            <li>
                                From the Ori folder, navigate to oriDE_Data/Managed. Look for a file named "Assembly-Csharp.dll". To install the randomizer, we will be replacing this file, so create a backup first, either by renaming it to something like Assembly-Csharp-Vanilla.dll, or moving it into a different folder.
                            </li>
                            <li>
                                Download the Randomizer version of Assembly-Csharp.dll <a target='_blank' rel='noopener noreferrer' href="/dll">here</a>, and move it into the oriDE_Data/Managed folder.
                            </li>
                            <li>
                                Installation complete! Try one of our tutorial seeds or check out the guide below to generate your own!
                            </li>
                        </ol>
                    </Collapse>
                </Row>
                <Row>
                    <Button ref="gen_seed" active={this.state.open["gen_seed"]} onClick={this.toggleOpen("gen_seed")}>Generating Your First Seed</Button>
                    <Collapse isOpen={isOpen}>
                        In order to play the Ori randomizer, you need a <i>seed file</i>, which specifies the randomized placement of the items. Each randomized playthrough of the game will require a different seed. This guide will walk you through the process of generating and downloading your first seed.
                        <ol>
                            <li>
                                Open the <a target="_blank" rel='noopener noreferrer' href="/">seed generator page</a>.
                            </li>
                            <li>
                                Change the Logic Mode (in the top-left) from "Standard" to "Casual". The default settings for the other options are fine. If you want, you can give your seed a name using the text box at the bottom.
                            </li>
                            <li>
                                Click the Generate Seed button to have the server begin generating your seed. It may take a few seconds.
                            </li>
                            <li>
                                Once the generation finishes, click the Download Seed button to get your seed file. It should download with the name "randomizer.dat".
                                <ul><li>
                                    You can also open a live-updating map that can help you keep track of reachable pickups by clicking Open Tracking Map. If you get stuck or have a second monitor, this can be very helpful!
                                </li></ul>
                            </li>
                            <li>
                                Move your randomizer.dat file to the same folder OriDE.exe is in. (See the installation guide for more details on how to find this folder)
                            </li>
                            <li>
                                You're all set! Launch the game and start a new save file to begin playing your seed.
                            </li>
                        </ol>
                    </Collapse>
                </Row>
            </Container>
        )
    }
};

