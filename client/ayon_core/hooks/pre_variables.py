import os
import json
from collections import defaultdict

import ayon_api
from ayon_applications import PreLaunchHook
from ayon_core.pipeline.template_data import get_template_data

class AddAnatomyVariablesToEnv(PreLaunchHook):
    """Add anatomy template keys to environment variables.
    
    This allows OCIO configs and other pipeline tools to use variables
    like AYON_PROJECT_NAME, AYON_FOLDER_NAME in their paths mapping to the
    anatomy templates.
    """
    
    order = 1  # Should be relatively early, before things that might use these variables
    
    def execute(self):
        project_entity = self.data.get("project_entity")
        folder_entity = self.data.get("folder_entity")
        task_entity = self.data.get("task_entity")
        
        if not project_entity:
            self.log.info("Project entity is not available. Skipping anatomy variables.")
            return

        template_data = get_template_data(
            project_entity,
            folder_entity,
            task_entity,
            self.host_name,
            self.data.get("project_settings")
        )
        
        # Inject parent folder names by their type
        if folder_entity:
            project_name = project_entity["name"]
            
            # Initialize all project folder types to an empty string to ensure they exist in the env
            project_folder_types = project_entity.get("folderTypes", [])
            for p_type in project_folder_types:
                template_data[p_type["name"]] = ""
            
            # Reconstruct the paths of all parents
            # Example path: "/seq01/sh010" -> parents: ["/seq01"]
            parts = [p for p in folder_entity["path"].split("/") if p]
            parent_paths = []
            current_path = ""
            for p in parts[:-1]: # exclude the current folder itself
                current_path += f"/{p}"
                parent_paths.append(current_path)
                
            type_groups = defaultdict(list)
            
            # Add parents to their type groups
            if parent_paths:
                parent_folders = ayon_api.get_folders(
                    project_name, 
                    folder_paths=parent_paths, 
                    fields={"name", "folderType"}
                )
                
                for pf in parent_folders:
                    ftype = pf.get("folderType")
                    fname = pf.get("name")
                    if ftype and fname:
                        type_groups[ftype].append(fname)
                        
            # Also add the current folder itself to its type group
            current_ftype = folder_entity.get("folderType")
            current_fname = folder_entity.get("name")
            if current_ftype and current_fname:
                type_groups[current_ftype].append(current_fname)
                        
            for ftype, fnames in type_groups.items():
                if len(fnames) == 1:
                    template_data[ftype] = fnames[0]
                else:
                    template_data[ftype] = fnames
        
        # Flatten and add template data to environment variables
        # Using AYON_ prefix for standard context keys
        prefix = "AYON_"
        variables = self._flatten_dict(template_data, parent_key=prefix)
        
        is_windows = os.name == "nt"
        
        for key, value in variables.items():
            if value is not None:
                value_str = str(value)
                
                # Fix slashes on Windows
                if is_windows and "/" in value_str:
                    value_str = value_str.replace("/", "\\")
                
                # Environment variables must be strings
                self.launch_context.env[key] = value_str
                self.log.debug(f"Set environment variable: {key} = {value_str}")

    def _flatten_dict(self, d, parent_key='', sep='_'):
        """Flatten a nested dictionary for use as environment variable keys.
        
        E.g., prefix_project_name, prefix_folder_path
        """
        items = []
        for k, v in d.items():
            # Create the new key, uppercase it for standard env var formatting
            new_key = f"{parent_key}{k}".upper() if parent_key else k.upper()
            
            if isinstance(v, dict):
                # Recursively flatten dictionaries
                items.extend(self._flatten_dict(v, new_key + sep, sep=sep).items())
            elif isinstance(v, list):
                # Serialize lists as JSON string so they can be parsed
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)
