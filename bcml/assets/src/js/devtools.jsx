import React from "react";
import {
    Col,
    Form,
    Row,
    OverlayTrigger,
    Tooltip,
    Button,
    Modal,
    Badge,
    Spinner,
    InputGroup,
    FormControl,
    Tabs,
    Tab
} from "react-bootstrap";
import FolderInput from "./folder.jsx";
import OptionsDialog from "./options.jsx";
import CompareView from "./compare.jsx";

class DevTools extends React.Component {
    blank = {
        name: "",
        folder: "",
        image: "",
        url: "",
        desc: "",
        version: 1.0,
        options: {},
        selects: {},
        depends: [],
        showDepends: false,
        showOptions: false,
        showCompare: false
    };

    constructor() {
        super();
        this.state = JSON.parse(JSON.stringify(this.blank));
        this.handleChange = this.handleChange.bind(this);
        this.setOptions = this.setOptions.bind(this);
        this.createBnp = this.createBnp.bind(this);
        this.generateRstb = this.generateRstb.bind(this);
        this.upgradeBnp = this.upgradeBnp.bind(this);
    }

    setOptions(options) {
        this.setState({ options: options });
    }

    handleChange(e) {
        try {
            e.persist();
        } catch (error) {}
        this.setState({ [e.target.id]: e.target.value });
    }

    createBnp() {
        this.props.onState(
            { showProgress: true, progressTitle: "Creating BNP..." },
            () => {
                let { showDepends, showOptions, ...args } = this.state;
                pywebview.api
                    .create_bnp(args)
                    .then(res => {
                        if (!res.success) {
                            throw res;
                        }
                        this.setState(
                            {
                                ...JSON.parse(JSON.stringify(this.blank))
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

    generateRstb() {
        this.props.onState(
            {
                showProgress: true,
                progressTitle: "Generating RSTB for Mod"
            },
            () => {
                pywebview.api
                    .gen_rstb()
                    .then(res => {
                        console.log("Hello there");
                        console.log(res);
                        if (!res.success) {
                            throw res;
                        }
                        this.props.onState({
                            showProgress: false,
                            showDone: true
                        });
                    })
                    .catch(this.props.onError);
            }
        );
    }

    upgradeBnp() {
        this.props.onState(
            { showProgress: true, progressTitle: "Upgrading BNP" },
            () => {
                pywebview.api
                    .upgrade_bnp()
                    .then(res => {
                        if (!res.success) {
                            throw res;
                        }
                        this.props.onState({
                            showProgress: false,
                            showDone: true
                        });
                    })
                    .catch(this.props.onError);
            }
        );
    }

    render() {
        return (
            <>
                <Row className="p-2" style={{ height: "100%" }}>
                    <Col className="bnp" xs={8}>
                        <h4>BNP Creator</h4>
                        <Form
                            style={{
                                display: "flex",
                                flexGrow: 1,
                                flexDirection: "column"
                            }}>
                            <Form.Group controlId="name">
                                <Form.Label>Name</Form.Label>
                                <Form.Control
                                    placeholder="Name your mod"
                                    value={this.state.name}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Form.Group controlId="image">
                                <Form.Label>Image</Form.Label>
                                <Form.Control
                                    placeholder="https://yourmod.com/preview.jpg"
                                    value={this.state.image}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Form.Group controlId="url">
                                <Form.Label>URL</Form.Label>
                                <Form.Control
                                    placeholder="https://www.yourmod.url/"
                                    value={this.state.url}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Form.Group controlId="version">
                                <Form.Label>Version</Form.Label>
                                <Form.Control
                                    type="number"
                                    step="0.1"
                                    value={this.state.version}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Form.Group controlId="folder">
                                <Form.Label>Mod root folder</Form.Label>
                                <FolderInput
                                    isValid={false}
                                    overlay={
                                        <Tooltip>
                                            The folder containing the main mod
                                            content, should contain "content"
                                            and/or "aoc."
                                        </Tooltip>
                                    }
                                    value={this.state.folder}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Form.Group
                                controlId="desc"
                                style={{
                                    flexGrow: 1,
                                    display: "flex",
                                    flexDirection: "column"
                                }}>
                                <Form.Label>Description</Form.Label>
                                <Form.Control
                                    as="textarea"
                                    style={{ height: "100%" }}
                                    value={this.state.desc}
                                    onChange={this.handleChange}
                                />
                            </Form.Group>
                            <Row>
                                <Col className="flex-grow-0">
                                    <OverlayTrigger
                                        onHide={() =>
                                            document
                                                .querySelector("body")
                                                .classList.remove("dev-open")
                                        }
                                        trigger="click"
                                        placement="auto"
                                        options={this.state.options}
                                        overlay={props => (
                                            <OptionsDialog
                                                {...props}
                                                onHide={this.setOptions}
                                            />
                                        )}>
                                        <Button
                                            onClick={() =>
                                                document
                                                    .querySelector("body")
                                                    .classList.toggle(
                                                        "dev-open"
                                                    )
                                            }
                                            variant="info"
                                            title="Advanced Options">
                                            <i
                                                className="material-icons"
                                                style={{
                                                    verticalAlign: "middle"
                                                }}>
                                                menu
                                            </i>
                                        </Button>
                                    </OverlayTrigger>
                                </Col>
                                <div className="flex-grow-1">{""}</div>
                                <Col
                                    style={{
                                        whiteSpace: "nowrap",
                                        textAlign: "right"
                                    }}>
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            this.setState({ showDepends: true })
                                        }>
                                        Dependencies
                                    </Button>{" "}
                                    <Button
                                        disabled={!this.state.folder}
                                        variant="secondary"
                                        onClick={() =>
                                            this.setState({ showOptions: true })
                                        }>
                                        Options
                                    </Button>{" "}
                                    <Button
                                        variant="primary"
                                        onClick={this.createBnp}>
                                        Create BNP
                                    </Button>
                                </Col>
                            </Row>
                        </Form>
                    </Col>
                    <Col xs={4} className="dev-other">
                        <h4>Other Tools</h4>
                        <Row>
                            <Col>
                                <Button
                                    variant="success"
                                    onClick={this.generateRstb}>
                                    Generate RSTB for Mod
                                </Button>
                            </Col>
                            <Col>
                                <Button
                                    variant="warning"
                                    onClick={() =>
                                        this.setState({ showCompare: true })
                                    }>
                                    Compare Mods
                                </Button>
                            </Col>
                            <Col>
                                <Button
                                    variant="info"
                                    onClick={() =>
                                        pywebview.api.explore_master()
                                    }>
                                    View Merged Files
                                </Button>
                            </Col>
                            <Col>
                                <Button
                                    variant="danger"
                                    onClick={this.upgradeBnp}>
                                    Upgrade Old BNP
                                </Button>
                            </Col>
                        </Row>
                    </Col>
                </Row>
                <Dependencies
                    show={this.state.showDepends}
                    onClose={() => this.setState({ showDepends: false })}
                    onSet={depends =>
                        this.setState({ showDepends: false, depends })
                    }
                    depends={this.state.depends}
                />
                <ModOptions
                    show={this.state.showOptions}
                    onClose={() => this.setState({ showOptions: false })}
                    onSet={selects =>
                        this.setState({ showOptions: false, selects })
                    }
                    folder={this.state.folder}
                />
                <CompareView
                    show={this.state.showCompare}
                    onHide={() => this.setState({ showCompare: false })}
                />
            </>
        );
    }
}

class Dependencies extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            depends: [],
            manualId: "",
            mods: [],
            modsLoaded: false
        };
        this.addDepend = this.addDepend.bind(this);
        this.removeDepend = this.removeDepend.bind(this);
    }

    addDepend(mod) {
        let depends = this.state.depends;
        depends.push(mod);
        this.setState({ depends });
    }

    removeDepend(mod) {
        let depends = this.state.depends;
        depends.pop(mod);
        this.setState({ depends });
    }

    componentDidMount() {
        this.setState(
            {
                depends: this.props.depends.map(depend => {
                    return { id: depend, name: atob(depend) };
                })
            },
            () => {
                pywebview.api.get_mods({ disabled: true }).then(mods => {
                    this.setState({ mods, modsLoaded: true });
                });
            }
        );
    }

    render() {
        return (
            <Modal
                show={this.props.show}
                onHide={this.props.onClose}
                className="depends">
                <Modal.Header closeButton>
                    <Modal.Title>Specify Dependencies</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <p>
                        Select required mods from your installed mods, or
                        manually add an ID
                    </p>
                    <p>
                        <h5>Installed Mods</h5>
                        <div className="bg-dark p-2 rounded">
                            {this.state.modsLoaded ? (
                                this.state.mods.length > 0 ? (
                                    this.state.mods.map(mod => (
                                        <div key={mod.id} className="d-flex">
                                            <div className="flex-grow-1">
                                                {mod.name}
                                            </div>
                                            <div className="add-depend">
                                                <a
                                                    onClick={() =>
                                                        this.addDepend(mod)
                                                    }>
                                                    <i className="material-icons text-success">
                                                        add_circle
                                                    </i>
                                                </a>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <span>No mods installed</span>
                                )
                            ) : (
                                <div className="text-center">
                                    <Spinner
                                        variant="secondary"
                                        animation="border"
                                    />
                                </div>
                            )}
                        </div>
                    </p>
                    <p>
                        <h5>Add Manual ID</h5>
                        <InputGroup>
                            <FormControl
                                placeholder="Mod ID"
                                value={this.state.manualId}
                                onChange={e =>
                                    this.setState({ manualId: e.target.value })
                                }
                            />
                            <InputGroup.Append>
                                <Button
                                    disabled={this.state.manualId.length == 0}
                                    variant="secondary"
                                    onClick={() => {
                                        try {
                                            this.addDepend({
                                                id: this.state.manualId,
                                                name: atob(this.state.manualId)
                                            });
                                            this.setState({ manualId: "" });
                                        } catch (error) {
                                            alert("Invalid mod ID provided");
                                        }
                                    }}>
                                    Add
                                </Button>
                            </InputGroup.Append>
                        </InputGroup>
                    </p>
                    <div>
                        <h5>Dependencies</h5>
                        <div className="bg-dark d-flex p-2 rounded">
                            {this.state.depends.length > 0 ? (
                                this.state.depends.map(depend => (
                                    <h5 key={depend.id}>
                                        <Badge
                                            variant="secondary"
                                            style={{ alignItems: "center" }}
                                            className="d-flex">
                                            <span className="flex-grow-1 mr-1">
                                                {depend.name || depend.id}
                                            </span>
                                            <a
                                                onClick={() =>
                                                    this.removeDepend(depend)
                                                }>
                                                <i
                                                    className="material-icons text-danger"
                                                    style={{
                                                        fontSize: "16px",
                                                        verticalAlign:
                                                            "text-top"
                                                    }}>
                                                    close
                                                </i>
                                            </a>
                                        </Badge>
                                    </h5>
                                ))
                            ) : (
                                <span className="text-secondary">
                                    No dependencies
                                </span>
                            )}
                        </div>
                    </div>
                </Modal.Body>
                <Modal.Footer className="alignright">
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() =>
                            this.props.onSet(
                                this.state.depends.map(depend => depend.id)
                            )
                        }>
                        OK
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    }
}

class ModOptions extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            singles: [],
            multi: [],
            folders: []
        };
        this.addGroup = this.addGroup.bind(this);
        this.addSingle = this.addSingle.bind(this);
        this.addMulti = this.addMulti.bind(this);
    }

    componentDidUpdate(prevProps) {
        if (this.props.folder != prevProps.folder) {
            pywebview.api
                .get_option_folders({ mod: this.props.folder })
                .then(folders => this.setState({ folders }));
        }
    }

    addGroup() {
        this.setState({
            singles: [
                ...this.state.singles,
                {
                    name: document.querySelector("#groupName").value,
                    desc: document.querySelector("#groupDesc").value,
                    options: []
                }
            ]
        });
    }

    delGroup(group) {
        let folders = this.state.folders;
        group.options.forEach(opt => {
            folders.push(opt.folder);
        });
        this.setState({
            singles: this.state.singles.filter(g => g != group),
            folders
        });
    }

    addSingle() {
        let singles = this.state.singles;
        let group = singles.find(
            single =>
                single.name == document.querySelector("#singleGroup").value
        );
        singles.pop(group);
        const folder = document.querySelector("#singleFolder").value;
        group.options.push({
            name: document.querySelector("#singleName").value,
            desc: document.querySelector("#singleDesc").value,
            folder
        });
        singles.push(group);
        this.setState(
            { singles, folders: this.state.folders.filter(f => f != folder) },
            () => {
                document.querySelector("#singleName").value = "";
                document.querySelector("#singleDesc").value = "";
                document.querySelector("#singleFolder").value = "";
            }
        );
    }

    delSingle(single, group) {
        group.options = group.options.filter(s => s != single);
        this.setState({
            singles: [...this.state.singles.filter(g => g != group), group],
            folders: [...this.state.folders, single.folder]
        });
    }

    addMulti() {
        const folder = document.querySelector("#multiFolder").value;
        this.setState(
            {
                multi: [
                    ...this.state.multi,
                    {
                        name: document.querySelector("#multiName").value,
                        desc: document.querySelector("#multiDesc").value,
                        folder,
                        default: document.querySelector("#multiDefault").checked
                    }
                ],
                folders: this.state.folders.filter(f => f != folder)
            },
            () => {
                document.querySelector("#multiName").value = "";
                document.querySelector("#multiDesc").value = "";
                document.querySelector("#multiDefault").checked = false;
            }
        );
    }

    delMulti(multi) {
        this.setState({
            multi: this.state.multi.filter(m => m != multi),
            folders: [...this.state.folders, multi.folder]
        });
    }

    render() {
        return (
            <Modal
                dialogClassName="modal-wide"
                show={this.props.show}
                onHide={this.props.onClose}
                scrollable={true}>
                <Modal.Header closeButton>
                    <Modal.Title>Add Mod Options</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <p>
                        Add options for customizing your mod's installation. You
                        can add any number of multiple choice checkboxes and/or
                        groups of mutually exclusive choices.
                    </p>
                    <Tabs defaultActiveKey="multi">
                        <Tab eventKey="multi" title="Multiple Choice">
                            <div className="my-2">
                                <h5>Define Options</h5>
                                <Form>
                                    <Form.Group controlId="multiFolder">
                                        <Form.Label>Option Folder</Form.Label>
                                        <Form.Control as="select">
                                            {this.state.folders.map(folder => (
                                                <option
                                                    key={folder}
                                                    value={folder}>
                                                    {folder}
                                                </option>
                                            ))}
                                        </Form.Control>
                                    </Form.Group>
                                    <Form.Group controlId="multiName">
                                        <Form.Label>Option Name</Form.Label>
                                        <Form.Control placeholder="Name of the option" />
                                    </Form.Group>
                                    <Form.Group controlId="multiDesc">
                                        <Form.Label>
                                            Option Description
                                        </Form.Label>
                                        <Form.Control placeholder="Description of the option" />
                                    </Form.Group>
                                    <Form.Group controlId="multiDefault">
                                        <Form.Check
                                            type="checkbox"
                                            label="Enable by default"
                                        />
                                    </Form.Group>
                                    <Button size="sm" onClick={this.addMulti}>
                                        Add Option
                                    </Button>
                                </Form>
                                <div className="m-2">
                                    <h5>Multiple Choice Options</h5>
                                    <div className="bg-dark p-2 rounded d-flex flex-wrap">
                                        {this.state.multi.length > 0 ? (
                                            this.state.multi.map(opt => (
                                                <Badge
                                                    variant="secondary"
                                                    style={{
                                                        alignItems: "center"
                                                    }}
                                                    key={opt.name}
                                                    className="d-flex m-1">
                                                    <span className="flex-grow-1 mr-1">
                                                        {opt.name}
                                                    </span>
                                                    <a
                                                        onClick={() =>
                                                            this.delMulti(opt)
                                                        }>
                                                        <i
                                                            className="material-icons text-danger"
                                                            style={{
                                                                fontSize:
                                                                    "16px",
                                                                verticalAlign:
                                                                    "text-top"
                                                            }}>
                                                            close
                                                        </i>
                                                    </a>
                                                </Badge>
                                            ))
                                        ) : (
                                            <span className="text-secondary">
                                                No options added
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </Tab>
                        <Tab eventKey="select" title="Single Select">
                            <Row className="my-2">
                                <Col>
                                    <h5>Add Select Group</h5>
                                    <Form>
                                        <Form.Group controlId="groupName">
                                            <Form.Label>Group Name</Form.Label>
                                            <Form.Control placeholder="Name of the group" />
                                        </Form.Group>
                                        <Form.Group controlId="groupDesc">
                                            <Form.Label>
                                                Group Description
                                            </Form.Label>
                                            <Form.Control placeholder="Description of the group" />
                                        </Form.Group>
                                        <Button
                                            size="sm"
                                            onClick={this.addGroup}>
                                            Add Group
                                        </Button>
                                    </Form>
                                </Col>
                                <Col>
                                    <h5>Define Option</h5>
                                    <Form>
                                        <Form.Group controlId="singleFolder">
                                            <Form.Label>
                                                Option Folder
                                            </Form.Label>
                                            <Form.Control as="select">
                                                {this.state.folders.map(
                                                    folder => (
                                                        <option
                                                            key={folder}
                                                            value={folder}>
                                                            {folder}
                                                        </option>
                                                    )
                                                )}
                                            </Form.Control>
                                        </Form.Group>
                                        <Form.Group controlId="singleGroup">
                                            <Form.Label>
                                                Option Group
                                            </Form.Label>
                                            <Form.Control as="select">
                                                {this.state.singles.map(
                                                    single => (
                                                        <option
                                                            key={single.name}
                                                            value={single.name}>
                                                            {single.name}
                                                        </option>
                                                    )
                                                )}
                                            </Form.Control>
                                        </Form.Group>
                                        <Form.Group controlId="singleName">
                                            <Form.Label>Option Name</Form.Label>
                                            <Form.Control placeholder="Name of the option" />
                                        </Form.Group>
                                        <Form.Group controlId="singleDesc">
                                            <Form.Label>
                                                Option Description
                                            </Form.Label>
                                            <Form.Control placeholder="Description of the option" />
                                        </Form.Group>
                                        <Button
                                            disabled={
                                                !document.querySelector(
                                                    "#singleFolder"
                                                ) ||
                                                !document.querySelector(
                                                    "#singleFolder"
                                                ).value
                                            }
                                            size="sm"
                                            onClick={this.addSingle}>
                                            Add Option
                                        </Button>
                                    </Form>
                                </Col>
                            </Row>
                            <div className="mb-2">
                                <h5>Options</h5>
                                <div className="bg-dark p-2 rounded d-flex">
                                    {this.state.singles.length > 0 ? (
                                        this.state.singles.map(group => (
                                            <div
                                                key={group.name}
                                                className="small card bg-secondary pt-1 px-2">
                                                <div className="d-flex">
                                                    <strong className="flex-grow-1">
                                                        {group.name}
                                                    </strong>
                                                    <a
                                                        onClick={() =>
                                                            this.delGroup(group)
                                                        }>
                                                        <i
                                                            className="material-icons text-danger"
                                                            style={{
                                                                fontSize:
                                                                    "16px",
                                                                verticalAlign:
                                                                    "text-top"
                                                            }}>
                                                            close
                                                        </i>
                                                    </a>
                                                </div>
                                                <div className="mt-1 d-flex">
                                                    {Object.keys(group.options)
                                                        .length > 0 ? (
                                                        Object.keys(
                                                            group.options
                                                        ).map(opt => (
                                                            <h5
                                                                key={
                                                                    group
                                                                        .options[
                                                                        opt
                                                                    ].name
                                                                }>
                                                                <Badge
                                                                    variant="dark"
                                                                    style={{
                                                                        alignItems:
                                                                            "center"
                                                                    }}
                                                                    className="d-flex mx-1">
                                                                    <span className="flex-grow-1 mr-1">
                                                                        {
                                                                            group
                                                                                .options[
                                                                                opt
                                                                            ]
                                                                                .name
                                                                        }
                                                                    </span>
                                                                    <a
                                                                        onClick={() =>
                                                                            this.delSingle(
                                                                                group
                                                                                    .options[
                                                                                    opt
                                                                                ],
                                                                                group
                                                                            )
                                                                        }>
                                                                        <i
                                                                            className="material-icons text-danger"
                                                                            style={{
                                                                                fontSize:
                                                                                    "16px",
                                                                                verticalAlign:
                                                                                    "text-top"
                                                                            }}>
                                                                            close
                                                                        </i>
                                                                    </a>
                                                                </Badge>
                                                            </h5>
                                                        ))
                                                    ) : (
                                                        <span className="text-dark">
                                                            Empty group
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <span className="text-secondary">
                                            No options added
                                        </span>
                                    )}
                                </div>
                            </div>
                        </Tab>
                    </Tabs>
                </Modal.Body>
                <Modal.Footer className="alignright">
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() =>
                            this.props.onSet({
                                multi: this.state.multi,
                                single: this.state.singles
                            })
                        }>
                        OK
                    </Button>
                </Modal.Footer>
            </Modal>
        );
    }
}

export default DevTools;
