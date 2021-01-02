const path = require("path");

module.exports = {
    output: {
        path: path.resolve(__dirname, "scripts"),
        publicPath: "/scripts/",
        filename: "bundle.js"
    },
    module: {
        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules/,
                use: {
                    loader: "babel-loader",
                    options: {
                        presets: [
                            ["@babel/preset-env", { modules: "commonjs" }],
                            "@babel/preset-react"
                        ],
                        plugins: [
                            "@babel/plugin-proposal-class-properties",
                            "@babel/plugin-proposal-object-rest-spread",
                            "@babel/plugin-syntax-dynamic-import",
                            "@babel/plugin-transform-runtime",
                            "@babel/plugin-proposal-optional-chaining"
                        ]
                    }
                }
            },
            {
                test: /\.s[ac]ss$/i,
                use: [
                    // Creates `style` nodes from JS strings
                    "style-loader",
                    // Translates CSS into CommonJS
                    "css-loader",
                    // Compiles Sass to CSS
                    "sass-loader"
                ]
            }
        ]
    }
};
