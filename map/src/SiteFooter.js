import React from 'react';
import {Nav, NavItem, NavLink} from 'reactstrap';
import {FaGithub, FaDiscord, FaEnvelope} from 'react-icons/fa';

const CONTACT = "eiko.the.blue+orisite@gmail.com"

// the repos behind /dll, /app and /tracker; the redirects point at their releases
const LINKS = [
    [FaGithub, "Client", "https://github.com/sparkle-preference/OriDERandomizer"],
    [FaGithub, "Server", "https://github.com/sparkle-preference/ori_rando_server"],
    [FaGithub, "App", "https://github.com/ori-community/bf-rando-installer"],
    [FaGithub, "Tracker", "https://github.com/jeflefou/OriDETracker"],
    [FaDiscord, "Discord", "/discord"],
    [FaEnvelope, "Contact", `mailto:${CONTACT}`],
]

// the width matches SiteBar's, so the two boxes line up on every page
const SiteFooter = (props) => {
    const disclaimer = (props.hasOwnProperty("hideDisclaim") && props["hideDisclaim"]) ? null : (<div className="justify-content-center text-center align-items-center d-flex w-100 h-100"><small>As of 2026, LLM coding tools are being used to develop and maintain the Ori BF Randomizer.&nbsp;&nbsp;<a href="/aiuse">Learn more here</a>.</small></div>);
    return (
        <footer style={{maxWidth: '1074px'}} className="site-footer border border-dark p-2 mt-4 mx-auto">
            <Nav className="justify-content-center flex-wrap">
                {LINKS.map(([Icon, label, href]) => {
                    // a mailto hands off to a mail client, so it must not open a tab
                    let external = !href.startsWith("mailto:")
                    return (
                        <NavItem key={label}>
                            <NavLink className="px-3" href={href}
                                     target={external ? "_blank" : undefined}
                                     rel={external ? "noopener noreferrer" : undefined}>
                                <Icon className="mr-2"/>{label}
                            </NavLink>
                        </NavItem>
                    )
                })}
            </Nav>
            {disclaimer}
        </footer>
    );
};
export default SiteFooter;
