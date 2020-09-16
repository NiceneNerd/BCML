import React from "react";
import {
    Modal,
    Badge,
    Accordion,
    Card,
    OverlayTrigger,
    Button,
    Tooltip
} from "react-bootstrap";

const ErrorDialog = props => {
    return (
        <Modal
            show={props.show}
            centered
            scrollable={true}
            dialogClassName="modal-wide"
            onHide={props.onClose}>
            <Modal.Header closeButton>
                <Modal.Title>Error</Modal.Title>
            </Modal.Header>
            <Modal.Body className="error">
                <div className="d-flex">
                    <div className="p-1">
                        <Badge variant="danger">
                            <i className="material-icons">error</i>
                        </Badge>
                    </div>
                    <div className="pl-2 flex-grow-1" style={{ minWidth: "0px" }}>
                        <p>
                            Oops!{" "}
                            <span
                                dangerouslySetInnerHTML={{
                                    __html: props.error && props.error.short
                                }}></span>
                        </p>
                        <Accordion>
                            <Card>
                                <Accordion.Toggle
                                    as={Card.Header}
                                    className="row"
                                    eventKey="0">
                                    <i className="material-icons">expand_more</i>{" "}
                                    <span>Error Details</span>
                                </Accordion.Toggle>
                                <Accordion.Collapse eventKey="0">
                                    <Card.Body style={{ padding: 0 }}>
                                        <textarea readOnly={true} className="error-msg">
                                            {props.error && props.error.error_text}
                                        </textarea>
                                    </Card.Body>
                                </Accordion.Collapse>
                            </Card>
                        </Accordion>
                    </div>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <OverlayTrigger overlay={<Tooltip>Open in-app help</Tooltip>}>
                    <Button
                        className="pt-1"
                        size="sm"
                        variant="info"
                        onClick={() => pywebview.api.open_help()}>
                        <i className="material-icons">help</i>
                    </Button>
                </OverlayTrigger>
                <OverlayTrigger overlay={<Tooltip>Copy error to clipboard</Tooltip>}>
                    <Button
                        variant="danger"
                        size="sm"
                        onClick={() => {
                            document.querySelector(".error-msg").select();
                            document.execCommand("copy");
                            window.getSelection().removeAllRanges();
                        }}>
                        <i className="material-icons">file_copy</i>
                    </Button>
                </OverlayTrigger>
                <div className="flex-grow-1"></div>
                <Button className="py-2" variant="primary" onClick={props.onClose}>
                    OK
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ErrorDialog;
