# WoW API Developer support

This repository is a combination of multiple sources of the API found in World of Warcraft.

It focuses almost exclusively on the "Classic" / "Era" API.
In Cata / MoP clients more modern functions exists which are more in line with how Retail looks and works.
This creates a small problem with most developer tools only supporting the newer functions but Questie due to being a project from the start still use some of these older functions.

# Sources

## Blizzard Interface Code
`https://github.com/BigWigsMods/WoWUI.git`

## Ketho vscode-wow-api extension data
`https://github.com/Ketho/vscode-wow-api.git`

## Warcraft Wiki data
`https://warcraft.wiki.gg/wiki/World_of_Warcraft_API/Classic`
Here we fetch the functions that are specific for Classic/Era which are missing or incomplete in Kethos project


# Flow
**(Step 1 does not yet exist in the repo)**
1. Generate data for missing functions
<https://warcraft.wiki.gg/wiki/World_of_Warcraft_API/Classic>
Looks at the list
Vanilla & MoP to find the missing functions such as "AbandonQuest" which is not under C_QuestLog
I just copied the list through HTML and created the list in 

2. Clone external Libraries

```bash
  bash generator/clone.sh
```

3. Generate data from the cloned repositories

```bash
  python WoWUI-generator.py --version Classic
```