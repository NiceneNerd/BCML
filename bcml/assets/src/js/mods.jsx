import { Badge, Button, ButtonGroup, Dropdown, Modal } from "react-bootstrap";

import InstallModal from "./install.jsx";
import ModInfo from "./modinfo.jsx";
import React from "react";
import SortSelect from "./sortselect.jsx";

class Mods extends React.Component {
    constructor() {
        super();
        this.state = {
            selectedMods: [],
            sortReverse: true,
            showHandle: false,
            showInstall: false,
            mods: [],
            dirty: false,
            mergersReady: false,
            mergers: []
        };
        window.addEventListener("pywebviewready", () =>
            pywebview.api
                .get_mergers()
                .then(mergers =>
                    this.setState(
                        { mergersReady: true, mergers },
                        this.sanityCheck
                    )
                )
        );
        this.sanityCheck = this.sanityCheck.bind(this);
        this.handleAction = this.handleAction.bind(this);
        this.handleQueue = this.handleQueue.bind(this);
        this.applyQueue = this.applyQueue.bind(this);
        this.uninstallAll = this.uninstallAll.bind(this);
        this.backupRef = React.createRef();
    }

    sanityCheck() {
        pywebview.api
            .sanity_check()
            .then(res => {
                if (!res.success) throw res;
            })
            .catch(err => {
                console.log(err);
                window.location = "index.html?firstrun=true";
            });
    }

    componentDidMount() {
        this.setState({ mods: this.props.mods });
    }

    static getDerivedStateFromProps(nextProps, prevState) {
        if (JSON.stringify(nextProps.mods) != JSON.stringify(prevState.mods)) {
            return { mods: nextProps.mods };
        } else return null;
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

    handleAction(mod, action) {
        if (action == "explore") {
            pywebview.api.explore({ mod: mod });
        } else {
            let verb = action.replace(/^\w/, c => c.toUpperCase());
            if (verb.endsWith("e")) verb = verb.substring(0, verb.length - 1);
            const task = () =>
                this.props.onState(
                    {
                        showProgress: true,
                        progressTitle: `${verb}ing ${mod.name}`
                    },
                    () => {
                        pywebview.api
                            .mod_action({ mod, action })
                            .then(res => {
                                if (!res.success) {
                                    throw res;
                                }
                                this.setState({ selectedMods: [] }, () => {
                                    this.props.onState(
                                        {
                                            showProgress: false,
                                            showDone: true
                                        },
                                        () => this.props.onRefresh()
                                    );
                                });
                            })
                            .catch(this.props.onError);
                    }
                );
            if (["enable", "update"].includes(action)) task();
            else
                this.props.onConfirm(
                    `Are you sure you want to ${action} ${mod.name}?`,
                    task
                );
        }
    }

    handleRemerge(merger) {
        this.props.onState(
            { showProgress: true, progressTitle: `Remerging ${merger}` },
            () => {
                pywebview.api
                    .remerge({ name: merger })
                    .then(res => {
                        if (!res.success) {
                            throw res;
                        }
                        this.setState(
                            {
                                selectedMods: []
                            },
                            () =>
                                this.props.onState({
                                    showProgress: false,
                                    showDone: true
                                })
                        );
                    })
                    .catch(this.props.onError);
            }
        );
    }

    uninstallAll() {
        this.props.onConfirm(
            "Are you sure you want to uninstall all of your mods?",
            () => {
                this.props.onState(
                    {
                        showProgress: true,
                        progressTitle: "Uninstalling All Mods"
                    },
                    () => {
                        pywebview.api
                            .uninstall_all()
                            .then(res => {
                                if (!res.success) {
                                    throw res;
                                }
                                this.props.onState(
                                    {
                                        showProgress: false,
                                        showDone: true
                                    },
                                    () => {
                                        this.props.onRefresh();
                                        this.setState({ selectedMods: [] });
                                    }
                                );
                            })
                            .catch(this.props.onError);
                    }
                );
            }
        );
    }

    applyQueue() {
        this.props.onState(
            { showProgress: true, progressTitle: "Applying Changes" },
            async () => {
                let installs = [];
                let moves = [];
                for (const [
                    i,
                    mod
                ] of this.state.mods.slice().reverse().entries()) {
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
                        if (!res.success) throw res;

                        this.props.onState(
                            { showProgress: false, showDone: true },
                            () => {
                                this.setState(
                                    {
                                        showHandle: false,
                                        selectedMods: [],
                                        dirty: false
                                    },
                                    () => this.props.onRefresh()
                                );
                            }
                        );
                    })
                    .catch(this.props.onError);
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
                                        this.state.mergers.map(m => (
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
                    onInstall={(mods, options) => {
                        this.setState({ showInstall: false }, () =>
                            this.props.onInstall(mods, options)
                        );
                    }}
                    onQueue={this.handleQueue}
                    onClose={() => this.setState({ showInstall: false })}
                />
            </React.Fragment>
        );
    }
}

export default Mods;
