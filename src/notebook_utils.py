import json
import re

class NotebookCell:
    def __init__(self, cell_type="code", source="", outputs=None):
        self.cell_type = cell_type
        self.source = source if isinstance(source, list) else [source]
        self.outputs = outputs or []
        self.metadata = {}
        
    def to_dict(self):
        cell_dict = {
            "cell_type": self.cell_type,
            "metadata": self.metadata,
            "source": self.source
        }
        
        if self.cell_type == "code":
            cell_dict["execution_count"] = None
            cell_dict["outputs"] = self.outputs
            
        return cell_dict
        
class NotebookDocument:
    def __init__(self):
        self.cells = []
        self.metadata = {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py", "mimetype": "text/x-python", "name": "python",
                "nbconvert_exporter": "python", "pygments_lexer": "ipython3", "version": "3.8.10"
            }
        }
        
    def add_cell(self, cell, index=None):
        if index is not None and 0 <= index < len(self.cells):
            self.cells.insert(index, cell)
        else:
            self.cells.append(cell)
    
    def update_cell(self, index, content):
        if 0 <= index < len(self.cells):
            self.cells[index].source = content if isinstance(content, list) else [content]
            return True
        return False
    
    def delete_cell(self, index):
        if 0 <= index < len(self.cells):
            del self.cells[index]
            return True
        return False
        
    def to_dict(self):
        return {
            "cells": [cell.to_dict() for cell in self.cells if cell.source and any(s.strip() for s in cell.source)],  # Only include non-empty cells
            "metadata": self.metadata,
            "nbformat": 4,
            "nbformat_minor": 5
        }
        
    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)
    
    def to_plain_text(self):
        text = "# Notebook Content:\n\n"
        for i, cell in enumerate(self.cells):
            content = "".join(cell.source)
            text += f"## Cell {i+1} ({cell.cell_type}):\n{content}\n\n"
        return text
        
    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        doc = cls()
        doc.metadata = data.get("metadata", doc.metadata)
        
        for cell_data in data.get("cells", []):
            cell = NotebookCell(
                cell_type=cell_data.get("cell_type", "code"),
                source=cell_data.get("source", []),
                outputs=cell_data.get("outputs", [])
            )
            cell.metadata = cell_data.get("metadata", {})
            doc.add_cell(cell)
            
        return doc

    def parse_tagged_content(self, content):
        """Parse content with markdown and code tags into separate cells"""
        cells = []
        
        # Clean up content first
        content = content.strip()
        
        # Handle version complete tag
        if '<version_complete>' in content:
            content = content.split('<version_complete>')[0].strip()
        
        # Split by complete cell tags
        cell_patterns = [
            (r'<md>(.*?)</md>', 'markdown'),
            (r'<code>(.*?)</code>', 'code')
        ]
        
        for pattern, cell_type in cell_patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                cell_content = match.group(1).strip()
                if cell_type == 'code':
                    # Clean up code block markers
                    cell_content = re.sub(r'```python\s*\n?|```\s*\n?', '', cell_content)
                cells.append(NotebookCell(cell_type, cell_content))
        
        return cells
