----------------------------------------------------------------------
-- MythicPlusTracker - Lightweight M+ data collector
-- Saves run data to SavedVariables for external companion app import
----------------------------------------------------------------------

local addonName = "MythicPlusTracker"
local frame = CreateFrame("Frame")
local currentRun = nil
local inspectQueue = {}
local inspectIndex = 0
local playedTime = nil

-- Saved variable (persisted between sessions)
MythicPlusTrackerDB = MythicPlusTrackerDB or { runs = {}, version = 1 }

----------------------------------------------------------------------
-- Utility functions
----------------------------------------------------------------------

local function Print(msg)
    DEFAULT_CHAT_FRAME:AddMessage("|cff00ccff[M+Tracker]|r " .. msg)
end

local function GetAverageDurability()
    local total, count = 0, 0
    for slot = 1, 19 do -- INVSLOT_HEAD through INVSLOT_TABARD
        local current, maximum = GetInventoryItemDurability(slot)
        if current and maximum and maximum > 0 then
            total = total + (current / maximum * 100)
            count = count + 1
        end
    end
    if count == 0 then return nil end
    return math.floor(total / count * 10) / 10 -- round to 1 decimal
end

local function GetMyMountName()
    -- Check if mounted and find active mount
    if not IsMounted() then return nil end
    local mountIDs = C_MountJournal.GetMountIDs()
    for _, mountID in ipairs(mountIDs) do
        local name, spellID, icon, isActive = C_MountJournal.GetMountInfoByID(mountID)
        if isActive then
            return name
        end
    end
    return nil
end

local function GetCompanionPetName()
    local petID = C_PetJournal.GetSummonedPetGUID()
    if not petID then return nil end
    local speciesID, customName, level, xp, maxXp, displayID, isFavorite,
          name = C_PetJournal.GetPetInfoByPetID(petID)
    return customName or name
end

local function GetPlayerTitle()
    local titleIndex = GetCurrentTitle()
    if titleIndex and titleIndex > 0 then
        local titleName = GetTitleName(titleIndex)
        if titleName then
            return titleName:gsub("^%s+", ""):gsub("%s+$", "") -- trim
        end
    end
    return nil
end

local function GetUnitMountFromAuras(unit)
    -- Scan buffs for mount aura and try to get the mount spell name
    for i = 1, 40 do
        local name, _, _, _, _, _, _, _, _, _, spellId = UnitBuff(unit, i)
        if not name then break end
        -- Check for known mount aura spell ID (164557) or any spell that
        -- gives a mount buff. The specific mount spell is usually the first
        -- HELPFUL aura that matches a mount.
        if spellId == 164557 then
            -- Generic mounted aura - player is mounted but we can't tell which
            return "Mounted (unknown)"
        end
    end
    -- Try checking if they're actually mounted via movement speed
    return nil
end

----------------------------------------------------------------------
-- Group member scanning
----------------------------------------------------------------------

local function ScanGroupMembers()
    local members = {}
    local numGroup = GetNumGroupMembers()
    if numGroup == 0 then numGroup = 1 end

    for i = 1, numGroup do
        local unit
        if i == 1 or numGroup == 1 then
            unit = "player"
        else
            unit = "party" .. (i - 1)
        end

        if UnitExists(unit) then
            local name, realm = UnitName(unit)
            realm = realm or GetRealmName() -- nil if same server
            local _, classFile = UnitClass(unit)
            local _, raceName = UnitRace(unit)
            local role = UnitGroupRolesAssigned(unit) -- TANK, HEALER, DAMAGER, NONE
            if role == "NONE" then role = "DAMAGER" end

            local spec = nil
            local ilvl = nil
            local guild = nil
            local mount = nil

            -- For the player, we can get spec and ilvl directly
            if UnitIsUnit(unit, "player") then
                local specIndex = GetSpecialization()
                if specIndex then
                    local _, specName = GetSpecializationInfo(specIndex)
                    spec = specName
                end
                local _, equipped = GetAverageItemLevel()
                ilvl = math.floor(equipped)
                mount = GetMyMountName()
            else
                -- For others, we'll get spec/ilvl via inspect (queued below)
                mount = GetUnitMountFromAuras(unit)
            end

            -- Guild info (works for nearby units)
            local guildName = GetGuildInfo(unit)

            -- Title
            local title = nil
            if UnitIsUnit(unit, "player") then
                title = GetPlayerTitle()
            else
                local pvpName = UnitPVPName(unit)
                if pvpName and pvpName ~= name then
                    title = pvpName
                end
            end

            local member = {
                name = name,
                realm = realm,
                class = classFile, -- English class token like "DRUID"
                race = raceName,   -- English race token like "NightElf"
                spec = spec,
                role = role,
                ilvl = ilvl,
                guild = guildName,
                title = title,
                mount = mount,
                isMe = UnitIsUnit(unit, "player"),
                unit = unit, -- temp, for inspect queue
            }
            table.insert(members, member)

            -- Queue inspection for non-player party members
            if not UnitIsUnit(unit, "player") then
                table.insert(inspectQueue, member)
            end
        end
    end

    return members
end

----------------------------------------------------------------------
-- Buff scanning (flask, food, rune)
----------------------------------------------------------------------

-- Common buff categories to check
local FLASK_BUFFS = {} -- Will match by name containing "Flask"
local FOOD_BUFFS = {}  -- Will match by name containing "Well Fed"

local function ScanGroupBuffs(members)
    local buffCheck = { flask = {}, food = {}, rune = {} }

    for _, member in ipairs(members) do
        local unit = member.unit or "player"
        if not UnitExists(unit) then break end

        for i = 1, 40 do
            local name, _, _, _, _, _, _, _, _, _, spellId = UnitBuff(unit, i)
            if not name then break end

            local lowerName = name:lower()
            if lowerName:find("flask") or lowerName:find("phial") then
                table.insert(buffCheck.flask, member.name)
                break -- one flask per person
            end
        end

        for i = 1, 40 do
            local name = UnitBuff(unit, i)
            if not name then break end
            local lowerName = name:lower()
            if lowerName:find("well fed") or lowerName:find("food") then
                table.insert(buffCheck.food, member.name)
                break
            end
        end

        for i = 1, 40 do
            local name = UnitBuff(unit, i)
            if not name then break end
            local lowerName = name:lower()
            if lowerName:find("rune") and not lowerName:find("runeb") then
                table.insert(buffCheck.rune, member.name)
                break
            end
        end
    end

    return buffCheck
end

----------------------------------------------------------------------
-- Inspect queue (staggered to avoid throttle)
----------------------------------------------------------------------

local function ProcessInspectQueue()
    if #inspectQueue == 0 then return end

    inspectIndex = inspectIndex + 1
    if inspectIndex > #inspectQueue then return end

    local member = inspectQueue[inspectIndex]
    if member.unit and UnitExists(member.unit) and CanInspect(member.unit) then
        NotifyInspect(member.unit)
    else
        -- Skip and try next
        C_Timer.After(0.5, ProcessInspectQueue)
    end
end

----------------------------------------------------------------------
-- Affix name lookup
----------------------------------------------------------------------

local function GetAffixNames(affixIDs)
    local names = {}
    if not affixIDs then return names end
    for _, id in ipairs(affixIDs) do
        local affixName = C_ChallengeMode.GetAffixInfo(id)
        if affixName then
            table.insert(names, affixName)
        end
    end
    return names
end

----------------------------------------------------------------------
-- Event handlers
----------------------------------------------------------------------

local function OnAddonLoaded(loadedAddon)
    if loadedAddon ~= addonName then return end
    MythicPlusTrackerDB = MythicPlusTrackerDB or { runs = {}, version = 1 }
    if not MythicPlusTrackerDB.runs then
        MythicPlusTrackerDB.runs = {}
    end
    Print("Loaded. " .. #MythicPlusTrackerDB.runs .. " run(s) saved.")
end

local function OnChallengeModeStart()
    -- Get dungeon info
    local mapID = C_ChallengeMode.GetActiveChallengeMapID()
    if not mapID then return end

    local mapName, _, timeLimit = C_ChallengeMode.GetMapUIInfo(mapID)
    local keystoneLevel, affixIDs = C_ChallengeMode.GetActiveKeystoneInfo()

    -- Request /played (async, handled in TIME_PLAYED_MSG)
    playedTime = nil
    RequestTimePlayed()

    -- Build current run
    currentRun = {
        runId = time() .. "-" .. mapID .. "-" .. keystoneLevel,
        dungeon = mapName,
        mapId = mapID,
        keyLevel = keystoneLevel,
        affixes = GetAffixNames(affixIDs),
        startTime = time(),
        endTime = nil,
        timed = false,
        completed = false,
        depleted = false,
        durationSeconds = nil,
        timeLimitSeconds = timeLimit and (timeLimit / 1000) or nil, -- API returns ms
        upgradeCount = 0,
        deaths = 0,
        members = {},
        goldBefore = GetMoney(),
        goldAfter = nil,
        durabilityBefore = GetAverageDurability(),
        durabilityAfter = nil,
        companionPet = GetCompanionPetName(),
        myMount = GetMyMountName(), -- might be nil if already dismounted
        playedBefore = playedTime,
        playedAfter = nil,
        buffCheck = nil,
        season = "midnight-1",
    }

    -- Scan group composition
    inspectQueue = {}
    inspectIndex = 0
    currentRun.members = ScanGroupMembers()

    -- Scan buffs (before combat starts)
    currentRun.buffCheck = ScanGroupBuffs(currentRun.members)

    -- Clean up temp unit references from members
    for _, m in ipairs(currentRun.members) do
        m.unit = nil
    end

    -- Start staggered inspects for party members
    if #inspectQueue > 0 then
        C_Timer.After(1.0, ProcessInspectQueue)
    end

    Print("Run started: " .. mapName .. " +" .. keystoneLevel)
end

local function OnChallengeModeCompleted()
    if not currentRun then return end

    -- Get completion info
    local mapID, level, completionTime, onTime, keystoneUpgradeLevels =
        C_ChallengeMode.GetCompletionInfo()

    currentRun.endTime = time()
    currentRun.completed = true
    currentRun.timed = onTime
    currentRun.depleted = not onTime
    currentRun.durationSeconds = completionTime and math.floor(completionTime / 1000) or nil
    currentRun.upgradeCount = keystoneUpgradeLevels or 0
    currentRun.goldAfter = GetMoney()
    currentRun.durabilityAfter = GetAverageDurability()

    -- Request /played for end time
    RequestTimePlayed()

    -- Save the run
    table.insert(MythicPlusTrackerDB.runs, currentRun)

    local resultText = onTime and ("|cff00ff00Timed|r +" .. (keystoneUpgradeLevels or 0))
                                or "|cffff0000Depleted|r"
    Print("Run saved: " .. currentRun.dungeon .. " +" .. currentRun.keyLevel .. " - " .. resultText)

    currentRun = nil
end

local function OnCombatLogEvent()
    if not currentRun then return end

    local _, subevent, _, _, _, _, _, destGUID, destName, destFlags = CombatLogGetCurrentEventInfo()

    if subevent == "UNIT_DIED" then
        -- Check if the dead unit is a player in our group
        if destFlags and bit.band(destFlags, COMBATLOG_OBJECT_TYPE_PLAYER) > 0 then
            if bit.band(destFlags, COMBATLOG_OBJECT_AFFILIATION_MINE) > 0 or
               bit.band(destFlags, COMBATLOG_OBJECT_AFFILIATION_PARTY) > 0 then
                currentRun.deaths = currentRun.deaths + 1
            end
        end
    end
end

local function OnInspectReady(guid)
    if not currentRun or #inspectQueue == 0 then return end
    if inspectIndex < 1 or inspectIndex > #inspectQueue then return end

    local member = inspectQueue[inspectIndex]

    -- Get spec from inspect
    local specID = GetInspectSpecialization(member.unit or "party1")
    if specID and specID > 0 then
        local _, specName = GetSpecializationInfoByID(specID)
        member.spec = specName

        -- Also update in the actual members list
        for _, m in ipairs(currentRun.members) do
            if m.name == member.name then
                m.spec = specName
                break
            end
        end
    end

    -- Try to get item level from inspect
    -- Note: This may not be available in all Midnight API restrictions
    local unit = member.unit
    if unit and UnitExists(unit) then
        local totalIlvl, numItems = 0, 0
        for slot = 1, 17 do
            if slot ~= 4 then -- skip shirt
                local itemLink = GetInventoryItemLink(unit, slot)
                if itemLink then
                    local effectiveIlvl = GetDetailedItemLevelInfo(itemLink)
                    if effectiveIlvl then
                        totalIlvl = totalIlvl + effectiveIlvl
                        numItems = numItems + 1
                    end
                end
            end
        end
        if numItems > 0 then
            local avgIlvl = math.floor(totalIlvl / numItems)
            member.ilvl = avgIlvl
            for _, m in ipairs(currentRun.members) do
                if m.name == member.name then
                    m.ilvl = avgIlvl
                    break
                end
            end
        end
    end

    ClearInspectPlayer()

    -- Process next in queue
    C_Timer.After(1.5, ProcessInspectQueue)
end

local function OnTimePlayed(totalTime, levelTime)
    playedTime = totalTime
    if currentRun then
        if not currentRun.playedBefore then
            currentRun.playedBefore = totalTime
        else
            currentRun.playedAfter = totalTime
        end
    end
end

local function OnSpellcastSucceeded(unit, castGUID, spellID)
    -- Try to capture mount casts for party members
    if not currentRun then return end
    if not unit or UnitIsUnit(unit, "player") then return end

    -- Check if this spell is a mount spell by seeing if the unit becomes mounted shortly after
    -- We store the spell name and associate it with the member
    local spellName = C_Spell.GetSpellName(spellID)
    if not spellName then return end

    -- Quick check: if unit is now mounted, this was likely a mount cast
    C_Timer.After(0.5, function()
        if UnitExists(unit) and IsMounted and UnitOnTaxi then
            -- Can't reliably check IsMounted for other units
            -- But we captured the spell name, store it optimistically
        end
    end)
end

----------------------------------------------------------------------
-- Mount scanning (snapshot before key, when group forms)
----------------------------------------------------------------------

local function SnapshotMounts()
    if not currentRun then return end
    for _, member in ipairs(currentRun.members) do
        if member.isMe then
            member.mount = GetMyMountName()
        end
        -- For others, we already scanned buffs in ScanGroupMembers
    end
end

----------------------------------------------------------------------
-- Slash command
----------------------------------------------------------------------

SLASH_MYTHICPLUSTRACKER1 = "/mpt"
SLASH_MYTHICPLUSTRACKER2 = "/mythicplustracker"
SlashCmdList["MYTHICPLUSTRACKER"] = function(msg)
    msg = msg:lower():gsub("^%s+", ""):gsub("%s+$", "")

    if msg == "status" then
        Print("Runs saved: " .. #MythicPlusTrackerDB.runs)
        if currentRun then
            Print("Active run: " .. currentRun.dungeon .. " +" .. currentRun.keyLevel)
        else
            Print("No active run.")
        end
    elseif msg == "clear" then
        MythicPlusTrackerDB.runs = {}
        Print("All run data cleared.")
    elseif msg == "last" then
        local runs = MythicPlusTrackerDB.runs
        if #runs == 0 then
            Print("No runs saved.")
        else
            local last = runs[#runs]
            local result = last.timed and "Timed" or "Depleted"
            Print("Last: " .. last.dungeon .. " +" .. last.keyLevel .. " - " .. result ..
                  " (" .. (last.durationSeconds or 0) .. "s, " .. last.deaths .. " deaths)")
        end
    else
        Print("Commands: /mpt status | /mpt last | /mpt clear")
    end
end

----------------------------------------------------------------------
-- Event registration
----------------------------------------------------------------------

frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("CHALLENGE_MODE_START")
frame:RegisterEvent("CHALLENGE_MODE_COMPLETED")
frame:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")
frame:RegisterEvent("INSPECT_READY")
frame:RegisterEvent("TIME_PLAYED_MSG")
frame:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")

frame:SetScript("OnEvent", function(self, event, ...)
    if event == "ADDON_LOADED" then
        OnAddonLoaded(...)
    elseif event == "CHALLENGE_MODE_START" then
        OnChallengeModeStart()
    elseif event == "CHALLENGE_MODE_COMPLETED" then
        OnChallengeModeCompleted()
    elseif event == "COMBAT_LOG_EVENT_UNFILTERED" then
        OnCombatLogEvent()
    elseif event == "INSPECT_READY" then
        OnInspectReady(...)
    elseif event == "TIME_PLAYED_MSG" then
        OnTimePlayed(...)
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        OnSpellcastSucceeded(...)
    end
end)
