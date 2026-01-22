import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Loads deterministic rules from YAML configs"""
    
    def _init_(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        
    def load_all_configs(self) -> Dict[str, Any]:
        """Load all configuration files"""
        configs = {}
        
        # Load thresholds
        thresholds_path = self.config_dir / "thresholds.yaml"
        if thresholds_path.exists():
            with open(thresholds_path, 'r') as f:
                configs['thresholds'] = yaml.safe_load(f)
        
        # Load rules
        rules_path = self.config_dir / "rules.yaml"
        if rules_path.exists():
            with open(rules_path, 'r') as f:
                configs['rules'] = yaml.safe_load(f)
        
        return configs
    
    def get_thresholds(self) -> Dict[str, Any]:
        """Get safety thresholds"""
        configs = self.load_all_configs()
        return configs.get('thresholds', {})
    
    def get_rules(self) -> Dict[str, Any]:
        """Get decision rules"""
        configs = self.load_all_configs()
        return configs.get('rules', {})