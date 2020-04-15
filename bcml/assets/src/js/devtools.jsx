import React from "react";
import { Col, Row } from "react-bootstrap";

class DevTools extends React.Component {
    constructor() {
        super();
        this.state = {
            someKey: "someValue",
        };
    }

    render() {
        return (
            <Row>
                <Col xs={8}>BNP Creator</Col>
                <Col xs={4}>Other tools</Col>
            </Row>
        );
    }
}

export default DevTools;
