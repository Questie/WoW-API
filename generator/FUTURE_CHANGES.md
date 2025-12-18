# Extract Frame/Button/etc names as globals
Parse all the XMLs and extract the name of frames.
All frames are global if they have a name.
Basically anything that contains the regex 'name="(\w.*?)"' is a global.
```xml
<Frame name="WorldMapFrame" inherits="WorldMapFrameTemplate" parent="UIParent" ignoreParentScale="true" frameBuffer="true">
```

We take the "type" `Frame` and the name `WorldMapFrame`

```lua
---@meta _

---@class WorldMapFrame : Frame
local WorldMapFrame = {}
```

Bonus:

We should create a inheritence tree to look for any `mixin=".*?"`

For example:
```xml
<Frame name="WorldMapFrame" inherits="WorldMapFrameTemplate" parent="UIParent" ignoreParentScale="true" frameBuffer="true"> <!-- This is a real frame that inherits a virtual frame -->

<Frame name="WorldMapFrameTemplate" inherits="MapCanvasFrameTemplate" mixin="WorldMapMixin" virtual="true"> <!-- This is virtual so it is not actually a frame but can be used as a template so "not a global" -->
<!-- PS. the "inherits can contain mulitple frames for example `inherits="Template1, Template2"`
```

```lua
---@meta _

---@class WorldMapFrame : Frame, WorldMapMixin
local WorldMapFrame = {}

```

It should be fully recursive parsing all trees and mixing them into one big inheritance if they exist.

```lua
---@meta _

---@class ExampleFrame : Frame, Mixin1, MixinFromAnotherTemplate, Mixin4
local ExampleFrame = {}

```
