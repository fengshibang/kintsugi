local dzapi = require 'jass.dzapi'
local japi  = require 'jass.japi'
local jass = require 'jass.common'
register_japi[[

native  InitGameCache    takes string campaignFile returns gamecache
native  SaveGameCache    takes gamecache whichCache returns boolean

native EXNetUseItem  takes player player_id,string itemid,integer amount returns boolean

native  StoreInteger					takes gamecache cache, string missionKey, string key, integer value returns nothing
native  StoreReal						takes gamecache cache, string missionKey, string key, real value returns nothing
native  StoreBoolean					takes gamecache cache, string missionKey, string key, boolean value returns nothing
native  StoreUnit						takes gamecache cache, string missionKey, string key, unit whichUnit returns boolean
native  StoreString						takes gamecache cache, string missionKey, string key, string value returns boolean

native SyncStoredInteger        takes gamecache cache, string missionKey, string key returns nothing
native SyncStoredReal           takes gamecache cache, string missionKey, string key returns nothing
native SyncStoredBoolean        takes gamecache cache, string missionKey, string key returns nothing
native SyncStoredUnit           takes gamecache cache, string missionKey, string key returns nothing
native SyncStoredString         takes gamecache cache, string missionKey, string key returns nothing

native  HaveStoredInteger					takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredReal						takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredBoolean					takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredUnit						takes gamecache cache, string missionKey, string key returns boolean
native  HaveStoredString					takes gamecache cache, string missionKey, string key returns boolean

native  FlushGameCache						takes gamecache cache returns nothing
native  FlushStoredMission					takes gamecache cache, string missionKey returns nothing
native  FlushStoredInteger					takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredReal						takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredBoolean					takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredUnit						takes gamecache cache, string missionKey, string key returns nothing
native  FlushStoredString					takes gamecache cache, string missionKey, string key returns nothing

native  GetStoredInteger				takes gamecache cache, string missionKey, string key returns integer
native  GetStoredReal					takes gamecache cache, string missionKey, string key returns real
native  GetStoredBoolean				takes gamecache cache, string missionKey, string key returns boolean
native  GetStoredString					takes gamecache cache, string missionKey, string key returns string

native DzAPI_Map_SaveServerValue        takes player whichPlayer, string key, string value returns boolean
native DzAPI_Map_GetServerValue         takes player whichPlayer, string key returns string
native DzAPI_Map_Ladder_SetStat         takes player whichPlayer, string key, string value returns nothing
native DzAPI_Map_IsRPGLadder            takes nothing returns boolean
native DzAPI_Map_GetGameStartTime       takes nothing returns integer
native DzAPI_Map_Stat_SetStat           takes player whichPlayer, string key, string value returns nothing
native DzAPI_Map_GetMatchType      		takes nothing returns integer
native DzAPI_Map_Ladder_SetPlayerStat   takes player whichPlayer, string key, string value returns nothing
native DzAPI_Map_GetServerValueErrorCode takes player whichPlayer returns integer
native DzAPI_Map_GetLadderLevel         takes player whichPlayer returns integer
native DzAPI_Map_IsRedVIP               takes player whichPlayer returns boolean
native DzAPI_Map_IsBlueVIP              takes player whichPlayer returns boolean
native DzAPI_Map_GetLadderRank          takes player whichPlayer returns integer
native DzAPI_Map_GetMapLevelRank        takes player whichPlayer returns integer
native DzAPI_Map_GetGuildName           takes player whichPlayer returns string
native DzAPI_Map_GetGuildRole           takes player whichPlayer returns integer
native DzAPI_Map_IsRPGLobby             takes nothing returns boolean
native DzAPI_Map_GetMapLevel            takes player whichPlayer returns integer
native DzAPI_Map_MissionComplete        takes player whichPlayer, string key, string value returns nothing
native DzAPI_Map_GetActivityData        takes nothing returns string
native DzAPI_Map_GetMapConfig           takes string key returns string
native DzAPI_Map_HasMallItem            takes player whichPlayer, string key returns boolean
native DzAPI_Map_SavePublicArchive      takes player whichPlayer, string key, string value returns boolean
native DzAPI_Map_GetPublicArchive       takes player whichPlayer, string key returns string
native DzAPI_Map_UseConsumablesItem     takes player whichPlayer, string key returns nothing
native DzAPI_Map_OrpgTrigger            takes player whichPlayer, string key returns nothing
native DzAPI_Map_GetServerArchiveDrop   takes player whichPlayer, string key returns string
native DzAPI_Map_GetServerArchiveEquip  takes player whichPlayer, string key returns integer
native RequestExtraIntegerData          takes integer dataType, player whichPlayer, string param1, string param2, boolean param3, integer param4, integer param5, integer param6 returns integer
native RequestExtraBooleanData          takes integer dataType, player whichPlayer, string param1, string param2, boolean param3, integer param4, integer param5, integer param6 returns boolean
native RequestExtraStringData           takes integer dataType, player whichPlayer, string param1, string param2, boolean param3, integer param4, integer param5, integer param6 returns string
native RequestExtraRealData             takes integer dataType, player whichPlayer, string param1, string param2, boolean param3, integer param4, integer param5, integer param6 returns real
native DzAPI_Map_GetPlatformVIP         takes player whichPlayer returns integer

native DzGetMouseTerrainX takes nothing returns real
native DzGetMouseTerrainY takes nothing returns real
native DzGetMouseTerrainZ takes nothing returns real
native DzIsMouseOverUI takes nothing returns boolean
native DzGetMouseX takes nothing returns integer
native DzGetMouseY takes nothing returns integer
native DzGetMouseXRelative takes nothing returns integer
native DzGetMouseYRelative takes nothing returns integer
native DzSetMousePos takes integer x, integer y returns nothing
native DzTriggerRegisterMouseEvent takes trigger trig, integer btn, integer status, boolean sync, string func returns nothing
native DzTriggerRegisterMouseEventByCode takes trigger trig, integer btn, integer status, boolean sync, code funcHandle returns nothing
native DzTriggerRegisterKeyEvent takes trigger trig, integer key, integer status, boolean sync, string func returns nothing
native DzTriggerRegisterKeyEventByCode takes trigger trig, integer key, integer status, boolean sync, code funcHandle returns nothing
native DzTriggerRegisterMouseWheelEvent takes trigger trig, boolean sync, string func returns nothing
native DzTriggerRegisterMouseWheelEventByCode takes trigger trig, boolean sync, code funcHandle returns nothing
native DzTriggerRegisterMouseMoveEvent takes trigger trig, boolean sync, string func returns nothing
native DzTriggerRegisterMouseMoveEventByCode takes trigger trig, boolean sync, code funcHandle returns nothing
native DzGetTriggerKey takes nothing returns integer
native DzGetWheelDelta takes nothing returns integer
native DzIsKeyDown takes integer iKey returns boolean
native DzGetTriggerKeyPlayer takes nothing returns player
native DzGetWindowWidth takes nothing returns integer
native DzGetWindowHeight takes nothing returns integer
native DzGetWindowX takes nothing returns integer
native DzGetWindowY takes nothing returns integer
native DzTriggerRegisterWindowResizeEvent takes trigger trig, boolean sync, string func returns nothing
native DzTriggerRegisterWindowResizeEventByCode takes trigger trig, boolean sync, code funcHandle returns nothing
native DzIsWindowActive takes nothing returns boolean
native DzDestructablePosition takes destructable d, real x, real y returns nothing
native DzSetUnitPosition takes unit whichUnit, real x, real y returns nothing
native DzExecuteFunc takes string funcName returns nothing
native DzGetUnitUnderMouse takes nothing returns unit
native DzSetUnitTexture takes unit whichUnit, string path, integer texId returns nothing
native DzSetMemory takes integer address, real value returns nothing
native DzSetUnitID takes unit whichUnit, integer id returns nothing
native DzSetUnitModel takes unit whichUnit, string path returns nothing
native DzSetWar3MapMap takes string map returns nothing
native DzTriggerRegisterSyncData takes trigger trig, string prefix, boolean server returns nothing
native DzSyncData takes string prefix, string data returns nothing
native DzGetTriggerSyncData takes nothing returns string
native DzGetTriggerSyncPlayer takes nothing returns player
native DzFrameHideInterface takes nothing returns nothing
native DzFrameEditBlackBorders takes real upperHeight, real bottomHeight returns nothing
native DzFrameGetPortrait takes nothing returns integer
native DzFrameGetMinimap takes nothing returns integer
native DzFrameGetCommandBarButton takes integer row, integer column returns integer
native DzFrameGetHeroBarButton takes integer buttonId returns integer
native DzFrameGetHeroHPBar takes integer buttonId returns integer
native DzFrameGetHeroManaBar takes integer buttonId returns integer
native DzFrameGetItemBarButton takes integer buttonId returns integer
native DzFrameGetMinimapButton takes integer buttonId returns integer
native DzFrameGetUpperButtonBarButton takes integer buttonId returns integer
native DzFrameGetTooltip takes nothing returns integer
native DzFrameGetChatMessage takes nothing returns integer
native DzFrameGetUnitMessage takes nothing returns integer
native DzFrameGetTopMessage takes nothing returns integer
native DzGetColor takes integer r, integer g, integer b, integer a returns integer
native DzFrameSetUpdateCallback takes string func returns nothing
native DzFrameSetUpdateCallbackByCode takes code funcHandle returns nothing
native DzFrameShow takes integer frame, boolean enable returns nothing
native DzCreateFrame takes string frame, integer parent, integer id returns integer
native DzCreateSimpleFrame takes string frame, integer parent, integer id returns integer
native DzDestroyFrame takes integer frame returns nothing
native DzLoadToc takes string fileName returns nothing
native DzFrameSetPoint takes integer frame, integer point, integer relativeFrame, integer relativePoint, real x, real y returns nothing
native DzFrameSetAbsolutePoint takes integer frame, integer point, real x, real y returns nothing
native DzFrameClearAllPoints takes integer frame returns nothing
native DzFrameSetEnable takes integer name, boolean enable returns nothing
native DzFrameSetScript takes integer frame, integer eventId, string func, boolean sync returns nothing
native DzFrameSetScriptByCode takes integer frame, integer eventId, code funcHandle, boolean sync returns nothing
native DzGetTriggerUIEventPlayer takes nothing returns player
native DzGetTriggerUIEventFrame takes nothing returns integer
native DzFrameFindByName takes string name, integer id returns integer
native DzSimpleFrameFindByName takes string name, integer id returns integer
native DzSimpleFontStringFindByName takes string name, integer id returns integer
native DzSimpleTextureFindByName takes string name, integer id returns integer
native DzGetGameUI takes nothing returns integer
native DzClickFrame takes integer frame returns nothing
native DzSetCustomFovFix takes real value returns nothing
native DzEnableWideScreen takes boolean enable returns nothing
native DzFrameSetText takes integer frame, string text returns nothing
native DzFrameGetText takes integer frame returns string
native DzFrameSetTextSizeLimit takes integer frame, integer size returns nothing
native DzFrameGetTextSizeLimit takes integer frame returns integer
native DzFrameSetTextColor takes integer frame, integer color returns nothing
native DzGetMouseFocus takes nothing returns integer
native DzFrameSetAllPoints takes integer frame, integer relativeFrame returns boolean
native DzFrameSetFocus takes integer frame, boolean enable returns boolean
native DzFrameSetModel takes integer frame, string modelFile, integer modelType, integer flag returns nothing
native DzFrameGetEnable takes integer frame returns boolean
native DzFrameSetAlpha takes integer frame, integer alpha returns nothing
native DzFrameGetAlpha takes integer frame returns integer
native DzFrameSetAnimate takes integer frame, integer animId, boolean autocast returns nothing
native DzFrameSetAnimateOffset takes integer frame, real offset returns nothing
native DzFrameSetTexture takes integer frame, string texture, integer flag returns nothing
native DzFrameSetScale takes integer frame, real scale returns nothing
native DzFrameSetTooltip takes integer frame, integer tooltip returns nothing
native DzFrameCageMouse takes integer frame, boolean enable returns nothing
native DzFrameGetValue takes integer frame returns real
native DzFrameSetMinMaxValue takes integer frame, real minValue, real maxValue returns nothing
native DzFrameSetStepValue takes integer frame, real step returns nothing
native DzFrameSetValue takes integer frame, real value returns nothing
native DzFrameSetSize takes integer frame, real w, real h returns nothing
native DzCreateFrameByTagName takes string frameType, string name, integer parent, string template, integer id returns integer
native DzFrameSetVertexColor takes integer frame, integer color returns nothing

native  UnitAlive  takes unit switchUnit returns boolean
]]

local null

---设置 ${player} 的 ${option} 号平台功能为 ${enable}  
---1,锁定视距 2,显血/显蓝 3,智能施法
rawset(dzapi,'DzAPI_Map_EnablePlatformSettings',function(whichPlayer,option,enable)
    return RequestExtraBooleanData(43, whichPlayer, null, null, enable, option, 0, 0)
end)
---使用商城道具（次数型）  
---使用 ${player} 名称 ${key} 的商城道具 ${value} 次  
---仅对次数消耗型商品有效，只能使用不能恢复，请谨慎使用
rawset(dzapi,'DzAPI_Map_ConsumeMallItem',function(whichPlayer,key,count)
    return RequestExtraBooleanData(42, whichPlayer, key, null, false, count, 0, 0)
end)
---未知(推测是获取商城消耗类道具数量)
rawset(dzapi,'DzAPI_Map_GetMallItemCount',function(whichPlayer,key)
    return RequestExtraIntegerData(41, whichPlayer, key, null, false, 0, 0, 0)
end)
---读取玩家服务器存档成功
rawset(dzapi,'GetPlayerServerValueSuccess',function(whichPlayer)
    if(dzapi.DzAPI_Map_GetServerValueErrorCode(whichPlayer)==0)then
        return true
    else
        return false
    end
end)
---获取玩家中游戏局数
rawset(dzapi,'DzAPI_Map_PlayedGames',function(whichPlayer)
    return RequestExtraIntegerData(45, whichPlayer, null, null, false, 0, 0, 0)
end)
---评论次数(调用DzAPI_Map_CommentTotalCount)
rawset(dzapi,'DzAPI_Map_CommentCount',function(whichPlayer)
    return RequestExtraIntegerData(51, null, null, null, false, 0, 0, 0)
    
end)
---好友数量
rawset(dzapi,'DzAPI_Map_FriendCount',function(whichPlayer)
    return RequestExtraIntegerData(47, whichPlayer, null, null, false, 0, 0, 0)
    
end)
---鉴赏家
rawset(dzapi,'DzAPI_Map_IsConnoisseur',function(whichPlayer)
    return RequestExtraBooleanData(48, whichPlayer, null, null, false, 0, 0, 0)
    
end)
---战网账号
rawset(dzapi,'DzAPI_Map_IsBattleNetAccount',function(whichPlayer)
    return RequestExtraBooleanData(49, whichPlayer, null, null, false, 0, 0, 0)
    
end)
---本图作者
rawset(dzapi,'DzAPI_Map_IsAuthor',function(whichPlayer)
    return RequestExtraBooleanData(50, whichPlayer, null, null, false, 0, 0, 0)
    
end)
---获取该图总评论次数
rawset(dzapi,'DzAPI_Map_CommentTotalCount',function(whichPlayer)
    return RequestExtraIntegerData(51, null, null, null, false, 0, 0, 0)
    
end)
---"平台统计： ",whichPlayer,"，埋点key：",eventKey,"，子key：",不填,"，次数 ",value  
---"一般用于统计游戏里某些事件的触发次数，可在作者之家查看。【第二个子key是以后备用暂时不要填】"
rawset(dzapi,'DzAPI_Map_Statistics',function(whichPlayer,eventKey,eventType,value)
    RequestExtraBooleanData(34, whichPlayer, eventKey, "", false, value, 0, 0)
end)
---是否回流/收藏过地图的用户  
---2,当前是平台回流用户 8,当前是地图回流用户 16,收藏过地图 1,曾经是平台回流用户 4,曾经是地图回流用户
rawset(dzapi,'DzAPI_Map_Returns',function(whichPlayer,label)
    return RequestExtraBooleanData(53, whichPlayer, null, null, false, label, 0, 0)
end)
---签到系统  
---0,总签到天数 1,最高连续签到天数 2,连续签到天数
rawset(dzapi,'DzAPI_Map_ContinuousCount',function(whichPlayer,id)
    return RequestExtraIntegerData(54, whichPlayer, null, null, false, id, 0, 0)
end)
---是玩家
rawset(dzapi,'DzAPI_Map_IsPlayer',function(whichPlayer)
    return RequestExtraBooleanData(55, whichPlayer, null, null, false, 0, 0, 0)
end)