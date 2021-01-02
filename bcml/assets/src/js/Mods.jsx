import {
    Button,
    ButtonGroup,
    ButtonToolbar,
    Dropdown,
    OverlayTrigger,
    Spinner,
    Tooltip
} from "react-bootstrap";

import InstallModal from "./Install.jsx";
import ModContext from "./Context.jsx";
import ModInfo from "./ModInfo.jsx";
import React from "react";
import SortSelect from "./SortSelect.jsx";

class Mods extends React.Component {
    static contextType = ModContext;

    constructor() {
        super();
        this.state = {
            selectedMods: [],
            sortReverse: true,
            showHandle: false,
            showInstall: false,
            showDisabled: true,
            dirty: false,
            mergersReady: false,
            mergers: [],
            hasCemu: false
        };
        window.addEventListener("pywebviewready", () =>
            pywebview.api
                .get_setup()
                .then(setup =>
                    this.setState({ mergersReady: true, ...setup }, this.sanityCheck)
                )
        );
    }

    defaultSelect = () => {
        if (this.context.mods.length > 0) {
            return [this.context.mods[0]];
        } else {
            return [];
        }
    };

    sanityCheck = () => {
        pywebview.api
            .sanity_check()
            .then(res => {
                if (!res.success) throw res.error;
            })
            .catch(err => {
                console.error(err);
                this.props.onError({
                    short:
                        err.short +
                        " The setup wizard will be relaunched in 5 seconds.",
                    error_text: err.error_text
                });
                setTimeout(() => (window.location = "index.html?firstrun=true"), 5000);
            });
    };

    handleQueue = (mods, options) => {
        this.setState(prevState => {
            let newMods = this.context.mods;
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
    };

    handleAction = action => {
        let tasks = [];
        let verb = action.replace(/^\w/, c => c.toUpperCase());
        if (verb.endsWith("e")) verb = verb.substring(0, verb.length - 1);
        for (const mod of this.state.selectedMods) {
            if (action == "explore") {
                tasks.push(() => pywebview.api.explore({ mod: mod }));
            } else {
                tasks.push(async () => {
                    this.props.onProgress(`${verb}ing ${mod.name}`);
                    try {
                        const res = await pywebview.api.mod_action({
                            mod,
                            action
                        });
                        if (!res.success) {
                            throw res.error;
                        }
                    } catch (err) {
                        this.props.onError(err);
                    }
                });
            }
        }
        let queue = async () => {
            for (const task of tasks) {
                try {
                    await task();
                } catch (err) {
                    this.props.onError(err);
                    break;
                }
            }
            if (action !== "explore") {
                try {
                    const res = await pywebview.api.remerge({ name: "all" });
                    if (!res.success) {
                        throw res.error;
                    }
                } catch (error) {
                    this.props.onError(error);
                    this.props.onRefresh();
                    return;
                }
                this.props.onDone();
            } else {
                this.props.onCancel();
            }
            this.props.onRefresh();
        };
        if (["enable", "update", "explore"].includes(action)) queue();
        else
            this.props.onConfirm(
                `Are you sure you want to ${action} ${this.state.selectedMods
                    .map(m => m.name)
                    .join(", ")}?`,
                queue
            );
    };

    handleRemerge = merger => {
        this.props.onProgress(`Remerging ${merger}`);
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
                    () => this.props.onDone()
                );
            })
            .catch(this.props.onError);
    };

    uninstallAll = () => {
        this.props.onConfirm(
            "Are you sure you want to uninstall all of your mods?",
            () => {
                this.props.onProgress("Uninstalling All Mods");
                pywebview.api
                    .uninstall_all()
                    .then(res => {
                        if (!res.success) {
                            throw res.error;
                        }
                        this.props.onDone();
                        this.props.onRefresh();
                        this.setState({
                            selectedMods: []
                        });
                    })
                    .catch(this.props.onError);
            }
        );
    };

    applyQueue = async () => {
        this.props.onProgress("Applying Changes");
        let installs = [];
        let moves = [];
        for (const [i, mod] of this.context.mods.slice().reverse().entries()) {
            if (mod.path.startsWith("QUEUE")) installs.push(mod);
            else {
                const newPriority = this.context.mods.length - i - 1 + 100;
                if (mod.priority != newPriority)
                    moves.push({ mod, priority: newPriority });
            }
        }
        pywebview.api
            .apply_queue({ installs, moves })
            .then(res => {
                if (!res.success) throw res.error;

                this.props.onDone();
                this.setState(
                    {
                        showHandle: false,
                        selectedMods: [],
                        dirty: false
                    },
                    () => this.props.onRefresh()
                );
            })
            .catch(this.props.onError);
    };

    launchNoMod = () => {
        pywebview.api
            .launch_game_no_mod()
            .then(res => {
                if (!res.success) {
                    throw res.error;
                }
            })
            .catch(this.props.onError);
    };

    launchCemu = () => {
        pywebview.api
            .launch_cemu({ run_game: false })
            .then(res => {
                if (!res.success) {
                    throw res.error;
                }
            })
            .catch(this.props.onError);
    };

    render() {
        return (
            <>
                <div className="row">
                    <div id="mods">
                        {this.props.loaded ? (
                            this.context.mods.length > 0 ? (
                                <SortSelect
                                    mods={
                                        this.state.sortReverse
                                            ? [...this.context.mods].reverse()
                                            : this.context.mods
                                    }
                                    showDisabled={this.state.showDisabled}
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
                                        disabled={this.state.showHandle}
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
                                                showHandle: !this.state.showHandle
                                            })
                                        }>
                                        <i className="material-icons">reorder</i>
                                    </Button>
                                </OverlayTrigger>
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>
                                            {this.state.showDisabled
                                                ? "Hide disabled mods"
                                                : "Show disabled mods"}
                                        </Tooltip>
                                    }>
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            this.setState({
                                                showDisabled: !this.state.showDisabled
                                            })
                                        }>
                                        <i className="material-icons">
                                            {this.state.showDisabled
                                                ? "visibility_off"
                                                : "visibility"}
                                        </i>
                                    </Button>
                                </OverlayTrigger>
                            </ButtonGroup>
                            <Dropdown as={ButtonGroup} size="xs">
                                <OverlayTrigger overlay={<Tooltip>Remerge</Tooltip>}>
                                    <Button
                                        variant="secondary"
                                        onClick={() => this.handleRemerge("all")}>
                                        <i className="material-icons">refresh</i>
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
                                                onClick={() => this.handleRemerge(m)}>
                                                Remerge {m}
                                            </Dropdown.Item>
                                        ))}
                                </Dropdown.Menu>
                            </Dropdown>
                            <ButtonGroup size="xs">
                                <OverlayTrigger
                                    overlay={<Tooltip>Backup and restore</Tooltip>}>
                                    <Button
                                        variant="secondary"
                                        onClick={this.props.onBackup}>
                                        <i className="material-icons">restore</i>
                                    </Button>
                                </OverlayTrigger>
                                <OverlayTrigger overlay={<Tooltip>Export</Tooltip>}>
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
                                    overlay={<Tooltip>Uninstall all mods</Tooltip>}>
                                    <Button
                                        variant="danger"
                                        onClick={this.uninstallAll}>
                                        <i className="material-icons">delete_sweep</i>
                                    </Button>
                                </OverlayTrigger>
                            </ButtonGroup>
                            <div className="flex-grow-1"></div>
                            {this.state.hasCemu && (
                                <Dropdown as={ButtonGroup} size="xs">
                                    <OverlayTrigger
                                        overlay={
                                            <Tooltip>Launch Breath of the Wild</Tooltip>
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
                                    <Dropdown.Toggle
                                        split
                                        variant="primary"
                                        id="dropdown-split-basic"
                                    />
                                    <Dropdown.Menu>
                                        <Dropdown.Item onClick={this.launchNoMod}>
                                            Launch without mods
                                        </Dropdown.Item>
                                        <Dropdown.Item onClick={this.launchCemu}>
                                            Launch Cemu without starting game
                                        </Dropdown.Item>
                                    </Dropdown.Menu>
                                </Dropdown>
                            )}
                        </div>
                    </div>
                    <div id="mod-info">
                        <ModInfo
                            mod={this.state.selectedMods[0]}
                            multi={this.state.selectedMods.length > 1}
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
