import React from 'react';
import {Nav, NavItem, NavLink} from 'reactstrap';
import {FaGithub, FaDiscord, FaEnvelope} from 'react-icons/fa';

const CONTACT = "eiko.the.blue+orisite@gmail.com"

const LINKS = [
    [FaGithub, "Website", "https://github.com/sparkle-preference/ori_rando_server"],
    [FaGithub, "Rando dll", "https://github.com/sparkle-preference/OriDERandomizer"],
    [FaDiscord, "Discord", "/discord"],
    [FaEnvelope, "Contact", `mailto:${CONTACT}`],
]

// the width matches SiteBar's, so the two boxes line up on every page
const SiteFooter = () => (
    <footer style={{maxWidth: '1074px'}} className="site-footer border border-dark p-2 mt-4">
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
    </footer>
)
export default SiteFooter;
