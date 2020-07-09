import BcmlRoot from "./js/bcml.jsx";
import FirstRun from "./js/firstrun.jsx";
import React from "react";
import ReactDOM from "react-dom";

document.addEventListener("DOMContentLoaded", async event => {
    let root;
    if (window.location.toString().includes("firstrun")) {
        root = <FirstRun />;
    } else {
        root = <BcmlRoot />;
    }
    ReactDOM.render(root, document.getElementById("root"));
});
