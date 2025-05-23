"""DOP2 tree visualization for Miele devices.

This module provides functionality to visualize the DOP2 tree structure
of Miele appliances. It can generate various representations of the tree,
including HTML, ASCII art, and interactive web-based visualizations.
"""

import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, cast

from .models import DOP2Tree, DOP2Node, DeviceGenerationType

logger = logging.getLogger(__name__)

# HTML template for tree visualization
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DOP2 Tree Visualization - {device_id}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .tree-container {{
            margin-top: 20px;
        }}
        .unit {{
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }}
        .unit-header {{
            background-color: #3498db;
            color: white;
            padding: 10px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
        }}
        .unit-content {{
            padding: 0;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        .unit-content.active {{
            max-height: 5000px;
            padding: 10px;
        }}
        .leaf {{
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }}
        .leaf-header {{
            font-weight: bold;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
        }}
        .leaf-content {{
            margin-top: 10px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 4px;
            display: none;
            white-space: pre-wrap;
            font-family: monospace;
        }}
        .leaf-content.active {{
            display: block;
        }}
        .stats {{
            margin-top: 20px;
            padding: 15px;
            background-color: #eaf2f8;
            border-radius: 4px;
        }}
        .stats h3 {{
            margin-top: 0;
            color: #2980b9;
        }}
        .search-box {{
            margin-bottom: 20px;
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        .filter-options {{
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 7px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 5px;
        }}
        .badge-primary {{
            background-color: #3498db;
            color: white;
        }}
        .badge-secondary {{
            background-color: #95a5a6;
            color: white;
        }}
        .badge-success {{
            background-color: #2ecc71;
            color: white;
        }}
        .badge-warning {{
            background-color: #f39c12;
            color: white;
        }}
        .badge-danger {{
            background-color: #e74c3c;
            color: white;
        }}
        .badge-info {{
            background-color: #1abc9c;
            color: white;
        }}
        .type-indicator {{
            font-size: 12px;
            color: #7f8c8d;
            margin-left: 5px;
        }}
        .leaf-summary {{
            margin-left: 10px;
            color: #7f8c8d;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>DOP2 Tree Visualization - {device_id}</h1>
        <p>Device Generation: <strong>{generation}</strong></p>
        
        <div class="filter-options">
            <input type="text" id="searchBox" class="search-box" placeholder="Search for leaf attributes...">
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
        </div>
        
        <div class="stats">
            <h3>Tree Statistics</h3>
            <p>Total Units: <strong>{unit_count}</strong></p>
            <p>Total Leaves: <strong>{leaf_count}</strong></p>
            <p>Exploration Duration: <strong>{duration:.2f} seconds</strong></p>
        </div>
        
        <div class="tree-container">
            {tree_content}
        </div>
    </div>
    
    <script>
        // Toggle unit content visibility
        function toggleUnit(unitId) {{
            const content = document.getElementById('unit-content-' + unitId);
            content.classList.toggle('active');
            
            const arrow = document.getElementById('unit-arrow-' + unitId);
            arrow.textContent = content.classList.contains('active') ? '▼' : '▶';
        }}
        
        // Toggle leaf content visibility
        function toggleLeaf(unitId, leafId) {{
            const content = document.getElementById(`leaf-content-${{unitId}}-${{leafId}}`);
            content.classList.toggle('active');
            
            const arrow = document.getElementById(`leaf-arrow-${{unitId}}-${{leafId}}`);
            arrow.textContent = content.classList.contains('active') ? '▼' : '▶';
        }}
        
        // Search functionality
        document.getElementById('searchBox').addEventListener('input', function() {{
            const searchTerm = this.value.toLowerCase();
            const units = document.querySelectorAll('.unit');
            
            units.forEach(unit => {{
                let unitHasMatch = false;
                const leaves = unit.querySelectorAll('.leaf');
                
                leaves.forEach(leaf => {{
                    const leafText = leaf.textContent.toLowerCase();
                    const hasMatch = leafText.includes(searchTerm);
                    
                    leaf.style.display = hasMatch || searchTerm === '' ? 'block' : 'none';
                    if (hasMatch) unitHasMatch = true;
                }});
                
                unit.style.display = unitHasMatch || searchTerm === '' ? 'block' : 'none';
                
                // Auto-expand units with matches
                if (unitHasMatch && searchTerm !== '') {{
                    const unitId = unit.getAttribute('data-unit-id');
                    const content = document.getElementById('unit-content-' + unitId);
                    const arrow = document.getElementById('unit-arrow-' + unitId);
                    content.classList.add('active');
                    arrow.textContent = '▼';
                }}
            }});
        }});
        
        // Expand all units
        function expandAll() {{
            const unitContents = document.querySelectorAll('.unit-content');
            unitContents.forEach(content => {{
                content.classList.add('active');
                const unitId = content.getAttribute('id').replace('unit-content-', '');
                document.getElementById('unit-arrow-' + unitId).textContent = '▼';
            }});
        }}
        
        // Collapse all units
        function collapseAll() {{
            const unitContents = document.querySelectorAll('.unit-content');
            unitContents.forEach(content => {{
                content.classList.remove('active');
                const unitId = content.getAttribute('id').replace('unit-content-', '');
                document.getElementById('unit-arrow-' + unitId).textContent = '▶';
            }});
        }}
        
        // Initialize with first unit expanded
        document.addEventListener('DOMContentLoaded', function() {{
            const firstUnit = document.querySelector('.unit');
            if (firstUnit) {{
                const unitId = firstUnit.getAttribute('data-unit-id');
                toggleUnit(unitId);
            }}
        }});
    </script>
</body>
</html>
"""


class DOP2Visualizer:
    """Visualizer for DOP2 tree structures.
    
    This class provides functionality to visualize the DOP2 tree structure
    of Miele appliances in various formats.
    """
    
    def __init__(self, tree: DOP2Tree):
        """Initialize the visualizer with a DOP2Tree.
        
        Args:
            tree: DOP2Tree object to visualize
        """
        self.tree = tree
        
    def _format_leaf_value(self, value: Any) -> str:
        """Format a leaf value for display.
        
        Args:
            value: Leaf value to format
            
        Returns:
            Formatted string representation of the value
        """
        if isinstance(value, bytes):
            # Format bytes as hex with ASCII representation
            hex_str = value.hex(' ')
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in value)
            return f"Hex: {hex_str}\nASCII: {ascii_str}"
        elif hasattr(value, '__dict__'):
            # Format objects with __dict__ attribute
            try:
                return json.dumps(vars(value), indent=2, default=str)
            except Exception:
                return str(value)
        else:
            # Format other values
            return str(value)
    
    def _get_value_type_badge(self, value: Any) -> str:
        """Get a badge indicating the type of a value.
        
        Args:
            value: Value to get badge for
            
        Returns:
            HTML badge string
        """
        if isinstance(value, bytes):
            return '<span class="badge badge-danger">binary</span>'
        elif isinstance(value, (int, float)):
            return '<span class="badge badge-primary">number</span>'
        elif isinstance(value, str):
            return '<span class="badge badge-success">string</span>'
        elif isinstance(value, dict):
            return '<span class="badge badge-warning">object</span>'
        elif isinstance(value, list):
            return '<span class="badge badge-info">array</span>'
        else:
            type_name = type(value).__name__
            return f'<span class="badge badge-secondary">{type_name}</span>'
    
    def _get_leaf_summary(self, value: Any) -> str:
        """Get a summary of a leaf value.
        
        Args:
            value: Leaf value to summarize
            
        Returns:
            Summary string
        """
        if isinstance(value, bytes):
            return f"({len(value)} bytes)"
        elif isinstance(value, str) and len(value) > 30:
            return f"\"{value[:30]}...\""
        elif isinstance(value, (list, dict)):
            return f"({len(value)} items)"
        else:
            return str(value)[:50] + ("..." if len(str(value)) > 50 else "")
    
    def generate_html(self) -> str:
        """Generate an HTML visualization of the DOP2 tree.
        
        Returns:
            HTML string
        """
        tree_content = []
        
        # Sort units for consistent display
        sorted_units = sorted(self.tree.nodes.keys())
        
        for unit in sorted_units:
            node = self.tree.nodes[unit]
            
            # Generate leaf content for this unit
            leaf_content = []
            
            # Sort leaves for consistent display
            sorted_leaves = sorted(node.leaves.keys())
            
            for attr in sorted_leaves:
                value = node.leaves[attr]
                formatted_value = self._format_leaf_value(value)
                type_badge = self._get_value_type_badge(value)
                summary = self._get_leaf_summary(value)
                
                leaf_content.append(f"""
                <div class="leaf">
                    <div class="leaf-header" onclick="toggleLeaf({unit}, {attr})">
                        <span>Leaf {unit}/{attr} {type_badge}</span>
                        <span>
                            <span class="leaf-summary">{summary}</span>
                            <span id="leaf-arrow-{unit}-{attr}">▶</span>
                        </span>
                    </div>
                    <div id="leaf-content-{unit}-{attr}" class="leaf-content">
                        {formatted_value}
                    </div>
                </div>
                """)
            
            # Generate unit content
            tree_content.append(f"""
            <div class="unit" data-unit-id="{unit}">
                <div class="unit-header" onclick="toggleUnit({unit})">
                    <span>Unit {unit} <span class="badge badge-primary">{len(sorted_leaves)} leaves</span></span>
                    <span id="unit-arrow-{unit}">▶</span>
                </div>
                <div id="unit-content-{unit}" class="unit-content">
                    {''.join(leaf_content)}
                </div>
            </div>
            """)
        
        # Calculate statistics
        unit_count = len(sorted_units)
        leaf_count = sum(len(node.leaves) for node in self.tree.nodes.values())
        
        # Get exploration duration if available
        duration = 0.0
        if hasattr(self.tree, 'exploration_stats'):
            stats = getattr(self.tree, 'exploration_stats', {})
            duration = stats.get('duration', 0.0)
        
        # Fill template
        html = HTML_TEMPLATE.format(
            device_id=self.tree.device_id,
            generation=self.tree.generation.name,
            unit_count=unit_count,
            leaf_count=leaf_count,
            duration=duration,
            tree_content=''.join(tree_content)
        )
        
        return html
    
    def generate_ascii(self) -> str:
        """Generate an ASCII art visualization of the DOP2 tree.
        
        Returns:
            ASCII string
        """
        lines = []
        
        # Add header
        lines.append(f"DOP2 Tree for Device: {self.tree.device_id}")
        lines.append(f"Generation: {self.tree.generation.name}")
        lines.append("-" * 50)
        
        # Sort units for consistent display
        sorted_units = sorted(self.tree.nodes.keys())
        
        for unit in sorted_units:
            node = self.tree.nodes[unit]
            lines.append(f"Unit {unit} ({len(node.leaves)} leaves)")
            
            # Sort leaves for consistent display
            sorted_leaves = sorted(node.leaves.keys())
            
            for attr in sorted_leaves:
                value = node.leaves[attr]
                
                # Format value for display
                if isinstance(value, bytes):
                    value_str = f"<binary data: {len(value)} bytes>"
                elif isinstance(value, (dict, list)) or hasattr(value, '__dict__'):
                    value_str = f"<complex data: {type(value).__name__}>"
                else:
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:47] + "..."
                
                lines.append(f"  ├─ {attr}: {value_str}")
            
            lines.append("")
        
        # Add statistics
        unit_count = len(sorted_units)
        leaf_count = sum(len(node.leaves) for node in self.tree.nodes.values())
        
        lines.append("-" * 50)
        lines.append(f"Total Units: {unit_count}")
        lines.append(f"Total Leaves: {leaf_count}")
        
        return "\n".join(lines)
    
    def save_html(self, output_file: str) -> None:
        """Save an HTML visualization of the DOP2 tree to a file.
        
        Args:
            output_file: Path to save the HTML file
        """
        html = self.generate_html()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML visualization saved to {output_file}")
    
    def save_ascii(self, output_file: str) -> None:
        """Save an ASCII art visualization of the DOP2 tree to a file.
        
        Args:
            output_file: Path to save the ASCII file
        """
        ascii_art = self.generate_ascii()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ascii_art)
        
        logger.info(f"ASCII visualization saved to {output_file}")


def visualize_tree(tree: DOP2Tree, output_file: Optional[str] = None, format_type: str = 'html') -> Optional[str]:
    """Visualize a DOP2 tree.
    
    Args:
        tree: DOP2Tree object to visualize
        output_file: Path to save the visualization (optional)
        format_type: Type of visualization to generate ('html' or 'ascii')
        
    Returns:
        Visualization string if output_file is None, otherwise None
    """
    visualizer = DOP2Visualizer(tree)
    
    if format_type.lower() == 'html':
        if output_file:
            visualizer.save_html(output_file)
            return None
        else:
            return visualizer.generate_html()
    elif format_type.lower() == 'ascii':
        if output_file:
            visualizer.save_ascii(output_file)
            return None
        else:
            return visualizer.generate_ascii()
    else:
        raise ValueError(f"Unsupported format type: {format_type}")


def visualize_from_json(json_file: str, output_file: Optional[str] = None, format_type: str = 'html') -> Optional[str]:
    """Visualize a DOP2 tree from a JSON file.
    
    Args:
        json_file: Path to JSON file containing tree data
        output_file: Path to save the visualization (optional)
        format_type: Type of visualization to generate ('html' or 'ascii')
        
    Returns:
        Visualization string if output_file is None, otherwise None
    """
    # Import here to avoid circular imports
    from .explorer import DOP2Explorer
    
    # Load tree from JSON
    tree = asyncio.run(DOP2Explorer.import_tree_from_json(json_file))
    
    # Visualize tree
    return visualize_tree(tree, output_file, format_type) 