import Form from "react-bootstrap/Form";
import Popover from "react-bootstrap/Popover";
import React from "react";
import Spinner from "react-bootstrap/Spinner";

class OptionsDialog extends React.Component {
    state = {
        loading: true,
        show: false,
        options: {}
    };

    componentDidMount() {
        if (this.props.options == null) {
            pywebview.api.get_options().then(opts => {
                this.refOpts = opts;
                let options = {};
                for (const m of opts) {
                    options[m.name] = {};
                    for (const opt of Object.keys(m.options)) {
                        options[m.name][opt] = false;
                    }
                }
                this.setState({
                    options: {
                        disable: [],
                        options
                    },
                    loading: false
                });
            });
        } else {
            this.setState({ options: this.props.options });
        }
    }

    toggleDisable(e) {
        e.persist();
        this.setState(
            prevState => {
                let dis = prevState.options.disable;
                const merger = e.target.dataset.merger;
                if (dis.includes(merger) && !e.target.checked) {
                    dis.pop(merger);
                } else if (!dis.includes(merger) && e.target.checked) {
                    dis.push(merger);
                }
                return {
                    ...this.state,
                    options: { ...this.state.options, disable: dis }
                };
            },
            () => this.props.onHide(this.state.options)
        );
    }

    toggleOption(e) {
        e.persist();
        this.setState(
            prevState => {
                let opts = prevState.options.options;
                const merger = e.target.dataset.merger;
                opts[merger][e.target.dataset.name] = e.target.checked;
                return {
                    ...this.state,
                    options: { ...this.state.options, options: opts }
                };
            },
            () => this.props.onHide(this.state.options)
        );
    }

    render() {
        return (
            <Popover {...this.props} className="options scroller">
                <Popover.Title>Advanced Options</Popover.Title>
                {!this.state.loading ? (
                    <Popover.Content>
                        {this.refOpts.map(opt => (
                            <React.Fragment key={opt.name}>
                                {opt.name != "general" && (
                                    <Form.Check
                                        type="checkbox"
                                        data-merger={opt.name}
                                        value={this.state.options.disable.includes(
                                            opt.name
                                        )}
                                        label={`Disable ${opt.friendly}`}
                                        onChange={this.toggleDisable.bind(this)}
                                    />
                                )}
                                {Object.keys(opt.options).map(optName => (
                                    <Form.Check
                                        key={opt.name + optName}
                                        type="checkbox"
                                        data-merger={opt.name}
                                        data-name={optName}
                                        value={
                                            this.state.options["options"][
                                                opt.name
                                            ][optName]
                                        }
                                        label={opt.options[optName]}
                                        onChange={this.toggleOption.bind(this)}
                                    />
                                ))}
                            </React.Fragment>
                        ))}
                    </Popover.Content>
                ) : (
                    <div className="loading">
                        <Spinner animation="border" variant="primary" />
                    </div>
                )}
            </Popover>
        );
    }
}

export default OptionsDialog;
