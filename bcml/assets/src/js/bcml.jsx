import { Button, Dropdown, Fade, Tab, Tabs } from "react-bootstrap";

import DevTools from "./devtools.jsx";
import Settings from "./settings.jsx";
import Mods from "./mods.jsx";
import React from "react";

class BcmlRoot extends React.Component {
    constructor() {
        super();
        this.state = {
            mods: [],
            settingsLoaded: false,
            settingsValid: false,
            savingSettings: false
        };
    }

    saveSettings(settings) {
        this.setState({ settingsValid: true, savingSettings: false }, () =>
            pywebview.api.save_settings({ settings }).then(() =>
                pywebview.api.get_old_mods().then(num => {
                    this.setState({ oldMods: num });
                    if (num > 0) {
                        this.pageCount = 5;
                    }
                })
            )
        );
    }

    componentDidMount() {
        this.setState({ mods: this.props.mods });
    }

    refreshMods() {
        pywebview.api.get_mods({ disabled: true }).then(mods => {
            this.setState({ mods });
        });
    }

    render() {
        return (
            <React.Fragment>
                <Dropdown alignRight className="overflow-menu">
                    <Dropdown.Toggle id="dropdown-basic">
                        <i className="material-icons">menu</i>
                    </Dropdown.Toggle>

                    <Dropdown.Menu>
                        <Dropdown.Item href="#/action-1">Remerge</Dropdown.Item>
                        <Dropdown.Item href="#/action-2">
                            Another action
                        </Dropdown.Item>
                        <Dropdown.Item href="#/action-3">
                            Something else
                        </Dropdown.Item>
                    </Dropdown.Menu>
                </Dropdown>
                <Tabs id="tabs" mountOnEnter transition={Fade}>
                    <Tab eventKey="mod-list" title="Mods">
                        <Mods
                            mods={this.state.mods}
                            onRefresh={this.refreshMods.bind(this)}
                            onChange={mods => this.setState({ mods })}
                        />
                    </Tab>
                    <Tab eventKey="dev-tools" title="Dev Tools">
                        <DevTools />
                    </Tab>
                    <Tab eventKey="settings" title="Settings" className="p-2">
                        <Settings
                            saving={this.state.savingSettings}
                            onFail={() =>
                                this.setState({
                                    savingSettings: false
                                })
                            }
                            onSubmit={this.saveSettings.bind(this)}
                        />
                        <Button
                            className="fab"
                            onClick={() =>
                                this.setState({ savingSettings: true })
                            }>
                            <i className="material-icons">save</i>
                        </Button>
                    </Tab>
                </Tabs>
            </React.Fragment>
        );
    }
}

export default BcmlRoot;
