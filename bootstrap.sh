#!/bin/bash
function version { echo "$@" | awk -F. '{ printf("%d%03d%03d%03d\n", $1,$2,$3,$4); }'; }

if [ ! command -v npm &> /dev/null ] || [ $(version $($(echo node -v) | sed -e s/^v//)) -lt 14000000000 ]
then
    echo "Node.js v14+ is required to build BCML but was not found"
    exit
fi

if [ ! command -v pip3 &> /dev/null ] || [ $(version $(python3 -V | sed -e s/^Python\ //)) -lt 3007000000 ]
then
    echo "Python 3.7+ is required to build BCML but was not found"
    exit
fi

if [ ! command -v cargo &> /dev/null ] || [ $(version $(cargo -V | sed -e s/^cargo\ //)) -lt 1060000000 ]
then
    echo "Cargo 1.60+ is required to build BCML but was not found"
    exit
fi

echo "Creating Python virtual environment..."
python3 -m venv venv >/dev/null
source venv/bin/activate

echo "Installing Python dependencies..."
pip3 install --disable-pip-version-check mkdocs mkdocs-material setuptools wheel pyqtwebengine maturin >/dev/null
pip3 install --disable-pip-version-check -r requirements.txt >/dev/null

echo "Building docs..."
mkdocs build -q -d bcml/assets/help >/dev/null

echo "Installing npm packages..."
export NODE_OPTIONS=--openssl-legacy-provider
cd bcml/assets
npm install --loglevel=error >/dev/null
echo "Building webpack bundle..."
npm run build --loglevel=error >/dev/null
cd ../../

echo "Compiling Rust extension module..."
maturin develop --cargo-extra-args="--quiet" >/dev/null

echo "Done! You are now ready to work on BCML."
echo "You can run with \`python -m bcml\` or build an installable wheel with \`maturin build\`."