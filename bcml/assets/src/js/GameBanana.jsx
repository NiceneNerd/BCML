import {
    Button,
    ButtonGroup,
    Card,
    CardColumns,
    Carousel,
    Dropdown,
    FormControl,
    InputGroup,
    Modal,
    Pagination,
    Spinner,
    SplitButton,
    ToggleButton
} from "react-bootstrap";

import ModContext from "./Context.jsx";
import React from "react";

class GameBanana extends React.Component {
    static contextType = ModContext;

    constructor(props) {
        super(props);

        this.state = {
            category: "",
            search: "",
            firstLoad: false,
            loaded: false,
            gbMods: [],
            mode: "new",
            lastTime: 0,
            page: 1,
            pages: 1,
            gameId: 5866
        };
    }

    async componentDidMount() {
        if (this.context.settings.auto_gb)
            this.props.onProgress(
                "Syncing GameBanana Mods",
                "Updating GameBanana database, please wait"
            );
        await pywebview.api.init_gb();
        this.loadMods();
    }

    sync = async () => {
        this.props.onProgress(
            "Syncing GameBanana Mods",
            "Updating GameBanana database, please wait"
        );
        await pywebview.api.update_gb();
        this.loadMods();
    };

    search = e => {
        this.setState({ search: document.getElementById("search").value }, () =>
            this.loadMods()
        );
        e.preventDefault();
    };

    clearSearch = () => {
        document.getElementById("search").value = "";
        this.search();
    };

    searchAuthor = author => {
        document.getElementById("search").value = `owner:"${author}"`;
        this.search();
    };

    setPage = num => {
        if (num < 1) num = 1;
        if (num > this.state.pages) num = this.state.pages;
        this.setState({ page: num }, () => this.loadMods());
    };

    loadMods = () => {
        this.setState({ loaded: false }, async () => {
            this.setState(
                {
                    gbMods: await pywebview.api.get_gb_mods(
                        this.state.page,
                        this.state.mode,
                        this.state.category,
                        this.state.search
                    ),
                    pages: await pywebview.api.get_gb_pages(
                        this.state.category,
                        this.state.search
                    ),
                    loaded: true,
                    firstLoad: true
                },
                () => this.props.onDone()
            );
        });
    };

    install = async file => {
        this.props.onProgress(`Downloading ${file._sFile}`, "Plz wait");
        const res = await pywebview.api.install_gb_mod(file);
        if (!res.success) {
            this.props.onError(res.error);
            return;
        }
        this.props.onDone();
        window.oneClick(res.data);
    };

    render() {
        return (
            <div
                style={{
                    overflowY: "auto",
                    overflowX: "hidden",
                    padding: "0 1rem 1rem"
                }}>
                <div className="gb-menu">
                    <ButtonGroup toggle size="sm" style={{ minWidth: "fit-content" }}>
                        {Object.entries({
                            New: "new",
                            Old: "old",
                            Downloads: "down",
                            Likes: "likes",
                            "A-Z": "abc"
                        }).map(([name, sort]) => (
                            <ToggleButton
                                variant="secondary"
                                type="radio"
                                checked={this.state.mode == sort}
                                key={sort}
                                onClick={() =>
                                    this.setState({ mode: sort, page: 1 }, () =>
                                        this.loadMods()
                                    )
                                }>
                                {name}
                            </ToggleButton>
                        ))}
                    </ButtonGroup>
                    <FormControl
                        as="select"
                        size="sm"
                        value={this.state.category}
                        onChange={e =>
                            this.setState({ category: e.currentTarget.value }, () =>
                                this.loadMods()
                            )
                        }>
                        {Object.entries({
                            "All Categories": "",
                            "Game Files": "Gamefile",
                            Sounds: "Sound",
                            Maps: "Map",
                            Skins: "Skin",
                            GUIs: "Gui",
                            Crafting: "Crafting",
                            Textures: "Texture"
                        }).map(([name, cat]) => (
                            <option key={cat} value={cat}>
                                {name}
                            </option>
                        ))}
                    </FormControl>
                    {!this.context.settings.auto_gb && (
                        <Button size="xs" variant="secondary" onClick={this.sync}>
                            <i className="material-icons">sync</i>
                        </Button>
                    )}
                    <form
                        onSubmit={this.search}
                        style={{ maxWidth: "37.5%", minWidth: "33%" }}>
                        <InputGroup size="sm">
                            <FormControl placeholder="Search..." id="search" />
                            {this.state.search != "" && (
                                <InputGroup.Append>
                                    <Button
                                        variant="danger"
                                        size="xs"
                                        onClick={this.clearSearch}>
                                        <i className="material-icons">clear</i>
                                    </Button>
                                </InputGroup.Append>
                            )}
                            <InputGroup.Append>
                                <Button
                                    size="xs"
                                    variant="primary"
                                    onClick={this.search}>
                                    <i className="material-icons">search</i>
                                </Button>
                            </InputGroup.Append>
                        </InputGroup>
                    </form>
                </div>
                {this.state.loaded ? (
                    <>
                        <ModList
                            mods={this.state.gbMods}
                            onInstall={this.install}
                            searchAuthor={this.searchAuthor}
                        />
                        <Pagination className="w-100">
                            {this.state.pages > 10 && (
                                <Pagination.First onClick={() => this.setPage(1)} />
                            )}
                            {this.state.page > 1 && (
                                <>
                                    <Pagination.Prev
                                        onClick={() =>
                                            this.setPage(this.state.page - 1)
                                        }
                                    />
                                </>
                            )}
                            {[...Array(this.state.pages).keys()]
                                .slice(
                                    Math.max(this.state.page - 2, 1),
                                    Math.min(this.state.page + 3, this.state.pages)
                                )
                                .map(i => (
                                    <Pagination.Item
                                        key={`page-${i}`}
                                        active={i == this.state.page}
                                        onClick={() => this.setPage(i)}>
                                        {i}
                                    </Pagination.Item>
                                ))}
                            {this.state.pages > 1 && (
                                <Pagination.Next
                                    onClick={() => this.setPage(this.state.page + 1)}
                                />
                            )}
                            {this.state.pages > 10 && (
                                <Pagination.Last
                                    onClick={() => this.setPage(this.state.pages)}
                                />
                            )}
                        </Pagination>
                    </>
                ) : (
                    <div className="text-center mt-3" style={{ height: "100%" }}>
                        <Spinner animation="border" variant="light" />
                    </div>
                )}
            </div>
        );
    }
}

class ModList extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            openMod: {},
            showModal: false
        };
    }

    openMod = async mod => {
        try {
            const res = await pywebview.api.update_gb_mod(mod.itemid);
            if (!res.success) throw res.error;
            mod = res.data;
        } catch (error) {
            console.error(error);
        }
        this.setState({
            openMod: mod,
            showModal: true
        });
    };

    render() {
        return (
            <>
                <CardColumns className="gb-list">
                    {this.props.mods.map(mod => (
                        <Card className="gb-mod" key={mod.itemid}>
                            <Card.Img src={mod.preview} alt={mod.name} />
                            <Card.Body>
                                <Card.Title>{mod.name}</Card.Title>
                                <Card.Text as="div">
                                    <div>{mod.description}</div>
                                </Card.Text>
                                <div
                                    style={{
                                        display: "flex",
                                        alignItems: "center",
                                        maxWidth: "100%"
                                    }}>
                                    <a
                                        href="#"
                                        className="text-secondary author"
                                        title={mod.owner}
                                        onClick={() =>
                                            this.props.searchAuthor(mod.owner)
                                        }>
                                        {mod.owner}
                                    </a>
                                    <div className="flex-grow-1"></div>
                                    <Button
                                        variant="success"
                                        size="sm"
                                        onClick={() =>
                                            this.props.onInstall(mod.files[0])
                                        }>
                                        Install
                                    </Button>
                                    <div>&nbsp;</div>
                                    <Button
                                        variant="primary"
                                        size="sm"
                                        onClick={() => this.openMod(mod)}>
                                        View
                                    </Button>
                                </div>
                            </Card.Body>
                            <Card.Footer>
                                <Metadata icon="category" label={mod.category} />
                                <Metadata
                                    icon="access_time"
                                    label={new Intl.DateTimeFormat().format(
                                        new Date(mod.updated * 1000)
                                    )}
                                />
                                <Metadata icon="cloud_download" label={mod.downloads} />
                                <Metadata icon="favorite" label={mod.likes} />
                            </Card.Footer>
                        </Card>
                    ))}
                </CardColumns>
                <ModModal
                    onClose={() => this.setState({ showModal: false })}
                    onInstall={this.props.onInstall}
                    show={this.state.showModal}
                    mod={this.state.openMod}
                />
            </>
        );
    }
}

class ModModal extends React.Component {
    static contextType = ModContext;

    constructor(props) {
        super(props);
        this.state = {};
    }

    hasMeta = file => {
        const json = JSON.stringify(file);
        return (
            json.includes("info.json") ||
            (json.includes("rules.txt") &&
                (json.includes("content") || json.includes("aoc")))
        );
    };

    render() {
        return (
            <Modal
                show={this.props.show}
                onHide={this.props.onClose}
                style={{
                    opacity: this.context.busy ? "0.0" : "1.0"
                }}
                dialogClassName="modal-wide">
                <Modal.Header closeButton>
                    <Modal.Title>{this.props.mod.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {this.props.mod.screenshots?.length > 0 ? (
                        <Carousel interval={null}>
                            {this.props.mod.screenshots.map(img => (
                                <Carousel.Item key={img._sFile}>
                                    <img
                                        className="d-block w-100"
                                        src={`https://screenshots.gamebanana.com/${img._sRelativeImageDir}/${img._sFile}`}
                                    />
                                    <Carousel.Caption>{img._sCaption}</Carousel.Caption>
                                </Carousel.Item>
                            ))}
                        </Carousel>
                    ) : (
                        <img className="d-block w-100" src={this.props.mod?.preview} />
                    )}
                    <br />
                    <div
                        className="gb-mod-desc"
                        dangerouslySetInnerHTML={{
                            __html: this.props.mod.text?.replace(/\u00a0/g, " ")
                        }}></div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={this.props.onClose}>
                        Close
                    </Button>
                    <Button
                        variant="primary"
                        href={`https://www.gamebanana.com/${this.props.mod?.category?.toLowerCase()}s/${
                            this.props.mod?.itemid
                        }`}
                        target="_blank">
                        View on GB
                    </Button>
                    {this.props.mod.files &&
                        (this.props.mod.files.length == 1 ? (
                            <Button
                                variant="success"
                                title="Install"
                                onClick={() =>
                                    this.props.onInstall(this.props.mod.files[0])
                                }>
                                Install
                            </Button>
                        ) : (
                            <SplitButton
                                variant="success"
                                title="Install"
                                onClick={() =>
                                    this.props.onInstall(this.props.mod.files[0])
                                }>
                                {this.props.mod.files
                                    .filter(file => this.hasMeta(file))
                                    .map((file, id) => (
                                        <Dropdown.Item
                                            key={id}
                                            title={file._sDescription}
                                            onClick={() => this.props.onInstall(file)}>
                                            {file._sFile}
                                        </Dropdown.Item>
                                    ))}
                            </SplitButton>
                        ))}
                </Modal.Footer>
            </Modal>
        );
    }
}

const Metadata = props => {
    return (
        <div className="meta">
            <i className="material-icons" style={{ fontSize: "16px" }}>
                {props.icon}
            </i>{" "}
            <span style={{ verticalAlign: "bottom", lineHeight: "16px" }}>
                {props.label}
            </span>
        </div>
    );
};

export default GameBanana;
