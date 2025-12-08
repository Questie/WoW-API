-- Auto-generated LuaLS Annotations, do not edit manually
---@meta _

function ConvertPixelsToUI(pixels, frameScale)
	local physicalScreenHeight = select(2, GetPhysicalScreenSize());
	return (pixels * 768.0)/(physicalScreenHeight * frameScale);
end