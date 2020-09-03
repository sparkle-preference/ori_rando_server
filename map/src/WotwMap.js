import './index.css';
import React, {Fragment} from 'react';
import {Map, Tooltip, ImageOverlay, Marker, ZoomControl, Circle} from 'react-leaflet';
import Leaflet from 'leaflet';
import {presets, player_icons, get_preset, logic_paths, Blabel, dev} from './common.js';
import {pickup_icons, picks_by_type, point, PickupMarkersList, select_styles, select_wrap} from './shared_map.js';
import Select from 'react-select';
import {Button, Collapse, Container, Row, Col, Input, UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap';
import Control from 'react-leaflet-control';
import {Helmet} from 'react-helmet';

const paths = Object.keys(presets);

const EMPTY_PLAYER = {seed: {}, pos: [-800, -4300], seen:[], show_marker: true, hide_found: true, hide_unreachable: true, spoiler: false, hide_remaining: false, sense: false, areas: []}

function getWotwCRS() {
    // pixel coords (approx)
    let source1 = new Leaflet.Point(1532, 1492) // burrows well
    let source2 = new Leaflet.Point(5632, 252)  // outer ruins well

    // game coords
    let target1 = new Leaflet.Point(-944.7414, -4581.923) // burrows well
    let target2 = new Leaflet.Point(2043.639, -3678.877)  // outer ruins well

    let a = (target2.x-target1.x)/(source2.x-source1.x)
    let b = target1.x - source1.x*a
    let c = (target2.y-target1.y)/(source2.y-source1.y)
    let d = target1.y - source1.y*c
    let trans = new Leaflet.Transformation(a, b, c, d)
    
    let tl = trans.transform(new Leaflet.Point(0, 0))
    let br = trans.transform(new Leaflet.Point(6193, 2061))

    Leaflet.CRS.WotwSimple = Leaflet.extend({}, Leaflet.CRS.Simple, {transformation: trans });
    console.log([trans.transform(tl), trans.transform(br)])
    return {crs: Leaflet.CRS.WotwSimple, bounds: [[tl.y, tl.x], [br.y, br.x]]};
};

const {crs, bounds} = getWotwCRS();

const wotwPicks = [
    {x: -461, y: -4195, name: 'swampStateGroup[21786].keyStoneA[27433]'},
    {x: -394, y: -4188, name: 'swampStateGroup[21786].keyStoneB[37225]'},
    {x: -439, y: -4462, name: 'swampStateGroup[21786].keyStone[22068]'},
    {x: -400, y: -4568, name: 'swampStateGroup[21786].laserPuzzleSolved[2852]'},
    {x: -852, y: -4404, name: 'swampStateGroup[21786].swampWalljumpChallengeBKeystoneBCollected[64677]'},
    {x: -221, y: -4406, name: 'questUberStateGroup[14019].braveMokiItemCollected[27539]'},
    {x: -664, y: -4187, name: 'inkwaterMarshStateGroup[9593].energyContainer[26457]'},
    {x: -473, y: -4340, name: 'inkwaterMarshStateGroup[9593].halfEnergyCellA[27562]'},
    {x: -625, y: -4418, name: 'swampStateGroup[21786].energyHalfCell[17920]'},
    {x: -422, y: -4273, name: 'swampStateGroup[21786].energyHalfCellA[10295]'},
    {x: -233, y: -4385, name: 'swampStateGroup[21786].halfEnergyCellA[61706]'},
    {x: -667, y: -4330, name: 'swampStateGroup[21786].halfEnergyCellA[7152]'},
    {x: -569, y: -4454, name: 'inkwaterMarshStateGroup[9593].healthContainer[61304]'},
    {x: -332, y: -4439, name: 'swampStateGroup[21786].halfHealthCellA[28908]'},
    {x: -718, y: -4278, name: 'swampStateGroup[21786].healthContainerA[25761]'},
    {x: -958, y: -4313, name: 'swampStateGroup[21786].healthContainerA[60210]'},
    {x: -437, y: -4381, name: 'swampStateGroup[21786].lifeCellA[20194]'},
    {x: -935, y: -4357, name: 'inkwaterMarshStateGroup[9593].gorlekOreA[20382]'},
    {x: -858, y: -4423, name: 'inkwaterMarshStateGroup[9593].gorlekOreA[23858]'},
    {x: -501, y: -4340, name: 'inkwaterMarshStateGroup[9593].gorlekOreA[25989]'},
    {x: -432, y: -4503, name: 'swampStateGroup[21786].gorlekOreA[2046]'},
    {x: -810, y: -4334, name: 'swampStateGroup[21786].gorlekOreA[29892]'},
    {x: -314, y: -4570, name: 'howlsOriginGroup[24922].shrineArena[45011]'},
    {x: -382, y: -4337, name: 'swampStateGroup[21786].enemyRoom[2869]'},
    {x: -916, y: -4399, name: 'pickupsGroup[23987].bloodPactShardPickup[50415]'},
    {x: -239, y: -4441, name: 'swampStateGroup[21786].spiritShardA[63545]'},
    {x: -499, y: -4411, name: 'pickupsGroup[23987].recklessShardPickup[9864]'},
    {x: -790, y: -4335, name: 'pickupsGroup[23987].barrierShardPickup[59173]'},
    {x: -547, y: -4530, name: 'pickupsGroup[23987].glueShardPickup[27134]'},
    {x: -589, y: -4348, name: 'npcsStateGroup[48248].hasMapInkwaterMarsh[18767]'},
    {x: -801, y: -4186, name: 'lagoonStateGroup[945].largeExpC[10833]'},
    {x: -979, y: -4510, name: 'howlsOriginGroup[24922].largeExpA[62138]'},
    {x: -1015, y: -4269, name: 'swampStateGroup[21786].largeExpA[21727]'},
    {x: -527, y: -4354, name: 'inkwaterMarshStateGroup[9593].expOrbA[5253]'},
    {x: -343, y: -4357, name: 'swampStateGroup[21786].largeExpA[10413]'},
    {x: -837, y: -4315, name: 'swampStateGroup[21786].mediumExpA[23154]'},
    {x: -641, y: -4223, name: 'swampStateGroup[21786].mediumExpA[50255]'},
    {x: -1001, y: -4451, name: 'howlsOriginGroup[24922].smallExpA[32076]'},
    {x: -507, y: -4537, name: 'inkwaterMarshStateGroup[9593].expOrb[17818]'},
    {x: -492, y: -4260, name: 'inkwaterMarshStateGroup[9593].expOrb[59344]'},
    {x: -783, y: -4452, name: 'inkwaterMarshStateGroup[9593].xpOrb[42047]'},
    {x: -656, y: -4342, name: 'inkwaterMarshStateGroup[9593].xpOrbA[5929]'},
    {x: -755, y: -4423, name: 'swampStateGroup[21786].expOrb[59513]'},
    {x: -764, y: -4313, name: 'swampStateGroup[21786].smallExpA[49485]'},
    {x: -739, y: -4324, name: 'swampStateGroup[21786].xpOrbA[6987]'},
    {x: -433, y: -4420, name: 'swampStateGroup[21786].xpOrbB[43668]'},
    {x: -389, y: -4503, name: 'swampStateGroup[21786].xpOrbC[16206]'},
    {x: -296, y: -4483, name: 'treesDontWorry[0].SpiritEdge[100]'},
    {x: -539, y: -4406, name: 'treesDontWorry[0].Regenerate[77]'},
    {x: -555, y: -4551, name: 'treesDontWorry[0].DoubleJump[5]'},
    {x: -457, y: -4267, name: 'treesDontWorry[0].SpiritArc[97]'},
    {x: -840, y: -4488, name: 'treesDontWorry[0].AncestralLight[121]'},
    {x: 331, y: -4192, name: '_petrifiedForestGroup[58674].energyContainerA[9583]'},
    {x: 46, y: -4237, name: 'kwolokGroupDescriptor[937].energyHalfCell[23772]'},
    {x: -238, y: -4301, name: 'kwolokGroupDescriptor[937].energyHalfCell[8518]'},
    {x: -177, y: -4353, name: 'kwolokGroupDescriptor[937].energyHalfContainer[24175]'},
    {x: -121, y: -4269, name: 'kwolokGroupDescriptor[937].halfHealthCell[2463]'},
    {x: 83, y: -4263, name: 'kwolokGroupDescriptor[937].healthHalfCell[58598]'},
    {x: -254, y: -4225, name: 'kwolokGroupDescriptor[937].healthHalfCell[61897]'},
    {x: 83, y: -4264, name: 'bashIntroductionA__clone1Group[13428].healthContainerA[59730]'},
    {x: -97, y: -4190, name: 'kwolokGroupDescriptor[937].gromOreA[10729]'},
    {x: 243, y: -4224, name: 'kwoloksCavernThroneRoomGroup[46462].gorlekOreA[37897]'},
    {x: -310, y: -4326, name: 'pickupsGroup[23987].frenzyShardPickup[61017]'},
    {x: 216, y: -4308, name: 'pickupsGroup[23987].splinterShardPickup[62973]'},
    {x: 289, y: -4196, name: '_petrifiedForestGroup[58674].expOrbA[20983]'},
    {x: 9, y: -4197, name: 'kwolokGroupDescriptor[937].mediumExpA[45987]'},
    {x: -31, y: -4302, name: 'kwolokGroupDescriptor[937].mediumExpB[30182]'},
    {x: 57, y: -4189, name: 'kwolokGroupDescriptor[937].mediumExpC[19529]'},
    {x: -37, y: -4453, name: 'kwolokGroupDescriptor[937].xpOrbA[50176]'},
    {x: 113, y: -4229, name: 'kwoloksCavernThroneRoomGroup[46462].largeExpA[29054]'},
    {x: 131, y: -4272, name: 'mouldwoodDepthsGroup[18793].mediumExpB[42980]'},
    {x: -357, y: -4294, name: 'kwolokGroupDescriptor[937].smallExpOrbPlaceholder[16163]'},
    {x: -296, y: -4293, name: 'kwolokGroupDescriptor[937].smallExpOrbPlaceholder[2538]'},
    {x: 11, y: -4401, name: 'kwolokGroupDescriptor[937].smallExpOrbPlaceholder[37926]'},
    {x: -82, y: -4370, name: 'kwolokGroupDescriptor[937].smallExpOrbPlaceholderA[48192]'},
    {x: -99, y: -4408, name: 'kwolokGroupDescriptor[937].smallExpOrbPlaceholderC[61744]'},
    {x: -85, y: -4209, name: 'kwolokGroupDescriptor[937].xpOrbA[13413]'},
    {x: -55, y: -4201, name: 'kwolokGroupDescriptor[937].xpOrbB[5568]'},
    {x: 161, y: -4245, name: 'kwoloksCavernThroneRoomGroup[46462].smallExpA[20780]'},
    {x: -146, y: -4321, name: 'npcsStateGroup[48248].hasMapKwoloksHollow[3638]'},
    {x: -69, y: -4453, name: 'treesDontWorry[0].Dash[102]'},
    {x: -20, y: -4326, name: 'treesDontWorry[0].Bash[0]'},
    {x: -232, y: -3869, name: 'baursReachGroup[28895].keystoneA[22382]'},
    {x: 34, y: -4025, name: 'baursReachGroup[28895].keystoneA[29898]'},
    {x: -248, y: -3891, name: 'baursReachGroup[28895].keystoneB[1053]'},
    {x: -80, y: -4040, name: 'baursReachGroup[28895].keystoneB[37444]'},
    {x: -84, y: -4025, name: 'baursReachGroup[28895].keystoneC[10823]'},
    {x: -184, y: -3867, name: 'baursReachGroup[28895].keystoneC[9949]'},
    {x: -58, y: -4055, name: 'baursReachGroup[28895].keystoneD[18358]'},
    {x: -207, y: -3843, name: 'baursReachGroup[28895].keystoneD[50368]'},
    {x: -103, y: -3858, name: 'questUberStateGroup[14019].gardenerSeedSpringCollected[32376]'},
    {x: -190, y: -4017, name: 'baursReachGroup[28895].healthCellA[40744]'},
    {x: -203, y: -3886, name: 'baursReachGroup[28895].gorlekOreA[23795]'},
    {x: -87, y: -3903, name: 'baursReachGroup[28895].gorlekOreA[39291]'},
    {x: -483, y: -3974, name: 'baursReachGroup[28895].gorlekOreA[58675]'},
    {x: -346, y: -3947, name: 'baursReachGroup[28895].orePlaceholder[47529]'},
    {x: -90, y: -4097, name: 'pickupsGroup[23987].hollowEnergyShardPickup[897]'},
    {x: -81, y: -4001, name: 'pickupsGroup[23987].fractureShardPickup[36359]'},
    {x: -400, y: -3861, name: 'pickupsGroup[23987].untouchableShardPickup[19630]'},
    {x: 71, y: -3731, name: 'baursReachGroup[28895].xpOrbB[46404]'},
    {x: -172, y: -3928, name: 'baursReachGroup[28895].largeExpOrb[2129]'},
    {x: -500, y: -3970, name: 'baursReachGroup[28895].largeXPOrbA[45337]'},
    {x: -282, y: -4013, name: 'baursReachGroup[28895].xpOrbB[38049]'},
    {x: -112, y: -3950, name: 'baursReachGroup[28895].xpOrbC[53283]'},
    {x: -194, y: -4043, name: 'hubUberStateGroup[42178].mediumExpB[40609]'},
    {x: -423, y: -3876, name: 'winterForestGroupDescriptor[28287].mediumExpA[32414]'},
    {x: -39, y: -4018, name: 'baursReachGroup[28895].mediumExpOrb[22761]'},
    {x: -194, y: -3854, name: 'baursReachGroup[28895].xpOrbB[40089]'},
    {x: -239, y: -3921, name: 'baursReachGroup[28895].xpOrbC[40242]'},
    {x: -350, y: -4039, name: 'baursReachGroup[28895].xpOrbF[4301]'},
    {x: -340, y: -3984, name: 'baursReachGroup[28895].[36231]'},
    {x: -439, y: -3946, name: 'baursReachGroup[28895].[3777]'},
    {x: -72, y: -3926, name: 'baursReachGroup[28895].smallExpB[7597]'},
    {x: -205, y: -4011, name: 'baursReachGroup[28895].smallXPOrbA[54373]'},
    {x: -401, y: -4053, name: 'baursReachGroup[28895].smallXPOrbA[55384]'},
    {x: -416, y: -3968, name: 'baursReachGroup[28895].smallXPOrbB[24533]'},
    {x: -215, y: -4057, name: 'baursReachGroup[28895].smallXPOrbB[35045]'},
    {x: -337, y: -3999, name: 'baursReachGroup[28895].xpOrbA[38143]'},
    {x: -72, y: -3951, name: 'baursReachGroup[28895].xpOrbB[46711]'},
    {x: -331, y: -4051, name: 'baursReachGroup[28895].xpOrbE[45066]'},
    {x: -275, y: -3996, name: 'npcsStateGroup[48248].hasMapBaursReach[29604]'},
    {x: -106, y: -3934, name: 'treesDontWorry[0].LightBurst[51]'},
    {x: -1548, y: -4081, name: 'lumaPoolsStateGroup[5377].keystoneA[35091]'},
    {x: -1538, y: -40748, name: 'lumaPoolsStateGroup[5377].keystoneB[16426]'},
    {x: -1576, y: -4126, name: 'lumaPoolsStateGroup[5377].keystoneC[46926]'},
    {x: -1518, y: -4079, name: 'lumaPoolsStateGroup[5377].keystoneD[41881]'},
    {x: -924, y: -4170, name: 'lagoonStateGroup[945].energyCellA[21334]'},
    {x: -1623, y: -4000, name: 'lumaPoolsStateGroup[5377].energyCellFragmentA[1600]'},
    {x: -1389, y: -4040, name: 'lumaPoolsStateGroup[5377].energyContainerA[32750]'},
    {x: -851, y: -4196, name: 'lagoonStateGroup[945].lagoonMillTransitionHealthCell[37243]'},
    {x: -1365, y: -4109, name: 'lumaPoolsStateGroup[5377].healthContainerA[45774]'},
    {x: -1278, y: -4086, name: 'lumaPoolsStateGroup[5377].healthContainerA[63201]'},
    {x: -1370, y: -4167, name: 'lumaPoolsStateGroup[5377].gorlekOreA[12235]'},
    {x: -1535, y: -4034, name: 'lumaPoolsStateGroup[5377].gorlekOreA[31434]'},
    {x: -1770, y: -4125, name: 'lumaPoolsStateGroup[5377].gorlekOreA[65019]'},
    {x: -1134, y: -4117, name: 'lumaPoolsStateGroup[5377].orePickupA[34852]'},
    {x: -1249, y: -4139, name: 'lumaPoolsStateGroup[5377].pickupA[19694]'},
    {x: -1528, y: -4140, name: 'questUberStateGroup[14019].gardenerSeedGrassCollected[28662]'},
    {x: -1284, y: -4197, name: 'pickupsGroup[23987].ultraBashShardPickup[25996]'},
    {x: -1441, y: -4130, name: 'lumaPoolsStateGroup[5377].spiritShard[40328]'},
    {x: -1572, y: -4077, name: 'lumaPoolsStateGroup[5377].largeExpOrbPlaceholderA[628]'},
    {x: -895, y: -4137, name: 'lagoonStateGroup[945].medExpA[58723]'},
    {x: -941, y: -4145, name: 'lagoonStateGroup[945].mediumExpA[14530]'},
    {x: -1047, y: -4217, name: 'lagoonStateGroup[945].mediumExpB[10682]'},
    {x: -1431, y: -4181, name: 'lumaPoolsStateGroup[5377].xpOrbA[18345]'},
    {x: -1645, y: -4085, name: 'lumaPoolsStateGroup[5377].xpOrbA[21860]'},
    {x: -1230, y: -4126, name: 'lumaPoolsStateGroup[5377].xpOrbA[27204]'},
    {x: -1449, y: -4037, name: 'lumaPoolsStateGroup[5377].xpOrbA[33180]'},
    {x: -1654, y: -4143, name: 'lumaPoolsStateGroup[5377].xpOrbA[44122]'},
    {x: -1336, y: -4104, name: 'lumaPoolsStateGroup[5377].xpOrbA[7540]'},
    {x: -1414, y: -4155, name: 'lumaPoolsStateGroup[5377].xpOrbB[35440]'},
    {x: -1468, y: -4098, name: 'lumaPoolsStateGroup[5377].xpOrbB[52791]'},
    {x: -1655, y: -4189, name: 'lumaPoolsStateGroup[5377].xpOrbB[62180]'},
    {x: -1214, y: -4181, name: 'lumaPoolsStateGroup[5377].xpOrbC[17396]'},
    {x: -1176, y: -4178, name: 'lumaPoolsStateGroup[5377].xpOrbD[13832]'},
    {x: -1568, y: -4063, name: 'lumaPoolsStateGroup[5377].mediumExpOrbPlaceholderC[33110]'},
    {x: -1650, y: -4160, name: 'lumaPoolsStateGroup[5377].xpOrbA[25391]'},
    {x: -1391, y: -4167, name: 'npcsStateGroup[48248].hasMapLumaPools[1557]'},
    {x: -1430, y: -4082, name: 'treesDontWorry[0].SwimDash[104]'},
    {x: -725, y: -4520, name: 'howlsOriginGroup[24922].keystoneA[34250]'},
    {x: -597, y: -4548, name: 'howlsOriginGroup[24922].keystoneA[47244]'},
    {x: -800, y: -4580, name: 'howlsOriginGroup[24922].keystoneA[60358]'},
    {x: -704, y: -4609, name: 'howlsOriginGroup[24922].keystoneB[33535]'},
    {x: -848, y: -4530, name: 'questUberStateGroup[14019].howlsOriginTreasureCollected[52747]'},
    {x: -773, y: -4528, name: 'howlsOriginGroup[24922].spiritShard[46311]'},
    {x: -870, y: -4555, name: 'npcsStateGroup[48248].hasMapHowlsOrigin[45538]'},
    {x: 317, y: -4454, name: 'mouldwoodDepthsGroup[18793].keystone[1914]'},
    {x: 146, y: -4426, name: 'mouldwoodDepthsGroup[18793].keystoneA[58148]'},
    {x: 498, y: -4463, name: 'mouldwoodDepthsGroup[18793].mouldwoodDepthsHKeystoneACollected[53953]'},
    {x: 524, y: -4465, name: 'mouldwoodDepthsGroup[18793].mouldwoodDepthsHKeystoneBCollected[23986]'},
    {x: 488, y: -4431, name: 'questUberStateGroup[14019].gardenerSeedBashCollected[8192]'},
    {x: 134, y: -4456, name: 'mouldwoodDepthsGroup[18793].energyContainerA[26618]'},
    {x: 324, y: -4535, name: 'mouldwoodDepthsGroup[18793].energyContainerA[28175]'},
    {x: 496, y: -4499, name: 'mouldwoodDepthsGroup[18793].healthCellA[62694]'},
    {x: 531, y: -4452, name: 'mouldwoodDepthsGroup[18793].healthCellB[42235]'},
    {x: 185, y: -4380, name: 'mouldwoodDepthsGroup[18793].orePickupA[35351]'},
    {x: 436, y: -4507, name: 'mouldwoodDepthsGroup[18793].orePickupA[836]'},
    {x: 212, y: -4510, name: 'mouldwoodDepthsGroup[18793].shrineEnemies[12512]'},
    {x: 564, y: -4571, name: 'pickupsGroup[23987].spiritPowerShardPickup[986]'},
    {x: 481, y: -4381, name: 'mouldwoodDepthsGroup[18793].expOrbA[29979]'},
    {x: 387, y: -4523, name: 'mouldwoodDepthsGroup[18793].expOrbB[2881]'},
    {x: 425, y: -4385, name: 'mouldwoodDepthsGroup[18793].expOrbB[6573]'},
    {x: 798, y: -4512, name: 'mouldwoodDepthsGroup[18793].expOrbC[23799]'},
    {x: 171, y: -4358, name: 'mouldwoodDepthsGroup[18793].mediumExpA[19004]'},
    {x: 567, y: -4443, name: 'mouldwoodDepthsGroup[18793].XPOrbA[18395]'},
    {x: 146, y: -4375, name: 'mouldwoodDepthsGroup[18793].xpOrbC[15396]'},
    {x: 682, y: -4576, name: 'npcsStateGroup[48248].hasMapMouldwoodDepths[48423]'},
    {x: 776, y: -4541, name: 'treesDontWorry[0].Flash[62]'},
    {x: 886, y: -4123, name: '_petrifiedForestGroup[58674].keyStoneA[42531]'},
    {x: 908, y: -4120, name: '_petrifiedForestGroup[58674].keyStoneB[19769]'},
    {x: 641, y: -4166, name: '_petrifiedForestGroup[58674].keyStoneC[11736]'},
    {x: 956, y: -4148, name: '_petrifiedForestGroup[58674].keyStoneC[43033]'},
    {x: 690, y: -4189, name: '_petrifiedForestGroup[58674].keyStoneD[40073]'},
    {x: 929, y: -4185, name: '_petrifiedForestGroup[58674].keyStoneD[780]'},
    {x: 1011, y: -4070, name: '_petrifiedForestGroup[58674].gorlekOreA[20713]'},
    {x: 988, y: -4172, name: '_petrifiedForestGroup[58674].gorlekOreA[26274]'},
    {x: 411, y: -4174, name: '_petrifiedForestGroup[58674].gorlekOreA[28710]'},
    {x: 1305, y: -3732, name: 'corruptedPeakGroup[36153].gorlekOreA[3013]'},
    {x: 1361, y: -4064, name: '_petrifiedForestGroup[58674].enemyRoom[56043]'},
    {x: 827, y: -3939, name: 'pickupsGroup[23987].recycleShardPickup[25183]'},
    {x: 1382, y: -3767, name: 'corruptedPeakGroup[36153].expOrb[36521]'},
    {x: 1331, y: -3798, name: 'corruptedPeakGroup[36153].xpOrbB[12077]'},
    {x: 1464, y: -4008, name: '_petrifiedForestGroup[58674].expOrb[64484]'},
    {x: 1406, y: -4065, name: '_petrifiedForestGroup[58674].expOrbA[32647]'},
    {x: 968, y: -4124, name: '_petrifiedForestGroup[58674].expOrbA[64057]'},
    {x: 968, y: -4142, name: '_petrifiedForestGroup[58674].expOrbC[30908]'},
    {x: 1069, y: -4099, name: '_petrifiedForestGroup[58674].expOrbD[59714]'},
    {x: 936, y: -4044, name: '_petrifiedForestGroup[58674].mediumPickupC[54516]'},
    {x: 628, y: -4156, name: '_petrifiedForestGroup[58674].CollecitbleXPB[59691]'},
    {x: 514, y: -4185, name: '_petrifiedForestGroup[58674].CollectibleXpA[8487]'},
    {x: 941, y: -4185, name: '_petrifiedForestGroup[58674].expOrbA[23186]'},
    {x: 948, y: -4210, name: '_petrifiedForestGroup[58674].expOrbC[42158]'},
    {x: 951, y: -4168, name: '_petrifiedForestGroup[58674].expOrbD[33893]'},
    {x: 904, y: -4075, name: '_petrifiedForestGroup[58674].smallPickupA[17974]'},
    {x: 485, y: -4165, name: '_petrifiedForestGroup[58674].xpOrbA[22472]'},
    {x: 1363, y: -3815, name: 'treesDontWorry[0].Launch[8]'},
    {x: -1186, y: -3697, name: 'wellspringGroupDescriptor[53632].questItemCompass[41227]'},
    {x: -1185, y: -3669, name: 'questUberStateGroup[14019].gardenerSeedGrappleCollected[24142]'},
    {x: -1109, y: -3865, name: 'waterMillStateGroupDescriptor[37858].energyVessel[57552]'},
    {x: -735, y: -3989, name: 'wellspringGroupDescriptor[53632].energyVesselA[1911]'},
    {x: -857, y: -4116, name: 'wellspringGroupDescriptor[53632].energyVesselB[6869]'},
    {x: -1168, y: -3991, name: 'waterMillStateGroupDescriptor[37858].healthContainerA[25833]'},
    {x: -877, y: -3962, name: 'wellspringGroupDescriptor[53632].lifeVesselA[17403]'},
    {x: -1204, y: -3715, name: 'waterMillStateGroupDescriptor[37858].gorlekOreA[32932]'},
    {x: -1178, y: -3756, name: 'waterMillStateGroupDescriptor[37858].gorlekOreA[47533]'},
    {x: -678, y: -3934, name: 'waterMillStateGroupDescriptor[37858].gorlekOreA[58286]'},
    {x: -1077, y: -3937, name: 'waterMillStateGroupDescriptor[37858].gorlekOreB[58846]'},
    {x: -761, y: -4094, name: 'wellspringGroupDescriptor[53632].orePickupA[21124]'},
    {x: -738, y: -4018, name: 'wellspringGroupDescriptor[53632].orePickupB[25556]'},
    {x: -998, y: -4030, name: 'pickupsGroup[23987].vitalityLuckShardPickup[53934]'},
    {x: -1376, y: -3995, name: 'pickupsGroup[23987].counterstrikeShardPickup[31426]'},
    {x: -799, y: -3913, name: 'pickupsGroup[23987].ultraLeashShardPickup[12104]'},
    {x: -1237, y: -3741, name: 'waterMillStateGroupDescriptor[37858].expOrb[64086]'},
    {x: -1223, y: -3907, name: 'waterMillStateGroupDescriptor[37858].xpOrbA[33063]'},
    {x: -1372, y: -3939, name: 'waterMillStateGroupDescriptor[37858].mediumExpA[22107]'},
    {x: -1308, y: -3885, name: 'waterMillStateGroupDescriptor[37858].mediumExpA[31136]'},
    {x: -1063, y: -3961, name: 'waterMillStateGroupDescriptor[37858].mediumExpA[41380]'},
    {x: -1252, y: -3683, name: 'waterMillStateGroupDescriptor[37858].mediumExpA[59022]'},
    {x: -1142, y: -3862, name: 'waterMillStateGroupDescriptor[37858].mediumExpB[41911]'},
    {x: -1151, y: -3841, name: 'waterMillStateGroupDescriptor[37858].mediumExpB[52110]'},
    {x: -1313, y: -3640, name: 'waterMillStateGroupDescriptor[37858].xpOrb[56444]'},
    {x: -1197, y: -3972, name: 'waterMillStateGroupDescriptor[37858].xpOrbWater[45656]'},
    {x: -825, y: -4086, name: 'wellspringGroupDescriptor[53632].mediumExpOrbPlaceholderC[62356]'},
    {x: -745, y: -3942, name: 'wellspringGroupDescriptor[53632].mediumExpOrbPlaceholderE[51706]'},
    {x: -850, y: -4024, name: 'wellspringGroupDescriptor[53632].mediumExpOrbPlaceholderF[42264]'},
    {x: -898, y: -4071, name: 'wellspringGroupDescriptor[53632].mediumExpOrbPlaceholderG[6500]'},
    {x: -1247, y: -3928, name: 'waterMillStateGroupDescriptor[37858].smallExpA[45906]'},
    {x: -1317, y: -3665, name: 'waterMillStateGroupDescriptor[37858].smallExpOrb[2797]'},
    {x: -1190, y: -3861, name: 'npcsStateGroup[48248].hasMapWellspring[1590]'},
    {x: -1309, y: -3905, name: 'treesDontWorry[0].Grapple[57]'},
    {x: -10, y: -4551, name: 'questUberStateGroup[14019].darkCaveQuestItemCollected[2782]'},
    {x: -116, y: -4540, name: 'hubUberStateGroup[42178].energyCellA[52786]'},
    {x: -690, y: -4115, name: 'kwolokGroupDescriptor[937].energyContainerA[17761]'},
    {x: -326, y: -4103, name: 'wellspringGladesGroup[44310].lifeVesselA[29043]'},
    {x: -688, y: -4009, name: 'wellspringGladesGroup[44310].lifeVesselA[36911]'},
    {x: -161, y: -4192, name: 'wellspringGladesGroup[44310].lifeVesselB[17523]'},
    {x: -416, y: -4174, name: 'hubUberStateGroup[42178].gorlekOreA[23125]'},
    {x: -418, y: -4104, name: 'hubUberStateGroup[42178].gorlekOreB[27110]'},
    {x: -690, y: -4098, name: 'kwolokGroupDescriptor[937].orePickup[6703]'},
    {x: -560, y: -4063, name: 'kwolokGroupDescriptor[937].orePickupB[11846]'},
    {x: -636, y: -4018, name: 'wellspringGladesGroup[44310].shardSlotUpgrade[9902]'},
    {x: -325, y: -4135, name: 'pickupsGroup[23987].chainLightningPickup[23015]'},
    {x: -247, y: -4106, name: 'pickupsGroup[23987].focusShardPickup[14014]'},
    {x: -161, y: -4521, name: 'hubUberStateGroup[42178].hutAExpOrb[51468]'},
    {x: -177, y: -4541, name: 'hubUberStateGroup[42178].hutBExpOrb[13327]'},
    {x: -172, y: -4584, name: 'hubUberStateGroup[42178].hutCExpOrb[57455]'},
    {x: -118, y: -4521, name: 'hubUberStateGroup[42178].hutDExpOrbB[30520]'},
    {x: -374, y: -4103, name: 'hubUberStateGroup[42178].mediumExpB[59623]'},
    {x: -225, y: -4162, name: 'hubUberStateGroup[42178].mediumExpE[9780]'},
    {x: -307, y: -4168, name: 'hubUberStateGroup[42178].mediumExpF[18448]'},
    {x: -232, y: -4106, name: 'hubUberStateGroup[42178].mediumExpG[6117]'},
    {x: -632, y: -4088, name: 'kwolokGroupDescriptor[937].mediumExpB[45744]'},
    {x: -586, y: -4091, name: 'kwolokGroupDescriptor[937].mediumExpC[31036]'},
    {x: -515, y: -4103, name: 'wellspringGroupDescriptor[53632].mediumExpA[12019]'},
    {x: -307, y: -4119, name: 'hubUberStateGroup[42178].smallExpH[42762]'},
    {x: -363, y: -4172, name: 'hubUberStateGroup[42178].smallExpA[30206]'},
    {x: -277, y: -4173, name: 'hubUberStateGroup[42178].smallExpB[37028]'},
    {x: -240, y: -4130, name: 'hubUberStateGroup[42178].smallExpC[63404]'},
    {x: -160, y: -4099, name: 'hubUberStateGroup[42178].smallExpG[44748]'},
    {x: -586, y: -4129, name: 'kwolokGroupDescriptor[937].smallExpA[40657]'},
    {x: 411, y: -3972, name: 'willowsEndGroup[16155].healthCellA[46270]'},
    {x: 557, y: -3876, name: 'willowsEndGroup[16155].gorlekOreA[38979]'},
    {x: 326, y: -3811, name: 'willowsEndGroup[16155].gorlekOreA[9230]'},
    {x: 434, y: -3640, name: 'corruptedPeakGroup[36153].expOrbA[23902]'},
    {x: 540, y: -3655, name: 'corruptedPeakGroup[36153].expOrbB[3662]'},
    {x: 470, y: -3915, name: 'willowsEndGroup[16155].expOrbA[49381]'},
    {x: 654, y: -3780, name: 'willowsEndGroup[16155].xpOrbA[55446]'},
    {x: 474, y: -3859, name: 'npcStateGroup[48248].hasMapWillowsEnd[4045]'},
    {x: 1877, y: -3844, name: 'desertAGroup[7228].keystoneAUberState[20282]'},
    {x: 1823, y: -3769, name: 'desertAGroup[7228].keystoneBUberStateGroup[62117]'},
    {x: 1996, y: -3651, name: 'questUberStateGroup[14019].gardenerSeedFlowersCollected[20601]'},
    {x: 1779, y: -3875, name: 'windsweptWastesGroupDescriptor[20120].energyContainer[50026]'},
    {x: 1653, y: -4015, name: 'windsweptWastesGroupDescriptor[20120].energyHalfCell[11785]'},
    {x: 1950, y: -3778, name: 'windsweptWastesGroupDescriptor[20120].energyOrbA[22354]'},
    {x: 1853, y: -3909, name: 'windsweptWastesGroupDescriptor[20120].halfLifeCell[59046]'},
    {x: 1860, y: -4022, name: 'windsweptWastesGroupDescriptor[20120].healthContainer[12941]'},
    {x: 1698, y: -3977, name: 'windsweptWastesGroupDescriptor[20120].lifeCellA[62264]'},
    {x: 2027, y: -3843, name: 'windsweptWastesGroupDescriptor[20120].lifeHalfCell[18965]'},
    {x: 1503, y: -4007, name: 'desertAGroup[7228].gorlekOre[54494]'},
    {x: 1952, y: -3616, name: 'desertAGroup[7228].gorlekOre[8370]'},
    {x: 1658, y: -3974, name: 'windsweptWastesGroupDescriptor[20120].gorlekOre[46919]'},
    {x: 1930, y: -3879, name: 'windsweptWastesGroupDescriptor[20120].gorlekOreB[40245]'},
    {x: 1833, y: -3936, name: 'pickupsGroup[23987].lastResortShardPickup[50364]'},
    {x: 1779, y: -3783, name: 'pickupsGroup[23987].aggressorShardPickup[48605]'},
    {x: 1887, y: -3973, name: 'windsweptWastesGroupDescriptor[20120].expOrb[224]'},
    {x: 1839, y: -3907, name: 'windsweptWastesGroupDescriptor[20120].expOrbB[33275]'},
    {x: 1862, y: -3874, name: 'windsweptWastesGroupDescriptor[20120].expOrbE[17798]'},
    {x: 1642, y: -3944, name: 'windsweptWastesGroupDescriptor[20120].xpOrbA[8910]'},
    {x: 1535, y: -3997, name: 'desertAGroup[7228].collectableADesertA[56821]'},
    {x: 1607, y: -3975, name: 'desertAGroup[7228].collectableCDesertA[52086]'},
    {x: 1907, y: -3807, name: 'desertAGroup[7228].expOrb[35329]'},
    {x: 1935, y: -3755, name: 'desertAGroup[7228].xpOrbAUberState[61548]'},
    {x: 1948, y: -3730, name: 'desertAGroup[7228].xpOrbBUberState[48993]'},
    {x: 2006, y: -3826, name: 'windsweptWastesGroupDescriptor[20120].xpOrb[52812]'},
    {x: 1951, y: -3838, name: 'windsweptWastesGroupDescriptor[20120].xpOrbA[30740]'},
    {x: 1795, y: -3998, name: 'windsweptWastesGroupDescriptor[20120].xpOrbB[10397]'},
    {x: 1601, y: -3953, name: 'windsweptWastesGroupDescriptor[20120].xpOrbB[19113]'},
    {x: 1719, y: -3962, name: 'windsweptWastesGroupDescriptor[20120].xpOrbB[57781]'},
    {x: 2025, y: -3729, name: 'windsweptWastesGroupDescriptor[20120].xpOrbG[2013]'},
    {x: 1809, y: -3883, name: 'windsweptWastesGroupDescriptor[20120].expOrbD[48829]'},
    {x: 2006, y: -3724, name: 'desertAGroup[7228].xpOrbB[54275]'},
    {x: 1765, y: -3921, name: 'windsweptWastesGroupDescriptor[20120].xpOrbA[57133]'},
    {x: 1647, y: -3899, name: 'npcsStateGroup[48248].hasMapWindsweptWastes[61146]'},
    {x: 1583, y: -3930, name: 'treesDontWorry[0].Grapple[101]'},
    {x: 2054, y: -4050, name: 'windtornRuinsGroup[10289].energyHalfCell[44555]'},
]
function getPickupMarkers(state)
 {
    let markers = wotwPicks.map(({x, y, name}) => {return {key: name+"|"+x+","+y, position: [y, x], inner: (<Tooltip><div>{name}</div></Tooltip>), icon: pickup_icons["EX"]} })
    markers.push({key: "burrowsTP", position: [-4581.923, -944.7414], inner: (<Tooltip><div>Burrows TP</div></Tooltip>), icon: pickup_icons["TP"]})
    markers.push({key: "ruinsTP", position: [-3678.877, 2043.639], inner: (<Tooltip><div>Ruins TP</div></Tooltip>), icon: pickup_icons["TP"]})
    return markers;
};

const DEFAULT_VIEWPORT = {
	  center: [-4300, -800],
	  zoom: 0,
};
const RETRY_MAX = 60;
const TIMEOUT_START = 5;
const TIMEOUT_INC = 5;


class WotwMap extends React.Component {
  constructor(props) {
    super(props)
    let modes = presets['standard'];
    let url = new URL(window.document.URL);
    this.state = {
        mousePos: {lat: 0, lng: 0}, players: {}, follow: url.searchParams.get("follow") || -1, retries: 0, check_seen: 1, modes: modes, timeout: TIMEOUT_START, searchStr: "", pickup_display: "all", 
        show_sidebar: !url.searchParams.has("hideSidebar"), idle_countdown: 3600, bg_update: true, pickups: ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV", "Ma", "CS"], show_tracker: !url.searchParams.has("hideTracker"),
        open_world: false, closed_dungeons: false, pathMode: get_preset(modes), hideOpt: "all", display_logic: false,  viewport: {...DEFAULT_VIEWPORT}, usermap: url.searchParams.get("usermap") || "",
        tracker_data: {events: [], teleporters: [], shards: {gs: 0, ss: 0, wv: 0}, skills: [], maps: 0,relics_found: [], relics: [], trees: []}, gameId: document.getElementsByClassName("game-id")[0].id
    };
  };

  componentDidMount() {
        setTimeout(() => {
            this.refs.map.leafletElement.invalidateSize(false);
            this.setState({viewport: DEFAULT_VIEWPORT});
        }, 100);
        this.interval = setInterval(() => this.tick(), 1000);
  };

  timeout = () => {
  	return {retries: this.state.retries+1, check_seen: this.state.timeout, timeout: this.state.timeout+TIMEOUT_INC}
  };
  tick = () => {
    let update = {}
    this.setState(update)
  };

  componentWillUnmount() {
    clearInterval(this.interval);
  };

  hideOptChanged = newVal => { this.setState({hideOpt: newVal}) }
  pickupsChanged = newVal => { this.setState({pickups: newVal}) }
  onSearch = event => { this.setState({searchStr: event.target.value}) }
  modesChanged = (paths) => this.setState(prevState => {
		let players = prevState.players
		Object.keys(players).forEach(id => {		
				players[id].areas = []
			});
		return {players: players, modes: paths, pathMode: get_preset(paths)}
		}, () => this.getUpdate(this.timeout))
        
  onMode = (m) => () => this.setState(prevState => {
        if(dev)
            console.log(this.state)

        let modes = prevState.modes;
        if(modes.includes(m)) {
            modes = modes.filter(x => x !== m)
        } else {
            modes.push(m)
        }
		let players = prevState.players
		Object.keys(players).forEach(id => {
				players[id].areas = []
			});
		return {players: players, modes: modes, pathMode: get_preset(modes)}}, () => this.getUpdate(this.timeout))
		
toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};

  onViewportChanged = viewport => { this.setState({ viewport }) }
 _onPathModeChange = (n) => paths.includes(n.value) ? this.modesChanged(presets[n.value]) : this.setState({pathMode: n.value})

  render() {
    try {
    let pickup_markers = (this.state.pickup_display !== "none") ? ( <PickupMarkersList markers={getPickupMarkers(this.state)} />) : null;

    return (
			<div className="wrapper">
	            <Helmet>
	                <style>{'body { background-color: black}'}</style>
					<link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
	            </Helmet>
		      	<Map style={{backgroundColor: "#121212"}} ref="map" crs={crs} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} zoomControl={false} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
		      	     <ZoomControl position="topright" />
                    <ImageOverlay url="/sprites/Niwen.png" bounds={bounds} />

					<Control position="topleft" >
					<div>
						<Button size="sm" onClick={() => this.setState({ viewport: DEFAULT_VIEWPORT })}>Reset View</Button>
						<Button size="sm" color="disabled">{Math.round(this.state.mousePos.lng)},{Math.round(this.state.mousePos.lat)}</Button>
					</div>
					</Control>
					{pickup_markers}
			    </Map>
			</div>
		)
    } catch(error) {
        return (<h1>Error: {error} Try Refreshing?</h1>)
    }
	}
};

function doNetRequest(onRes, setter, url, timeout)
{
    try {
        var xmlHttp = new XMLHttpRequest();
        xmlHttp.onreadystatechange = function() {
            try {
                if (xmlHttp.readyState === 4) {
                    if(xmlHttp.status === 404)
                        setter(timeout())
                    else
                        onRes(xmlHttp.responseText);
                }
            } catch(err) {
                console.log(`netCallback: ${err} status ${xmlHttp.statusText}`)
            }
        }
        xmlHttp.open("GET", url, true); // true for asynchronous
        xmlHttp.send(null);
    } catch(e) {
        console.log(`doNetRequest: ${e}`)
    }
}

export default WotwMap;