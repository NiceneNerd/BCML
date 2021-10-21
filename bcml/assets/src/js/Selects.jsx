import { Alert, Button, Form, Modal, OverlayTrigger, Tooltip } from "react-bootstrap";

import React from "react";

class SelectsDialog extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            folders: [],
            error: null
        };
        this.handleChange = this.handleChange.bind(this);
    }

    componentDidUpdate(prevProps) {
        if (
            this.props.mod &&
            (!prevProps.mod || prevProps.mod.options != this.props.mod.options)
        ) {
            this.setState({
                folders: this.props.mod.options.multi
                    .map(m => (m.default ? m.folder : null))
                    .filter(m => m)
            });
        }
    }

    handleChange(e) {
        e.persist();
        if (!e.currentTarget.checked) {
            this.setState({
                folders: this.state.folders.filter(f => f != e.currentTarget.value)
            });
        } else {
            if (e.currentTarget.type === "radio") {
                const removals = Array.from(
                    document.querySelectorAll(`[name="${e.currentTarget.name}"]`)
                ).map(i => i.value);
                this.setState({
                    folders: [
                        ...this.state.folders.filter(f => !removals.includes(f)),
                        e.currentTarget.value
                    ]
                });
            } else {
                this.setState({
                    folders: [...this.state.folders, e.currentTarget.value]
                });
            }
        }
    }

    submit = () => {
        if (
            this.props.mod.options.single
                .filter(g => g.required)
                .some(
                    g =>
                        document.querySelector(`input[name="${g.name}"]:checked`)
                            ?.value == null
                )
        ) {
            this.setState({
                error: "One or more required options have not been selected."
            });
        } else {
            this.setState({ error: null });
            this.props.onSet(this.state.folders);
        }
    };

    render() {
        return (
            <Modal
                show={this.props.show}
                scrollable={true}
                onHide={this.props.onClose}
                class="selects">
                <Modal.Header closeButton>
                    <Modal.Title>
                        Select Options for {this.props.mod && this.props.mod.name}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {this.state.error && (
                        <Alert variant="danger">{this.state.error}</Alert>
                    )}
                    <p>
                        {this.props.mod && this.props.mod.name} has customization
                        options. Please select the options you would like to use below.
                    </p>
                    <Form>
                        {this.props.mod &&
                            this.props.mod.options.multi &&
                            Object.keys(this.props.mod.options.multi).length > 0 && (
                                <>
                                    <h5>Multiple Choice Options</h5>
                                    {this.props.mod.options.multi.map(m => (
                                        <Form.Group key={m.folder}>
                                            <OverlayTrigger
                                                overlay={
                                                    <Tooltip>
                                                        {m.desc || "No description"}
                                                    </Tooltip>
                                                }>
                                                <Form.Check
                                                    type="checkbox"
                                                    checked={this.state.folders.includes(
                                                        m.folder
                                                    )}
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
                            Object.keys(this.props.mod.options.single).length > 0 && (
                                <>
                                    <h5>Single Choice Options</h5>
                                    {this.props.mod.options.single.map(s => (
                                        <div key={s.name} className="radio-group my-2">
                                            <strong>
                                                {s.name}{" "}
                                                {s.required && (
                                                    <span
                                                        className="text-danger"
                                                        title="Required">
                                                        *
                                                    </span>
                                                )}
                                            </strong>
                                            <small className="my-1 d-block">
                                                {s.desc}
                                            </small>
                                            {s.options.map(opt => (
                                                <Form.Group
                                                    controlId={opt.folder}
                                                    key={opt.folder}>
                                                    <OverlayTrigger
                                                        overlay={
                                                            <Tooltip>
                                                                {opt.desc ||
                                                                    "No description"}
                                                            </Tooltip>
                                                        }>
                                                        <Form.Check
                                                            type="radio"
                                                            name={s.name}
                                                            label={opt.name}
                                                            value={opt.folder}
                                                            onChange={this.handleChange}
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
                    <Button variant="primary" onClick={this.submit}>
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
