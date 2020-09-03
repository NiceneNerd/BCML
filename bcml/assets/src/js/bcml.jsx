import {
    Badge,
    Button,
    Dropdown,
    Fade,
    Modal,
    OverlayTrigger,
    Tab,
    Tabs,
    Tooltip,
    Accordion,
    Card
} from "react-bootstrap";

import DevTools from "./devtools.jsx";
import Settings from "./settings.jsx";
import Mods from "./mods.jsx";
import BackupModal from "./backup.jsx";
import ProgressModal from "./progress.jsx";
import React from "react";
import SelectsDialog from "./selects.jsx";
import AboutDialog from "./about.jsx";

class BcmlRoot extends React.Component {
    constructor() {
        super();
        this.state = {
            mods: [],
            modsLoaded: false,
            selects: null,
            selectMod: null,
            selectPath: null,
            settingsLoaded: false,
            settingsValid: false,
            savingSettings: false,
            showDone: false,
            showBackups: false,
            showError: false,
            error: null,
            showProgress: false,
            progressStatus: "",
            progressTitle: "",
            showConfirm: false,
            confirmText: "",
            confirmCallback: () => {},
            showAbout: false,
            version: "3.0"
        };
        this.selects = null;
        this.backupRef = React.createRef();
        this.handleBackups = this.handleBackups.bind(this);
        this.handleInstall = this.handleInstall.bind(this);
        this.saveSettings = this.saveSettings.bind(this);
        this.showError = this.showError.bind(this);
        this.confirm = this.confirm.bind(this);
        this.refreshMods = this.refreshMods.bind(this);
        this.export = this.export.bind(this);
        this.launchGame = this.launchGame.bind(this);
        this.updateBcml = this.updateBcml.bind(this);
        window.addEventListener("pywebviewready", () => {
            setTimeout(async () => {
                let version = await pywebview.api.get_ver();
                this.setState({ version });
                this.refreshMods();
            }, 125);
        });
    }

    componentDidCatch(error) {
        this.showError(error);
    }

    saveSettings(settings) {
        this.setState(
            {
                settingsValid: true,
                savingSettings: false,
                showProgress: true,
                progressTitle: "Saving Settings"
            },
            () =>
                pywebview.api
                    .save_settings({ settings })
                    .then(() => setTimeout(() => window.location.reload(), 500))
                    .catch(this.showError)
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

    showError(error) {
        try {
            console.error(JSON.stringify(error));
        } catch (error) {
            console.log(JSON.stringify(error));
        }
        this.setState(
            {
                showProgress: false,
                showError: true,
                error
            },
            () => this.refreshMods()
        );
    }

    async handleInstall(mods, options) {
        if (!this.selects) {
            await new Promise(resolve =>
                this.setState(
                    {
                        progressTitle: "One Sec",
                        progressStatus: "Processing",
                        showProgress: true
                    },
                    () => resolve()
                )
            );
            this.selects = await pywebview.api.check_mod_options({ mods });
            await new Promise(resolve =>
                this.setState(
                    {
                        showProgress: true
                    },
                    () => resolve()
                )
            );
        }
        const num_selects = Object.keys(this.selects).length;
        if (
            num_selects > 0 &&
            (!this.state.selects ||
                num_selects > Object.keys(this.state.selects).length)
        ) {
            this.installArgs = { mods, options };
            this.setState({
                selectPath: Object.keys(this.selects)[0],
                selectMod: this.selects[Object.keys(this.selects)[0]]
            });
            return;
        }
        this.setState(
            {
                showProgress: true,
                progressTitle: "Installing Mod" + (mods.length > 1 ? "s" : "")
            },
            () => {
                pywebview.api
                    .install_mod({ mods, options, selects: this.state.selects })
                    .then(res => {
                        if (!res.success) {
                            throw res.error;
                        }
                        this.selects = null;
                        this.setState(
                            {
                                showProgress: false,
                                showDone: true,
                                selects: {}
                            },
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
                                throw res.error;
                            }
                            this.setState(
                                { showProgress: false, showDone: true },
                                () => {
                                    this.backupRef.current.refreshBackups();
                                    if (operation == "restore")
                                        this.refreshMods();
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
                        if (!res.success) throw res.error;

                        this.setState({ showProgress: false, showDone: true });
                    })
                    .catch(this.showError);
            }
        );
    }

    componentDidMount() {
        window.onMsg = msg => {
            this.setState({ progressStatus: msg });
        };
    }

    refreshMods() {
        this.setState({ modsLoaded: false }, () => {
            pywebview.api.get_mods({ disabled: true }).then(mods => {
                this.setState({ mods, modsLoaded: true });
            });
        });
    }

    launchGame() {
        pywebview.api
            .launch_game()
            .then(res => {
                if (!res.success) {
                    throw res.error;
                }
            })
            .catch(this.props.onError);
    }

    updateBcml() {
        this.setState(
            {
                progressTitle: "Upgrading BCML",
                progressStatus: "Please wait while BCML upgrades...",
                showProgress: true
            },
            () => {
                pywebview.api
                    .update_bcml()
                    .then(res => {
                        if (res.error) {
                            throw res.error;
                        }
                        this.setState({
                            showProgress: false,
                            showConfirm: true,
                            confirmText:
                                "BCML has been updated successfully. You must restart the program for changes to take effect. Restart now?",
                            confirmCallback: () => pywebview.api.restart()
                        });
                    })
                    .catch(this.showError);
            }
        );
    }

    render() {
        return (
            <>
                <Dropdown alignRight className="overflow-menu">
                    <Dropdown.Toggle id="dropdown-basic">
                        <i className="material-icons">menu</i>
                    </Dropdown.Toggle>

                    <Dropdown.Menu>
                        <Dropdown.Item
                            onClick={() => pywebview.api.open_help()}>
                            Help
                        </Dropdown.Item>
                        <Dropdown.Item onClick={this.updateBcml}>
                            Update BCML
                        </Dropdown.Item>
                        <Dropdown.Item as="a" href="/index.html?firstrun">
                            Run Setup Wizard
                        </Dropdown.Item>
                        <Dropdown.Item
                            onClick={() => this.setState({ showAbout: true })}>
                            About
                        </Dropdown.Item>
                    </Dropdown.Menu>
                </Dropdown>
                <Tabs id="tabs" mountOnEnter transition={Fade}>
                    <Tab eventKey="mod-list" title="Mods">
                        <Mods
                            mods={this.state.mods}
                            onBackup={() =>
                                this.setState({ showBackups: true })
                            }
                            loaded={this.state.modsLoaded}
                            onRefresh={this.refreshMods}
                            onConfirm={this.confirm}
                            onChange={mods => this.setState({ mods })}
                            onInstall={this.handleInstall}
                            onError={this.showError}
                            onState={this.setState.bind(this)}
                            onExport={this.export}
                            onLaunch={this.launchGame}
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
                                    savingSettings: false,
                                    showError: true,
                                    error: {
                                        short:
                                            "Your settings are not valid and cannot be saved. Check that all required fields are completed and green before submitting.",
                                        error_text:
                                            "Your settings are not valid and cannot be saved. Check that all required fields are completed and green before submitting."
                                    }
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
                    onError={this.showError}
                    onLaunch={this.launchGame}
                />
                <ErrorDialog
                    show={this.state.showError}
                    error={this.state.error}
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
                <AboutDialog
                    show={this.state.showAbout}
                    onClose={() => this.setState({ showAbout: false })}
                    version={this.state.version}
                />
                <SelectsDialog
                    show={this.state.selectMod != null}
                    path={this.state.selectPath}
                    mod={this.state.selectMod}
                    onClose={() => {
                        this.setState({
                            selectMod: null,
                            selectPath: null,
                            selects: {}
                        });
                        this.installArgs = null;
                        this.selects = null;
                    }}
                    onSet={folders => {
                        delete this.selects[this.state.selectPath];
                        this.setState(
                            {
                                selectMod: null,
                                selectPath: null,
                                selects: {
                                    ...this.state.selects,
                                    [this.state.selectPath]: folders
                                }
                            },
                            () => {
                                this.handleInstall(
                                    this.installArgs.mods,
                                    this.installArgs.options
                                );
                                this.installArgs = null;
                            }
                        );
                    }}
                />
            </>
        );
    }
}

class DoneDialog extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            hasCemu: false
        };
        this.launch_game = this.launch_game.bind(this);
    }

    componentDidUpdate(prevProps) {
        if (this.props.show != prevProps.show) {
            try {
                pywebview.api
                    .get_setup()
                    .then(res => this.setState({ ...res }));
            } catch (error) {}
        }
    }

    launch_game() {
        this.props.onLaunch();
        this.props.onClose();
    }

    render() {
        return (
            <Modal
                show={this.props.show}
                size="sm"
                centered
                onHide={this.props.onClose}>
                <Modal.Header closeButton>
                    <Modal.Title>Done!</Modal.Title>
                </Modal.Header>
                <Modal.Footer>
                    <Button variant="primary" onClick={this.props.onClose}>
                        OK
                    </Button>
                    {this.state.hasCemu && (
                        <Button variant="secondary" onClick={this.launch_game}>
                            Launch Game
                        </Button>
                    )}
                </Modal.Footer>
            </Modal>
        );
    }
}

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
                    <div
                        className="pl-2 flex-grow-1"
                        style={{ minWidth: "0px" }}>
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
                                    <i className="material-icons">
                                        expand_more
                                    </i>{" "}
                                    <span>Error Details</span>
                                </Accordion.Toggle>
                                <Accordion.Collapse eventKey="0">
                                    <Card.Body style={{ padding: 0 }}>
                                        <textarea
                                            readOnly={true}
                                            className="error-msg">
                                            {props.error &&
                                                props.error.error_text}
                                        </textarea>
                                    </Card.Body>
                                </Accordion.Collapse>
                            </Card>
                        </Accordion>
                    </div>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <OverlayTrigger
                    overlay={<Tooltip>Copy error to clipboard</Tooltip>}>
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
                <Button
                    className="py-2"
                    variant="primary"
                    onClick={props.onClose}>
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
