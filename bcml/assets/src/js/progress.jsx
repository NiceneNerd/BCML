import { Modal, Spinner } from "react-bootstrap";

import React from "react";

class ProgressModal extends React.Component {
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
                            __html: this.props.status
                        }}></div>
                </Modal.Body>
            </Modal>
        );
    }
}

export default ProgressModal;
