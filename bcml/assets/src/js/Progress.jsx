import { Modal, Spinner } from "react-bootstrap";

import React from "react";

let messages = [
    "Finding Koroks",
    "Polishing Master Sword",
    "Dancing with Bokoblins",
    "Stealing bananas from Yigas",
    "Eating raw meat like a chad",
    "Thinking about Zelda's warm embrace",
    "Slaying Lynels by the dozen",
    "Spamming Urbosa's Fury",
    "Running away from Guardians",
    "Detonating remote bombs",
    "Avoiding Beedle",
    "Exacting revenge on Magda",
    "Debating between Hylia and the Golden Goddesses",
    "Oh, look, more opal",
    "Attempting to climb a mountain in the rain",
    "Thinking about Mipha's slimy embrace",
    "Finding yet more Koroks",
    "Disturbing the Monk's Sleep",
    "Slashing Cuccos since 1991",
    "Becoming a Pot Lid Hero",
    "Ragdolling like a Goron",
    "Not running at 60FPS",
    "That mountain over there, I can't reach it",
    '"O Epona, Epona, wherefore art thou Epona?"',
    "The batteries are about to run out again",
    "Oh look, yet another Korok",
    "Cooking only hearty foods",
    "Friend-zoning Paya",
    "Hiding secrets from everybody",
    "Riding a shrine elevator",
    "Bow-spinning mods",
    "Eating a Royal Claymore",
    "Ignoring the old man",
    "Selling the Sheikah Slate",
    "Annoying the monks",
    "Pushing Master Kohga",
    "Deleting the Great Plateau",
    "Moisturizing Ganon",
    "Going back to bed",
    "100 more years never hurt anyone",
    "Changing name and joining a construction company",
    "Trapping fairies in cooking pot",
    "Flushing Hetsu's gift",
    "Bullet time? What's a bullet?",
    "Pretending to remember Zelda",
    "I can't go any farther",
    '"Linkle, you\'re going the wrong way!"',
    "Believe it or not, real progress updates are not an option",
    "BCML tip: When in doubt, remerge",
    "BCML tip: The in-app help has a lot of information",
    "BCML tip: Read the in-app help",
    "BCML tip: Questions or problems? Try the in-app help",
    "BCML tip: To reorder your mods, click the Show Sort Handles toggle",
    "BCML tip: Ctrl-Click to select multiple mods",
    "BCML tip: Higher number priority overrides lower number priority",
    "BCML tip: When using a set of related mods, put the base mod beneath the addons",
    "BCML tip: Back up your mods when making substantial changes",
    'BCML tip: The backup/restore feature can be used for mod "profiles"',
    "Downloading RAM so Link goes fast",
    "Feeding Koroks",
    "Leaving Ganon in peace",
    "Selling apples to Koroks",
    "Becoming a traveling merchant",
    "Stalking Beedle",
    "Creating a paper currency",
    "Planting Korok seeds",
    "Fleeing Daruk's crushing embrace",
    "Turning the Shrine of Resurrection into a tourist attraction",
    "Climbing Death Mountian in the buff",
    "Accidentally stoning a Korok",
    "Dying to Dark Beast Ganon",
    "Building a Master Rocket Zero to the moon",
    "Taking bets on Sand Seal races",
    "Upgrading to the Master Cycle One",
    "Ascending to High Hrothgar—oh wait, wrong game",
    "Collecting monk dust for elixirs",
    "Chasing a Hinox eyeball",
    "Abusing ghost rabbits for money",
    "Making Tik Toks on Sheikah Slate",
    "Old enough to save Hyrule, too young for The Noble Canteen",
    '"Hold on Zelda, only 842 more Koroks!"',
    "Shameless plug: I blog at <a href='https://calebdixonsmith.wordpress.com' target='_blank'>Theology Without Warranty</a>",
    "“What we call Man's power over Nature turns out to be a power exercised by some men over other men with Nature as its instrument.”"
];

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

class ProgressModal extends React.Component {
    constructor(props) {
        super(props);
        this.timer = null;
        this.state = {
            messageIdx: 0
        };
    }

    componentDidUpdate(prevProps) {
        if (!prevProps.show && this.props.show) {
            shuffle(messages);
            this.timer = setInterval(() => {
                if (this.props.show) {
                    this.setState({
                        messageIdx:
                            this.state.messageIdx < messages.length - 1
                                ? this.state.messageIdx + 1
                                : 0
                    });
                }
            }, 3000);
        } else if (prevProps.show && !this.props.show) {
            clearInterval(this.timer);
        }
    }

    render() {
        return (
            <Modal centered show={this.props.show}>
                <Modal.Header>
                    <Modal.Title>{this.props.title}</Modal.Title>
                </Modal.Header>
                <Modal.Body className="d-flex align-items-start">
                    <Spinner
                        animation="border"
                        role="status"
                        className="flex-shrink-0"
                    />
                    <div
                        className="m-1 ml-3"
                        style={{ minHeight: "1rem" }}
                        dangerouslySetInnerHTML={{
                            __html:
                                messages[this.state.messageIdx] +
                                (/[a-zA-Z]/.test(
                                    messages[this.state.messageIdx].slice(-1)
                                )
                                    ? "…"
                                    : "")
                        }}></div>
                </Modal.Body>
            </Modal>
        );
    }
}

export default ProgressModal;
