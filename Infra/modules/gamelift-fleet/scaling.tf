# Auto-scaling configuration for GameLift fleet

# Scaling policy for target tracking
resource "aws_appautoscaling_target" "fleet" {
  count = var.enable_auto_scaling ? 1 : 0

  max_capacity       = var.max_fleet_capacity
  min_capacity       = var.min_fleet_capacity
  resource_id        = "fleet/${aws_gamelift_fleet.main.id}"
  scalable_dimension = "fleet:desired:EC2"
  service_namespace  = "gamelift"
}

# Target tracking scaling policy based on available game sessions
resource "aws_appautoscaling_policy" "fleet_target_tracking" {
  count = var.enable_auto_scaling ? 1 : 0

  name               = "${var.project_name}-${var.environment}-fleet-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.fleet[0].resource_id
  scalable_dimension = aws_appautoscaling_target.fleet[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.fleet[0].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = var.target_utilization_percentage

    predefined_metric_specification {
      predefined_metric_type = "GameLiftFleetUtilization"
    }

    scale_in_cooldown  = var.scale_in_cooldown_seconds
    scale_out_cooldown = var.scale_out_cooldown_seconds
  }
}

# Note: Manual capacity configuration is managed via AWS Console or CLI
# Terraform does not support aws_gamelift_fleet_capacity resource
