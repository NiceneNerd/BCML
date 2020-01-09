import BcmlRoot from "./js/bcml.jsx";
import FirstRun from "./js/firstrun.jsx";
import React from "react";
import ReactDOM from "react-dom";

document.addEventListener("DOMContentLoaded", async event => {
    let root;
    if (window.location.toString().includes("firstrun")) {
        root = <FirstRun />;
    } else {
        let mods;
        if ("pywebview" in window) {
            mods = await pywebview.api.get_mods({ disabled: true });
        } else {
            mods = JSON.parse(
                decodeURIComponent(
                    new URLSearchParams(window.location.search).get("mods")
                )
            );
        }
        root = <BcmlRoot mods={mods} />;
    }
    ReactDOM.render(root, document.getElementById("root"));
});
