extends Node3D
# Game-rules marker (F6). An invisible, converter-generated data node scanned by
# GameState.begin() from the "game_rules" group. Optional lose conditions:
#   time_limit       seconds to finish the required objectives (0 = no limit)
#   max_team_deaths  total F5 deaths the team may suffer before losing (<0 = never)

@export var time_limit: float = 0.0
@export var max_team_deaths: int = -1

func _ready() -> void:
	add_to_group("game_rules")
