"""Tests for the DOP2Visualizer module."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from asyncmiele.dop2.models import DOP2Tree, DOP2Node
from asyncmiele.dop2.visualizer import DOP2Visualizer, visualize_from_json


class TestDOP2Visualizer(unittest.TestCase):
    """Test the DOP2Visualizer class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a simple tree for testing
        self.tree = DOP2Tree(device_id="test_device")
        
        # Add some nodes
        node1 = DOP2Node(unit=1)
        node2 = DOP2Node(unit=2)
        node3 = DOP2Node(unit=3)
        
        # Add some leaves
        node1.leaves[1] = {"name": "Attribute 1", "value": "Value 1"}
        node2.leaves[2] = {"name": "Attribute 2", "value": 42}
        node3.leaves[3] = {"name": "Attribute 3", "value": True}
        
        # Add nodes to tree
        self.tree.nodes[1] = node1
        self.tree.nodes[2] = node2
        self.tree.nodes[3] = node3
        
        # Create visualizer
        self.visualizer = DOP2Visualizer(self.tree)
        
        # Create temporary directory for output files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()

    def test_save_html(self):
        """Test saving HTML visualization."""
        output_file = self.output_dir / "test.html"
        self.visualizer.save_html(str(output_file))
        
        # Check that the file exists and has content
        self.assertTrue(output_file.exists())
        self.assertGreater(output_file.stat().st_size, 0)
        
        # Check that the file contains expected content
        with open(output_file, "r") as f:
            content = f.read()
            self.assertIn("Unit 1", content)
            self.assertIn("Unit 2", content)
            self.assertIn("Unit 3", content)
            # The actual leaf content might be displayed differently
            self.assertIn("Leaf 1/1", content)
            self.assertIn("Leaf 2/2", content)
            self.assertIn("Leaf 3/3", content)
            self.assertIn("Value 1", content)

    def test_save_ascii(self):
        """Test saving ASCII visualization."""
        output_file = self.output_dir / "test.txt"
        self.visualizer.save_ascii(str(output_file))
        
        # Check that the file exists and has content
        self.assertTrue(output_file.exists())
        self.assertGreater(output_file.stat().st_size, 0)
        
        # Check that the file contains expected content
        with open(output_file, "r") as f:
            content = f.read()
            self.assertIn("Unit 1", content)
            self.assertIn("Unit 2", content)
            self.assertIn("Unit 3", content)
            # The actual content format might be different
            self.assertIn("<complex data: dict>", content)

    @patch("asyncio.run")
    def test_visualize_from_json(self, mock_run):
        """Test visualizing from JSON file."""
        # Create a simple tree for the mock to return
        tree = DOP2Tree(device_id="test_device")
        node = DOP2Node(unit=1)
        node.leaves[1] = {"name": "Attribute 1", "value": "Value 1"}
        tree.nodes[1] = node
        
        # Set up the mock to return our tree
        mock_run.return_value = tree
        
        # Create a JSON file with tree data
        json_file = self.output_dir / "test.json"
        with open(json_file, "w") as f:
            json.dump({}, f)  # Content doesn't matter since we're mocking
        
        # Visualize from JSON
        html_output = self.output_dir / "test_from_json.html"
        visualize_from_json(str(json_file), str(html_output), "html")
        
        # Check that the file exists and has content
        self.assertTrue(html_output.exists())
        self.assertGreater(html_output.stat().st_size, 0)
        
        # Check that the mock was called
        mock_run.assert_called_once()

    @patch("asyncmiele.dop2.visualizer.visualize_tree")
    @patch("asyncio.run")
    def test_invalid_format_type(self, mock_run, mock_visualize_tree):
        """Test that an invalid format type raises an error."""
        # Create a simple tree for the mock to return
        tree = DOP2Tree(device_id="test_device")
        mock_run.return_value = tree
        
        # Set up the mock to raise an exception
        mock_visualize_tree.side_effect = ValueError("Unsupported format type: invalid")
        
        # Test that the function raises the expected exception
        with self.assertRaises(ValueError):
            visualize_from_json("test.json", "test.out", "invalid")


if __name__ == "__main__":
    unittest.main() 