import React from 'react';
import {Container} from 'reactstrap';

import {get_param} from "./common.js"
import SiteBar from "./SiteBar.js"
import SiteFooter from "./SiteFooter.js"

// Twitch review links here, so every claim must stay true of the extension (ori_bingo_twitch)
export default class TwitchPrivacy extends React.Component {
    state = {user: get_param("user")}

    render = () => {
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <SiteBar user={this.state.user}/>
                <div className="p-4 pt-1">
                <h3>Ori Rando Bingo: privacy and terms</h3>
                <p className="text-muted"><small>Last updated November 25, 2026</small></p>
                <p>Ori Rando Bingo is a Twitch extension that shows a streamer's bingo board from this site. Viewers can click a square to see what it asks for.</p>
                <h5>Privacy</h5>
                <p><strong>We don't collect anything about you.</strong> The extension has no accounts, ads, analytics or cookies, and it stores nothing in your browser. Twitch gives every extension an ID for each viewer, but this one never reads it. The only thing it checks is whether you're the streamer, so that only the streamer sees the setup buttons.</p>
                <p><strong>What your browser sends.</strong> To show the board, your browser fetches it from bf.orirando.com and keeps checking for updates while you watch. Those requests don't say who you are, but like any web request they carry your IP address and browser type. The site's host, Google Cloud, keeps them in its request logs for 30 days. We use those logs only to keep the site running.</p>
                <p><strong>What the board shows</strong> is already public on this site: the squares, each player's progress, and the usernames they play under.</p>
                <p><strong>What the streamer saves</strong> is their username or game, and where the board sits on their stream. Twitch stores these settings and sends them to viewers.</p>
                <p><strong>Twitch</strong> runs the extension, and its own <a target="_blank" rel="noopener noreferrer" href="https://legal.twitch.com/en/legal/privacy-notice/">Privacy Notice</a> covers what Twitch collects.</p>
                <h5>Terms</h5>
                <ul>
                    <li>Ori Rando Bingo is free and provided as is, without warranty of any kind.</li>
                    <li>Using it means following Twitch's <a target="_blank" rel="noopener noreferrer" href="https://legal.twitch.com/legal/terms-of-service">Terms of Service</a>.</li>
                    <li>We may change or retire it at any time. Changes to this page take effect when they're posted.</li>
                </ul>
                <h5>Questions</h5>
                <p>Ask in the community <a href="/discord" target="_blank" rel="noopener noreferrer">Discord</a>.</p>
                </div>
                <SiteFooter/>
            </Container>
        )
    }
};
