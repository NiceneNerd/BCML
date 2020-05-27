import {
    Button,
    Col,
    Form,
    InputGroup,
    OverlayTrigger,
    Row,
    Tooltip
} from "react-bootstrap";

import FolderInput from "./folder.jsx";
import React from "react";

class Settings extends React.Component {
    constructor() {
        super();
        this.state = {
            cemu_dir: "",
            game_dir: "",
            game_dir_nx: "",
            update_dir: "",
            dlc_dir: "",
            dlc_dir_nx: "",
            store_dir: "",
            load_reverse: false,
            site_meta: "",
            no_guess: false,
            lang: "",
            no_cemu: false,
            wiiu: true,
            no_hardlinks: false,
            valid: false,
            use_cef: false
        };
        this.handleChange = this.handleChange.bind(this);
        this.formRef = React.createRef();
    }

    checkValid() {
        return (
            (this.state.game_dir != "" || !this.state.wiiu) &&
            (this.state.game_dir_nx != "" || this.state.wiiu) &&
            (this.state.update_dir != "" || !this.state.wiiu) &&
            this.state.lang != "" &&
            (this.state.cemu_dir != "" || this.state.no_cemu) &&
            this.formRef.current.checkValidity()
        );
    }

    componentDidMount() {
        pywebview.api.get_settings().then(settings => {
            this.setState({ ...settings });
        });
    }

    componentDidUpdate(prevProps) {
        if (!prevProps.saving && this.props.saving) {
            if (!this.checkValid()) {
                this.setState({ valid: false }, () => this.props.onFail());
            } else {
                this.setState({ valid: true }, () => {
                    let { valid, ...settings } = this.state;
                    this.props.onSubmit(settings);
                });
            }
        }
    }

    handleChange(e) {
        try {
            e.persist();
        } catch (error) {}
        console.log(e);
        this.setState({
            [e.target.id]: e.target.type != "checkbox" ? e.target.value : e.target.checked
        });
    }

    render() {
        return (
            <Form
                noValidate
                validated={this.state.valid}
                onSubmit={this.handleSubmit}
                ref={this.formRef}>
                <h5>Game Folders</h5>
                <Row>
                    <Col>
                        <Form.Group controlId="cemu_dir">
                            <Form.Label>Cemu Directory</Form.Label>
                            <FolderInput
                                value={this.state.cemu_dir}
                                disabled={!this.state.wiiu || this.state.no_cemu}
                                onChange={this.handleChange}
                                isValid={this.state.cemu_dir != "" || this.state.no_cemu}
                                overlay={
                                    <Tooltip>
                                        {this.state.wiiu ? (
                                            <>
                                                (Optional) The directory where Cemu is
                                                installed. Note that this <em>must</em> be
                                                the folder that directly contains
                                                "Cemu.exe" and "settings.xml"
                                            </>
                                        ) : (
                                            "Not applicable for Switch mode"
                                        )}
                                    </Tooltip>
                                }
                            />
                            <Form.Control.Feedback type="invalid">
                                A Cemu folder is required unless you check the no Cemu
                                option
                            </Form.Control.Feedback>
                        </Form.Group>
                    </Col>
                    <Col>
                        <Form.Group
                            controlId="game_dir"
                            className={!this.state.wiiu && "d-none"}>
                            <Form.Label>Base Game Directory</Form.Label>
                            <FolderInput
                                value={this.state.game_dir}
                                onChange={this.handleChange}
                                isValid={this.state.game_dir != "" || !this.state.wiiu}
                                overlay={
                                    <Tooltip>
                                        The folder containing the base game files for
                                        BOTW, without the update or DLC files. The last
                                        folder should be "content", e.g.
                                        <br />
                                        <code>
                                            C:\Games\The Legend of Zelda Breath of the
                                            Wild [AZE01]\content
                                        </code>
                                    </Tooltip>
                                }
                                placement={"left"}
                            />
                        </Form.Group>
                        <Form.Control.Feedback type="invalid">
                            The BOTW dump folder is required
                        </Form.Control.Feedback>
                        <Form.Group
                            controlId="game_dir_nx"
                            className={this.state.wiiu && "d-none"}>
                            <Form.Label>Base Game Directory</Form.Label>
                            <FolderInput
                                value={this.state.game_dir_nx}
                                onChange={this.handleChange}
                                isValid={this.state.game_dir_nx != "" || this.state.wiiu}
                                overlay={
                                    <Tooltip>
                                        The folder containing the base game files for
                                        BOTW, without the update or DLC files. The last
                                        folder should be "romfs", e.g.
                                        <br />
                                        <code>C:\Games\BOTW\01007EF00011E000\romfs</code>
                                    </Tooltip>
                                }
                                placement={"left"}
                            />
                        </Form.Group>
                        <Form.Control.Feedback type="invalid">
                            The BOTW dump folder is required
                        </Form.Control.Feedback>
                    </Col>
                </Row>
                <Row>
                    <Col>
                        <Form.Group controlId="update_dir">
                            <Form.Label>Update Directory</Form.Label>
                            <FolderInput
                                value={this.state.update_dir}
                                onChange={this.handleChange}
                                isValid={this.state.update_dir != "" || !this.state.wiiu}
                                disabled={!this.state.wiiu}
                                overlay={
                                    <Tooltip>
                                        {this.state.wiiu ? (
                                            <>
                                                The folder containing the update files for
                                                BOTW, version 1.5.0. The last folder
                                                should be "content", and if you use Cemu,
                                                it should be in your "mlc01" folder, e.g.
                                                <br />
                                                <code>
                                                    C:\Cemu\mlc01\usr\title\0005000E\101C9400\content
                                                </code>
                                            </>
                                        ) : (
                                            "Not applicable for Switch mode"
                                        )}
                                    </Tooltip>
                                }
                            />
                        </Form.Group>
                        <Form.Control.Feedback type="invalid">
                            The BOTW update folder is required
                        </Form.Control.Feedback>
                    </Col>
                    <Col>
                        <Form.Group
                            controlId="dlc_dir"
                            className={!this.state.wiiu && "d-none"}>
                            <Form.Label>DLC Directory</Form.Label>
                            <FolderInput
                                value={this.state.dlc_dir}
                                onChange={this.handleChange}
                                isValid={true}
                                overlay={
                                    <Tooltip>
                                        (Optional) The folder containing the DLC files for
                                        BOTW, version 3.0. The last folder should usually
                                        be "0010", and if you use Cemu, it should be in
                                        your "mlc01" folder, e.g.
                                        <br />
                                        <code>
                                            C:\Cemu\mlc01\usr\title\0005000C\101C9400\content\0010
                                        </code>
                                    </Tooltip>
                                }
                                placement={"left"}
                            />
                        </Form.Group>

                        <Form.Group
                            controlId="dlc_dir_nx"
                            className={this.state.wiiu && "d-none"}>
                            <Form.Label>DLC Directory</Form.Label>
                            <FolderInput
                                value={this.state.dlc_dir_nx}
                                onChange={this.handleChange}
                                isValid={true}
                                overlay={
                                    <Tooltip>
                                        (Optional) The folder containing the DLC files for
                                        BOTW, version 3.0.
                                        <br />
                                        <code>C:\Games\BOTW\01007EF00011F001\romfs</code>
                                    </Tooltip>
                                }
                                placement={"left"}
                            />
                        </Form.Group>
                    </Col>
                </Row>
                <h5>Options</h5>
                <Row>
                    <Col>
                        <Form.Group controlId="lang">
                            <Form.Label>Game Language</Form.Label>
                            <OverlayTrigger
                                overlay={
                                    <Tooltip>
                                        The game language you play with. This will be
                                        prioritized when attempting to merge text mods.
                                    </Tooltip>
                                }>
                                <Form.Control
                                    as="select"
                                    value={this.state.lang}
                                    isValid={this.state.lang != ""}
                                    onChange={this.handleChange}>
                                    <option value={""}>Select a language</option>
                                    {LANGUAGES.map(lang => (
                                        <option value={lang} key={lang}>
                                            {lang}
                                        </option>
                                    ))}
                                </Form.Control>
                            </OverlayTrigger>
                            <Form.Control.Feedback type="invalid">
                                You must select a game language
                            </Form.Control.Feedback>
                        </Form.Group>
                        <Form.Group controlId="store_dir">
                            <Form.Label>BCML Data Directory</Form.Label>
                            <FolderInput
                                value={this.state.store_dir}
                                onChange={this.handleChange}
                                isValid={this.state.store_dir != ""}
                                overlay={
                                    <Tooltip>
                                        The folder where BCML will store internal files
                                        like installed mods, merged data, and backups.
                                    </Tooltip>
                                }
                            />
                        </Form.Group>
                        <Form.Control.Feedback type="invalid">
                            The BCML data folder is required
                        </Form.Control.Feedback>
                    </Col>
                    <Col>
                        <br />
                        <Form.Group controlId="wiiu">
                            <OverlayTrigger
                                overlay={
                                    <Tooltip>
                                        Turn on Switch mode instead of Wii U/Cemu mode
                                    </Tooltip>
                                }
                                placement={"left"}>
                                <Form.Check
                                    type="checkbox"
                                    label="Use Switch mode"
                                    checked={!this.state.wiiu}
                                    onChange={e =>
                                        this.setState({
                                            wiiu: !e.target.checked,
                                            no_cemu: true
                                        })
                                    }
                                />
                            </OverlayTrigger>
                        </Form.Group>
                        <Form.Group controlId="no_cemu">
                            <OverlayTrigger
                                overlay={
                                    <Tooltip>
                                        Allows you to use BCML without Cemu on your PC. If
                                        you do this, you will need to be careful about
                                        getting the right directories for update and DLC
                                        files. You will be able to merge installed mods
                                        with Export.
                                    </Tooltip>
                                }
                                placement={"left"}>
                                <Form.Check
                                    type="checkbox"
                                    disabled={!this.state.wiiu}
                                    label="Use BCML without a Cemu installation"
                                    checked={this.state.no_cemu}
                                    onChange={this.handleChange}
                                />
                            </OverlayTrigger>
                        </Form.Group>
                        <Form.Group controlId="no_guess">
                            <OverlayTrigger
                                overlay={
                                    <Tooltip>
                                        Don't estimate proper RSTB values for merged
                                        files. Deletes entries which cannot be calculated
                                        instead.
                                    </Tooltip>
                                }
                                placement={"left"}>
                                <Form.Check
                                    type="checkbox"
                                    label="Disable RSTB estimation on merged files"
                                    checked={this.state.no_guess}
                                    onChange={this.handleChange}
                                />
                            </OverlayTrigger>
                        </Form.Group>
                        <Form.Group controlId="no_hardlinks">
                            <OverlayTrigger
                                overlay={
                                    <Tooltip>
                                        By default, BCML uses hard links to connect
                                        installed mods to a single Cemu graphic pack. Use
                                        this option to disable this if it doesn't work and
                                        just copy the files instead.
                                    </Tooltip>
                                }
                                placement={"left"}>
                                <Form.Check
                                    type="checkbox"
                                    disabled={this.state.no_cemu}
                                    label="Disable hard links for master mod"
                                    checked={this.state.no_hardlinks}
                                    onChange={this.handleChange}
                                />
                            </OverlayTrigger>
                        </Form.Group>
                        {navigator.userAgent.includes("Windows") && (
                            <Form.Group controlId="use_cef">
                                <OverlayTrigger
                                    overlay={
                                        <Tooltip>
                                            By default, BCML will use the built-in
                                            EdgeHTML renderer for its webview UI. If this
                                            doesn't work well, you can try using the
                                            Chromium Embedded Framework (CEF) renderer
                                            instead.
                                        </Tooltip>
                                    }
                                    placement={"left"}>
                                    <Form.Check
                                        type="checkbox"
                                        label="Use CEF renderer"
                                        checked={this.state.use_cef}
                                        onChange={this.handleChange}
                                    />
                                </OverlayTrigger>
                            </Form.Group>
                        )}
                    </Col>
                </Row>
            </Form>
        );
    }
}

const LANGUAGES = [
    "USen",
    "EUen",
    "USfr",
    "USes",
    "EUde",
    "EUes",
    "EUfr",
    "EUit",
    "EUnl",
    "EUru",
    "CNzh",
    "JPja",
    "KRko",
    "TWzh"
];

export default Settings;
