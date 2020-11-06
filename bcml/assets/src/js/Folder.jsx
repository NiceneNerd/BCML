import { Button, Form, InputGroup, OverlayTrigger } from "react-bootstrap";

import React from "react";

class FolderInput extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            value: "",
            valid: false
        };
        this.idRef = React.createRef();
        this.folderPick = this.folderPick.bind(this);
        this.handleChange = this.handleChange.bind(this);
    }

    async componentDidMount() {
        const valid = pywebview.api
            .dir_exists({
                folder: this.state.value,
                type: this.idRef.current.id
            })
            .then(valid => this.setState({ valid: valid && this.props.isValid }));
        this.id = this.idRef.current.id;
        this.setState({ value: this.props.value, valid });
    }

    UNSAFE_componentWillReceiveProps(nextProps) {
        if (nextProps.value != this.state.value) {
            this.setState({ value: nextProps.value }, () => {
                pywebview.api
                    .dir_exists({ folder: this.state.value, type: this.id })
                    .then(valid => this.setState({ valid: valid && this.props.isValid }));
            });
        }
    }

    componentDidUpdate(_, prevState) {
        if (prevState.value != this.state.value) {
            this.props.onChange({
                target: { id: this.id, value: this.state.value }
            });
            pywebview.api
                .dir_exists({ folder: this.state.value, type: this.id })
                .then(valid => this.setState({ valid: valid && this.props.isValid }));
        }
    }

    folderPick() {
        pywebview.api.get_folder().then(folder => this.setState({ value: folder }));
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
                        disabled={this.props.disabled}
                        placeholder={this.props.placeholder || "Select a directory"}
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
