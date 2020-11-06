import React from "react";
import ReactSortable from "react-sortablejs";

class ModSelect extends React.Component {
    constructor() {
        super();
        this.state = {
            selectedItems: [],
            mods: [],
            justSorted: false
        };
    }

    componentDidMount() {
        this.setState({
            mods: this.props.mods,
            selectedItems: [this.props.mods[0].priority]
        });
    }

    static getDerivedStateFromProps(nextProps, prevState) {
        if (JSON.stringify(nextProps.mods) != JSON.stringify(prevState.mods)) {
            return {
                mods: nextProps.mods,
                selectedItems: [nextProps.mods[0].priority]
            };
        } else return null;
    }

    componentDidUpdate(prevProps, prevState) {
        if (prevState.selectedItems != this.state.selectedItems) {
            this.props.onSelect(
                this.state.mods.filter(
                    mod =>
                        this.state.selectedItems.includes(mod.priority) &&
                        !mod.path.startsWith("QUEUE")
                )
            );
            return;
        }
        if (JSON.stringify(prevProps.mods) != JSON.stringify(this.state.mods)) {
            this.setState({
                selectedItems: this.state.justSorted
                    ? prevState.selectedItems
                    : [],
                justSorted: false
            });
        }
    }

    onItemSelect(e, mod) {
        e.persist();
        if (mod.path.startsWith("QUEUE")) return;
        let items;
        if (!this.state.selectedItems.includes(mod.priority)) {
            if (!e.ctrlKey) items = [mod.priority];
            else items = [mod.priority, ...this.state.selectedItems];
        } else {
            if (e.ctrlKey) {
                items = this.state.selectedItems;
                items.pop();
            } else {
                items = [mod.priority];
            }
        }
        this.setState({
            selectedItems: items
        });
    }

    onSort(order, sortable, event) {
        const mod = JSON.parse(event.item.dataset.id);
        this.setState(
            prevState => ({
                selectedItems: !mod.path.startsWith("QUEUE")
                    ? [mod.priority]
                    : prevState.selectedItems,
                justSorted: true
            }),
            () => this.props.onChange(order.map(mod => JSON.parse(mod)))
        );
    }

    render() {
        return (
            this.state.mods.length > 0 && (
                <ReactSortable
                    className="mod-list scroller"
                    key={JSON.stringify(this.state.selectedItems)}
                    onChange={this.onSort.bind(this)}
                    options={{ handle: ".mod-handle" }}>
                    {this.state.mods.map(mod => (
                        <ModItem
                            key={JSON.stringify(mod)}
                            mod={mod}
                            active={this.state.selectedItems.includes(
                                mod.priority
                            )}
                            showHandle={this.props.showHandle}
                            onClick={e => this.onItemSelect(e, mod)}
                        />
                    ))}
                </ReactSortable>
            )
        );
    }
}

class ModItem extends React.Component {
    render() {
        return (
            <div
                className={
                    "list-group-item" +
                    (this.props.active ? " active" : "") +
                    (this.props.mod.disabled ? " mod-disabled" : "") +
                    (this.props.mod.path.startsWith("QUEUE")
                        ? " mod-queued"
                        : "")
                }
                onClick={this.props.onClick}
                data-id={JSON.stringify(this.props.mod)}>
                <span
                    className={
                        "mod-handle" + (!this.props.showHandle ? " d-none" : "")
                    }>
                    <i className="material-icons">drag_handle</i>
                </span>
                {this.props.mod.name}
            </div>
        );
    }
}

export default ModSelect;
