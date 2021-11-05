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
        window.handleKeyMods = e => {
            if (e.ctrlKey) {
                switch (e.key) {
                    case "i":
                        this.setState({ showInstall: true });
                        break;
                    case "d":
                        this.handleAction("disable");
                        break;
                    case "e":
                        this.handleAction("enable");
                        break;
                    case "x":
                        this.handleAction("explore");
                        break;
                    case "u":
                        if (e.shiftKey) {
                            this.uninstallAll();
                        } else {
                            this.handleAction("uninstall");
                        }
                        break;
                    case "p":
                        this.handleAction("reprocess");
                        break;
                    case "m":
                        this.handleRemerge("all");
                        break;
                    case "l":
                        this.props.onLaunch();
                        break;
                    case "h":
                        this.setState({ showDisabled: !this.state.showDisabled });
                        break;
                    case "s":
                        this.setState({ showHandle: !this.state.showHandle });
                        break;
                    case "o":
                        this.setState({ sortReverse: !this.state.sortReverse });
                        break;
                    case "b":
                        this.props.onBackup();
                        break;
                    case "f":
                        this.props.onProfile();
                        break;
                    default:
                        return e;
                }
            }
        };
        document.addEventListener("dragover", e => e.preventDefault());
        document.addEventListener("drop", this.handleDrop);
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

    handleDrop = async e => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            this.props.onProgress("Processing Drag-and-Drop");
            for (let f of e.dataTransfer.files) {
                let reader = new FileReader();
                reader.readAsArrayBuffer(f);
                reader.onload = async () => {
                    if (reader.result.byteLength > 52428800) {
                        this.props.onCancel();
                        this.props.onError({
                            short: "You can only drag and drop files under 50 MB. Use the floating Install button instead.",
                            error_text:
                                "Due to technical limitations, files over 50 MB are not supported\n" +
                                `for drag-and-drop install. This file is ${
                                    reader.result.byteLength / 1024 / 1024
                                } MB. Please use the Install button (big floating icon) instead.`
                        });
                        return;
                    }
                    const file = await pywebview.api.file_drop({
                        file: f.name,
                        data: base64ArrayBuffer(reader.result)
                    });
                    this.props.onCancel();
                    window.oneClick(file);
                };
            }
        }
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
                        console.log(res);
                        if (!res.success) {
                            throw res.error;
                        }
                    } catch (err) {
                        if (err.short == "canceled") {
                            this.props.onCancel();
                        } else {
                            this.props.onError(err);
                        }
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
            if (
                action !== "explore" &&
                !(
                    this.state.selectedMods.every(m => m.disabled) &&
                    action == "uninstall"
                )
            ) {
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
                                                    : "lowest to highest") +
                                                " (Ctrl+O)"}
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
                                            {(this.state.showHandle
                                                ? "Hide sort handles"
                                                : "Show sort handles") + " (Ctrl+S)"}
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
                                            {(this.state.showDisabled
                                                ? "Hide disabled mods"
                                                : "Show disabled mods") + " (Ctrl+H)"}
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
                                <OverlayTrigger
                                    overlay={<Tooltip>Remerge (Ctrl+M)</Tooltip>}>
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
                                    overlay={
                                        <Tooltip>Backup and restore (Ctrl+B)</Tooltip>
                                    }>
                                    <Button
                                        variant="secondary"
                                        onClick={this.props.onBackup}>
                                        <i className="material-icons">restore</i>
                                    </Button>
                                </OverlayTrigger>
                                <OverlayTrigger
                                    overlay={<Tooltip>Profiles (Ctrl+F)</Tooltip>}>
                                    <Button
                                        variant="secondary"
                                        onClick={this.props.onProfile}>
                                        <i className="material-icons">dynamic_feed</i>
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
                                    overlay={
                                        <Tooltip>
                                            Uninstall all mods (Ctrl+Shift+U)
                                        </Tooltip>
                                    }>
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
                                            <Tooltip>
                                                Launch Breath of the Wild (Ctrl+L)
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
                    title="Install (Ctrl+I)"
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

function base64ArrayBuffer(arrayBuffer) {
    let base64 = "";
    const encodings =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    const bytes = new Uint8Array(arrayBuffer);
    const byteLength = bytes.byteLength;
    const byteRemainder = byteLength % 3;
    const mainLength = byteLength - byteRemainder;

    let a;
    let b;
    let c;
    let d;
    let chunk;

    // Main loop deals with bytes in chunks of 3
    for (let i = 0; i < mainLength; i += 3) {
        // Combine the three bytes into a single integer
        chunk = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];

        // Use bitmasks to extract 6-bit segments from the triplet
        a = (chunk & 16515072) >> 18; // 16515072 = (2^6 - 1) << 18
        b = (chunk & 258048) >> 12; // 258048   = (2^6 - 1) << 12
        c = (chunk & 4032) >> 6; // 4032     = (2^6 - 1) << 6
        d = chunk & 63; // 63       = 2^6 - 1

        // Convert the raw binary segments to the appropriate ASCII encoding
        base64 += encodings[a] + encodings[b] + encodings[c] + encodings[d];
    }

    // Deal with the remaining bytes and padding
    if (byteRemainder === 1) {
        chunk = bytes[mainLength];

        a = (chunk & 252) >> 2; // 252 = (2^6 - 1) << 2

        // Set the 4 least significant bits to zero
        b = (chunk & 3) << 4; // 3   = 2^2 - 1

        base64 += `${encodings[a]}${encodings[b]}==`;
    } else if (byteRemainder === 2) {
        chunk = (bytes[mainLength] << 8) | bytes[mainLength + 1];

        a = (chunk & 64512) >> 10; // 64512 = (2^6 - 1) << 10
        b = (chunk & 1008) >> 4; // 1008  = (2^6 - 1) << 4

        // Set the 2 least significant bits to zero
        c = (chunk & 15) << 2; // 15    = 2^4 - 1

        base64 += `${encodings[a]}${encodings[b]}${encodings[c]}=`;
    }

    return base64;
}
