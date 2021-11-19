import {
    Button,
    Dropdown,
    Fade,
    Modal,
    OverlayTrigger,
    Tab,
    Tabs,
    Tooltip
} from "react-bootstrap";

import AboutDialog from "./About.jsx";
import BackupModal from "./Backup.jsx";
import DevTools from "./DevTools.jsx";
import ErrorDialog from "./Error.jsx";
import GameBanana from "./GameBanana.jsx";
import ModContext from "./Context.jsx";
import Mods from "./Mods.jsx";
import ProfileModal from "./Profile.jsx";
import ProgressModal from "./Progress.jsx";
import React from "react";
import ReactMarkdown from "react-markdown";
import SelectsDialog from "./Selects.jsx";
import Settings from "./Settings.jsx";

const TABS = ["mod-list", "gamebanana", "dev-tools", "settings"];

class App extends React.Component {
    constructor() {
        super();
        this.state = {
            tab: "mod-list",
            mods: [],
            modsLoaded: false,
            selects: null,
            selectMod: null,
            selectPath: null,
            settingsLoaded: false,
            settings: {},
            settingsValid: false,
            savingSettings: false,
            showDone: false,
            showBackups: false,
            showProfiles: false,
            showError: false,
            error: null,
            showProgress: false,
            progressStatus: "",
            progressTitle: "",
            showConfirm: false,
            confirmText: "",
            confirmCallback: () => {},
            showAbout: false,
            update: false,
            changelog: true,
            showChangelog: false,
            version: "3.0"
        };
        this.selects = null;
        this.backupRef = React.createRef();
        this.profileRef = React.createRef();
        window.addEventListener("pywebviewready", () => {
            setTimeout(async () => {
                let settings = await pywebview.api.get_settings();
                this.setState({ settings }, async () => {
                    let res = await pywebview.api.get_ver();
                    this.setState({ ...res });
                });
            }, 500);
            setTimeout(() => {
                this.refreshMods();
            }, 250);
        });
        window.addEventListener("focus", () => {
            document.body.focus();
        });
    }

    componentDidUpdate = () => {
        document.body.focus();
    };

    componentDidCatch = error => {
        this.showError(error);
    };

    componentDidMount = () => {
        window.onMsg = msg => {
            this.setState({ progressStatus: msg });
        };

        document.addEventListener("keyup", e => {
            try {
                e.persist();
            } catch {}
            if (e.key == "F5") {
                window.location.reload();
            }
            if (e.key == "F1") {
                pywebview.api.open_help();
            }
            if (e.ctrlKey) {
                switch (e.key) {
                    case "Tab":
                        let idx = TABS.indexOf(this.state.tab) + 1;
                        if (idx == TABS.length) idx = 0;
                        this.setState({ tab: TABS[idx] });
                        return;
                    default:
                        break;
                }
            } else if (e.altKey) {
                switch (e.key) {
                    case "m":
                        document.querySelector("#dropdown-basic").click();
                        document.querySelector(".dropdown-menu a:first-child").focus();
                        return;
                    default:
                        break;
                }
            }
            return window.handleKeyMods(e);
        });
    };

    saveSettings = settings => {
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
    };

    confirm = (message, callback) => {
        this.setState({
            showConfirm: true,
            confirmText: message,
            confirmCallback: yesNo =>
                this.setState({ showConfirm: false }, () => (yesNo ? callback() : null))
        });
    };

    showError = error => {
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
    };

    handleInstall = async (mods, options) => {
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
        if (num_selects > 0 && num_selects > (this.state.selects?.length || 0)) {
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
                        this.installArgs = null;
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
    };

    handleBackups = (backup, operation) => {
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
                                    if (operation == "restore") this.refreshMods();
                                }
                            );
                        })
                        .catch(this.showError)
            );
        if (operation == "delete")
            this.confirm("Are you sure you want to delete this backup?", task);
        else task();
    };

    handleProfile = async (profile, operation) => {
        let progressTitle;
        let action;
        if (operation == "save") {
            progressTitle = "Saving Profile";
            action = pywebview.api.save_profile;
        } else if (operation == "load") {
            progressTitle = `Loading ${profile.name}`;
            action = pywebview.api.set_profile;
            profile = profile.path;
        } else {
            progressTitle = `Deleting ${profile.name}`;
            action = pywebview.api.delete_profile;
            profile = profile.path;
        }
        const task = () =>
            this.setState(
                {
                    showProgress: operation == "delete" ? false : true,
                    showProfiles: operation == "delete" ? true : false,
                    progressTitle
                },
                () =>
                    action({ profile })
                        .then(res => {
                            console.log(res);
                            if (!res.success) {
                                throw res.error;
                            }
                            this.setState(
                                { showProgress: false, showDone: true },
                                () => {
                                    this.profileRef.current.refreshProfiles();
                                    if (operation == "load") this.refreshMods();
                                }
                            );
                        })
                        .catch(this.showError)
            );
        if (operation == "delete")
            this.confirm("Are you sure you want to delete this profile?", task);
        else task();
    };

    handleOldRestore = () => {
        this.setState(
            {
                showProgress: true,
                showBackups: false,
                progressTitle: "Restoring BCML 2.8 Backup"
            },
            () => {
                pywebview.api
                    .restore_old_backup()
                    .then(res => {
                        if (!res.success) {
                            throw res.error;
                        }

                        this.setState({ showProgress: false, showDone: true }, () =>
                            this.refreshMods()
                        );
                    })
                    .catch(this.showError);
            }
        );
    };

    export = () => {
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
    };

    refreshMods = () => {
        this.setState({ modsLoaded: false }, () => {
            pywebview.api
                .get_mods({ disabled: true })
                .then(res => {
                    if (!res.success) {
                        throw res.error;
                    }
                    this.setState({ mods: res.data, modsLoaded: true });
                })
                .catch(this.showError);
        });
    };

    launchGame = () => {
        pywebview.api
            .launch_game()
            .then(res => {
                if (!res.success) {
                    throw res.error;
                }
            })
            .catch(this.props.onError);
    };

    updateBcml = () => {
        this.confirm(
            "Are you sure you want to update BCML? " +
                "Updating will close the program, run the update, and attempt to lauch it again.",
            () => {
                pywebview.api.update_bcml();
            }
        );
    };

    setProgress = (title, msg) => {
        this.setState({
            progressTitle: title,
            progressStatus: msg || "",
            showProgress: true
        });
    };

    setDone = () => {
        this.setState({ showProgress: false, showDone: true });
    };

    render() {
        return (
            <>
                <div className="overflow-menu d-flex">
                    <Dropdown alignRight>
                        <Dropdown.Toggle
                            id="dropdown-basic"
                            title="Overflow Menu (Alt+M)">
                            <i className="material-icons">menu</i>
                        </Dropdown.Toggle>
                        <Dropdown.Menu>
                            <Dropdown.Item
                                onClick={() => pywebview.api.save_mod_list()}>
                                Save Mod List
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
                    <OverlayTrigger
                        overlay={<Tooltip>Help (F1)</Tooltip>}
                        placement="bottom">
                        <Button
                            size="xs"
                            variant="outline text-light"
                            onClick={() => pywebview.api.open_help()}>
                            <i className="material-icons">help</i>
                        </Button>
                    </OverlayTrigger>
                </div>
                <ModContext.Provider
                    value={{
                        mods: this.state.mods,
                        busy: this.state.showProgress,
                        settings: this.state.settings
                    }}>
                    <Tabs
                        id="tabs"
                        mountOnEnter
                        activeKey={this.state.tab}
                        onSelect={k => this.setState({ tab: k })}
                        transition={Fade}>
                        <Tab eventKey="mod-list" title="Mods">
                            <Mods
                                onBackup={() => this.setState({ showBackups: true })}
                                onProfile={() => this.setState({ showProfiles: true })}
                                loaded={this.state.modsLoaded}
                                onRefresh={this.refreshMods}
                                onConfirm={this.confirm}
                                onChange={mods => this.setState({ mods })}
                                onInstall={this.handleInstall}
                                onError={this.showError}
                                onProgress={this.setProgress}
                                onDone={() =>
                                    this.setState({
                                        showProgress: false,
                                        showDone: true
                                    })
                                }
                                onCancel={() => this.setState({ showProgress: false })}
                                onExport={this.export}
                                onLaunch={this.launchGame}
                            />
                        </Tab>
                        {this.state.settings.show_gb && (
                            <Tab eventKey="gamebanana" title="GameBanana">
                                <GameBanana
                                    onError={this.showError}
                                    onProgress={this.setProgress}
                                    onDone={() =>
                                        this.setState({ showProgress: false })
                                    }
                                />
                            </Tab>
                        )}
                        <Tab eventKey="dev-tools" title="Dev Tools">
                            <DevTools
                                onError={this.showError}
                                onProgress={this.setProgress}
                                onCancel={() => this.setState({ showProgress: false })}
                                onDone={() =>
                                    this.setState({
                                        showProgress: false,
                                        showDone: true
                                    })
                                }
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
                                                "Your settings are not valid and cannot be saved. " +
                                                "Check that all required fields are completed and " +
                                                "green before submitting. If you have trouble, consult " +
                                                "the in-app help.",
                                            error_text:
                                                "Your settings are not valid and cannot be saved. " +
                                                "Check that all required fields are completed and " +
                                                "green before submitting. If you have trouble, consult " +
                                                "the in-app help."
                                        }
                                    })
                                }
                                onSubmit={this.saveSettings}
                                onProgress={this.setProgress}
                                onDone={() => this.setState({ showProgress: false })}
                            />
                            <Button
                                className="fab"
                                onClick={() => this.setState({ savingSettings: true })}>
                                <i className="material-icons">save</i>
                            </Button>
                        </Tab>
                    </Tabs>
                </ModContext.Provider>
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
                <UpdateDialog
                    show={this.state.update}
                    onClose={confirmed =>
                        this.setState({ update: false }, () =>
                            confirmed ? this.updateBcml() : null
                        )
                    }
                />
                <BackupModal
                    show={this.state.showBackups}
                    busy={this.state.showProgress}
                    ref={this.backupRef}
                    onCreate={this.handleBackups}
                    onRestore={this.handleBackups}
                    onOldRestore={this.handleOldRestore}
                    onDelete={this.handleBackups}
                    onClose={() => this.setState({ showBackups: false })}
                />
                <ProfileModal
                    show={this.state.showProfiles}
                    busy={this.state.showProgress}
                    ref={this.profileRef}
                    onLoad={this.handleProfile}
                    onSave={this.handleProfile}
                    onDelete={this.handleProfile}
                    onClose={() => this.setState({ showProfiles: false })}
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
                            selects: {},
                            showProgress: false,
                            showDone: false
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
                            }
                        );
                    }}
                />
                {this.state.changelog && (
                    <Changelog
                        show={this.state.showChangelog}
                        onClose={() => this.setState({ showChangelog: false })}
                        version={this.state.version}
                    />
                )}
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
                pywebview.api.get_setup().then(res => this.setState({ ...res }));
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

const ConfirmDialog = props => {
    return (
        <Modal show={props.show} onHide={props.onClose}>
            <Modal.Header closeButton>
                <Modal.Title>Please Confirm</Modal.Title>
            </Modal.Header>
            <Modal.Body>{props.message}</Modal.Body>
            <Modal.Footer>
                <Button onClick={() => props.onClose(true)}>OK</Button>
                <Button variant="secondary" onClick={() => props.onClose(false)}>
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

const UpdateDialog = props => {
    return (
        <Modal show={props.show}>
            <Modal.Header>
                <Modal.Title>Update Available</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                There is a new update available for BCML. Would you like to install it?
            </Modal.Body>
            <Modal.Footer>
                <Button onClick={() => props.onClose(true)}>OK</Button>
                <Button variant="secondary" onClick={() => props.onClose(false)}>
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

class Changelog extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            info: {}
        };
    }

    componentDidUpdate = async prevProps => {
        if (this.props.version != prevProps.version) {
            try {
                const releases = await (
                    await fetch(
                        "https://api.github.com/repos/NiceneNerd/BCML/releases?per_page=5"
                    )
                ).json();
                console.log(releases);
                const latest = releases.find(
                    r => r.tag_name.substring(1, 7) == this.props.version.trim()
                );
                this.setState({
                    info: latest
                });
            } catch (e) {}
        }
    };

    render = () => {
        return this.state.info?.body ? (
            <Modal show={this.props.show}>
                <Modal.Header closeButton>
                    <Modal.Title>BCML Updated</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <p>
                        BCML has been updated to {this.state.info?.tag_name}. Changelog:
                    </p>
                    <ReactMarkdown>{this.state.info?.body}</ReactMarkdown>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={() => this.props.onClose()}>OK</Button>
                </Modal.Footer>
            </Modal>
        ) : (
            <></>
        );
    };
}

export default App;
