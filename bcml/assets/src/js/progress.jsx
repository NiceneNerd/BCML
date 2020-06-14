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
    "Forcing fairies to stay in a cooking pot"
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
        this.state = {
            messageIdx: 0
        };
        setInterval(() => {
            if (this.props.show) {
                this.setState({
                    messageIdx: (messages.length * Math.random()) | 0
                });
            }
        }, 2000);
    }

    componentDidUpdate() {
        shuffle(messages);
    }

    render() {
        return (
            <Modal centered show={this.props.show}>
                <Modal.Header>
                    <Modal.Title>{this.props.title}</Modal.Title>
                </Modal.Header>
                <Modal.Body className="d-flex align-items-start">
                    <Spinner animation="border" role="status" className="flex-shrink-0" />
                    <div className="m-1 ml-3" style={{ minHeight: "1rem" }}>
                        {messages[this.state.messageIdx]}…
                    </div>
                </Modal.Body>
            </Modal>
        );
    }
}

export default ProgressModal;
