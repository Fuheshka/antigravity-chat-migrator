import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from antigravity_migrator.project_registry import (
    ProjectRegistry,
    load_registered_projects,
    normalize_workspace_uri,
    register_new_project,
)


class TestProjectRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.projects_dir = self.config_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalize_workspace_uri_macos(self):
        # Local Unix path
        self.assertEqual(
            normalize_workspace_uri("/Users/testuser/project"),
            "file:///Users/testuser/project",
        )
        # With trailing slash
        self.assertEqual(
            normalize_workspace_uri("/Users/testuser/project/"),
            "file:///Users/testuser/project",
        )
        # Already canonical
        self.assertEqual(
            normalize_workspace_uri("file:///Users/testuser/project"),
            "file:///Users/testuser/project",
        )
        # Double slash
        self.assertEqual(
            normalize_workspace_uri("file://Users/testuser/project"),
            "file:///Users/testuser/project",
        )
        # Single slash
        self.assertEqual(
            normalize_workspace_uri("file:/Users/testuser/project"),
            "file:///Users/testuser/project",
        )

    def test_normalize_workspace_uri_windows(self):
        # Backslashes
        self.assertEqual(
            normalize_workspace_uri(r"C:\Users\testuser\project"),
            "file:///C:/Users/testuser/project",
        )
        # Forward slashes with drive
        self.assertEqual(
            normalize_workspace_uri("C:/Users/testuser/project"),
            "file:///C:/Users/testuser/project",
        )
        # Lowercase drive letter
        self.assertEqual(
            normalize_workspace_uri("c:/Users/testuser/project"),
            "file:///C:/Users/testuser/project",
        )
        # file:// prefix with drive
        self.assertEqual(
            normalize_workspace_uri("file://C:/Users/testuser/project"),
            "file:///C:/Users/testuser/project",
        )
        # file:/// prefix with backslashes
        self.assertEqual(
            normalize_workspace_uri(r"file:///C:\Users\testuser\project"),
            "file:///C:/Users/testuser/project",
        )

    def test_load_registered_projects(self):
        # 1. Project with gitFolder
        proj1 = {
            "id": "proj-uuid-1",
            "name": "migrator",
            "projectResources": {
                "resources": [
                    {
                        "gitFolder": {
                            "folderUri": "file:///Users/testuser/migrator",
                            "defaultBranch": "main",
                        }
                    }
                ]
            },
        }
        with open(self.projects_dir / "proj-uuid-1.json", "w", encoding="utf-8") as f:
            json.dump(proj1, f)

        # 2. Project with folderUri directly (e.g. Obsidian Vault with space)
        proj2 = {
            "id": "proj-uuid-2",
            "name": "My Vault",
            "projectResources": {
                "resources": [
                    {
                        "folderUri": "file:///Users/testuser/My%20Vault",
                    }
                ]
            },
        }
        with open(self.projects_dir / "proj-uuid-2.json", "w", encoding="utf-8") as f:
            json.dump(proj2, f)

        # 3. outside-of-project.json must be excluded!
        outside = {
            "id": "outside-of-project",
            "name": "Outside of Project",
            "settings": {},
        }
        with open(self.projects_dir / "outside-of-project.json", "w", encoding="utf-8") as f:
            json.dump(outside, f)

        # 4. default-cli-project.json without resources
        cli_proj = {
            "id": "default-cli-project",
            "name": "CLI Project",
            "projectResources": {},
        }
        with open(self.projects_dir / "default-cli-project.json", "w", encoding="utf-8") as f:
            json.dump(cli_proj, f)

        # Load passing root config_dir
        mapping = load_registered_projects(self.config_dir)
        self.assertEqual(mapping.get("file:///Users/testuser/migrator"), "proj-uuid-1")
        # Should also resolve decoded URI for My Vault
        self.assertEqual(mapping.get("file:///Users/testuser/My%20Vault"), "proj-uuid-2")
        self.assertEqual(mapping.get("file:///Users/testuser/My Vault"), "proj-uuid-2")

        # outside-of-project must NOT be in mapping values
        self.assertNotIn("outside-of-project", mapping.values())

        # Load passing projects_dir directly
        mapping_direct = load_registered_projects(self.projects_dir)
        self.assertEqual(mapping_direct.get("file:///Users/testuser/migrator"), "proj-uuid-1")

    def test_load_registered_projects_corrupt_and_missing(self):
        # Empty / non-existent directory
        non_existent = self.config_dir / "does_not_exist"
        self.assertEqual(load_registered_projects(non_existent), {})

        # Corrupt JSON file
        with open(self.projects_dir / "corrupted.json", "w", encoding="utf-8") as f:
            f.write("{invalid json")

        mapping = load_registered_projects(self.config_dir)
        self.assertEqual(mapping, {})

    def test_register_new_project_git_repo(self):
        # Create a workspace folder with .git
        workspace = Path(self.temp_dir.name) / "workspaces" / "test-repo"
        (workspace / ".git").mkdir(parents=True, exist_ok=True)

        workspace_uri = f"file://{workspace.as_posix()}"
        project_id = register_new_project(
            config_dir=self.config_dir,
            workspace_uri=workspace_uri,
            project_name="Custom Repo Name",
        )

        self.assertTrue(project_id)
        # Check descriptor file exists
        desc_path = self.projects_dir / f"{project_id}.json"
        self.assertTrue(desc_path.exists())

        with open(desc_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["id"], project_id)
        self.assertEqual(data["name"], "Custom Repo Name")
        self.assertEqual(data["permissionGrants"]["v2Migrated"], True)
        self.assertEqual(data["isWorkspaceOnly"], False)
        # Must have gitFolder resource
        resources = data["projectResources"]["resources"]
        self.assertEqual(len(resources), 1)
        self.assertIn("gitFolder", resources[0])
        self.assertEqual(
            resources[0]["gitFolder"]["folderUri"],
            normalize_workspace_uri(workspace_uri),
        )

    def test_register_new_project_plain_folder(self):
        # Workspace without .git
        workspace = Path(self.temp_dir.name) / "workspaces" / "docs-folder"
        workspace.mkdir(parents=True, exist_ok=True)

        workspace_uri = f"file://{workspace.as_posix()}"
        # Test default project_name derivation
        project_id = register_new_project(
            config_dir=self.config_dir,
            workspace_uri=workspace_uri,
        )

        desc_path = self.projects_dir / f"{project_id}.json"
        self.assertTrue(desc_path.exists())

        with open(desc_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["name"], "docs-folder")
        resources = data["projectResources"]["resources"]
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0].get("folderUri") or resources[0].get("gitFolder", {}).get("folderUri"),
            normalize_workspace_uri(workspace_uri),
        )

    def test_project_registry_class(self):
        registry = ProjectRegistry(config_dir=self.config_dir)
        workspace = "/Users/testuser/auto-project"
        norm_uri = normalize_workspace_uri(workspace)

        # Before registration
        self.assertIsNone(registry.get_project_id(workspace))

        # Get or register
        proj_id, created = registry.get_or_register(workspace)
        self.assertTrue(created)
        self.assertTrue(proj_id)

        # Now lookup returns proj_id
        self.assertEqual(registry.get_project_id(workspace), proj_id)
        self.assertEqual(registry.get_project_id(norm_uri), proj_id)

        # Second get_or_register returns existing without creating new
        proj_id2, created2 = registry.get_or_register(workspace)
        self.assertFalse(created2)
        self.assertEqual(proj_id, proj_id2)

    def test_package_exports(self):
        import antigravity_migrator as am

        self.assertTrue(hasattr(am, "ProjectRegistry"))
        self.assertTrue(hasattr(am, "load_registered_projects"))
        self.assertTrue(hasattr(am, "normalize_workspace_uri"))
        self.assertTrue(hasattr(am, "register_new_project"))

    def test_path_manager_integration(self):
        from antigravity_migrator.paths import PathManager

        pm = PathManager(config_dir=self.config_dir)
        registry = ProjectRegistry(path_manager=pm)
        self.assertEqual(registry.projects_dir, self.projects_dir)


if __name__ == "__main__":
    unittest.main()

