import React from 'react';
import {doNetRequest, get_param} from './common.js';
import {Helmet} from 'react-helmet';

const game_id = get_param("game-id");
const player_id = get_param("player-id");
const imageMap = {
    '/sprites/tracker/Bash.png': (data) => data.skills.includes("Bash"),
    '/sprites/tracker/ChargeFlame.png': (data) => data.skills.includes("Charge Flame"),
    '/sprites/tracker/ChargeJump.png': (data) => data.skills.includes("Charge Jump"),
    '/sprites/tracker/Climb.png': (data) => data.skills.includes("Climb"),
    '/sprites/tracker/Dash.png': (data) => data.skills.includes("Dash"),
    '/sprites/tracker/Stomp.png': (data) => data.skills.includes("Stomp"),
    '/sprites/tracker/DoubleJump.png': (data) => data.skills.includes("Double Jump"),
    '/sprites/tracker/WallJump.png': (data) => data.skills.includes("Wall Jump"),
    '/sprites/tracker/Glide.png': (data) => data.skills.includes("Glide"),
    '/sprites/tracker/LightGrenade.png': (data) => data.skills.includes("Grenade"),
    '/sprites/tracker/TBash.png': (data) => data.trees.includes("Bash"),
    '/sprites/tracker/TChargeFlame.png': (data) => data.trees.includes("Charge Flame"),
    '/sprites/tracker/TChargeJump.png': (data) => data.trees.includes("Charge Jump"),
    '/sprites/tracker/TClimb.png': (data) => data.trees.includes("Climb"),
    '/sprites/tracker/TStomp.png': (data) => data.trees.includes("Stomp"),
    '/sprites/tracker/TDoubleJump.png': (data) => data.trees.includes("Double Jump"),
    '/sprites/tracker/TWallJump.png': (data) => data.trees.includes("Wall Jump"),
    '/sprites/tracker/TGlide.png': (data) => data.trees.includes("Glide"),
    '/sprites/tracker/TDash.png': (data) => data.trees.includes("Dash"),
    '/sprites/tracker/TLightGrenade.png': (data) => data.trees.includes("Grenade"),
    '/sprites/tracker/CleanWater.png': (data) => data.events.includes("Clean Water"),
    '/sprites/tracker/WindRestored.png': (data) => data.events.includes("Wind Restored"),
    '/sprites/tracker/WaterVein.png': (data) => data.events.includes("Water Vein"),
    '/sprites/tracker/WaterVeinShard1.png': (data) => data.shards.wv > 0,
    '/sprites/tracker/WaterVeinShard2.png': (data) => data.shards.wv > 1,
    '/sprites/tracker/GumonSeal.png': (data) => data.events.includes("Gumon Seal"),
    '/sprites/tracker/GumonSealShard1.png': (data) => data.shards.gs > 0,
    '/sprites/tracker/GumonSealShard2.png': (data) => data.shards.gs > 1,
    '/sprites/tracker/Sunstone.png': (data) => data.events.includes("Sunstone"),
    '/sprites/tracker/SunstoneShard1.png': (data) => data.shards.ss > 0,
    '/sprites/tracker/SunstoneShard2.png': (data) => data.shards.ss > 1,
    '/sprites/tracker/BlackrootTP.png': (data) => data.teleporters.includes("Blackroot"),
    '/sprites/tracker/ForlornTP.png': (data) => data.teleporters.includes("Forlorn"),
    '/sprites/tracker/GinsoTP.png': (data) => data.teleporters.includes("Ginso"),
    '/sprites/tracker/HoruTP.png': (data) => data.teleporters.includes("Horu"),
    '/sprites/tracker/SwampTP.png': (data) => data.teleporters.includes("Swamp"),
    '/sprites/tracker/GroveTP.png': (data) => data.teleporters.includes("Grove"),
    '/sprites/tracker/GrottoTP.png': (data) => data.teleporters.includes("Grotto"),
    '/sprites/tracker/ValleyTP.png': (data) => data.teleporters.includes("Valley"),
    '/sprites/tracker/SorrowTP.png': (data) => data.teleporters.includes("Sorrow"),
    '/sprites/tracker/relics/found/Blackroot.png': (data) => data.relics_found.includes("Blackroot"),
    '/sprites/tracker/relics/found/Forlorn.png': (data) => data.relics_found.includes("Forlorn"),
    '/sprites/tracker/relics/found/Ginso.png': (data) => data.relics_found.includes("Ginso"),
    '/sprites/tracker/relics/found/Horu.png': (data) => data.relics_found.includes("Horu"),
    '/sprites/tracker/relics/found/Swamp.png': (data) => data.relics_found.includes("Swamp"),
    '/sprites/tracker/relics/found/Grove.png': (data) => data.relics_found.includes("Grove"),
    '/sprites/tracker/relics/found/Grotto.png': (data) => data.relics_found.includes("Grotto"),
    '/sprites/tracker/relics/found/Valley.png': (data) => data.relics_found.includes("Valley"),
    '/sprites/tracker/relics/found/Sorrow.png': (data) => data.relics_found.includes("Sorrow"),
    '/sprites/tracker/relics/found/Glades.png': (data) => data.relics_found.includes("Glades"),
    '/sprites/tracker/relics/found/Misty.png': (data) => data.relics_found.includes("Misty"),
    '/sprites/tracker/relics/exists/Blackroot.png': (data) => data.relics.includes("Blackroot"),
    '/sprites/tracker/relics/exists/Forlorn.png': (data) => data.relics.includes("Forlorn"),
    '/sprites/tracker/relics/exists/Ginso.png': (data) => data.relics.includes("Ginso"),
    '/sprites/tracker/relics/exists/Horu.png': (data) => data.relics.includes("Horu"),
    '/sprites/tracker/relics/exists/Swamp.png': (data) => data.relics.includes("Swamp"),
    '/sprites/tracker/relics/exists/Grove.png': (data) => data.relics.includes("Grove"),
    '/sprites/tracker/relics/exists/Grotto.png': (data) => data.relics.includes("Grotto"),
    '/sprites/tracker/relics/exists/Valley.png': (data) => data.relics.includes("Valley"),
    '/sprites/tracker/relics/exists/Sorrow.png': (data) => data.relics.includes("Sorrow"),
    '/sprites/tracker/relics/exists/Glades.png': (data) => data.relics.includes("Glades"),
    '/sprites/tracker/relics/exists/Misty.png': (data) => data.relics.includes("Misty"),
}
const always = ["GCleanWater", "GGumonSeal", "GreyTrees", "GreySkillRing", "GSunstone", "GWaterVein", "SpiritFlame", "TSpiritFlame",
                "GWindRestored", "SkillRing_Single", "SkillRing_Triple", "SkillRing_Double", "MapStone"].map(n => `/sprites/tracker/${n}.png`)

export default class ItemTracker extends React.Component {
    constructor(props) {
        super(props)
        this.state = {data: {events: [], teleporters: [], shards: {gs: 0, ss: 0, wv: 0}, skills: [], maps: 0, relics_found: [], relics: [], trees: []}};
    }

    componentDidMount() {
        if(!this.props.embedded) {
            this.getUpdate();
            this.interval = setInterval(() => this.getUpdate(), 1000);
        }
    };

    getUpdate = () => {
        doNetRequest(`/tracker/game/${game_id}/fetch/items/${player_id}`, ({response}) => this.setState({ data: JSON.parse(response) }))
    }

	render = () => {
        let embedded = this.props.embedded
        let data = embedded ? this.props.data : this.state.data
        let style = embedded ? {width: "100%", height: "100%", position: "absolute"} : {position: "absolute"}
        let bg = always.map(a => (<div style={{top: 0, ...style}}><img style={style} alt={a} src={a}/></div>))
        let fg = Object.keys(imageMap).filter(uri => imageMap[uri](data)).map(a => (<div style={{zIndex: a.includes("relics/found") ? 2001 : 2000, top: 0, ...style}}><img style={style} alt={a} src={a}/></div>))
        let helmet = embedded ? null : (<Helmet><style>{'body { background-color: black}'}</style></Helmet>)
	return (
        <div className="position-relative" style={embedded ? {width: "100%", paddingTop: "100%"} : {width: "750px", height: "750px"}}>
            {helmet}
            {fg}
            {bg}
            <div style={{position: "absolute", top: "62%", width: "100%", color: "yellow", textAlign: "center", fontSize: embedded ? "1.5vh" : "2vh"}}>{data.maps}/9</div> 
       </div>
    )
	}
};

