import jinja2
from pathlib import Path
from src.schema_mapping.ocsf_resolver import OCSFResolver

class BaseGenerator:
    """
    Base class for all deterministic rule generators.
    Loads the Jinja2 templates and initializes the OCSF schema resolver.
    """
    def __init__(self, platform_name: str, template_name: str):
        self.platform = platform_name
        self.resolver = OCSFResolver()
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "templates" / platform_name
        
        # Ensure template directory exists
        template_dir.mkdir(parents=True, exist_ok=True)
        
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)), 
            trim_blocks=True, 
            lstrip_blocks=True
        )
        self.template_name = template_name

    def generate(self, ir_dict: dict) -> str:
        """
        Translates the vendor-neutral SecurityIR dict into a platform-specific query string.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement generate()")
