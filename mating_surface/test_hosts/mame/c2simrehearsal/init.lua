-- license:BSD-3-Clause
-- copyright-holders:Jonathan Sandhu
--
-- C2SIM Semantic Rehearsal MAME projection.
--
-- This plugin reads one already-verified standards-semantic-rehearsal-frame/1
-- file and exposes a bounded menu. It owns no payload interpretation,
-- simulation, command authority, process launch, emulated memory, input,
-- networking, reconciliation, or evidence mutation.

local exports = {
    name = "c2simrehearsal",
    version = "0.1.0",
    description = "C2SIM semantic rehearsal receipt projection",
    license = "BSD-3-Clause",
    author = { name = "Jonathan Sandhu" }
}

local c2simrehearsal = exports
local plugin_path = nil
local reset_subscription = nil
local frame = nil
local frame_error = "NO VERIFIED FRAME"

local function non_negative_integer(value)
    return type(value) == "number" and value >= 0 and math.floor(value) == value
end

local function non_empty_string(value)
    return type(value) == "string" and #value > 0
end

local function validate_messages(value)
    return type(value) == "table"
        and non_negative_integer(value.schemaValid)
        and non_negative_integer(value.authorityAllowed)
        and non_negative_integer(value.receiverAccepted)
        and non_negative_integer(value.receiverRefused)
        and non_negative_integer(value.replayRefused)
end

local function validate_transport(value)
    return type(value) == "table"
        and non_negative_integer(value.sentPackets)
        and non_negative_integer(value.deliveredCopies)
        and non_negative_integer(value.deliveredUniquePackets)
        and non_negative_integer(value.droppedPackets)
        and non_negative_integer(value.duplicateExtraCopies)
        and non_negative_integer(value.delayedPackets)
        and non_negative_integer(value.bufferedPackets)
        and non_negative_integer(value.pendingDelayedPackets)
        and non_negative_integer(value.pendingBufferedPackets)
        and type(value.reordered) == "boolean"
        and (value.finalLinkState == "up" or value.finalLinkState == "down")
end

function c2simrehearsal.validate_frame(value)
    if type(value) ~= "table" then
        return false, "frame is not an object"
    end
    if value.schema ~= "standards-semantic-rehearsal-frame/1" then
        return false, "unsupported frame schema"
    end
    if not non_empty_string(value.frameId)
        or not non_empty_string(value.semanticConversationId)
        or not non_empty_string(value.standardId)
        or not non_empty_string(value.scenarioDigest)
        or not non_empty_string(value.faultRunId)
        or not non_empty_string(value.faultJournalRoot)
        or not non_empty_string(value.authorityProfileId)
        or not non_empty_string(value.partitionEpochId)
        or not non_empty_string(value.reconciliationId) then
        return false, "frame identity is incomplete"
    end
    if value.status ~= "reconciled" and value.status ~= "attention_required" then
        return false, "unsupported frame status"
    end
    if value.reconciliationStatus ~= "continuous_authority"
        and value.reconciliationStatus ~= "explicitly_superseded"
        and value.reconciliationStatus ~= "human_required" then
        return false, "unsupported reconciliation status"
    end
    if not validate_messages(value.messages) then
        return false, "message counters are invalid"
    end
    if not validate_transport(value.transport) then
        return false, "transport counters are invalid"
    end
    if type(value.hostContracts) ~= "table" or #value.hostContracts ~= 2 then
        return false, "host contracts are missing"
    end
    local hosts = { }
    for _, contract in ipairs(value.hostContracts) do
        if type(contract) ~= "table" or contract.mode ~= "read_only" then
            return false, "host contract is not read-only"
        end
        hosts[contract.host] = true
    end
    if not hosts.mame or not hosts.motiondeck then
        return false, "required host contracts are missing"
    end
    return true, nil
end

local function shorten(value, limit)
    if not non_empty_string(value) then
        return "-"
    end
    if #value <= limit then
        return value
    end
    return value:sub(1, limit - 3) .. "..."
end

function c2simrehearsal.menu_items_for_frame(value, error_message)
    local ok, validation_error = c2simrehearsal.validate_frame(value)
    if not ok then
        return {
            { "C2SIM Semantic Rehearsal", "v0.1.0", "off" },
            { "Receipt state", error_message or validation_error or "NO VERIFIED FRAME", "off" },
            { "Authority", "NONE", "off" },
            { "Reload local frame", "", "off" }
        }
    end
    return {
        { "C2SIM Semantic Rehearsal", "v0.1.0", "off" },
        { "Receipt state", string.upper(value.status), "off" },
        { "Standard", shorten(value.standardId, 38), "off" },
        { "Schema-valid messages", tostring(value.messages.schemaValid), "off" },
        { "Receiver accepted", tostring(value.messages.receiverAccepted), "off" },
        { "Receiver refused", tostring(value.messages.receiverRefused), "off" },
        { "Replay refused", tostring(value.messages.replayRefused), "off" },
        { "Delivered copies", tostring(value.transport.deliveredCopies), "off" },
        { "Dropped packets", tostring(value.transport.droppedPackets), "off" },
        { "Buffered packets", tostring(value.transport.bufferedPackets), "off" },
        { "Final link", string.upper(value.transport.finalLinkState), "off" },
        { "Reconciliation", string.upper(value.reconciliationStatus), "off" },
        { "Conversation", shorten(value.semanticConversationId, 38), "off" },
        { "Frame", shorten(value.frameId, 38), "off" },
        { "Authority", "READ-ONLY RECEIPT", "off" },
        { "Reload local frame", "", "off" }
    }
end

function c2simrehearsal.set_folder(path)
    plugin_path = path
end

local function load_frame()
    frame = nil
    frame_error = "NO VERIFIED FRAME"
    if not plugin_path then
        frame_error = "PLUGIN PATH UNAVAILABLE"
        return false
    end
    local file = io.open(plugin_path .. "/semantic-host-frame.json", "r")
    if not file then
        frame_error = "FRAME FILE MISSING"
        return false
    end
    local encoded = file:read("a")
    file:close()
    local json = require("json")
    local parse_ok, parsed = pcall(json.parse, encoded)
    if not parse_ok or parsed == nil then
        frame_error = "FRAME JSON INVALID"
        return false
    end
    local valid, validation_error = c2simrehearsal.validate_frame(parsed)
    if not valid then
        frame_error = string.upper(validation_error or "FRAME INVALID")
        return false
    end
    frame = parsed
    frame_error = nil
    return true
end

function c2simrehearsal.startplugin()
    load_frame()

    reset_subscription = emu.add_machine_reset_notifier(function()
        load_frame()
    end)

    local function populate_menu()
        return c2simrehearsal.menu_items_for_frame(frame, frame_error)
    end

    local function handle_menu(index, event)
        local items = populate_menu()
        if event == "select" and index == #items then
            load_frame()
            if frame then
                emu.print_info("C2SIM semantic rehearsal frame reloaded")
            else
                emu.print_error("C2SIM semantic rehearsal frame refused: " .. tostring(frame_error))
            end
            return true
        end
        return false
    end

    emu.register_menu(handle_menu, populate_menu, "C2SIM Semantic Rehearsal")
end

return exports
