import { Button, ButtonGroup, FormControl, InputGroup, Modal } from "react-bootstrap";

import React from "react";

class ProfileModal extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            profiles: [],
            currentProfile: "Default",
            profileName: ""
        };
    }

    componentDidUpdate = prevProps => {
        if (prevProps.show != this.props.show) this.refreshProfiles();
    };

    refreshProfiles = async () => {
        const profiles = await pywebview.api.get_profiles();
        const currentProfile = await pywebview.api.get_current_profile();
        this.setState({
            profiles,
            profileName: "",
            currentProfile
        });
    };

    render = () => {
        return (
            <Modal
                show={this.props.show}
                style={{ opacity: this.props.busy ? "0" : "1.0" }}
                onHide={this.props.onClose}>
                <Modal.Header closeButton>
                    <Modal.Title>Mod Profiles</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div className="h5">
                        <strong>Current Profile:</strong> {this.state.currentProfile}
                    </div>
                    <InputGroup className="mb-3">
                        <FormControl
                            placeholder="Name new profile"
                            value={this.state.profileName}
                            onChange={e =>
                                this.setState({ profileName: e.currentTarget.value })
                            }
                        />
                        <InputGroup.Append>
                            <Button
                                variant="primary"
                                disabled={!this.state.profileName}
                                onClick={() =>
                                    this.props.onSave(this.state.profileName, "save")
                                }>
                                Save
                            </Button>
                        </InputGroup.Append>
                    </InputGroup>
                    <div className="h5">Available Profiles</div>
                    {this.state.profiles.length > 0 ? (
                        this.state.profiles.map(profile => (
                            <div
                                className="d-flex flex-row align-items-center mb-1"
                                key={profile.path}>
                                <span>{profile.name}</span>
                                <div className="flex-grow-1"> </div>
                                <ButtonGroup size="xs">
                                    <Button
                                        variant="success"
                                        title="Load Profile"
                                        onClick={() =>
                                            this.props.onLoad(profile, "load")
                                        }>
                                        <i className="material-icons">refresh</i>
                                    </Button>
                                    <Button
                                        variant="danger"
                                        title="Delete Profile"
                                        onClick={() =>
                                            this.props.onDelete(profile, "delete")
                                        }>
                                        <i className="material-icons">delete</i>
                                    </Button>
                                </ButtonGroup>
                            </div>
                        ))
                    ) : (
                        <p>No profiles yet</p>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <div className="flex-grow-1"></div>
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    };
}

export default ProfileModal;
