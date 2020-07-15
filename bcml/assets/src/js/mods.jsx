import {
    Button,
    ButtonGroup,
    Dropdown,
    OverlayTrigger,
    Tooltip,
    Spinner
} from "react-bootstrap";

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
            mergers: [],
            hasCemu: false
        };
        window.addEventListener("pywebviewready", () =>
            pywebview.api
                .get_setup()
                .then(setup =>
                    this.setState(
                        { mergersReady: true, ...setup },
                        this.sanityCheck
                    )
                )
        );
        this.sanityCheck = this.sanityCheck.bind(this);
        this.handleAction = this.handleAction.bind(this);
        this.handleQueue = this.handleQueue.bind(this);
        this.applyQueue = this.applyQueue.bind(this);
        this.uninstallAll = this.uninstallAll.bind(this);
        this.defaultSelect = this.defaultSelect.bind(this);
    }

    defaultSelect() {
        if (this.state.mods.length > 0) {
            return [this.state.mods[0]];
        } else {
            return [];
        }
    }

    sanityCheck() {
        pywebview.api
            .sanity_check()
            .then(res => {
                if (!res.success) throw res.error;
            })
            .catch(err => {
                console.error(err);
                this.props.onError(err);
                setTimeout(
                    () => (window.location = "index.html?firstrun=true"),
                    1500
                );
            });
    }

    componentDidMount() {
        this.setState({ mods: this.props.mods });
    }

    static getDerivedStateFromProps(nextProps, prevState) {
        if (JSON.stringify(nextProps.mods) != JSON.stringify(prevState.mods)) {
            return { mods: nextProps.mods, selectedMods: [nextProps.mods[0]] };
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
                                    throw res.error;
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
                            throw res.error;
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
                                    throw res.error;
                                }
                                this.props.onState(
                                    {
                                        showProgress: false,
                                        showDone: true
                                    },
                                    () => {
                                        this.props.onRefresh();
                                        this.setState({
                                            selectedMods: []
                                        });
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
                        if (!res.success) throw res.error;

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
            <>
                <div className="row">
                    <div className="col-4" id="mods">
                        {this.props.loaded ? (
                            this.state.mods.length > 0 ? (
                                <SortSelect
                                    mods={
                                        this.state.sortReverse
                                            ? [...this.state.mods].reverse()
                                            : this.state.mods
                                    }
                                    showHandle={this.state.showHandle}
                                    onSelect={selected =>
                                        this.setState({
                                            selectedMods: selected
                                        })
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
                            ) : (
                                <div className="text-secondary m-2 text-center">
                                    No mods installed
                                </div>
                            )
                        ) : (
                            <div className="text-center mt-3">
                                <Spinner animation="border" variant="light" />
                            </div>
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
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>
                                            {"Sort priority:\n" +
                                                (this.state.sortReverse
                                                    ? "highest to lowest"
                                                    : "lowest to highest")}
                                        </Tooltip>
                                    }>
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            this.setState({
                                                sortReverse: !this.state
                                                    .sortReverse
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
                                </OverlayTrigger>
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>
                                            {this.state.showHandle
                                                ? "Hide sort handles"
                                                : "Show sort handles"}
                                        </Tooltip>
                                    }>
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            this.setState({
                                                showHandle: !this.state
                                                    .showHandle
                                            })
                                        }>
                                        <i className="material-icons">
                                            reorder
                                        </i>
                                    </Button>
                                </OverlayTrigger>
                            </ButtonGroup>
                            <Dropdown as={ButtonGroup} size="xs">
                                <OverlayTrigger
                                    overlay={<Tooltip>Remerge</Tooltip>}>
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            this.handleRemerge("all")
                                        }>
                                        <i className="material-icons">
                                            refresh
                                        </i>
                                    </Button>
                                </OverlayTrigger>
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
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>Backup and restore</Tooltip>
                                    }>
                                    <Button
                                        variant="secondary"
                                        onClick={this.props.onBackup}>
                                        <i className="material-icons">
                                            restore
                                        </i>
                                    </Button>
                                </OverlayTrigger>
                                <OverlayTrigger
                                    overlay={<Tooltip>Export</Tooltip>}>
                                    <Button
                                        variant="secondary"
                                        onClick={this.props.onExport}
                                        className="pr-1">
                                        <i className="material-icons">
                                            open_in_browser
                                        </i>
                                    </Button>
                                </OverlayTrigger>
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>Uninstall all mods</Tooltip>
                                    }>
                                    <Button
                                        variant="danger"
                                        onClick={this.uninstallAll}>
                                        <i className="material-icons">
                                            delete_sweep
                                        </i>
                                    </Button>
                                </OverlayTrigger>
                            </ButtonGroup>
                            <div className="flex-grow-1"></div>
                            {this.state.hasCemu && (
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>
                                            Launch Breath of the Wild
                                        </Tooltip>
                                    }>
                                    <Button
                                        variant="primary"
                                        size="xs"
                                        onClick={this.props.onLaunch}>
                                        <svg
                                            xmlns="http://www.w3.org/2000/svg"
                                            x="0px"
                                            y="0px"
                                            width="24"
                                            height="24"
                                            viewBox="0 0 171 171"
                                            style={{ fill: "#000000" }}>
                                            <g
                                                fill="none"
                                                fillRule="nonzero"
                                                stroke="none"
                                                strokeWidth="1"
                                                strokeLinecap="butt"
                                                strokeLinejoin="miter"
                                                strokeMiterlimit="10"
                                                strokeDasharray=""
                                                strokeDashoffset="0"
                                                fontFamily="none"
                                                fontWeight="none"
                                                fontSize="none"
                                                textAnchor="none"
                                                style={{
                                                    mixBlendMode: "normal"
                                                }}>
                                                <path
                                                    d="M0,171.98863v-171.98863h171.98863v171.98863z"
                                                    fill="none"></path>
                                                <g fill="#ffb300">
                                                    <path d="M85.5,19.14844l-35.625,61.67578h71.25zM121.125,80.82422l-35.625,61.67578h71.25zM85.5,142.5l-35.625,-61.67578l-35.625,61.67578z"></path>
                                                </g>
                                            </g>
                                        </svg>
                                    </Button>
                                </OverlayTrigger>
                            )}
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
                    onOneClick={() => this.setState({ showInstall: true })}
                    onClose={() => this.setState({ showInstall: false })}
                />
            </>
        );
    }
}

export default Mods;
