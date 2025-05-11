"""
Models for Miele API responses.
"""

import re
from typing import Dict, Any, Optional, List, Callable, TypeVar, Union
from pydantic import BaseModel, Field

T = TypeVar('T')


class MieleResponse(BaseModel):
    """Model for Miele API responses."""
    
    # The raw data from the API
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # The root path for this response
    root_path: str = "/"
    
    class Config:
        arbitrary_types_allowed = True
    
    def _convert_value(self, key: str, value: Any) -> Any:
        """
        Convert special values in the response based on path patterns.
        
        Args:
            key: The key of the value in the response
            value: The raw value to convert
            
        Returns:
            The converted value
        """
        path = f'{self.root_path}{("/" if self.root_path[-1] != "/" else "")}{key}'
        
        # Convert time values (minutes:seconds) to total seconds
        if (re.match(r'/Devices/[0-9]+/State(/RemainingTime{1,2}|/StartTime{1,2}|/ElapsedTime{1,2})', path) 
                is not None and isinstance(value, list)):
            return int(value[0]) * 60 + int(value[1])
            
        # Recursively convert nested dictionaries
        elif isinstance(value, dict):
            return {
                k: self._convert_value(
                    f'{key}{("/" if key[-1] != "/" else "")}{k}',
                    value.get(k)
                ) for k in value.keys()
            }
            
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the response with special processing for nested objects.
        
        Args:
            key: The key to retrieve
            default: Default value if key is not found
            
        Returns:
            The value for the key, potentially converted based on path patterns
        """
        value = self.data.get(key, default)
        
        if isinstance(value, dict):
            # Handle hyperlinks in the API response
            if 'href' in value and isinstance(value['href'], str):
                return MieleResponse(
                    data=value,
                    root_path=f'{self.root_path}{value["href"]}'
                )
            else:
                return MieleResponse(
                    data=value,
                    root_path=self.root_path
                )
                
        return self._convert_value(key, value)
    
    def to_dict(self, level: int = 0) -> Dict[str, Any]:
        """
        Convert the response to a dictionary with optional depth limit.
        
        Args:
            level: How many levels of nested responses to resolve (0 = all)
            
        Returns:
            Dictionary representation of the response
        """
        def resolve(data: Any) -> Any:
            if isinstance(data, MieleResponse):
                if level == 1:
                    return data
                return data.to_dict(max(level-1, 0))
            return data
            
        return {k: resolve(self.get(k)) for k in self.data.keys()} 