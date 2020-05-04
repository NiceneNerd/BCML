import BcmlRoot from "./js/bcml.jsx";
import FirstRun from "./js/firstrun.jsx";
import React from "react";
import ReactDOM from "react-dom";
import ReactMarkdown from "react-markdown";

document.addEventListener("DOMContentLoaded", async event => {
    let root;
    if (window.location.toString().includes("firstrun")) {
        root = <FirstRun />;
    } else if (window.location.toString().includes("help")) {
        let data = await fetch(
            `help/${new URLSearchParams(window.location.search).get("page")}.md`
        );
        let text = await data.text();
        root = <ReactMarkdown source={text} />;
    } else {
        root = <BcmlRoot />;
    }
    ReactDOM.render(root, document.getElementById("root"));
});
