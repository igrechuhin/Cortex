"""
Tests for manager_groups.py - Manager initialization groups.

This module tests:
- ManagerGroup dataclass initialization and methods
- MANAGER_GROUPS list structure and validation
- Manager group priorities and manager names
"""

from cortex.managers.manager_groups import MANAGER_GROUPS, ManagerGroup


class TestManagerGroupInitialization:
    """Tests for ManagerGroup dataclass initialization."""

    def test_manager_group_initialization(self):
        """Test ManagerGroup can be initialized with valid parameters."""
        # Arrange
        name = "test_group"
        managers = ["manager1", "manager2"]
        priority = 2

        # Act
        group = ManagerGroup(name=name, managers=managers, priority=priority)

        # Assert
        assert group.name == name
        assert group.managers == managers
        assert group.priority == priority

    def test_manager_group_str_representation(self):
        """Test ManagerGroup __str__ method returns correct format."""
        # Arrange
        group = ManagerGroup(
            name="test_group", managers=["manager1", "manager2"], priority=3
        )

        # Act
        str_repr = str(group)

        # Assert
        assert "test_group" in str_repr
        assert "2 managers" in str_repr
        assert "priority 3" in str_repr


class TestManagerGroupsList:
    """Tests for MANAGER_GROUPS list structure."""

    def test_manager_groups_list_not_empty(self):
        """Test that MANAGER_GROUPS list is not empty."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        assert isinstance(groups, list)
        assert len(groups) > 0

    def test_manager_groups_all_have_valid_priority(self):
        """Test that all manager groups have valid priority (1-4)."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        for group in groups:
            assert isinstance(group, ManagerGroup)
            assert isinstance(group.priority, int)
            assert (
                1 <= group.priority <= 4
            ), f"Group {group.name} has invalid priority {group.priority}"

    def test_manager_groups_all_have_valid_names(self):
        """Test that all manager groups have non-empty names."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        for group in groups:
            assert isinstance(group.name, str)
            assert len(group.name) > 0, "Group has empty name"
            assert group.name.strip() != "", "Group name contains only whitespace"

    def test_manager_groups_all_have_valid_manager_lists(self):
        """Test that all manager groups have valid manager lists."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        for group in groups:
            assert isinstance(group.managers, list)
            assert (
                len(group.managers) > 0
            ), f"Group {group.name} has empty managers list"
            for manager in group.managers:
                assert isinstance(
                    manager, str
                ), f"Manager in {group.name} is not a string"
                assert len(manager) > 0, f"Manager name in {group.name} is empty"

    def test_manager_group_priority_range(self):
        """Test that manager group priorities are in valid range."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        priorities = [group.priority for group in groups]
        assert all(
            1 <= p <= 4 for p in priorities
        ), f"Invalid priorities found: {priorities}"

    def test_manager_groups_unique_names(self):
        """Test that all manager group names are unique."""
        # Arrange & Act
        groups = MANAGER_GROUPS

        # Assert
        names = [group.name for group in groups]
        assert len(names) == len(set(names)), f"Duplicate group names found: {names}"
