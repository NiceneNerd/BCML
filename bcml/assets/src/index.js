import "./scss/App.scss";
import App from "./js/App.jsx";
import FirstRun from "./js/FirstRun.jsx";
import React from "react";
import ReactDOM from "react-dom";

document.addEventListener("DOMContentLoaded", async event => {
    let root;
    if (window.location.toString().includes("firstrun")) {
        root = <FirstRun />;
    } else {
        root = <App />;
    }
    ReactDOM.render(root, document.getElementById("root"));
});
