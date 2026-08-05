-- license:BSD-3-Clause
-- Read-only MAME diagnostic for a verified Polybolos partition-authority frame.
local exports = {
  name = "polybolospartition",
  version = "0.1.0",
  description = "Polybolos signed partition-authority cabinet frame",
  license = "BSD-3-Clause",
  author = { name = "AXM / Polybolos integration lane" },
}

local plugin = exports
local json = require("json")
local frame_path = os.getenv("POLYBOLOS_PARTITION_CABINET_FRAME") or "polybolos-partition-cabinet-frame.json"
local frame = nil
local load_error = nil
local reset_subscription = nil
local maximum_bytes = 1024 * 1024

local function bounded(value, fallback, maximum)
  local text = tostring(value or fallback or "")
  if #text > maximum then return string.sub(text, 1, maximum) end
  return text
end

local function starts_with(value, prefix)
  return type(value) == "string" and string.sub(value, 1, #prefix) == prefix
end

local function is_hex64(value)
  return type(value) == "string" and #value == 64 and string.match(value, "^[0-9a-f]+$") ~= nil
end

local forbidden_keys = {
  payload = true,
  signature = true,
  privatekey = true,
  command = true,
  targeting = true,
  engagement = true,
  effector = true,
  execute = true,
  actuation = true,
  weapon = true,
}

local function normalized_key(value)
  return string.lower(string.gsub(tostring(value or ""), "[^%w]", ""))
end

local function no_forbidden_keys(value, depth)
  if depth > 12 then return false, "frame nesting exceeds bound" end
  if type(value) ~= "table" then return true, nil end
  for key, nested in pairs(value) do
    local normalized = normalized_key(key)
    if forbidden_keys[normalized] then
      return false, "forbidden frame key: " .. tostring(key)
    end
    local valid, reason = no_forbidden_keys(nested, depth + 1)
    if not valid then return false, reason end
  end
  return true, nil
end

local valid_modes = { candidate = true, reconciliation = true }
local valid_dispositions = {
  allow = true,
  hold = true,
  refuse = true,
  safe_state = true,
  explicitly_superseded = true,
  human_required = true,
}

local function validate_frame(parsed)
  if type(parsed) ~= "table" then return false, "frame is not an object" end
  if parsed.schema ~= "polybolos-partition-cabinet-frame/1" then
    return false, "unsupported frame schema"
  end
  if not starts_with(parsed.frameId, "partitionframe1_") or not starts_with(parsed.stateId, "partitionstate1_") then
    return false, "invalid frame identity"
  end
  if not valid_modes[parsed.mode] or not valid_dispositions[parsed.disposition] then
    return false, "invalid mode or disposition"
  end
  if type(parsed.profileId) ~= "string" or type(parsed.reasonCode) ~= "string" then
    return false, "profile or reason is missing"
  end
  if type(parsed.links) ~= "table" or type(parsed.lease) ~= "table" or type(parsed.lamps) ~= "table" then
    return false, "topology, lease, or lamps are missing"
  end
  if type(parsed.verification) ~= "table" or parsed.verification.signedJournal ~= true then
    return false, "signed journal verification is missing"
  end
  if type(parsed.evidence) ~= "table" then return false, "evidence is missing" end
  if not starts_with(parsed.evidence.recordId, "partitionrecord1_") then
    return false, "signed record identity is missing"
  end
  if not is_hex64(parsed.evidence.journalSha256) then
    return false, "journal digest is invalid"
  end
  if type(parsed.evidence.recordSequence) ~= "number" or parsed.evidence.recordSequence < 1 then
    return false, "signed record sequence is invalid"
  end
  local valid, reason = no_forbidden_keys(parsed, 0)
  if not valid then return false, reason end
  return true, nil
end

local function load_frame()
  local file = io.open(frame_path, "r")
  if not file then
    frame = nil
    load_error = "frame unavailable"
    return false
  end
  local content = file:read("*a")
  file:close()
  if #content > maximum_bytes then
    frame = nil
    load_error = "frame exceeds local bound"
    return false
  end
  local ok, parsed = pcall(json.parse, content)
  if not ok then
    frame = nil
    load_error = "invalid JSON frame"
    return false
  end
  local valid, reason = validate_frame(parsed)
  if not valid then
    frame = nil
    load_error = reason
    return false
  end
  frame = parsed
  load_error = nil
  return true
end

local function lamp(name)
  if frame and frame.lamps and frame.lamps[name] then return "ON" end
  return "off"
end

local function link_state(name)
  if frame and frame.links then return bounded(frame.links[name], "unknown", 20) end
  return "unknown"
end

local function lease_text()
  if not frame or not frame.lease then return "unavailable" end
  if not frame.lease.partitioned then return "connected" end
  return tostring(frame.lease.elapsedMs or "?") .. " / " .. tostring(frame.lease.maxOfflineMs or "?") .. " ms"
end

local function remaining_text()
  if not frame or not frame.lease or frame.lease.remainingMs == nil then return "n/a" end
  return tostring(frame.lease.remainingMs) .. " ms"
end

local function menu_populate()
  local rows = {
    { "Refresh local partition frame", load_error or "ready", 0 },
    { "Frame path", bounded(frame_path, "", 72), "off" },
  }
  if not frame then
    rows[#rows + 1] = { "Partition authority", load_error or "no frame", "off" }
    return rows
  end

  rows[#rows + 1] = { "State", bounded(frame.stateId, "unknown", 34), "off" }
  rows[#rows + 1] = { "Capture", bounded(frame.frameId, "unknown", 34), "off" }
  rows[#rows + 1] = { "Mode", bounded(frame.mode, "unknown", 24), "off" }
  rows[#rows + 1] = { "Profile", bounded(frame.profileId, "unknown", 36), "off" }
  rows[#rows + 1] = { "Disposition", bounded(frame.disposition, "unknown", 28), "off" }
  rows[#rows + 1] = { "Reason", bounded(frame.reasonCode, "unknown", 48), "off" }
  rows[#rows + 1] = { "Headquarters link", link_state("headquarters"), "off" }
  rows[#rows + 1] = { "Local control link", link_state("local-control"), "off" }
  rows[#rows + 1] = { "Lease elapsed / max", lease_text(), "off" }
  rows[#rows + 1] = { "Lease remaining", remaining_text(), "off" }
  rows[#rows + 1] = { "Candidate eligible", lamp("candidateEligible"), "off" }
  rows[#rows + 1] = { "Safe state", lamp("safeState"), "off" }
  rows[#rows + 1] = { "Lease warning", lamp("leaseWarning"), "off" }
  rows[#rows + 1] = { "Lease expired", lamp("leaseExpired"), "off" }
  rows[#rows + 1] = { "Local operator present", lamp("localOperatorPresent"), "off" }
  rows[#rows + 1] = { "Signed evidence", lamp("signedEvidence"), "off" }
  rows[#rows + 1] = { "Reconciliation pending", lamp("reconciliationPending"), "off" }
  rows[#rows + 1] = { "Reconciliation complete", lamp("reconciliationComplete"), "off" }
  rows[#rows + 1] = { "Human disposition required", lamp("humanRequired"), "off" }
  rows[#rows + 1] = { "Signed record", tostring(frame.evidence.recordSequence or "?") .. " / " .. bounded(frame.evidence.recordId, "unknown", 28), "off" }
  rows[#rows + 1] = { "Journal", bounded(frame.evidence.journalSha256, "unknown", 24), "off" }
  rows[#rows + 1] = { "Local decisions", tostring((frame.counts and frame.counts.localDecisions) or 0), "off" }
  return rows
end

local function menu_callback(index, event)
  if index == 1 and event == "select" then
    load_frame()
    return true
  end
  return false
end

function plugin.startplugin()
  reset_subscription = emu.add_machine_reset_notifier(function()
    load_frame()
  end)
  load_frame()
  emu.register_menu(menu_callback, menu_populate, "Polybolos Partition")
end

return exports
