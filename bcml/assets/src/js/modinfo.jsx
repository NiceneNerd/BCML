import { Badge, Button, Spinner } from "react-bootstrap";

import React from "react";

class ModInfo extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            image: "",
            desc: "",
            url: "",
            changes: [],
            loading: false
        };
        this.modInfos = {};
    }

    componentDidMount() {
        this.updateInfo();
    }

    componentDidUpdate(prevProps) {
        if (prevProps != this.props) {
            this.setState({ loading: true }, () => {
                this.updateInfo();
            });
        } else if (!this.props.mod && this.state.loading) {
            this.setState({ loading: false });
        }
    }

    updateInfo() {
        if (!this.props.mod) {
            this.setState({ image: "", description: "", changes: [], url: "" });
        } else {
            const mod = JSON.stringify(this.props.mod);
            if (!(mod in this.modInfos)) {
                pywebview.api
                    .get_mod_info({ mod: this.props.mod })
                    .then(info => {
                        this.modInfos[mod] = info;
                        this.setState({ ...info, loading: false });
                    });
            } else {
                this.setState({ ...this.modInfos[mod], loading: false });
            }
        }
    }

    render() {
        return (
            <>
                <div className="mod-header">
                    <img
                        src={
                            this.state.image
                                ? "data:image/*;charset=utf-8;base64," +
                                  this.state.image
                                : "logo-smaller.png"
                        }
                        className="mod-preview"
                    />
                    <div className="mod-preview-shadow"></div>
                    <div className="mod-title">
                        <h1>
                            {this.props.mod ? (
                                this.state.url ? (
                                    <a href={this.state.url} target="_blank">
                                        {this.props.mod.name}
                                    </a>
                                ) : (
                                    this.props.mod.name
                                )
                            ) : (
                                "Welcome to BCML"
                            )}
                        </h1>
                        {this.props.mod && this.props.mod.disabled && (
                            <Badge variant="danger">DISABLED</Badge>
                        )}
                    </div>
                </div>
                <div className="mod-descrip">
                    {this.props.mod
                        ? this.state.desc || "No description"
                        : "No mod selected"}
                </div>
                <div className="mod-actions">
                    <Button
                        variant="primary"
                        size="sm"
                        title="Explore"
                        disabled={!this.props.mod}
                        onClick={() =>
                            this.props.onAction(this.props.mod, "explore")
                        }>
                        <i className="material-icons">folder_open</i>{" "}
                        <span>Explore</span>
                    </Button>
                    {this.props.mod &&
                        (this.props.mod.disabled ? (
                            <Button
                                variant="success"
                                size="sm"
                                title="Enable"
                                disabled={!this.props.mod}
                                onClick={() =>
                                    this.props.onAction(
                                        this.props.mod,
                                        "enable"
                                    )
                                }>
                                <i className="material-icons">check_box</i>{" "}
                                <span>Enable</span>
                            </Button>
                        ) : (
                            <Button
                                variant="warning"
                                size="sm"
                                title="Disable"
                                disabled={!this.props.mod}
                                onClick={() =>
                                    this.props.onAction(
                                        this.props.mod,
                                        "disable"
                                    )
                                }>
                                <i className="material-icons">block</i>{" "}
                                <span>Disable</span>
                            </Button>
                        ))}
                    <Button
                        variant="info"
                        size="sm"
                        title="Update"
                        disabled={!this.props.mod}
                        onClick={() =>
                            this.props.onAction(this.props.mod, "update")
                        }>
                        <i className="material-icons">update</i>{" "}
                        <span>Update</span>
                    </Button>
                    <Button
                        variant="danger"
                        size="sm"
                        title="Uninstall"
                        disabled={!this.props.mod}
                        onClick={() =>
                            this.props.onAction(this.props.mod, "uninstall")
                        }>
                        <i className="material-icons">delete</i>{" "}
                        <span>Uninstall</span>
                    </Button>
                </div>
                <div className="mod-details">
                    {this.props.mod ? (
                        <>
                            <span>
                                <strong>Priority:</strong>{" "}
                                {this.props.mod.priority}
                            </span>
                            <span>
                                <strong>Changes:</strong>{" "}
                                {this.state.changes.join(", ")}
                            </span>
                            <span
                                style={{
                                    whiteSpace: "nowrap",
                                    maxWidth: "100%",
                                    overflow: "hidden"
                                }}>
                                <strong>Path:</strong> {this.props.mod.path}
                            </span>
                            {this.state.url && (
                                <span>
                                    <strong>URL:</strong>{" "}
                                    <a href={this.state.url} target="_blank">
                                        {this.state.url}
                                    </a>
                                </span>
                            )}
                        </>
                    ) : (
                        "No mod selected"
                    )}
                </div>
                {this.state.loading && (
                    <div className="load-backdrop">
                        <div className="loading">
                            <Spinner animation="border" variant="primary" />
                        </div>
                    </div>
                )}
            </>
        );
    }
}

export default ModInfo;
