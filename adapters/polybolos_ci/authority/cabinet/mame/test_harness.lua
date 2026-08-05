-- Standalone Lua harness for the read-only partition-authority MAME plugin.
-- Requires lua-dkjson only in the CI venue. MAME supplies its own json module.
local plugin_path = assert(arg[1], "plugin path required")
local expected_mode = assert(arg[2], "expected mode required")
local expected_disposition = assert(arg[3], "expected disposition required")

package.preload["json"] = function()
  local dkjson = require("dkjson")
  return {
    parse = function(text)
      local value, _, err = dkjson.decode(text, 1, nil)
      if err then error(err) end
      return value
    end,
  }
end

local menu_callback = nil
local menu_populate = nil
local menu_title = nil
_G.emu = {
  add_machine_reset_notifier = function(fn)
    return fn
  end,
  register_menu = function(callback, populate, title)
    menu_callback = callback
    menu_populate = populate
    menu_title = title
  end,
}

local loader, load_error = loadfile(plugin_path)
assert(loader, load_error)
local plugin = loader()
assert(type(plugin) == "table", "plugin did not return exports")
assert(plugin.name == "polybolospartition", "wrong plugin name")
assert(plugin.version == "0.1.0", "wrong plugin version")
plugin.startplugin()
assert(menu_title == "Polybolos Partition", "menu was not registered")
assert(type(menu_callback) == "function" and type(menu_populate) == "function", "menu callbacks missing")

local rows = menu_populate()
assert(type(rows) == "table" and #rows >= 20, "qualified partition frame did not populate the menu")
local found_state = false
local found_mode = false
local found_disposition = false
local found_signed = false
for index, row in ipairs(rows) do
  assert(type(row) == "table", "menu row is not a table")
  local label = tostring(row[1] or "")
  local status = tostring(row[2] or "")
  if label == "State" and string.find(status, "partitionstate1_", 1, true) == 1 then found_state = true end
  if label == "Mode" and status == expected_mode then found_mode = true end
  if label == "Disposition" and status == expected_disposition then found_disposition = true end
  if label == "Signed evidence" and status == "ON" then found_signed = true end
  local combined = string.lower(label .. " " .. status)
  for _, forbidden in ipairs({
    "fire",
    "targeting",
    "engagement",
    "effector",
    "execute",
    "actuate",
    "weapon release",
    "process launch",
  }) do
    assert(not string.find(combined, forbidden, 1, true), "forbidden authority term crossed into the MAME menu")
  end
  if index > 1 then
    assert(menu_callback(index, "select") == false, "non-refresh menu row gained a control action")
  end
end
assert(found_state, "semantic partition state identity was not visible")
assert(found_mode, "expected partition frame mode was not visible")
assert(found_disposition, "expected partition disposition was not visible")
assert(found_signed, "signed evidence lamp was not visible")
assert(menu_callback(1, "select") == true, "refresh did not remain local and read-only")
print("POLYBOLOS_PARTITION_MAME_FRAME_PASS")
