-- Auto-generated LuaLS Annotations, do not edit manually
---@meta _
function TogglePVPFrame()
	if ( PVEFrame:IsShown() and PVPQueueFrame and PVPQueueFrame:IsShown() ) then
		HideUIPanel(PVEFrame);
	else
		ShowPVPQueueUI();
	end
	UpdateMicroButtons();
end
