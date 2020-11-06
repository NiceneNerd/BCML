import Form from "react-bootstrap/Form";
import Popover from "react-bootstrap/Popover";
import React from "react";
import Spinner from "react-bootstrap/Spinner";

class OptionsDialog extends React.Component {
    state = {
        loading: true,
        show: false,
        refs: null
    };

    componentDidMount() {
        pywebview.api.get_options().then(opts => {
            let options = this.props.options.options;
            if (Object.keys(options).length == 0) {
                for (const m of opts) {
                    options[m.name] = {};
                    for (const opt of Object.keys(m.options)) {
                        options[m.name][opt] = false;
                    }
                }
                this.props.onHide({
                    disable: [],
                    options
                });
            }
            this.setState({ loading: false, refs: opts });
        });
    }

    componentDidUpdate(prevProps) {
        if (this.props.options != prevProps.options) {
            const refs = this.state.refs;
            this.setState({ refs });
        }
    }

    toggleDisable(e) {
        e.persist();
        let dis = this.props.options.disable;
        const merger = e.target.dataset.merger;
        if (dis.includes(merger) && !e.target.checked) {
            dis.pop(merger);
        } else if (!dis.includes(merger) && e.target.checked) {
            dis.push(merger);
        }
        this.props.onHide({
            options: this.props.options.options,
            disable: dis
        });
    }

    toggleOption(e) {
        e.persist();
        let opts = this.props.options.options;
        const merger = e.target.dataset.merger;
        opts[merger][e.target.dataset.name] = e.target.checked;
        this.props.onHide({
            options: opts,
            disable: this.props.options.disable
        });
    }

    render() {
        return (
            <Popover className="options">
                <Popover.Title>Advanced Options</Popover.Title>
                {!this.state.loading ? (
                    <Popover.Content>
                        {this.state.refs.map(opt => (
                            <React.Fragment key={opt.name}>
                                {opt.name != "general" && (
                                    <Form.Check
                                        type="checkbox"
                                        data-merger={opt.name}
                                        checked={this.props.options.disable.includes(
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
                                        checked={
                                            this.props.options["options"][
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
