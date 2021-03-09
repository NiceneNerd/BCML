import React from "react";
import { Button, OverlayTrigger, Tooltip } from "react-bootstrap";

function DonateWidget() {
    return (
        <ul className="donate-list">
            <li>
                <Button
                    variant="danger"
                    target="_blank"
                    href="https://www.patreon.com/join/nicenenerdbcml?">
                    <PatreonIcon /> Patreon
                </Button>{" "}
                <Button
                    variant="primary"
                    target="_blank"
                    href="https://www.paypal.com/donate?business=macadamiadaze%40gmail.com&item_name=BCML+support&currency_code=USD">
                    <PaypalIcon /> PayPal
                </Button>
            </li>
            <li>
                <OverlayTrigger overlay={<Tooltip>Donate Bitcoin</Tooltip>}>
                    <>
                        <BtcIcon /> <code>392YEGQ8WybkRSg4oyeLf7Pj2gQNhPcWoa</code>
                    </>
                </OverlayTrigger>
            </li>
            <li>
                <OverlayTrigger overlay={<Tooltip>Donate Ethereum</Tooltip>}>
                    <>
                        <EthIcon />{" "}
                        <code>0xbA189996b1eF94Bd93Cd097a4094Fbd9e3500455</code>
                    </>
                </OverlayTrigger>
            </li>
            <li>
                <OverlayTrigger overlay={<Tooltip>Donate Graph</Tooltip>}>
                    <>
                        <GrtIcon />{" "}
                        <code>0x5f400A54D264185a70CFFd969C8d64b9d209361d</code>
                    </>
                </OverlayTrigger>
            </li>
        </ul>
    );
}

function BtcIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            version="1.1"
            width="28px"
            height="28px"
            viewBox="0 0 1 1"
            preserveAspectRatio="xMidYMid"
            id="svg2">
            <metadata id="metadata22"></metadata>
            <defs id="defs4">
                <filter id="_drop-shadow" color-interpolation-filters="sRGB">
                    <feGaussianBlur
                        in="SourceAlpha"
                        result="blur-out"
                        stdDeviation="1"
                        id="feGaussianBlur7"
                    />
                    <feBlend
                        in="SourceGraphic"
                        in2="blur-out"
                        mode="normal"
                        id="feBlend9"
                    />
                </filter>
                <linearGradient id="coin-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style={{ stopColor: "#f9aa4b" }} id="stop12" />
                    <stop offset="100%" style={{ stopColor: "#f7931a" }} id="stop14" />
                </linearGradient>
            </defs>
            <g transform="scale(0.015625)" id="g16">
                <path
                    id="coin"
                    d="m 63.0359,39.741 c -4.274,17.143 -21.637,27.576 -38.782,23.301 -17.138,-4.274 -27.571,-21.638 -23.295,-38.78 4.272,-17.145 21.635,-27.579 38.775,-23.305 17.144,4.274 27.576,21.64 23.302,38.784 z"
                    style={{ fill: "url(#coin-gradient)" }}
                />
                <path
                    id="symbol"
                    d="m 46.1009,27.441 c 0.637,-4.258 -2.605,-6.547 -7.038,-8.074 l 1.438,-5.768 -3.511,-0.875 -1.4,5.616 c -0.923,-0.23 -1.871,-0.447 -2.813,-0.662 l 1.41,-5.653 -3.509,-0.875 -1.439,5.766 c -0.764,-0.174 -1.514,-0.346 -2.242,-0.527 l 0.004,-0.018 -4.842,-1.209 -0.934,3.75 c 0,0 2.605,0.597 2.55,0.634 1.422,0.355 1.679,1.296 1.636,2.042 -3.94,15.801 0,0 -3.94,15.801 -0.174,0.432 -0.615,1.08 -1.609,0.834 0.035,0.051 -2.552,-0.637 -2.552,-0.637 l -1.743,4.019 4.569,1.139 c 0.85,0.213 1.683,0.436 2.503,0.646 l -1.453,5.834 3.507,0.875 1.439,-5.772 c 0.958,0.26 1.888,0.5 2.798,0.726 l -1.434,5.745 3.511,0.875 1.453,-5.823 c 5.987,1.133 10.489,0.676 12.384,-4.739 1.527,-4.36 -0.076,-6.875 -3.226,-8.515 2.294,-0.529 4.022,-2.038 4.483,-5.155 z m -8.022,11.249 c -1.085,4.36 -8.426,2.003 -10.806,1.412 l 1.928,-7.729 c 2.38,0.594 10.012,1.77 8.878,6.317 z m 1.086,-11.312 c -0.99,3.966 -7.1,1.951 -9.082,1.457 l 1.748,-7.01 c 1.982,0.494 8.365,1.416 7.334,5.553 z"
                    style={{ fill: "#ffffff" }}
                />
            </g>
        </svg>
    );
}

function EthIcon() {
    return (
        <svg
            width="18px"
            height="28px"
            style={{ margin: "0 5px" }}
            viewBox="0 0 256 417"
            version="1.1"
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="xMidYMid">
            <g>
                <polygon
                    fill="#343434"
                    points="127.9611 0 125.1661 9.5 125.1661 285.168 127.9611 287.958 255.9231 212.32"
                />
                <polygon
                    fill="#8C8C8C"
                    points="127.962 0 0 212.32 127.962 287.959 127.962 154.158"
                />
                <polygon
                    fill="#3C3C3B"
                    points="127.9611 312.1866 126.3861 314.1066 126.3861 412.3056 127.9611 416.9066 255.9991 236.5866"
                />
                <polygon
                    fill="#8C8C8C"
                    points="127.962 416.9052 127.962 312.1852 0 236.5852"
                />
                <polygon
                    fill="#141414"
                    points="127.9611 287.9577 255.9211 212.3207 127.9611 154.1587"
                />
                <polygon
                    fill="#393939"
                    points="0.0009 212.3208 127.9609 287.9578 127.9609 154.1588"
                />
            </g>
        </svg>
    );
}

function GrtIcon() {
    return (
        <svg
            version="1.1"
            className="grt-icon"
            id="GRT"
            xmlns="http://www.w3.org/2000/svg"
            x="0px"
            y="0px"
            viewBox="0 0 96 96">
            <circle class="st0" cx="48" cy="48" r="48" />
            <g id="Symbols">
                <g transform="translate(-88.000000, -52.000000)">
                    <path
                        id="Fill-19"
                        class="st1"
                        d="M135.3,106.2c-7.1,0-12.8-5.7-12.8-12.8c0-7.1,5.7-12.8,12.8-12.8c7.1,0,12.8,5.7,12.8,12.8
           C148.1,100.5,142.4,106.2,135.3,106.2 M135.3,74.2c10.6,0,19.2,8.6,19.2,19.2s-8.6,19.2-19.2,19.2c-10.6,0-19.2-8.6-19.2-19.2
           S124.7,74.2,135.3,74.2z M153.6,113.6c1.3,1.3,1.3,3.3,0,4.5l-12.8,12.8c-1.3,1.3-3.3,1.3-4.5,0c-1.3-1.3-1.3-3.3,0-4.5l12.8-12.8
           C150.3,112.3,152.4,112.3,153.6,113.6z M161,77.4c0,1.8-1.4,3.2-3.2,3.2c-1.8,0-3.2-1.4-3.2-3.2s1.4-3.2,3.2-3.2
           C159.5,74.2,161,75.6,161,77.4z"
                    />
                </g>
            </g>
        </svg>
    );
}

function PatreonIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 180 180"
            className="patreon-icon">
            <path
                fill="#ffffff"
                d="M108.8135992 26.06720125c-26.468266 0-48.00213212 21.53066613-48.00213212 47.99733213 0 26.38653268 21.53386613 47.85426547 48.00213213 47.85426547 26.38639937 0 47.8530655-21.4677328 47.8530655-47.85426547 0-26.466666-21.46666613-47.99733213-47.85306547-47.99733213"
            />
            <path
                fill="#ffffff"
                d="M23.333335 153.93333178V26.0666679h23.46666576v127.8666639z"
            />
        </svg>
    );
}

function PaypalIcon() {
    return (
        <svg
            height="512"
            id="Layer_1"
            version="1.1"
            viewBox="0 0 512 512"
            width="16"
            height="16"
            xmlns="http://www.w3.org/2000/svg"
            className="paypal-icon">
            <defs id="defs12" />
            <g id="g3902" transform="translate(297.22034,0)">
                <g id="g4245" transform="matrix(1.5,0,0,1.5,-1577.2207,-616.58906)">
                    <path
                        d="m 1137.6643,497.07514 c 10.8261,19.37702 7.252,42.20175 2.9945,55.70278 -23.0796,73.52807 -127.1776,69.52647 -142.23964,69.52647 -15.04761,0 -18.54361,13.68395 -18.54361,13.68395 l -11.2536,47.86708 c -3.05925,16.7915 -18.68234,15.96837 -18.68234,15.96837 0,0 -20.29778,0 -33.88204,0 -0.85294,0 -1.64833,-0.0647 -2.38205,-0.16031 -0.16854,3.07879 0.27129,12.05412 11.56496,12.05412 13.57193,0 33.86972,0 33.86972,0 0,0 15.62308,0.84882 18.69364,-15.94268 l 11.24538,-47.86914 c 0,0 3.5145,-13.69011 18.55188,-13.69011 15.0291,0 119.1672,4.00777 142.2396,-69.51825 5.1546,-16.42978 9.336,-46.62263 -12.1764,-67.62228 z"
                        id="path11"
                    />
                    <path
                        d="m 958.16375,673.42085 11.25359,-47.87531 c 0,0 3.48881,-13.67058 18.55184,-13.67058 15.02912,0 119.15182,3.98002 142.21082,-69.52751 8.4595,-26.87256 14.315,-90.61553 -90.8128,-90.61553 h -75.92245 c 0,0 -15.78956,-0.71421 -19.68326,15.65391 l -49.62947,208.89595 c 0,0 -2.12309,13.09408 11.45295,13.09408 13.58426,0 33.89335,0 33.89335,0 0,0 15.62617,0.84369 18.68543,-15.95501 z m 28.62262,-121.50512 10.08518,-42.46996 c 0,0 3.21135,-11.53928 13.58015,-13.24515 10.3709,-1.72333 28.0194,0.29288 32.5821,1.13965 29.4817,5.40329 23.206,32.62217 23.206,32.62217 -5.8462,42.025 -72.88172,36.1788 -72.88172,36.1788 -10.50959,-3.69537 -6.57171,-14.22551 -6.57171,-14.22551 z"
                        id="path13"
                    />
                </g>
            </g>
        </svg>
    );
}

export default DonateWidget;
