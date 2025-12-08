# Cd to script directory
cd "$(dirname "$0")"

rm -rf WoWUI
rm -rf vscode-wow-api

git clone https://github.com/BigWigsMods/WoWUI.git

git clone --filter=blob:none --sparse --no-checkout --no-tags --depth=1 --single-branch https://github.com/Ketho/vscode-wow-api.git
cd vscode-wow-api
git sparse-checkout set --no-cone Annotations/Core
git checkout
cd ..