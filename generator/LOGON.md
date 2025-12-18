# How i run it in one command

`cd /d/Projekt/WoW-API/generator && rm -rf API-Vanilla && uv run WoWUI-generator.py --version Vanilla > output.txt && uv run inject_annotations.py > output_inject.txt && rm -rf ../WoW-API/FrameXML && rm -rf ../WoW-API/_UI && cp -r API-Vanilla/* ../WoW-API/`