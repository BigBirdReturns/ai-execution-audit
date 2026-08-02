local plugin_path = arg[1]
assert(plugin_path, "usage: lua smoke.lua <init.lua>")

local plugin = dofile(plugin_path)
assert(plugin.name == "c2simrehearsal")
assert(type(plugin.validate_frame) == "function")
assert(type(plugin.menu_items_for_frame) == "function")

local good = {
    schema = "standards-semantic-rehearsal-frame/1",
    frameId = "standardsemanticrehearsalframe1_abc",
    semanticConversationId = "c2simsemanticconversation1_abc",
    standardId = "siso-std-019-2020-c2sim",
    artifactUseId = "standardartifactuse1_abc",
    scenarioDigest = "standardfaultscenario1_abc",
    faultRunId = "standardfaultrun1_abc",
    faultJournalRoot = "standardfaultrecord1_abc",
    faultFrameId = "standardporttestframe1_abc",
    authorityProfileId = "c2sim-semantic-rehearsal-authority/1",
    authorityGeneration = 1,
    partitionEpochId = "standardmessagepartitionepoch1_abc",
    reconciliationId = "standardmessagereconciliation1_abc",
    reconciliationStatus = "explicitly_superseded",
    status = "reconciled",
    messages = {
        schemaValid = 4,
        authorityAllowed = 4,
        receiverAccepted = 4,
        receiverRefused = 1,
        replayRefused = 1
    },
    transport = {
        sentPackets = 4,
        deliveredCopies = 5,
        deliveredUniquePackets = 4,
        droppedPackets = 0,
        explicitDrops = 0,
        linkDownDrops = 0,
        queueCapacityDrops = 0,
        duplicateExtraCopies = 1,
        delayedPackets = 1,
        bufferedPackets = 1,
        pendingDelayedPackets = 0,
        pendingBufferedPackets = 0,
        reordered = true,
        finalLinkState = "up"
    },
    lastEvent = {
        recordId = "standardfaultrecord1_last",
        step = 6,
        type = "deliver"
    },
    hostContracts = {
        {
            host = "mame",
            mode = "read_only",
            inputs = { "select_fixture", "step", "reset_rehearsal" },
            outputs = { "transport_metrics", "authority_dispositions" }
        },
        {
            host = "motiondeck",
            mode = "read_only",
            inputs = { "select_fixture", "step", "reset_rehearsal" },
            outputs = { "transport_metrics", "authority_dispositions" }
        }
    },
    claimBoundary = "read-only fixture"
}

local valid, reason = plugin.validate_frame(good)
assert(valid, reason)
local items = plugin.menu_items_for_frame(good)
assert(#items == 16)
assert(items[2][2] == "RECONCILED")
assert(items[7][2] == "1")
assert(items[12][2] == "EXPLICITLY_SUPERSEDED")
assert(items[15][2] == "READ-ONLY RECEIPT")

local wrong_schema = {}
for key, value in pairs(good) do wrong_schema[key] = value end
wrong_schema.schema = "invented-frame/1"
assert(not plugin.validate_frame(wrong_schema))

local bad_counter = {}
for key, value in pairs(good) do bad_counter[key] = value end
bad_counter.messages = {
    schemaValid = -1,
    authorityAllowed = 4,
    receiverAccepted = 4,
    receiverRefused = 1,
    replayRefused = 1
}
assert(not plugin.validate_frame(bad_counter))

local bad_host = {}
for key, value in pairs(good) do bad_host[key] = value end
bad_host.hostContracts = {
    { host = "mame", mode = "read_write" },
    { host = "motiondeck", mode = "read_only" }
}
assert(not plugin.validate_frame(bad_host))

local failed_items = plugin.menu_items_for_frame(nil, "NO VERIFIED FRAME")
assert(#failed_items == 4)
assert(failed_items[2][2] == "NO VERIFIED FRAME")
assert(failed_items[3][2] == "NONE")

print("MAME_C2SIM_REHEARSAL_SMOKE_PASS")
