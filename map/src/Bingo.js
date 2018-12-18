import React from 'react';
import {Container, Row, Col, Button, Modal, ModalHeader, ModalBody, ModalFooter, Input, Card, CardBody, CardFooter, Media} from 'reactstrap';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import {Helmet} from 'react-helmet';

import {download} from './shared_map.js'
import {doNetRequest, player_icons, get_random_loader, PickupSelect} from './common.js'
import SiteBar from "./SiteBar.js";

import 'react-notifications/lib/notifications.css';

const textStyle = {color: "black", textAlign: "center"}
const niceTPNames = {
    "sunkenGlades": "Sunken Glades",
    "moonGrotto": "Moon Grotto", 
    "mangroveFalls": "Blackroot Burrows", 
    "valleyOfTheWind": "Sorrow Pass", 
    "spiritTree": "Hollow Grove",
    "mangroveB": "Lost Grove", 
    "horuFields": "Horu Fields",
    "ginsoTree": "Ginso Tree", 
    "forlorn": "Forlorn Ruins",
    "mountHoru": "Mount Horu",
    "swamp": "Thornfelt Swamp", 
    "sorrowPass": "Valley of the Wind"
}
const niceLocNames = {
    "LostGroveLongSwim" : "Lost Grove Long Swim",
    "ValleyEntryGrenadeLongSwim": "Valley Long Swim" ,
    "SpiderSacEnergyDoor" : "Spider Energy Door",
    "SorrowHealthCell" : "Sorrow HC",
    "SunstonePlant" : "Sunstone Plant",
    "GladesLaser" : "Gladzer EC",
    "LowerBlackrootLaserAbilityCell": "BRB Right Laser AC",
    "MistyGrenade" : "Misty Grenade EX",
    "LeftSorrowGrenade": "Sorrow Grenade EX",
    "DoorWarpExp" : "Door Warp EX",
    "HoruR3Plant" : "R3 Plant",
    "RightForlornHealthCell" : "Right Forlorn HC",
    "ForlornEscapePlant" : "Forlorn Escape Plant"
}
const handleCard = (card, playerData, activePlayer) => {
    let {name, type} = card;
    let text = name
    let help = ""
    let extraLines = []
    let players = [];
    let valid = (p) => playerData.hasOwnProperty(p) && playerData[p].hasOwnProperty(name)
    let apValid = valid(activePlayer)
    try {
        switch(type) {
            case "bool":
                players = Object.keys(playerData).filter(p => valid(p) && playerData[p][name].value)
                switch(name) {
                    case "FastStompless":
                        text = "Fast Stompless"
                        help = "Break the rocks above Kuro's head in the Valley of the Wind with a long-distance spider shot"
                    break;
                    case "CoreSkip":
                        text = "Core Skip"
                        help = "Skip one of the Ginso core rooms by destroying both sets of brambles with a well-timed level-up."
                    break;
                    case "DrownFrog":
                        text = "Drown an amphibian"
                        help = "The amphibians native to Nibel are fronkeys, red spitters, and green spitters"
                    break;
                    case "DrainSwamp":
                        text = "Drain the Swamp"
                        help = "Drain the pool in the area above and to the right of the Grotto Teleporter by breaking the blue barrier there."
                    break;
                    case "WilhelmScream":
                        text = "Make Wilhelm Scream"
                        help = "Throw Wilhelm (a green spitter on the top left cliff in the main Valley of the Wind room) off his cliff. Note: Wilhelm does not spawn unless you have the Sunstone."
                    break;
                    default:
                        text = name;
                        help = "???";
                    break;
                }
            break;
            case "int":
                let target = card.target
                players = Object.keys(playerData).filter(p => valid(p) && playerData[p][name].value >= target)
                let progress = apValid ? `(${Math.min(playerData[activePlayer][name].value, target)}/${target})` : `(${target})`
                switch(name) {
                    case "CollectMapstones":
                        text = `Collect mapstones ${progress}`
                        help = "You do not need to turn them in."
                        break;
                    case "ActivateMaps":
                        text = `Activate map altars ${progress}`
                        help = ""
                        break;
                    case "OpenKSDoors":
                        text = `Open keystone doors ${progress}`
                        help = "The already-opened door in Sunken Glades does not count."
                        break;
                    case "OpenEnergyDoors":
                        text = `Open energy doors ${progress}`
                        help = "There are 2 energy doors in Grotto, 2 in Glades, 1 in Grove, and 1 in Sorrow."
                        break;
                    case "BreakFloors":
                        text = `Break floors or ceilings. ${progress}`
                        help = "Any horizontal barrier that can be broken with a skill counts."
                        break;
                    case "BreakWalls":
                        text = `Break walls ${progress}`
                        help = "Any vertical barrier that can be broken with a skill counts."
                        break;
                    case "UnspentKeystones":
                        text = `Get ${progress} keystones in your inventory`
                        help = "Keyduping is allowed, and you can spend them after completing this goal."
                        break;
                    case "BreakPlants":
                        text = `Break plants ${progress}`
                        help = "Petrified plants are the large blue bulbs that can only be broken with Charge Flame, Grenade, or Charge Dash"
                        break;
                    case "TotalPickups":
                        text = `Collect pickups ${progress}`
                        help = "This includes petrified plants, mapstone turnins, world events, and horu rooms."
                        break;
                    case "UnderwaterPickups":
                        text = `Collect underwater pickups ${progress}`
                        help = "The pickup itself must be underwater, not just the path to reach it."
                        break;
                    case "HealthCells":
                        text = `Collect Health Cells ${progress}`
                        help = "Any bonus health cells you spawn with will not count."
                        break;
                    case "EnergyCells":
                        text = `Collect Energy Cells ${progress}`
                        help = "Any bonus energy cells you spawn with will not count."
                        break;
                    case "AbilityCells":
                        text = `Collect Ability Cells ${progress}`
                        help = "Any bonus ability cells you spawn with will not count."
                        break;
                    case "LightLanterns":
                        text = `Use Grenade to light Lanterns ${progress}`
                        help = "The lanterns in the pre-dash area of BRB do not count."
                        break;
                    case "SpendPoints":
                        text = `Spend Ability Points ${progress}`
                        help = "What you spend them on is up to you."
                        break;
                    case "GainExperience":
                        text = `Gain spirit light ${progress}`
                        help = "bonus experience gained from the Spirit Light Efficiency ability counts"
                        break;
                    case "KillEnemies":
                        text = `Kill enemies ${progress}`
                        help = "Large swarms count as 3 enemies (the initial swarm and the first split)."
                        break;
                }
            break;
            case "multi":
                let infix = "";
                let suffix = ":";
                let optionNames = []
                let s = card.parts && card.parts.length > 1 ? "s" : ""
                let yies = card.parts && card.parts.length > 1 ? "ies" : "y"
                switch(card.method) {
                    case "and":
                        players = Object.keys(playerData).filter(p =>  valid(p) && card.parts.every(part => playerData[p][name].value[part.name].value))
                        infix = card.parts.length > 1 ? ( card.parts.length > 2 ? "all of these " : "both of these ") : "this "
                        break;
                    case "or":
                        players = Object.keys(playerData).filter(p =>  valid(p) && card.parts.some(part => playerData[p][name].value[part.name].value))
                        infix = card.parts.length > 1 ? "any of these " : "this "
                        break;
                    case "count":
                        players = Object.keys(playerData).filter(p => valid(p) && playerData[p][name].total >= card.target)
                        suffix = apValid ? ` (${Math.min(playerData[activePlayer][name].total, card.target)}/${card.target})` : ` (${card.target})`
                        s = "s"
                        yies = "ies"
                        break;
                }
                switch(name) {
                    case "CompleteHoruRoom":
                        text = `Complete ${infix}Horu room${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "CompleteEscape":
                        text = `Escape ${infix}dungeon${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "ActivateTeleporter":
                        text = `Activate ${infix}spirit well${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {niceName: niceTPNames[part.name], partname: part.name}})
                    break;
                    case "EnterArea":
                        text = `Enter ${infix}area${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetItemAtLoc":
                        text = `Get the pickup${s} at ${infix}location${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {niceName: niceLocNames[part.name], partname: part.name}})
                    break;
                    case "VisitTree":
                        text = `Visit ${infix}tree${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetAbility":
                        text = `Level up ${infix}abilit${yies+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetEvent":
                        text = `Unlock ${infix}event${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "StompPeg":
                        text = `Stomp ${infix}post${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "HuntEnemies":
                        text = `Defeat ${infix}Miniboss encounter${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                }
                extraLines = optionNames.map(({partname, niceName}) => 
                {
                    niceName = niceName || partname
                    let checked = "☐";
                    if(apValid && playerData[activePlayer][name].value[partname].value)
                        checked = "☑"
                    return `᛫ ${niceName} ${checked}`
                })
            break;
        }
        text = [text].concat(extraLines).map(t => (<div>{t}</div>))
        return {text: text, help: help, players: players}
    }
    catch(error)
    {
        console.log(error, card, playerData)
        return {text: text, help: help, players: players}
    }
}

const make_icons = players => players.map(p => (<Media object style={{width: "25px", height: "25px"}} src={player_icons(p, false)} alt={"Icon for player "+p} />))
const BingoCard = ({text, players}) => {
    let className = "pl-1 pr-1 pb-0 justify-content-center text-center align-items-center d-flex " + ((text.length > 1) ? "pt-0 flex-column" : "pt-1")
    return (
        <Card style={{width: 160, height: 160}}>
            <CardBody style={{fontSize: ".8rem"}} className={className}>{text}</CardBody>
            <CardFooter className="p-0 justify-content-center d-flex">{make_icons(players)}</CardFooter>
        </Card>
)}

const BingoBoard = ({cards, playerData, activePlayer}) => {
    cards = [...cards]
    if(cards.length < 25) {
        return null
    }
    let rows = []
    while(rows.length < 5) {
        let row = []
        while(row.length < 5) {
            let card = cards.shift()
            let {text, players} = handleCard(card, playerData, activePlayer)
            row.push((<Col><BingoCard text={text} players={players} /></Col>))
        }
        rows.push((<Row className="justify-content-center align-items-center w-100">{row}</Row>))
    }
    return (<Container>{rows}</Container>);
}


export default class Bingo extends React.Component {
    constructor(props) {
        super(props);
        let url = new URL(window.document.location.href);
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        this.state = {cards: [], haveGame: false, creatingGame: false, createModalOpen: true, playerData: {}, activePlayer: 1, gameId: gameId, startSkills: 3, startCells: 4, startMisc: "MU|TP/Swamp/TP/Valley"};
 
        if(gameId > 0)
        {
            let url = `/bingo/game/${gameId}/fetch`
            doNetRequest(url, this.createCallback)
            this.state.creatingGame = true
            this.state.createModalOpen = false
            this.state.loader = get_random_loader()
        }
    }
    componentDidMount() {
        this.interval = setInterval(() => this.tick(), 5000);
  };
    updateUrl = () => {
        let {gameId} = this.state;
        let url = window.document.URL.split("?")[0];
        if(gameId && gameId > 0)
            url += `?game_id=${gameId}`
        window.history.replaceState('',window.document.title, url);
    }

    joinGame = () => {
        let {gameId, seed, activePlayer, haveGame} = this.state;
        if(!haveGame) return;
        let nextPlayer = activePlayer;
        let players = Object.keys(this.state.playerData)
        while(players.includes("" + nextPlayer))
            nextPlayer++;

        seed = `Sync${gameId}.${nextPlayer},` + seed
        download("randomizer.dat", seed)
        this.setState({activePlayer: nextPlayer})
        doNetRequest(`/bingo/game/${gameId}/add/${nextPlayer}`, this.tickCallback)
    }
    tick = () => {
        let {gameId, haveGame} = this.state;
        if(gameId && gameId > 0 && haveGame)
            doNetRequest(`/bingo/game/${gameId}/fetch`, this.tickCallback)
    }

    tickCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error("error getting data from server", "connection error", 5000)
        } else {
            let res = JSON.parse(responseText)
            this.setState({playerData: res.playerData})
        }
    }



    loadingModal = () => { return (
        <Modal size="sm" isOpen={this.state.creatingGame } backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader centered>Please wait...</ModalHeader>
            <ModalBody>
                <Container fluid>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </Container>
            </ModalBody>
        </Modal>
    )}
    createModal = () =>  { return (
        <Modal size="lg" isOpen={this.state.createModalOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.toggleCreate}>
            <ModalHeader toggle={this.toggleCreate} centered>Bingo options</ModalHeader>
            <ModalBody>
                <Container fluid>
                <Row className="p-1">
                    <Col xs="4" className="text-center pt-1 border">
                        <span class="align-middle">random free skill count</span>
                    </Col><Col xs="4">
                        <Input type="number" value={this.state.startSkills}  onChange={(e) => this.setState({startSkills: parseInt(e.target.value, 10)})}/> 
                    </Col>
                </Row>
                <Row className="p-1">
                    <Col xs="4" className="text-center pt-1 border">
                        <span class="align-middle">random free cell count</span>
                    </Col><Col xs="4">
                        <Input type="number" value={this.state.startCells} onChange={(e) => this.setState({startCells: parseInt(e.target.value, 10)})}/> 
                    </Col>
                </Row>
                <Row className="p-1">
                    <Col xs="4" className="text-center pt-1 border">
                        <span class="align-middle">Also start with</span>
                    </Col><Col xs="8">
                        <PickupSelect value={this.state.startMisc} updater={(code, _) => this.setState({startMisc: code})}/> 
                    </Col>
                </Row>
            </Container>
            </ModalBody>
            <ModalFooter>
            <Button color="primary" onClick={this.createGame}>Create Game</Button>
            <Button color="secondary" onClick={this.toggleCreate}>Cancel</Button>
            </ModalFooter>
        </Modal>
    )}
    toggleCreate = () => this.setState({createModalOpen: !this.state.createModalOpen})
    createGame = () => {
        let url = `/bingo/new?skills=${this.state.startSkills}&cells=${this.state.startCells}&misc=${this.state.startMisc}`
        doNetRequest(url, this.createCallback)
        this.setState({creatingGame: true, createModalOpen: false, loader: get_random_loader()})
    }

    createCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error("Failed to generate bingo game!", "bingo generation failure!", 5000)
            this.setState({createModalOpen: false, haveGame: false, creatingGame: false, activeTab: 'variations'}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            this.setState({gameId: res.gameId, createModalOpen: false, creatingGame: false, haveGame: true, seed: res.seed, playerData: res.playerData, cards: res.cards}, this.updateUrl)
        }
    }
  
    render = () => {
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <Helmet>
                    <style>{'body { background-color: white}'}</style>
                </Helmet>
                <NotificationContainer/>
                <SiteBar user={this.state.user}/>
                {this.createModal()}
                {this.loadingModal()}
                <Row className="p-1">
                    <Col>
                        <span><h3 style={textStyle}>Bingo!</h3></span>
                    </Col>
                </Row>
                <BingoBoard cards={this.state.cards} playerData={this.state.playerData} activePlayer={this.state.activePlayer}/>
                <Row className="align-items-center pt-2">
                    <Col xs="4">
                        <Button onClick={this.toggleCreate}>Create New Game</Button>
                    </Col><Col xs="4">
                        <Button onClick={this.joinGame}>Join Game</Button>
                    </Col><Col xs="3">
                        {this.state.activePlayer > 0 ? make_icons([this.state.activePlayer]) : null}
                        Player Number: <Input type="number" value={this.state.activePlayer} onChange={(e) => this.setState({activePlayer: parseInt(e.target.value, 10)})}/> 
                    </Col>
                </Row>
            </Container>
        )
    }
};

