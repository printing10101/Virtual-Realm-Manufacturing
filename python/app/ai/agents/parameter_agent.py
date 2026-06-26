"""Parameter optimization agent for intelligent process planning."""

from typing import Dict, Any, List


class ParameterAgent:
    """
    Intelligent parameter optimization agent.
    
    Uses LNN predictions and knowledge graph to optimize
    machining parameters based on material, tool, and machine constraints.
    """
    
    def __init__(self):
        """Initialize parameter agent."""
        self._knowledge_cache: Dict[str, Any] = {}
    
    def optimize_parameters(
        self,
        material: str,
        tool_type: str,
        operation: str,
        constraints: Dict[str, Any] = None,
    ) -> Dict[str, float]:
        """
        Optimize machining parameters for given conditions.
        
        Args:
            material: Material type (e.g., 'Al6061', 'Steel45')
            tool_type: Tool type (e.g., 'end_mill', 'drill')
            operation: Operation type (e.g., 'roughing', 'finishing')
            constraints: Machine/workpiece constraints
            
        Returns:
            Optimized parameters dict with spindle_speed, feed_rate, depth_of_cut
        """
        # Simplified parameter optimization logic
        # In production, this would query knowledge graph and LNN model
        
        base_params = self._get_base_parameters(material, tool_type, operation)
        
        # Apply constraints
        if constraints:
            base_params = self._apply_constraints(base_params, constraints)
        
        return base_params
    
    def _get_base_parameters(
        self,
        material: str,
        tool_type: str,
        operation: str,
    ) -> Dict[str, float]:
        """Get base parameters from knowledge base."""
        # Simplified lookup - would use knowledge graph in production
        params = {
            "spindle_speed": 1500.0,  # RPM
            "feed_rate": 200.0,  # mm/min
            "depth_of_cut": 2.0,  # mm
            "width_of_cut": 5.0,  # mm
        }
        
        # Material-specific adjustments
        if "Al" in material or "aluminum" in material.lower():
            params["spindle_speed"] *= 1.5
            params["feed_rate"] *= 1.3
        elif "Steel" in material or "steel" in material.lower():
            params["spindle_speed"] *= 0.8
            params["feed_rate"] *= 0.9
        
        # Operation-specific adjustments
        if operation == "finishing":
            params["depth_of_cut"] *= 0.3
            params["feed_rate"] *= 0.7
        elif operation == "roughing":
            params["depth_of_cut"] *= 2.0
            params["feed_rate"] *= 1.2
        
        return params
    
    def _apply_constraints(
        self,
        params: Dict[str, float],
        constraints: Dict[str, Any],
    ) -> Dict[str, float]:
        """Apply machine/workpiece constraints to parameters."""
        constrained = params.copy()
        
        if "max_spindle_speed" in constraints:
            constrained["spindle_speed"] = min(
                constrained["spindle_speed"],
                constraints["max_spindle_speed"]
            )
        
        if "max_feed_rate" in constraints:
            constrained["feed_rate"] = min(
                constrained["feed_rate"],
                constraints["max_feed_rate"]
            )
        
        if "max_depth" in constraints:
            constrained["depth_of_cut"] = min(
                constrained["depth_of_cut"],
                constraints["max_depth"]
            )
        
        return constrained
    
    def validate_parameters(
        self,
        params: Dict[str, float],
        material: str,
        tool_type: str,
    ) -> tuple[bool, List[str]]:
        """
        Validate parameters against safety limits.
        
        Returns:
            (is_valid, list_of_warnings)
        """
        warnings = []
        
        # Check spindle speed limits
        if params.get("spindle_speed", 0) > 20000:
            warnings.append("Spindle speed exceeds typical machine limit (20000 RPM)")
        
        # Check feed rate limits
        if params.get("feed_rate", 0) > 5000:
            warnings.append("Feed rate exceeds typical machine limit (5000 mm/min)")
        
        # Check depth of cut
        if params.get("depth_of_cut", 0) > 10:
            warnings.append("Depth of cut may be too aggressive for most tools")
        
        return len(warnings) == 0, warnings
