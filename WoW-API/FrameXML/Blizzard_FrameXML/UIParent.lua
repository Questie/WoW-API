---@meta _

---@class UIParent : Frame
---@field firstTimeLoaded number
---@field variablesLoaded boolean
UIParent = {}

---[FrameXML](https://www.townlong-yak.com/framexml/go/ShowUIPanel)
---@param frame Frame
---@param force? number
function ShowUIPanel(frame, force) end

---[FrameXML](https://www.townlong-yak.com/framexml/go/AbbreviateNumbers)
---@param value number
---@return string
function AbbreviateNumbers(value) end
