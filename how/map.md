In this project, there are actually two ways the robot can handle three medicine deliveries, and they behave a little differently.

If they are three separate queued requests
The robot takes them one by one from the task queue, sorted by priority and then by oldest first in 
app.py (line 1195)
. For each task, it goes to that room, opens the drawer, waits, closes the drawer, and then returns to the dock before starting the next one in 
Robo_programs/main.py (line 145)
. So if patients are in 3 different rooms, the current flow is basically:

Pick task 1 from /api/robot/queue/<user_id>
Navigate to room 1
Deliver medicine
Return to base
Pick task 2
Repeat
Pick task 3
Repeat
That is simple, but not the most efficient because it does a full round trip for each task.

If they are scheduled medicine tasks
This is the smarter multi-room flow. The server collects all due medicines, groups them by room, and plans a room-to-room route in 
app.py (line 1476)
. It uses the saved map, checks which rooms are reachable, and chooses the next closest room with a nearest-neighbor route planner in 
app.py (line 1356)
. Then the robot runs the batch in 
Robo_programs/main.py (line 219)
, going stop by stop without returning to dock after every room.

So for 3 patients in 3 rooms, the system will usually do:

Find all due meds
Group them by room
Read room coordinates from the saved map
Compute path from base to the nearest room
Then from that room to the next nearest reachable room
Then to the third room
Then return to base at the end
How it navigates through rooms
The map is grid-based. Walls are blocked cells, the dock/base is one coordinate, and each room like A-101 is stored as a coordinate marker in the map editor at 
templates/map.html (line 136)
 and 
static/js/astar.js (line 136)
. The actual pathfinding is A* in both the server and robot code:

Server planner: 
app.py (line 1278)
Robot-side planner: 
Robo_programs/navigation.py (line 55)
Once it gets a cell-by-cell path, it converts that into movement commands like L, R, and F in 
Robo_programs/navigation.py (line 119)
, then sends them to the Arduino over serial in 
Robo_programs/main.py (line 43)
.

How it is connected to the system map
The connection is through the backend API:

Admin saves the map to /api/map/save in 
app.py (line 1942)
It is stored in the UserMap.grid_data database field in 
app.py (line 186)
The robot fetches it from /api/robot/map/<user_id> in 
app.py (line 1986)
The robot calls that endpoint in 
Robo_programs/navigation.py (line 28)
So the robot is not “seeing” rooms automatically. It depends on the map you draw and save in the system.

One important detail: if a room is not mapped, the scheduled multi-room batch will skip it as unroutable, but single-room navigation can still fall back to hardcoded routes like A-101, A-102, B-201 in 
Robo_programs/navigation.py (line 196)
.










