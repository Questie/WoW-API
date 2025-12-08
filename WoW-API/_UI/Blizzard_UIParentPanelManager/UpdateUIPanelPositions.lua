-- Auto-generated LuaLS Annotations, do not edit manually
---@meta _
if not IsInGlobalEnvironment() then
	return;
end

UIParent:SetScript("OnAttributeChanged", UpdateUIPanelPositions);