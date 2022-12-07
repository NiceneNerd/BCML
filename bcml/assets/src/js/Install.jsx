import Button from "react-bootstrap/Button";
import Modal from "react-bootstrap/Modal";
import OptionsDialog from "./Options.jsx";
import OverlayTrigger from "react-bootstrap/OverlayTrigger";
import React from "react";
import ReactSortable from "react-sortablejs";
import Spinner from "react-bootstrap/Spinner";

const MOD_STATE_ERROR = 'error';
const MOD_STATE_DOWNLOADING = 'downloading';
const MOD_STATE_INSTALLABLE = 'installable';

class InstallModal extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            mods: {},
            options: {
                disable: [],
                options: {}
            }
        };
        this.setOptions = this.setOptions.bind(this);
        this.allModsReady = this.allModsReady.bind(this);
        window.errorOneClick = (mod, error) =>
            this.setState({ mods: { ...this.state.mods, [mod]: { state: MOD_STATE_ERROR, error } } }, () => {
                this.props.onOneClick()
            })
        window.prepareOneClick = mod =>
            this.setState({ mods: { ...this.state.mods, [mod]: { state: MOD_STATE_DOWNLOADING } } }, () =>
                this.props.onOneClick()
            );
        window.oneClick = mod =>
            this.setState({ mods: { ...this.state.mods, [mod]: { state: MOD_STATE_INSTALLABLE } } }, () =>
                this.props.onOneClick()
            );
    }

    browse() {
        pywebview.api.file_pick().then(file =>
            this.setState(prev => {
                const mods = prev.mods;
                for (const mod of file) {
                    mods[mod] = { state: MOD_STATE_INSTALLABLE };
                }
                return mods;
            })
        );
    }

    handleClose() {
        this.props.onClose();
        this.resetDialog();
    }

    setOptions(options) {
        this.setState({ options: options });
    }

    resetDialog() {
        this.setState({ mods: {}, options: { disable: [], options: {} } });
    }

    showModError(mod) {
        let data = this.state.mods[mod];
        console.log(mod, data);
        if (data.state == MOD_STATE_ERROR) {
            this.props.onShowError(data.error);
        }
    }

    removeMod(mod) {
        this.setState(prevState => {
            let mods = prevState.mods;
            delete mods[mod];
            return { mods };
        });
    }

    allModsReady() {
        return Object.keys(this.state.mods).length && Object.values(this.state.mods).every(v => v.state == MOD_STATE_INSTALLABLE)
    }

    render() {
        return (
            <Modal show={this.props.show} onHide={this.props.onClose}>
                <Modal.Header closeButton>
                    <Modal.Title>Install Mod</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <p>
                        Select a mod or mods to install (must be a BNP or
                        graphic pack). You can select a <code>.bnp</code>,{" "}
                        <code>.zip</code>, <code>.rar</code>, or{" "}
                        <code>.7z</code> file or the <code>rules.txt</code> or{" "}
                        <code>info.json</code> of an unpacked mod.
                    </p>
                    <Button size="sm" onClick={() => this.browse()}>
                        Browse...
                    </Button>
                    {Object.keys(this.state.mods).length > 0 && (
                        <div className="mt-2">
                            <strong>
                                Mod{Object.keys(this.state.mods).length > 1 && "s"} to
                                install
                            </strong>
                            <ReactSortable
                                id="install-queue"
                                onChange={order => {
                                    this.setState({ mods: order });
                                }}
                                tag="div"
                                handle="mod-handle">
                                {Object.entries(this.state.mods).map(([mod, data]) => (
                                    <div
                                        key={mod}
                                        className="d-flex flex-row"
                                        data-id={mod}>
                                        <div className="mod-handle">
                                            <i className="material-icons">
                                                drag_handle
                                            </i>
                                        </div>
                                        <div className="flex-grow-1">
                                            {mod.split(/[\\\/]/).slice(-1)[0]}
                                        </div>
                                        <div className="wait-mod" hidden={data.state != MOD_STATE_DOWNLOADING}>
                                            <Spinner animation="border" size="sm"/>
                                        </div>
                                        <div className="err-mod" hidden={data.state != MOD_STATE_ERROR}>
                                            <a
                                                onClick={() =>
                                                    this.showModError(mod)
                                                }>
                                                <i className="material-icons text-danger">
                                                    report
                                                </i>
                                            </a>
                                        </div>
                                        <div className="rem-mod">
                                            <a
                                                onClick={() =>
                                                    this.removeMod(mod)
                                                }>
                                                <i className="material-icons text-danger">
                                                    remove_circle
                                                </i>
                                            </a>
                                        </div>
                                    </div>
                                ))}
                            </ReactSortable>
                        </div>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <OverlayTrigger
                        placement="right"
                        trigger="click"
                        rootClose={true}
                        rootCloseEvent="mousedown"
                        overlay={
                            <OptionsDialog
                                options={this.state.options}
                                onHide={this.setOptions}
                            />
                        }>
                        <Button variant="info" title="Advanced Options">
                            <i
                                className="material-icons"
                                style={{ verticalAlign: "middle" }}>
                                menu
                            </i>
                        </Button>
                    </OverlayTrigger>
                    <div className="flex-grow-1">{""}</div>
                    <Button
                        variant="secondary"
                        onClick={this.handleClose.bind(this)}>
                        Close
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() => {
                            this.props.onQueue(
                                Object.keys(this.state.mods),
                                this.state.options
                            );
                            this.resetDialog();
                        }}
                        disabled={!this.allModsReady()}>
                        Queue
                    </Button>
                    <Button
                        variant="success"
                        onClick={() => {
                            setTimeout(() => {
                                this.props.onInstall(
                                    Object.keys(this.state.mods),
                                    this.state.options
                                );
                                this.resetDialog();
                            }, 333);
                        }}
                        disabled={!this.allModsReady()}>
                        Install
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    }
}

export default InstallModal;
