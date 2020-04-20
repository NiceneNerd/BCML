import { Button, Form, InputGroup, OverlayTrigger } from "react-bootstrap";

import React from "react";

class FolderInput extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            value: this.props.value,
            valid: false
        };
        this.idRef = React.createRef();
        this.folderPick = this.folderPick.bind(this);
        this.handleChange = this.handleChange.bind(this);
    }

    componentDidMount() {
        this.setState({ value: this.props.value });
        this.id = this.idRef.current.id;
    }

    componentWillReceiveProps(nextProps) {
        if (nextProps.value != this.state.value) {
            this.setState({ value: nextProps.value });
        }
    }

    componentDidUpdate(_, prevState) {
        if (prevState.value != this.state.value) {
            this.props.onChange({
                target: { id: this.id, value: this.state.value }
            });
            pywebview.api
                .dir_exists({ folder: this.state.value, type: this.id })
                .then(valid => this.setState({ valid }));
        }
    }

    folderPick() {
        pywebview.api
            .get_folder()
            .then(folder => this.setState({ value: folder }));
    }

    handleChange(e) {
        e.persist();
        this.setState({ value: e.target.value });
    }

    render() {
        const overlay = this.props.overlay;
        return (
            <InputGroup>
                <OverlayTrigger
                    overlay={overlay}
                    placement={this.props.placement || "right"}>
                    <Form.Control
                        placeholder="Select a directory"
                        value={this.state.value}
                        onChange={this.handleChange}
                        ref={this.idRef}
                        isValid={this.state.valid}
                    />
                </OverlayTrigger>
                <InputGroup.Append>
                    <Button variant="secondary" onClick={this.folderPick}>
                        Browse...
                    </Button>
                </InputGroup.Append>
            </InputGroup>
        );
    }
}

export default FolderInput;
