local folderOfThisFile = (...)..'.'
FSM = {}
FSM.machine = require (folderOfThisFile..'FSM')
FSM.empty = require (folderOfThisFile..'EmptyState')
FSM.state = require (folderOfThisFile..'FSMState')