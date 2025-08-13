import React from 'react';
import {doNetRequest, get_param} from './common.js';
import {Helmet} from 'react-helmet';

const game_id = get_param("game_id");
const player_id = get_param("player_id");
const imageMap = {
    '/static/sprites/tracker/Bash.png': (data) => data.skills.includes("Bash"),
    '/static/sprites/tracker/ChargeFlame.png': (data) => data.skills.includes("Charge Flame"),
    '/static/sprites/tracker/ChargeJump.png': (data) => data.skills.includes("Charge Jump"),
    '/static/sprites/tracker/Climb.png': (data) => data.skills.includes("Climb"),
    '/static/sprites/tracker/Dash.png': (data) => data.skills.includes("Dash"),
    '/static/sprites/tracker/Stomp.png': (data) => data.skills.includes("Stomp"),
    '/static/sprites/tracker/DoubleJump.png': (data) => data.skills.includes("Double Jump"),
    '/static/sprites/tracker/WallJump.png': (data) => data.skills.includes("Wall Jump"),
    '/static/sprites/tracker/Glide.png': (data) => data.skills.includes("Glide"),
    '/static/sprites/tracker/LightGrenade.png': (data) => data.skills.includes("Grenade"),
    '/static/sprites/tracker/TBash.png': (data) => data.trees.includes("Bash"),
    '/static/sprites/tracker/TChargeFlame.png': (data) => data.trees.includes("Charge Flame"),
    '/static/sprites/tracker/TChargeJump.png': (data) => data.trees.includes("Charge Jump"),
    '/static/sprites/tracker/TClimb.png': (data) => data.trees.includes("Climb"),
    '/static/sprites/tracker/TStomp.png': (data) => data.trees.includes("Stomp"),
    '/static/sprites/tracker/TDoubleJump.png': (data) => data.trees.includes("Double Jump"),
    '/static/sprites/tracker/TWallJump.png': (data) => data.trees.includes("Wall Jump"),
    '/static/sprites/tracker/TGlide.png': (data) => data.trees.includes("Glide"),
    '/static/sprites/tracker/TDash.png': (data) => data.trees.includes("Dash"),
    '/static/sprites/tracker/TLightGrenade.png': (data) => data.trees.includes("Grenade"),
    '/static/sprites/tracker/CleanWater.png': (data) => data.events.includes("Clean Water"),
    '/static/sprites/tracker/WindRestored.png': (data) => data.events.includes("Wind Restored"),
    '/static/sprites/tracker/WaterVein.png': (data) => data.events.includes("Water Vein"),
    '/static/sprites/tracker/WaterVeinShard1.png': (data) => data.shards.wv > 0,
    '/static/sprites/tracker/WaterVeinShard2.png': (data) => data.shards.wv > 1,
    '/static/sprites/tracker/GumonSeal.png': (data) => data.events.includes("Gumon Seal"),
    '/static/sprites/tracker/GumonSealShard1.png': (data) => data.shards.gs > 0,
    '/static/sprites/tracker/GumonSealShard2.png': (data) => data.shards.gs > 1,
    '/static/sprites/tracker/Sunstone.png': (data) => data.events.includes("Sunstone"),
    '/static/sprites/tracker/SunstoneShard1.png': (data) => data.shards.ss > 0,
    '/static/sprites/tracker/SunstoneShard2.png': (data) => data.shards.ss > 1,
    '/static/sprites/tracker/BlackrootTP.png': (data) => data.teleporters.includes("Blackroot"),
    '/static/sprites/tracker/ForlornTP.png': (data) => data.teleporters.includes("Forlorn"),
    '/static/sprites/tracker/GinsoTP.png': (data) => data.teleporters.includes("Ginso"),
    '/static/sprites/tracker/HoruTP.png': (data) => data.teleporters.includes("Horu"),
    '/static/sprites/tracker/SwampTP.png': (data) => data.teleporters.includes("Swamp"),
    '/static/sprites/tracker/GroveTP.png': (data) => data.teleporters.includes("Grove"),
    '/static/sprites/tracker/GrottoTP.png': (data) => data.teleporters.includes("Grotto"),
    '/static/sprites/tracker/ValleyTP.png': (data) => data.teleporters.includes("Valley"),
    '/static/sprites/tracker/SorrowTP.png': (data) => data.teleporters.includes("Sorrow"),
    '/static/sprites/tracker/relics/found/Blackroot.png': (data) => data.relics_found.includes("Blackroot"),
    '/static/sprites/tracker/relics/found/Forlorn.png': (data) => data.relics_found.includes("Forlorn"),
    '/static/sprites/tracker/relics/found/Ginso.png': (data) => data.relics_found.includes("Ginso"),
    '/static/sprites/tracker/relics/found/Horu.png': (data) => data.relics_found.includes("Horu"),
    '/static/sprites/tracker/relics/found/Swamp.png': (data) => data.relics_found.includes("Swamp"),
    '/static/sprites/tracker/relics/found/Grove.png': (data) => data.relics_found.includes("Grove"),
    '/static/sprites/tracker/relics/found/Grotto.png': (data) => data.relics_found.includes("Grotto"),
    '/static/sprites/tracker/relics/found/Valley.png': (data) => data.relics_found.includes("Valley"),
    '/static/sprites/tracker/relics/found/Sorrow.png': (data) => data.relics_found.includes("Sorrow"),
    '/static/sprites/tracker/relics/found/Glades.png': (data) => data.relics_found.includes("Glades"),
    '/static/sprites/tracker/relics/found/Misty.png': (data) => data.relics_found.includes("Misty"),
    '/static/sprites/tracker/relics/exists/Blackroot.png': (data) => data.relics.includes("Blackroot"),
    '/static/sprites/tracker/relics/exists/Forlorn.png': (data) => data.relics.includes("Forlorn"),
    '/static/sprites/tracker/relics/exists/Ginso.png': (data) => data.relics.includes("Ginso"),
    '/static/sprites/tracker/relics/exists/Horu.png': (data) => data.relics.includes("Horu"),
    '/static/sprites/tracker/relics/exists/Swamp.png': (data) => data.relics.includes("Swamp"),
    '/static/sprites/tracker/relics/exists/Grove.png': (data) => data.relics.includes("Grove"),
    '/static/sprites/tracker/relics/exists/Grotto.png': (data) => data.relics.includes("Grotto"),
    '/static/sprites/tracker/relics/exists/Valley.png': (data) => data.relics.includes("Valley"),
    '/static/sprites/tracker/relics/exists/Sorrow.png': (data) => data.relics.includes("Sorrow"),
    '/static/sprites/tracker/relics/exists/Glades.png': (data) => data.relics.includes("Glades"),
    '/static/sprites/tracker/relics/exists/Misty.png': (data) => data.relics.includes("Misty"),
}
const always = ["GCleanWater", "GGumonSeal", "GreyTrees", "GreySkillRing", "GSunstone", "GWaterVein", "SpiritFlame", "TSpiritFlame",
                "GWindRestored", "SkillRing_Single", "SkillRing_Triple", "SkillRing_Double", "MapStone"].map(n => `/static/sprites/tracker/${n}.png`)

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

