# Cd to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo $SCRIPT_DIR

cd "$(dirname "$0")"

# If $1 is not provided default to "Vanilla"
if [ -z "$1" ]; then
    echo "No version argument provided. Defaulting to 'Vanilla'."
    VERSION="Vanilla"
else
    VERSION="$1"
fi

echo "Cleaning up old repositories..."

rm -rf WoWUI
rm -rf vscode-wow-api

echo ""
echo "Cloning fresh repositories..."

echo ""

git clone https://github.com/BigWigsMods/WoWUI.git

echo ""

git clone --filter=blob:none --sparse --no-checkout --no-tags --depth=1 --single-branch https://github.com/Ketho/vscode-wow-api.git
cd vscode-wow-api
git sparse-checkout set --no-cone Annotations/Core
git checkout
cd $SCRIPT_DIR

echo ""
echo "Cloning complete."
echo ""

# Check if python or python3 exists
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null
then
    echo "python3 could not be found, please install python3 to continue."
    exit
fi

PYTHON_CMD="python3"
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# Run the generator script
echo "Running WoWUI-generator.py with version $VERSION..."
$PYTHON_CMD WoWUI-generator.py --version $VERSION > generate_output.log 2>&1
if [ $? -ne 0 ]; then
    echo "Generation failed. Check generate_output.log for details."
    exit 1
fi
echo "Generation complete. Check generate_output.log for details."
echo "Injecting annotations..."
$PYTHON_CMD inject_annotations.py > inject_output.log 2>&1
if [ $? -ne 0 ]; then
    echo "Annotation injection failed. Check inject_output.log for details."
    exit 1
fi
echo "Annotation injection complete. Check inject_output.log for details."

echo "Copying the finished generated API to the WoW-API folder..."
cd $SCRIPT_DIR
cp -r ./API-$VERSION/. ../WoW-API/
if [ $? -ne 0 ]; then
    echo "Copying API failed."
    exit 1
fi