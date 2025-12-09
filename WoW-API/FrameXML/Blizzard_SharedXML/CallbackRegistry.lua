---@meta _
---@class CallbackRegistryMixin
CallbackRegistryMixin = {}

function CallbackRegistryMixin:SetUndefinedEventsAllowed(allowed) end

function CallbackRegistryMixin:SecureInsertEvent(event) end

function CallbackRegistryMixin:TriggerEvent(event, ...) end

function CallbackRegistryMixin:UnregisterCallback(event, owner) end

function CallbackRegistryMixin:UnregisterEvents(eventTable) end

function CallbackRegistryMixin:GenerateCallbackEvents(events) end

function CallbackRegistryMixin:OnLoad() end
