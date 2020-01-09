import { Badge, Button, ButtonGroup, Dropdown, Modal } from "react-bootstrap";

import BackupModal from "./backup.jsx";
import InstallModal from "./install.jsx";
import ModInfo from "./modinfo.jsx";
import ProgressModal from "./progress.jsx";
import React from "react";
import SortSelect from "./sortselect.jsx";

class Mods extends React.Component {
    constructor() {
        super();
        this.state = {
            selectedMods: [],
            showDone: false,
            showBackups: false,
            showError: false,
            errorText: "",
            showInstall: false,
            showProgress: false,
            progressStatus: "",
            progressTitle: "",
            showConfirm: false,
            confirmText: "",
            confirmCallback: () => {},
            sortReverse: true,
            showHandle: false,
            mods: [],
            dirty: false,
            mergersReady: false
        };
        window.loadMergers = () =>
            this.setState({ mergersReady: true }, this.sanityCheck);
        this.sanityCheck = this.sanityCheck.bind(this);
        this.showError = this.showError.bind(this);
        this.handleAction = this.handleAction.bind(this);
        this.handleBackups = this.handleBackups.bind(this);
        this.handleInstall = this.handleInstall.bind(this);
        this.handleQueue = this.handleQueue.bind(this);
        this.applyQueue = this.applyQueue.bind(this);
        this.uninstallAll = this.uninstallAll.bind(this);
        this.backupRef = React.createRef();
    }

    sanityCheck() {
        pywebview.api
            .sanity_check()
            .then(res => {
                if (!res.success) throw res.error;
            })
            .catch(err => {
                this.showError(err);
                window.location = "index.html?firstrun=true";
            });
    }

    componentDidMount() {
        this.setState({ mods: this.props.mods });
        window.onMsg = msg => {
            this.setState({ progressStatus: msg });
        };
    }

    static getDerivedStateFromProps(nextProps, prevState) {
        if (JSON.stringify(nextProps.mods) != JSON.stringify(prevState.mods)) {
            return { mods: nextProps.mods };
        } else return null;
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

    handleQueue(mods, options) {
        this.setState(prevState => {
            let newMods = prevState.mods;
            let priority = newMods.length + 99;
            for (const [i, mod] of mods.entries()) {
                newMods.push({
                    name: mod.split("\\").slice(-1)[0],
                    priority: priority + i,
                    path: "QUEUE" + mod,
                    options
                });
            }
            return { mods: newMods, showInstall: false, dirty: true };
        });
    }

    showError(errorText) {
        if (typeof errorText !== String) {
            errorText = unescape(
                errorText
                    .toString()
                    .replace(/\\\\/g, "\\")
                    .replace(/\\n/g, "\n")
                    .replace(/\\\"/g, '"')
                    .replace('Error: "', "")
            );
            errorText = `Oops, ran into an error. Details:<pre class="scroller">${unescape(
                errorText
            )}</pre>`;
        }
        this.setState({
            showProgress: false,
            showError: true,
            errorText
        });
    }

    handleInstall(mods, options) {
        this.setState(
            {
                showInstall: false,
                showProgress: true,
                progressTitle: "Installing Mod" + (mods.length > 1 ? "s" : "")
            },
            () => {
                pywebview.api
                    .install({ mods, options })
                    .then(res => {
                        if (!res.success) {
                            throw res.error;
                        }
                        this.setState(
                            { showProgress: false, showDone: true },
                            () => this.props.onRefresh()
                        );
                    })
                    .catch(this.showError);
            }
        );
    }

    handleAction(mod, action) {
        if (action == "explore") {
            pywebview.api.explore({ mod: mod });
        } else {
            let verb = action.replace(/^\w/, c => c.toUpperCase());
            if (verb.endsWith("e")) verb = verb.substring(0, verb.length - 1);
            const task = () =>
                this.setState(
                    {
                        showProgress: true,
                        progressTitle: `${verb}ing ${mod.name}`
                    },
                    () => {
                        pywebview.api
                            .mod_action({ mod, action })
                            .then(res => {
                                if (!res.success) {
                                    throw res.error;
                                }
                                this.setState(
                                    {
                                        showProgress: false,
                                        showDone: true,
                                        selectedMods: []
                                    },
                                    () => this.props.onRefresh()
                                );
                            })
                            .catch(this.showError);
                    }
                );
            if (action == "enable") task();
            else
                this.confirm(
                    `Are you sure you want to ${action} ${mod.name}?`,
                    task
                );
        }
    }

    handleRemerge(merger) {
        this.setState(
            { showProgress: true, progressTitle: `Remerging ${merger}` },
            () => {
                pywebview.api
                    .remerge({ name: merger })
                    .then(res => {
                        if (!res.success) {
                            throw res.error;
                        }
                        this.setState({
                            showProgress: false,
                            showDone: true,
                            selectedMods: []
                        });
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

    uninstallAll() {
        this.confirm(
            "Are you sure you want to uninstall all of your mods?",
            () => {
                this.setState(
                    {
                        showProgress: true,
                        progressTitle: "Uninstalling All Mods"
                    },
                    () => {
                        pywebview.api
                            .uninstall_all()
                            .then(res => {
                                if (!res.success) {
                                    throw res.error;
                                }
                                this.setState(
                                    {
                                        showProgress: false,
                                        showDone: true,
                                        selectedMods: []
                                    },
                                    () => this.props.onRefresh()
                                );
                            })
                            .catch(this.showError);
                    }
                );
            }
        );
    }

    applyQueue() {
        this.setState(
            { showProgress: true, progressTitle: "Applying Changes" },
            async () => {
                let installs = [];
                let moves = [];
                for (const [i, mod] of this.state.mods
                    .slice()
                    .reverse()
                    .entries()) {
                    if (mod.path.startsWith("QUEUE")) installs.push(mod);
                    else {
                        const newPriority = !this.state.sortReverse
                            ? i + 100
                            : this.state.mods.length - i - 1 + 100;
                        if (mod.priority != newPriority)
                            moves.push({ mod, priority: newPriority });
                    }
                }
                pywebview.api
                    .apply_queue({ installs, moves })
                    .then(res => {
                        if (!res.success) throw res.error;

                        this.setState(
                            {
                                showProgress: false,
                                showDone: true,
                                showHandle: false,
                                selectedMods: [],
                                dirty: false
                            },
                            () => this.props.onRefresh()
                        );
                    })
                    .catch(this.showError);
            }
        );
    }

    render() {
        return (
            <React.Fragment>
                <div className="row">
                    <div className="col-4" id="mods">
                        {this.state.mods.length > 0 && (
                            <SortSelect
                                mods={
                                    this.state.sortReverse
                                        ? [...this.state.mods].reverse()
                                        : this.state.mods
                                }
                                showHandle={this.state.showHandle}
                                onSelect={selected =>
                                    this.setState({ selectedMods: selected })
                                }
                                onChange={mods =>
                                    this.setState({ dirty: true }, () =>
                                        this.props.onChange(
                                            !this.state.sortReverse
                                                ? mods
                                                : mods.reverse()
                                        )
                                    )
                                }
                            />
                        )}
                        <div className="flex-grow-1"> </div>
                        {this.state.dirty && (
                            <Button
                                size="xs"
                                variant="success"
                                className="btn-apply position-fixed"
                                title="Apply pending load order changes and queued installs"
                                onClick={this.applyQueue}>
                                <i className="material-icons">check</i>
                                <span>Apply Pending Changes</span>
                            </Button>
                        )}
                        <div className="list-actions d-flex pt-1">
                            <ButtonGroup size="xs">
                                <Button
                                    variant="secondary"
                                    title={
                                        "Sort priority: " +
                                        (this.state.sortReverse
                                            ? "highest to lowest"
                                            : "lowest to highest")
                                    }
                                    onClick={() =>
                                        this.setState({
                                            sortReverse: !this.state.sortReverse
                                        })
                                    }>
                                    <i
                                        className={
                                            "material-icons" +
                                            (!this.state.sortReverse
                                                ? " reversed"
                                                : "")
                                        }>
                                        sort
                                    </i>
                                </Button>
                                <Button
                                    variant="secondary"
                                    onClick={() =>
                                        this.setState({
                                            showHandle: !this.state.showHandle
                                        })
                                    }
                                    title={
                                        this.state.showHandle
                                            ? "Hide sort handles"
                                            : "Show sort handles"
                                    }>
                                    <i className="material-icons">reorder</i>
                                </Button>
                            </ButtonGroup>
                            <Dropdown as={ButtonGroup} size="xs">
                                <Button
                                    variant="secondary"
                                    title="Remerge"
                                    onClick={() => this.handleRemerge("all")}>
                                    <i className="material-icons">refresh</i>
                                </Button>

                                <Dropdown.Toggle
                                    split
                                    variant="secondary"
                                    id="dropdown-split-basic"
                                />

                                <Dropdown.Menu>
                                    {this.state.mergersReady &&
                                        window.mergers.map(m => (
                                            <Dropdown.Item
                                                key={m}
                                                onClick={() =>
                                                    this.handleRemerge(m)
                                                }>
                                                Remerge {m}
                                            </Dropdown.Item>
                                        ))}
                                </Dropdown.Menu>
                            </Dropdown>
                            <ButtonGroup size="xs">
                                <Button
                                    variant="secondary"
                                    title="Backup and restore mods"
                                    onClick={() =>
                                        this.setState({ showBackups: true })
                                    }
                                    style={{ paddingRight: "0.5rem" }}>
                                    <i className="material-icons">restore</i>
                                </Button>
                                <Button
                                    variant="danger"
                                    title="Uninstall all mods"
                                    onClick={this.uninstallAll}>
                                    <i className="material-icons">
                                        delete_sweep
                                    </i>
                                </Button>
                            </ButtonGroup>
                            <div className="flex-grow-1"></div>
                        </div>
                    </div>
                    <div className="col-8 scroller" id="mod-info">
                        <ModInfo
                            mod={this.state.selectedMods[0]}
                            onAction={this.handleAction}
                        />
                    </div>
                </div>
                <a
                    className="fab"
                    title="Install"
                    onClick={() => this.setState({ showInstall: true })}>
                    <i className="material-icons">add</i>
                </a>
                <InstallModal
                    show={this.state.showInstall}
                    onInstall={this.handleInstall}
                    onQueue={this.handleQueue}
                    onClose={() => this.setState({ showInstall: false })}
                />
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
                <div class="d-flex">
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

export default Mods;
