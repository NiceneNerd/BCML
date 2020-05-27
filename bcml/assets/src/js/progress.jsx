import { Modal, Spinner } from "react-bootstrap";

import React from "react";

const MESSAGES = [
    "Finding Koroks",
    "Polishing Master Sword",
    "Dancing with Bokoblins",
    "Stealing bananas from Yigas",
    "Eating raw meat like a chad",
    "Thinking about Zelda's warm embrace",
    "Slaying dozens of Lynels",
    "Spamming Urbosa's Fury",
    "Running away from Guardians",
    "Detonating remote bombs",
    "Avoiding Beedle",
    "Enacting revenge on Magda",
    "Debating between Hylia and the Golden Goddesses",
    "Oh, look, more opal",
    "Attempting to climb a mountain in the rain",
    "Thinking about Mipha's slimy embrace",
    "Finding yet more Koroks"
];

class ProgressModal extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            messageIdx: 0
        };
        setInterval(() => {
            if (this.props.show) {
                this.setState({ messageIdx: (MESSAGES.length * Math.random()) | 0 });
            }
        }, 2000);
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
                        {MESSAGES[this.state.messageIdx]}…
                    </div>
                </Modal.Body>
            </Modal>
        );
    }
}

export default ProgressModal;
