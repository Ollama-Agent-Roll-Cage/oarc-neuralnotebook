import asyncio
from PyQt6.QtCore import QObject, pyqtSignal
from ollama import AsyncClient
import re
import json

class OllamaWorker(QObject):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    structure_ready = pyqtSignal(dict)  # Emits notebook structure
    cell_ready = pyqtSignal(str, str, int)  # Emits (content, cell_type, position)
    
    def __init__(self, model="llama3:latest"):
        super().__init__()
        self.model = model
        
    async def generate_content(self, prompt, notebook_context=None, cell_type="code", is_derive_mode=False):
        try:
            if is_derive_mode:
                # First, generate notebook structure
                structure = await self.generate_notebook_structure(prompt)
                self.structure_ready.emit(structure)
                
                # Then generate each section
                for section in structure['sections']:
                    cells = await self.generate_section(section, notebook_context)
                    for cell in cells:
                        self.result_ready.emit(cell)
            else:
                messages = []
                
                # Enhanced system prompt for better notebook structure
                if is_derive_mode:
                    system_prompt = """You are a Jupyter notebook generator. Generate a complete notebook with alternating markdown and code cells.
                    Use this EXACT format with clear separation between cells:

                    <md>
                    # Section Title
                    Clear explanation of what follows
                    </md>

                    <code>
                    ```python
                    # Python code with comments
                    code_here()
                    ```
                    </code>

                    <md>
                    ## Subsection
                    Explanation of results or next steps
                    </md>

                    Rules:
                    1. ALWAYS separate cells with blank lines
                    2. ALWAYS use <md></md> for markdown and <code></code> for code
                    3. ALWAYS include markdown explanations between code blocks
                    4. NEVER mix markdown and code in the same cell
                    5. Code MUST be complete and executable
                    6. When finished, end with <version_complete>Done</version_complete>
                    """
                else:
                    system_prompt = (
                        "You are a Python notebook cell generator.\n"
                        f"Generate {'code' if cell_type == 'code' else 'markdown'} content using this exact format:\n\n"
                        "For code cells:\n"
                        "<code>\n"
                        "```python\n"
                        "# Python code here\n"
                        "print('hello world')\n"
                        "```\n"
                        "</code>\n\n"
                        "For markdown cells:\n"
                        "<md>\n"
                        "# Section heading\n"
                        "Explanation text here\n"
                        "</md>\n\n"
                        "Important: ALWAYS use these exact tags and formatting."
                    )
                
                if notebook_context:
                    system_prompt += f"\n\nCurrent notebook context:\n{notebook_context}"
                
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                result = ""
                async for part in await AsyncClient().chat(model=self.model, messages=messages, stream=True):
                    content = part['message']['content']
                    result += content
                    self.result_ready.emit(result)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def start_generation(self, prompt, notebook_context=None, cell_type="code", is_derive_mode=False):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.generate_content(prompt, notebook_context, cell_type, is_derive_mode))

    async def generate_notebook_structure(self, prompt):
        """Generate high-level notebook structure first"""
        structure_prompt = f"""Generate a notebook structure for: {prompt}
        
        Return ONLY valid JSON in this EXACT format:
        {{
            "title": "Descriptive Title",
            "sections": [
                {{
                    "title": "Section Name",
                    "type": "section",
                    "dependencies": [],
                    "cells": [
                        {{"type": "markdown", "content": "Section explanation"}},
                        {{"type": "code", "purpose": "implementation"}}
                    ]
                }}
            ]
        }}"""
        
        messages = [
            {"role": "system", "content": "You are a JSON generator. Return ONLY valid JSON without any additional text."},
            {"role": "user", "content": structure_prompt}
        ]
        
        try:
            result = ""
            async for part in await AsyncClient().chat(model=self.model, messages=messages, stream=True):
                result += part['message']['content']
            
            # Clean up and extract JSON
            result = result.strip()
            json_start = result.find('{')
            json_end = result.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = result[json_start:json_end]
                try:
                    structure = json.loads(json_str)
                    if isinstance(structure, dict) and 'title' in structure and 'sections' in structure:
                        return structure
                except json.JSONDecodeError:
                    pass
                    
            # If we get here, something went wrong - use default structure
            return {
                "title": prompt.strip().capitalize(),
                "sections": [
                    {
                        "title": "Introduction",
                        "type": "section",
                        "cells": [
                            {"type": "markdown", "content": f"# {prompt}\n\nThis notebook will explore {prompt}"},
                            {"type": "code", "purpose": "Setup", "content": "# Initial setup and imports"}
                        ]
                    }
                ]
            }
                
        except Exception as e:
            print(f"Structure generation error: {str(e)}")
            return {
                "title": prompt.strip().capitalize(),
                "sections": [
                    {
                        "title": "Main Section",
                        "type": "section",
                        "cells": [{"type": "markdown", "content": f"# {prompt}"}]
                    }
                ]
            }

    async def generate_section(self, section, context=None):
        """Generate cells for a specific section"""
        section_prompt = f"""
        Generate content for notebook section: {section['title']}
        
        Use these exact tags for cells:
        <md>
        # Markdown content here
        </md>

        <code>
        ```python
        # Python code here
        ```
        </code>

        Requirements:
        1. Start with a markdown cell explaining the section
        2. Include necessary imports and setup
        3. Break code into logical chunks with explanations
        4. Add comments to code
        5. End with output explanation if applicable
        
        Context from previous sections:
        {context if context else 'No previous context'}
        """
        
        messages = [
            {"role": "system", "content": self.get_section_system_prompt()},
            {"role": "user", "content": section_prompt}
        ]
        
        try:
            complete_result = ""
            async for part in await AsyncClient().chat(model=self.model, messages=messages, stream=True):
                content = part['message']['content']
                complete_result += content
                
                # Only emit when we have a complete cell
                if '</md>' in content or '</code>' in content:
                    self.result_ready.emit(complete_result)
                    complete_result = ""  # Reset for next cell
                    
            return complete_result
            
        except Exception as e:
            print(f"Section generation error: {str(e)}")
            return f"<md>\n## {section['title']}\nContent generation failed\n</md>"

    def get_section_system_prompt(self):
        return """You are generating a section of a Jupyter notebook.
        Follow these rules:
        1. Start with a markdown cell explaining the section
        2. Include all necessary imports at the start
        3. Break code into logical chunks with markdown explanations
        4. Include error handling in code cells
        5. Add markdown cells explaining outputs
        
        Use these exact tags:
        <md>
        # Markdown content
        </md>
        
        <code>
        ```python
        # Code content
        ```
        </code>
        """
    
    async def generate_complete_notebook(self, prompt):
        """Generate a complete notebook in phases"""
        phases = [
            ("planning", "Plan the notebook structure and outline key sections"),
            ("setup", "Generate setup and import code cells"),
            ("implementation", "Implement core functionality"),
            ("analysis", "Add analysis and visualization cells"),
            ("documentation", "Add comprehensive documentation and explanations")
        ]
        
        structure = None
        current_context = ""
        
        for phase, phase_prompt in phases:
            phase_message = f"""
            Phase: {phase}
            Main prompt: {prompt}
            Current context: {current_context}
            
            Generate the next set of cells for this phase.
            Include both markdown documentation and code cells.
            
            Use these exact tags:
            <md>Markdown content</md>
            <code>```python
            Code content
            ```</code>
            """
            
            result = ""
            async for part in await AsyncClient().chat(
                model=self.model,
                messages=[{"role": "user", "content": phase_message}],
                stream=True
            ):
                content = part['message']['content']
                result += content
                # Process complete cells as they arrive
                if '</md>' in content or '</code>' in content:
                    self.result_ready.emit(result)
                    current_context += f"\n{result}"
                    result = ""
                    
            # Small delay between phases
            await asyncio.sleep(1)
