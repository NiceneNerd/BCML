import React from "react";

class DevTools extends React.Component {
    constructor() {
        super();
        this.state = {
            someKey: "someValue"
        };
    }

    render() {
        return <p>BCML developer tools</p>;
    }
}

export default DevTools;
