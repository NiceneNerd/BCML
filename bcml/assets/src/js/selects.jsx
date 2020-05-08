import React from "react";
import { Modal, Form, OverlayTrigger, Tooltip, Button } from "react-bootstrap";

class SelectsDialog extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            folders: []
        };
        this.handleChange = this.handleChange.bind(this);
    }

    handleChange(e) {
        e.persist();
        if (!e.currentTarget.checked) {
            this.setState({
                folders: this.state.folders.filter(
                    f => f != e.currentTarget.value
                )
            });
        } else {
            this.setState({
                folders: [...this.state.folders, e.currentTarget.value]
            });
        }
    }

    render() {
        return (
            <Modal show={this.props.show} scrollable={true}>
                <Modal.Header closeButton>
                    <Modal.Title>
                        Select Options for{" "}
                        {this.props.mod && this.props.mod.name}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <p>
                        {this.props.mod && this.props.mod.name} has
                        customization options. Please select the options you
                        would like to use below.
                    </p>
                    <Form>
                        {this.props.mod &&
                            this.props.mod.options.multi &&
                            Object.keys(this.props.mod.options.multi).length >
                                0 && (
                                <>
                                    <h5>Multiple Choice Options</h5>
                                    {this.props.mod.options.multi.map(m => (
                                        <Form.Group key={m.folder}>
                                            <OverlayTrigger
                                                overlay={
                                                    m.desc && (
                                                        <Tooltip>
                                                            {m.desc}
                                                        </Tooltip>
                                                    )
                                                }>
                                                <Form.Check
                                                    type="checkbox"
                                                    label={m.name}
                                                    value={m.folder}
                                                    onChange={this.handleChange}
                                                />
                                            </OverlayTrigger>
                                        </Form.Group>
                                    ))}
                                </>
                            )}
                        {this.props.mod &&
                            this.props.mod.options.single &&
                            Object.keys(this.props.mod.options.single).length >
                                0 && (
                                <>
                                    <h5>Single Choice Options</h5>
                                    {this.props.mod.options.single.map(s => (
                                        <div
                                            key={s.name}
                                            className="radio-group">
                                            <strong>{s.name}</strong>
                                            <br />
                                            {s.desc}
                                            {s.options.map(opt => (
                                                <Form.Group
                                                    controlId={opt.folder}
                                                    key={opt.folder}>
                                                    <OverlayTrigger
                                                        overlay={
                                                            opt.desc && (
                                                                <Tooltip>
                                                                    {opt.desc}
                                                                </Tooltip>
                                                            )
                                                        }>
                                                        <Form.Check
                                                            type="radio"
                                                            name={s.name}
                                                            label={opt.name}
                                                            value={opt.folder}
                                                            onChange={
                                                                this
                                                                    .handleChange
                                                            }
                                                        />
                                                    </OverlayTrigger>
                                                </Form.Group>
                                            ))}
                                        </div>
                                    ))}
                                </>
                            )}
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button
                        variant="primary"
                        onClick={() => this.props.onSet(this.state.folders)}>
                        OK
                    </Button>
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    }
}

export default SelectsDialog;
