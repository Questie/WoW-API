---@meta _
--- not yet annotated, inherits NamePlateDriverMixin
---@class NamePlateDriverFrame

---@class NamePlateBaseMixin
local NamePlateBaseMixin = {}

function NamePlateBaseMixin:OnRemoved() end

function NamePlateBaseMixin:OnOptionsUpdated() end

function NamePlateBaseMixin:ApplyOffsets() end

function NamePlateBaseMixin:OnSizeChanged() end

---@class Nameplate : Frame, NamePlateBaseMixin
---@field UnitFrame Button
---@field driverFrame NamePlateDriverFrame
---@field namePlateUnitToken UnitToken
---@field template string
