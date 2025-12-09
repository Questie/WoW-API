---@meta _
ItemLocation = {}

---@class ItemLocation : ItemLocationData, ItemLocationMixin

---@class ItemLocationData
---@field equipmentSlotIndex? number
---@field bagID? number
---@field slotIndex? number

---@class ItemLocationMixin
---[Documentation](https://warcraft.wiki.gg/wiki/ItemLocationMixin)
ItemLocationMixin = {}

function ItemLocationMixin:Clear() end

