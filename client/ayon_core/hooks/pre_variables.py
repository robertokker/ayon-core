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
        
        # Flatten and add template data to environment variables
        # Using AYON_ prefix for standard context keys
        prefix = "AYON_"
        variables = self._flatten_dict(template_data, parent_key=prefix)
        
        for key, value in variables.items():
            if value is not None:
                # Environment variables must be strings
                self.launch_context.env[key] = str(value)
                self.log.debug(f"Set environment variable: {key} = {value}")

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
                # Skip lists (like folder_parents) as they don't cleanly map to env vars
                continue
            else:
                items.append((new_key, v))
        return dict(items)
