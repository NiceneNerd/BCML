import {
    Badge,
    Button,
    Dropdown,
    Fade,
    Modal,
    OverlayTrigger,
    Tab,
    Tabs,
    Tooltip
} from "react-bootstrap";

import DevTools from "./devtools.jsx";
import Settings from "./settings.jsx";
import Mods from "./mods.jsx";
import BackupModal from "./backup.jsx";
import ProgressModal from "./progress.jsx";
import React from "react";

class BcmlRoot extends React.Component {
    constructor() {
        super();
        this.state = {
            mods: [],
            settingsLoaded: false,
            settingsValid: false,
            savingSettings: false,
            showDone: false,
            showBackups: false,
            showError: false,
            errorText: "",
            showProgress: false,
            progressStatus: "",
            progressTitle: "",
            showConfirm: false,
            confirmText: "",
            confirmCallback: () => {}
        };
        this.handleBackups = this.handleBackups.bind(this);
        this.handleInstall = this.handleInstall.bind(this);
        this.saveSettings = this.saveSettings.bind(this);
        this.showError = this.showError.bind(this);
        this.confirm = this.confirm.bind(this);
        this.refreshMods = this.refreshMods.bind(this);
        this.export = this.export.bind(this);
    }

    componentDidCatch(error) {
        this.showError(error);
    }

    saveSettings(settings) {
        this.setState({ settingsValid: true, savingSettings: false }, () =>
            pywebview.api.save_settings({ settings }).then(() =>
                pywebview.api.get_old_mods().then(num => {
                    this.setState({ oldMods: num });
                    if (num > 0) {
                        this.pageCount = 5;
                    }
                })
            )
        );
    }

    confirm(message, callback) {
        this.setState({
            showConfirm: true,
            confirmText: message,
            confirmCallback: yesNo =>
                this.setState({ showConfirm: false }, () =>
                    yesNo ? callback() : null
                )
        });
    }

    showError(errorText) {
        if (typeof errorText !== String) {
            if (errorText.error_text) {
                errorText = errorText.error;
            } else {
                errorText = unescape(
                    errorText.error
                        .toString()
                        .replace(/\\\\/g, "\\")
                        .replace(/\\n/g, "\n")
                        .replace(/\\\"/g, '"')
                        .replace('Error: "', "")
                );
                errorText = `Oops, ran into an error. Details:<pre className="scroller">${unescape(
                    errorText
                )}</pre>`;
            }
        }
        this.setState({
            showProgress: false,
            showError: true,
            errorText
        });
    }

    async handleInstall(mods, options) {
        const selects = await pywebview.api.check_mod_options({ mods });
        this.setState(
            {
                showProgress: true,
                progressTitle: "Installing Mod" + (mods.length > 1 ? "s" : "")
            },
            () => {
                pywebview.api
                    .install_mod({ mods, options, selects })
                    .then(res => {
                        if (!res.success) {
                            throw res;
                        }
                        this.setState(
                            { showProgress: false, showDone: true },
                            () => this.refreshMods()
                        );
                    })
                    .catch(this.showError);
            }
        );
    }

    handleBackups(backup, operation) {
        let progressTitle;
        let action;
        if (operation == "create") {
            progressTitle = "Creating Backup";
            action = pywebview.api.create_backup;
        } else if (operation == "restore") {
            progressTitle = `Restoring ${backup.name}`;
            action = pywebview.api.restore_backup;
            backup = backup.path;
        } else {
            progressTitle = `Deleting ${backup.name}`;
            action = pywebview.api.delete_backup;
            backup = backup.path;
        }
        const task = () =>
            this.setState(
                {
                    showProgress: operation == "delete" ? false : true,
                    showBackups: operation == "delete" ? true : false,
                    progressTitle
                },
                () =>
                    action({ backup })
                        .then(res => {
                            if (!res.success) {
                                throw res;
                            }
                            this.setState(
                                { showProgress: false, showDone: true },
                                () => {
                                    this.backupRef.current.refreshBackups();
                                    if (operation == "restore")
                                        this.props.onRefresh();
                                }
                            );
                        })
                        .catch(this.showError)
            );
        if (operation == "delete")
            this.confirm("Are you sure you want to delete this backup?", task);
        else task();
    }

    export() {
        this.setState(
            {
                showProgress: true,
                progressTitle: "Exporting Mods..."
            },
            () => {
                pywebview.api
                    .export()
                    .then(res => {
                        if (!res.success) throw res;

                        this.setState({ showProgress: false, showDone: true });
                    })
                    .catch(this.showError);
            }
        );
    }

    componentDidMount() {
        this.setState({ mods: this.props.mods });
        window.onMsg = msg => {
            this.setState({ progressStatus: msg });
        };
    }

    refreshMods() {
        pywebview.api.get_mods({ disabled: true }).then(mods => {
            this.setState({ mods });
        });
    }

    render() {
        return (
            <React.Fragment>
                <Dropdown alignRight className="overflow-menu">
                    <Dropdown.Toggle id="dropdown-basic">
                        <i className="material-icons">menu</i>
                    </Dropdown.Toggle>

                    <Dropdown.Menu>
                        <OverlayTrigger
                            overlay={
                                <Tooltip>
                                    Exports all installed mods to a single
                                    modpack, either as a BNP or a plain format.
                                </Tooltip>
                            }
                            placement={"left"}>
                            <Dropdown.Item onClick={this.export}>
                                Export
                            </Dropdown.Item>
                        </OverlayTrigger>
                        <Dropdown.Item>About</Dropdown.Item>
                    </Dropdown.Menu>
                </Dropdown>
                <Tabs id="tabs" mountOnEnter transition={Fade}>
                    <Tab eventKey="mod-list" title="Mods">
                        <Mods
                            mods={this.state.mods}
                            onRefresh={this.refreshMods}
                            onConfirm={this.confirm}
                            onChange={mods => this.setState({ mods })}
                            onInstall={this.handleInstall}
                            onError={this.showError}
                            onState={this.setState.bind(this)}
                        />
                    </Tab>
                    <Tab eventKey="dev-tools" title="Dev Tools">
                        <DevTools
                            onError={this.showError}
                            onState={this.setState.bind(this)}
                        />
                    </Tab>
                    <Tab eventKey="settings" title="Settings" className="p-2">
                        <Settings
                            saving={this.state.savingSettings}
                            onFail={() =>
                                this.setState({
                                    savingSettings: false
                                })
                            }
                            onSubmit={this.saveSettings}
                        />
                        <Button
                            className="fab"
                            onClick={() =>
                                this.setState({ savingSettings: true })
                            }>
                            <i className="material-icons">save</i>
                        </Button>
                    </Tab>
                </Tabs>
                <ProgressModal
                    show={this.state.showProgress}
                    title={this.state.progressTitle}
                    status={this.state.progressStatus}
                />
                <DoneDialog
                    show={this.state.showDone}
                    onClose={() => this.setState({ showDone: false })}
                />
                <ErrorDialog
                    show={this.state.showError}
                    error={this.state.errorText}
                    onClose={() => this.setState({ showError: false })}
                />
                <ConfirmDialog
                    show={this.state.showConfirm}
                    message={this.state.confirmText}
                    onClose={this.state.confirmCallback.bind(this)}
                />
                <BackupModal
                    show={this.state.showBackups}
                    ref={this.backupRef}
                    onCreate={this.handleBackups}
                    onRestore={this.handleBackups}
                    onDelete={this.handleBackups}
                    onClose={() => this.setState({ showBackups: false })}
                />
            </React.Fragment>
        );
    }
}

const DoneDialog = props => {
    return (
        <Modal show={props.show} size="sm" centered>
            <Modal.Header closeButton>
                <Modal.Title>Done!</Modal.Title>
            </Modal.Header>
            <Modal.Footer>
                <Button variant="primary" onClick={props.onClose}>
                    OK
                </Button>
                <Button variant="secondary">Launch Game</Button>
            </Modal.Footer>
        </Modal>
    );
};

const ErrorDialog = props => {
    return (
        <Modal show={props.show} centered>
            <Modal.Header closeButton>
                <Modal.Title>Error</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <div className="d-flex">
                    <div className="p-1">
                        <Badge variant="danger">
                            <i className="material-icons">error</i>
                        </Badge>
                    </div>
                    <div
                        className="pl-2 flex-grow-1"
                        style={{ minWidth: "0px" }}
                        dangerouslySetInnerHTML={{
                            __html: props.error.replace("\n", "<br>")
                        }}></div>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="primary" onClick={props.onClose}>
                    OK
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

const ConfirmDialog = props => {
    return (
        <Modal show={props.show}>
            <Modal.Header>
                <Modal.Title>Please Confirm</Modal.Title>
            </Modal.Header>
            <Modal.Body>{props.message}</Modal.Body>
            <Modal.Footer>
                <Button onClick={() => props.onClose(true)}>OK</Button>
                <Button
                    variant="secondary"
                    onClick={() => props.onClose(false)}>
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default BcmlRoot;
