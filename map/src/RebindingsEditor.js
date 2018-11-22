import React from 'react';
import {Container, Row, Col, Button} from 'reactstrap';
import {Helmet} from 'react-helmet';
import {download, uniq} from "./shared_map.js"
import Select, { createFilter } from 'react-select';
import SiteBar from "./SiteBar.js"

const textStyle = {color: "black", textAlign: "center"}

const keyFilter = createFilter({
  ignoreCase: true,
  ignoreAccents: true,
  stringify: (obj) => obj,
  trim: true,
  matchFrom: 'start'
});
const START_LINES = [
    "Keyboard Rebindings",
    "--------",
    "Activate Key Rebinding: True",
    "--------"
]
const END_LINES = [
    "--------",
    "Usage:",
    "- There is no guarantee of the game still being playable after key rebinding. Please use with caution and delete this file in case of breakage",
    "- Spelling and syntactical errors will result in the key rebindings not registering properly, and the game will get set to default",
    "- Deleting this file will result in this file being recreated by the game, containing the default settings",
    "--------",
    "Don't forget to restart the game after editing this file!",
    "Don't forget to close this file before restarting the game!",
    "--------",
    "Mouse0 is left mouse button",
    "Mouse1 is right mouse button",
    "AlphaX is the number X on the keyboard (not num pad, the stuff above your keys)"
]
const Actions = [
    "Movement Left", "Movement Right", "Movement Down", "Movement Up", "Menu Left", "Menu Right", "Menu Down", "Menu Up", "Menu Previous", "Menu Next", "Proceed", "Soul Link", "Jump", "Grab", "Spirit Flame",
    "Bash", "Glide", "Charge Jump", "Select", "Start", "Cancel", "Grenade", "Dash", "Left Stick", "Debug Menu (shhh)", "Zoom In World Map", "Zoom Out World Map", "Copy", "Delete", "Focus", "Filter", "Legend"
]
const Keys = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "Alpha0", "Alpha1", "Alpha2", "Alpha3", "Alpha4", "Alpha5", "Alpha6", "Alpha7", "Alpha8", "Alpha9",
    "Backspace", "Delete", "Tab", "Clear", "Return", "Pause", "Escape", "Space", "Keypad0", "UpArrow", "DownArrow", "RightArrow", 
    "LeftArrow", "Insert", "Home", "End", "PageUp", "PageDown", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14", "F15",
    "Exclaim", "DoubleQuote", "Hash", "Dollar", "Ampersand", "Quote", "LeftParen", "RightParen",  "Asterisk", "Plus", "Comma", "Minus", "Period", "Slash", "Colon", 
    "Semicolon", "Less", "Equals", "Greater", "Question", "At", "LeftBracket", "Backslash", "RightBracket", "Caret", "Underscore", "BackQuote", "Numlock", "CapsLock",
    "ScrollLock", "RightShift", "LeftShift", "RightControl", "LeftControl", "RightAlt", "LeftAlt", "LeftCommand", "LeftApple", "LeftWindows", "RightCommand", "RightApple", "RightWindows",
    "Keypad1", "Keypad2", "Keypad3", "Keypad4", "Keypad5", "Keypad6", "Keypad7", "Keypad8", "Keypad9", "KeypadPeriod", "KeypadDivide", "KeypadMultiply", "KeypadMinus", "KeypadPlus", "KeypadEnter", "KeypadEquals",
    "AltGr", "Help", "Print", "SysReq", "Break", "Menu", "Mouse0", "Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5", "Mouse6", "JoystickButton0", "JoystickButton1", "JoystickButton2",
    "JoystickButton3", "JoystickButton4", "JoystickButton5", "JoystickButton6", "JoystickButton7", "JoystickButton8", "JoystickButton9", "JoystickButton10", "JoystickButton11",
    "JoystickButton12", "JoystickButton13", "JoystickButton14", "JoystickButton15", "JoystickButton16", "JoystickButton17", "JoystickButton18", "JoystickButton19", "None"
]
const DEFAULT_BINDINGS = {
    "Movement Left": ["A", "LeftArrow"], "Movement Right": ["D", "RightArrow"], "Movement Down": ["S", "DownArrow"], "Movement Up": ["W", "UpArrow"], "Menu Left": ["A", "LeftArrow"], "Menu Right": ["D", "RightArrow"], 
    "Menu Down": ["S", "DownArrow"], "Menu Up": ["W", "UpArrow"], "Menu Previous": ["K", "PageUp"], "Menu Next": ["L", "PageDown"], "Proceed": ["Space", "Return"], "Soul Link": ["E"], "Jump": ["Space"], 
    "Grab": ["LeftShift", "RightShift"], "Spirit Flame": ["X"], "Bash": ["Mouse1", "C"], "Glide": ["LeftShift", "RightShift"], "Charge Jump": ["UpArrow", "W"], "Select": ["Tab"], "Start": ["Escape"], "Cancel": ["Escape", "Mouse1"], 
    "Grenade": ["R"], "Dash": ["LeftControl", "RightControl"], "Left Stick": ["Alpha7"], "Debug Menu (shhh)": ["Alpha8"], "Zoom In World Map": ["RightShift", "LeftShift"], 
    "Zoom Out World Map": ["RightControl", "LeftControl"], "Copy": ["C"], "Delete": ["Delete"], "Focus": ["F"], "Filter": ["F"], "Legend": ["L"]
}

const COMPOUND_ACTIONS = {
    "Save Anywhere": ["Spirit Flame", "Cancel", "Proceed"],
    "Charge Dash": ["Charge Jump", "Dash"],
    "Rocket Jump": ["Charge Jump", "Dash", "Jump"],
    "Bashable Grenade": ["Grenade", "Movement Down"],
}

const KeyRow = ({setter, action, keys}) => (
    <Row>
    <Col xs="4">{action}:</Col>
    <Col xs="8">
        <Select getOptionLabel={opt => opt} isMulti getOptionValue={opt => opt} options={Keys} filterOption={createFilter(keyFilter)} value={keys} onChange={value => setter(action, value)}/>
    </Col>
    </Row>
)
const KeyRows = ({setter, bindings}) => Object.keys(bindings).map(action => (
    <KeyRow setter={setter} action={action} keys={bindings[action]}/>
))

export default class RebindingsEditor extends React.Component {
  constructor(props) {
    super(props);
    this.state = {bindings: {...DEFAULT_BINDINGS}, compounds: {"Save Anywhere": [], "Charge Dash": [], "Rocket Jump": [], "Bashable Grenade": []}};
}
    OnKey = (action, value) => this.setState(prev => {
        let bindings = prev.bindings;
        bindings[action] = value;
        return {bindings: bindings}
    })
    OnCompound = (action, value) => this.setState(prev => {
        let compounds = prev.compounds;
        compounds[action] = value;
        return {compounds: compounds}
    })
    reset = () => this.setState({bindings: {...DEFAULT_BINDINGS}})
    download = () => {
        let lines = [...START_LINES]
        Actions.forEach(action => {
            let bindings = this.state.bindings[action];
            Object.keys(this.state.compounds).forEach(c_act => {
                if(COMPOUND_ACTIONS[c_act].includes(action))
                    bindings = bindings.concat(this.state.compounds[c_act])
            })
            bindings = uniq(bindings)
            if(bindings.length == 0) {
                bindings.push("None")
            }
            lines.push(`${action}: ${bindings.join(", ")}`)
        })
        lines = lines.concat(END_LINES)
        download("KeyRebindings.txt", lines.join("\r\n"))
    }
    render = () => {
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <Helmet>
                    <style>{'body { background-color: white}'}</style>
                </Helmet>
                <SiteBar user={this.state.user}/>
                <Row className="p-1">
                    <Col>
                        <span><h3 style={textStyle}>Ori Rebinding Editor</h3></span>
                    </Col>
                </Row>
                <Row>
                    <Col xs="7">
                        <Row className="p-1">
                            <Col>
                                <span><h5 style={textStyle}>Normal Controls</h5></span>
                            </Col>
                        </Row>
                        <KeyRows setter={this.OnKey} bindings={this.state.bindings}/>
                    </Col>
                    <Col xs="5">
                        <Row className="p-1">
                            <Col>
                                <span><h5 style={textStyle}>Common Shortcuts</h5></span>
                            </Col>
                        </Row>
                        <KeyRows setter={this.OnCompound} bindings={this.state.compounds}/>
                        <Row>
                            <Col xs={{size: 4, offset: 2}}>
                                <Button block onClick={this.reset}>Defaults</Button>
                            </Col>
                            <Col xs="4">
                                <Button block onClick={this.download}>Download</Button>
                            </Col>
                        </Row>
                        <Row className="p-2 m-2 border">
                            <Col xs="12" className="p-2">
                                Ori and the Blind Forest supports key remapping through a text file,
                                KeyRebindings.txt. This webpage creates properly formatted versions of 
                                that file. 
                            </Col>
                            <Col xs="12" className="p-2">
                                To use: customize your keybindings using the form and click download.
                                Then, press Windows+R to open the "run" dialog, paste in this text <code>%localappdata%/Ori&nbsp;and&nbsp;the&nbsp;Blind&nbsp;Forest&nbsp;DE/</code> and
                                press enter to open your Ori AppData folder (this is where your keybindings and save files are stored).
                                Copy the downloaded KeyRebindings.txt into this folder, replacing the existing one (You'll need to restart the game if it's already running).
                            </Col>
                            <Col xs="12" className="p-2">
                                The common shortcuts above are compound binds (Charge Dash is Dash + Charge Jump, for example) to make certain tricks or actions easier. Depending on how
                                you play Ori, you may want other, more specific bindings: ask around on the discord for more info.
                            </Col>
                            <Col xs="12" className="p-2">
                                <i>The instructions on this page are still being written. If you're confused, don't panic! Join the <a href="/discord" target='_blank' rel='noopener noreferrer'>Ori Discord</a> for help. (Feel free to ping @Eiko with any questions about this website).</i>
                            </Col>
                        </Row>
                    </Col>
                </Row>
            </Container>
        )
    }
};

