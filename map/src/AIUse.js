import React from 'react';
import {Container} from 'reactstrap';
import SiteBar from "./SiteBar.js"
import SiteFooter from "./SiteFooter.js"


export default class AIUse extends React.Component {
  constructor(props) {
    super(props);
    this.state = {};
}
    render = () => {
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <SiteBar user={this.state.user}/>
                <div className="p-4 pt-1">
                <h3>AI/LLM usage disclosure</h3>
                <p>I (Eiko, current lead dev of the Ori BF Randomizer) use AI/LLM coding tools (specifically, Anthropic's Claude Code) in my current work on the project.</p>
                <div>Quick facts:</div>
                <ul>
                    <li>I use Claude Code to write code, help debug issues, draft patchnotes, and monitor traffic data.
                        <ul>
                        <li>I sometimes use text Claude Code generates while working on features, though for user-facing text I typically edit it heavily or replace it outright.</li>
                        <li>I do not use image models to create artwork.</li>
                        </ul>
                    </li>
                    <li>To the best of my knowledge, I'm the only developer working on any of the Ori Rando projects using AI/LLM coding tools. The WotW Randomizer does not use any AI/LLM-generated code.</li>
                    <li>Almost all of my AI/LLM-assisted work is marked on GitHub as co-authored by Claude and specifies the model(s) used.
                    <small><ul><li>(I misconfigured my GitHub setup for this during my first few weeks using these tools, so some early commits are not properly tagged in this way.)</li></ul></small></li>
                    <li>The last version of the Ori BF Randomizer with no AI/LLM-assisted code in it was&nbsp;<a target="_blank" rel="noopener noreferrer" href="/patchnotes#4.1.6">4.1.6</a>. (Relevant GitHub commits:&nbsp;<a target="_blank" rel="noopener noreferrer" href="https://github.com/sparkle-preference/OriDERandomizer/commit/5f35ae1d7f43148dca868a4b43850bec4409c4ad">client</a>,&nbsp;<a target="_blank" rel="noopener noreferrer"href="https://github.com/sparkle-preference/ori_rando_server/commit/7ed937a2ce25fe009160a5eb52f57c56719e26d8">server</a>.)</li>
                </ul>
                <p>I understand that some people are ideologically opposed to AI/LLM usage in full generality. To them, the main thing I have to say is that the Ori Randomizer is and always has been open source - you have (but do not need!) my blessing to fork the client and server and host your own AI-free version. I will give you subdomains at orirando.com for it, if you want them, and if you have questions about how any of the code works I will do my best to answer them.</p>
                <p><em><strong>Why are you doing this?</strong></em> I have, for the last several years, had very little free time or energy to devote to this project, despite having an ever-growing list of features I have wanted to add and bugs I needed to fix. (High on that list - the Ori Rando website has been expensive to host for what it does. It cost me about $70/month during 2025-2026, and about a fifth of that cost was due to some legacy code issues that I have wanted to fix for five years but was previously unable to.) Additionally, my employer has been making it more and more obvious that I need to start using AI/LLM coding tools if I want to keep my job, so in July 2026, after discussing the idea with the community, I decided to try out using Claude Code to pick up work on the project.</p>
                <p><em><strong>Isn't AI code pretty bad?</strong></em> AI/LLM coding tools have dramatically improved since the early vibe-coding days. Opus 5 typically writes slightly better code than I was writing for this project in 2018 and 2019 - Fable 5.1, which I use for more complicated tasks and important verification, writes better code than 90% of my work on any Ori Randomizer project.</p>
                <p>If you have any questions or concerns, please feel free to join the community <a href="/discord" target="_blank" rel="noopener noreferrer">discord</a> and discuss this there.</p>
                </div>
                <SiteFooter hideDisclaim={true}/>
            </Container>
        )
    }
};

