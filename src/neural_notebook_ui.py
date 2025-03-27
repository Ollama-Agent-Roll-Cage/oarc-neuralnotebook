import sys
import os
import subprocess
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, QVBoxLayout, 
                           QWidget, QPushButton, QToolBar, QLabel, QStatusBar,
                           QComboBox, QFileDialog, QInputDialog, QMessageBox,
                           QCheckBox, QHBoxLayout, QButtonGroup, QRadioButton)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QObject
from PyQt6.QtGui import QColor, QPalette, QAction

from notebook_utils import NotebookDocument, NotebookCell
from ollama_agent import OllamaWorker

class NotebookApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neural Notebook")
        self.setGeometry(100, 100, 1200, 800)
        self.current_file = None
        self.notebook = NotebookDocument()
        self.ollama_model = "llama3:latest"
        self.current_editing_cell = None
        self.generating_cell_index = None
        self.is_dark_mode = False
        self.generation_mode = "single"  # "single" or "derive"
        self.derive_mode_in_progress = False
        self.derive_mode_prompt = ""
        self.iteration_count = 0
        
        # Theme colors (light mode default)
        self.update_colors(is_dark=False)
        
        # Setup UI
        self.setup_ui()
        
        # Initialize Ollama worker
        self.ollama_worker = OllamaWorker(self.ollama_model)
        self.ollama_worker.result_ready.connect(self.handle_ollama_result)
        self.ollama_worker.error_occurred.connect(self.handle_ollama_error)
        
        # Start with a blank notebook
        self.new_notebook()
        
        # Fetch available models
        self.fetch_ollama_models()
    
    def update_colors(self, is_dark=False):
        if is_dark:
            # Dark mode
            self.colors = {
                'bg_primary': '#1a1a2e',       # Dark blue background
                'bg_secondary': '#16213e',     # Slightly lighter blue for cells
                'accent': '#FFD700',           # Race car yellow (kept)
                'text': '#e1e1e1',             # Light text
                'cell_code': '#2c2c44',        # Dark blue-purple for code cells
                'cell_md': '#262640',          # Dark blue for markdown cells
                'cell_border': '#3a3a5c',      # Subtle border
                'button_bg': '#FFD700',        # Yellow button background
                'button_text': '#000000',      # Black button text
                'selected': '#FFA500',         # Orange for selected items
                'toolbar_bg': '#16213e',       # Toolbar background
                'status_bg': '#16213e'         # Status bar background
            }
        else:
            # Light mode - UPDATED with new blue color
            self.colors = {
                'bg_primary': '#058EFF',      # New blue background (changed from sky blue)
                'bg_secondary': '#e1f5fe',    # Lighter blue
                'accent': '#FFD700',          # Race car yellow
                'text': '#343434',            # Dark text
                'cell_code': '#F0F8FF',       # Light blue for code cells
                'cell_md': '#FFFAF0',         # Warm white for markdown cells
                'cell_border': '#4682B4',     # Steel blue borders
                'button_bg': '#FFD700',       # Yellow button background
                'button_text': '#000000',     # Black button text
                'selected': '#FFA500',        # Orange for selected items
                'toolbar_bg': '#e1f5fe',      # Toolbar background  
                'status_bg': '#e1f5fe'        # Status bar background
            }
    
    def setup_theme(self):
        # Set application palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['bg_primary']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.colors['text']))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.colors['cell_code']))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.colors['button_bg']))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.colors['button_text']))
        self.setPalette(palette)
        
        # Set application stylesheet
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color: {self.colors['bg_primary']}; }}
            QPushButton {{ 
                background-color: {self.colors['button_bg']}; 
                color: {self.colors['button_text']}; 
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                margin: 2px;
            }}
            QPushButton:hover {{ background-color: {self.colors['selected']}; }}
            QToolBar {{ 
                background-color: {self.colors['toolbar_bg']}; 
                border: 1px solid {self.colors['cell_border']}; 
                border-radius: 4px;
                spacing: 5px;
                padding: 5px;
            }}
            QStatusBar {{ background-color: {self.colors['status_bg']}; }}
            QComboBox {{ 
                background-color: {self.colors['cell_code']}; 
                border: 1px solid {self.colors['cell_border']}; 
                border-radius: 4px;
                padding: 4px;
                color: {self.colors['text']};
            }}
            QRadioButton, QLabel, QCheckBox {{ 
                color: {self.colors['text']}; 
                font-weight: bold; 
                margin-right: 8px;
            }}
            QRadioButton::indicator, QCheckBox::indicator {{
                width: 15px;
                height: 15px;
            }}
            QSplitter::handle {{
                background-color: {self.colors['accent']};
            }}
            QMenuBar {{ 
                background-color: {self.colors['toolbar_bg']}; 
                color: {self.colors['text']}; 
            }}
            QMenuBar::item:selected {{ background-color: {self.colors['selected']}; }}
            QMenu {{ 
                background-color: {self.colors['bg_secondary']}; 
                color: {self.colors['text']}; 
            }}
            QMenu::item:selected {{ background-color: {self.colors['selected']}; }}
        """)
        
        # Also need to update editor content
        if hasattr(self, 'editor'):
            self.update_editor()
        
    def setup_ui(self):
        # Create central widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create menu bar
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("&New Notebook", self.new_notebook)
        file_menu.addAction("&Open Notebook", self.open_notebook)
        file_menu.addAction("&Save", self.save_notebook)
        file_menu.addAction("Save &As...", self.save_notebook_as)
        
        # Ollama menu
        ollama_menu = menu_bar.addMenu("&Ollama")
        ollama_menu.addAction("Select &Model", self.select_ollama_model)
        ollama_menu.addAction("&Refresh Models", self.fetch_ollama_models)
        
        # View menu
        view_menu = menu_bar.addMenu("&View")
        toggle_theme_action = QAction("Toggle Dark/Light Mode", self)
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)
        
        # Create toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Cell operations
        cell_ops_layout = QHBoxLayout()
        cell_ops_widget = QWidget()
        cell_ops_widget.setLayout(cell_ops_layout)
        
        add_code_btn = QPushButton("+ Code")
        add_code_btn.setToolTip("Add a new code cell")
        add_code_btn.clicked.connect(lambda: self.add_cell("code"))
        cell_ops_layout.addWidget(add_code_btn)
        
        add_md_btn = QPushButton("+ Markdown")
        add_md_btn.setToolTip("Add a new markdown cell")
        add_md_btn.clicked.connect(lambda: self.add_cell("markdown"))
        cell_ops_layout.addWidget(add_md_btn)
        
        delete_cell_btn = QPushButton("Delete")
        delete_cell_btn.setToolTip("Delete selected cell")
        delete_cell_btn.clicked.connect(self.delete_current_cell)
        cell_ops_layout.addWidget(delete_cell_btn)
        
        toolbar.addWidget(cell_ops_widget)
        toolbar.addSeparator()
        
        # Generation mode selection
        gen_mode_widget = QWidget()
        gen_mode_layout = QHBoxLayout(gen_mode_widget)
        gen_mode_layout.setContentsMargins(0, 0, 0, 0)
        
        gen_mode_layout.addWidget(QLabel("Mode:"))
        
        self.mode_group = QButtonGroup(self)
        
        self.single_mode_radio = QRadioButton("Single Cell")
        self.single_mode_radio.setChecked(True)
        self.single_mode_radio.toggled.connect(lambda: self.set_generation_mode("single"))
        gen_mode_layout.addWidget(self.single_mode_radio)
        self.mode_group.addButton(self.single_mode_radio)
        
        self.derive_mode_radio = QRadioButton("Derive Notebook")
        self.derive_mode_radio.toggled.connect(lambda: self.set_generation_mode("derive"))
        gen_mode_layout.addWidget(self.derive_mode_radio)
        self.mode_group.addButton(self.derive_mode_radio)
        
        toolbar.addWidget(gen_mode_widget)
        toolbar.addSeparator()
        
        # Ollama controls widget
        ollama_widget = QWidget()
        ollama_layout = QHBoxLayout(ollama_widget)
        ollama_layout.setContentsMargins(0, 0, 0, 0)
        
        ollama_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(150)
        ollama_layout.addWidget(self.model_combo)
        
        self.use_context_checkbox = QCheckBox("Use context")
        self.use_context_checkbox.setChecked(True)
        ollama_layout.addWidget(self.use_context_checkbox)
        
        toolbar.addWidget(ollama_widget)
        
        # Generate buttons
        gen_buttons_widget = QWidget()
        gen_buttons_layout = QHBoxLayout(gen_buttons_widget)
        gen_buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create distinctive, more prominent buttons
        generate_code_btn = QPushButton("💻 Generate Code")
        generate_code_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                font-size: 14px;
                padding: 10px 20px;
            }}
        """)
        generate_code_btn.clicked.connect(lambda: self.generate_with_ollama("code"))
        gen_buttons_layout.addWidget(generate_code_btn)
        
        generate_md_btn = QPushButton("📝 Generate Markdown")
        generate_md_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                font-size: 14px;
                padding: 10px 20px;
            }}
        """)
        generate_md_btn.clicked.connect(lambda: self.generate_with_ollama("markdown"))
        gen_buttons_layout.addWidget(generate_md_btn)
        
        toolbar.addWidget(gen_buttons_widget)
        
        toolbar.addSeparator()
        
        # Run button
        run_btn = QPushButton("▶ Run Notebook")
        run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28a745;
                color: white;
                font-size: 14px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
        """)
        run_btn.clicked.connect(self.run_notebook)
        toolbar.addWidget(run_btn)
        
        # Create editor and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.editor = QWebEngineView()
        self.editor.page().loadFinished.connect(self.on_editor_loaded)
        
        self.preview = QWebEngineView()
        
        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.setSizes([600, 600])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Apply theme
        self.setup_theme()
        
        # Setup JavaScript communication channel
        self.editor.page().javaScriptConsoleMessage = self.handle_js_console
        
    def set_generation_mode(self, mode):
        if mode in ["single", "derive"]:
            self.generation_mode = mode
            self.status_label.setText(f"Generation mode set to: {mode}")
    
    def toggle_theme(self):
        # Toggle the dark mode flag
        self.is_dark_mode = not self.is_dark_mode
        
        # Update colors based on new setting
        self.update_colors(is_dark=self.is_dark_mode)
        
        # Apply the theme
        self.setup_theme()
        
    def handle_js_console(self, level, message, line, source):
        # Handle cell content updates from JavaScript
        if message.startswith("CELL_UPDATE:"):
            try:
                _, cell_index, content = message.split(":", 2)
                self.update_cell_content(int(cell_index), content)
            except Exception as e:
                print(f"Error handling cell update: {str(e)}")
                
        # Handle cell selection
        elif message.startswith("CELL_SELECTED:"):
            try:
                _, cell_index = message.split(":", 1)
                self.current_editing_cell = int(cell_index)
                print(f"Selected cell: {self.current_editing_cell}")  # Debug output
                self.update_status_bar()
            except Exception as e:
                print(f"Error handling cell selection: {str(e)}")

    def update_status_bar(self):
        """Update status bar with current cell selection and other info"""
        if self.current_editing_cell is not None and 0 <= self.current_editing_cell < len(self.notebook.cells):
            cell = self.notebook.cells[self.current_editing_cell]
            status = f"Selected: Cell {self.current_editing_cell + 1} ({cell.cell_type})"
            if self.current_file:
                status += f" | File: {os.path.basename(self.current_file)}"
            self.status_label.setText(status)
        else:
            self.current_editing_cell = None
            self.status_label.setText("No cell selected")
        
    def on_editor_loaded(self, success):
        if success:
            # Add event handlers for cell editing and selection
            self.editor.page().runJavaScript("""
                document.querySelectorAll('.cell-content').forEach(cell => {
                    cell.addEventListener('input', function() {
                        const cellIndex = this.closest('.cell').dataset.index;
                        console.log('CELL_UPDATE:' + cellIndex + ':' + this.innerText);
                    });
                    
                    cell.addEventListener('focus', function() {
                        const cellIndex = this.closest('.cell').dataset.index;
                        console.log('CELL_SELECTED:' + cellIndex);
                    });
                });
            """)
            
    def update_cell_content(self, cell_index, content):
        # Update the notebook document with edited cell content
        self.notebook.update_cell(cell_index, content)
        
    def new_notebook(self):
        self.notebook = NotebookDocument()
        self.notebook.add_cell(NotebookCell("markdown", "# New Neural Notebook\n\nCreate powerful notebooks with AI assistance."))
        self.notebook.add_cell(NotebookCell("code", "# Your code here\n"))
        self.current_file = None
        self.current_editing_cell = 0  # Set initial selection
        self.update_editor()
        self.status_label.setText("New notebook created")
        
    def open_notebook(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Notebook", "", "Jupyter Notebooks (*.ipynb)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    notebook_json = f.read()
                    
                self.notebook = NotebookDocument.from_json(notebook_json)
                self.current_file = file_path
                self.update_editor()
                self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open notebook: {str(e)}")
                
    def save_notebook(self):
        if not self.current_file:
            return self.save_notebook_as()
            
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.notebook.to_json())
            self.status_label.setText(f"Saved: {os.path.basename(self.current_file)}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save notebook: {str(e)}")
            return False
            
    def save_notebook_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Notebook As", "", "Jupyter Notebooks (*.ipynb)"
        )
        
        if file_path:
            if not file_path.endswith('.ipynb'):
                file_path += '.ipynb'
                
            self.current_file = file_path
            return self.save_notebook()
        return False
        
    def add_cell(self, cell_type):
        default_content = "# Your code here\n" if cell_type == "code" else "## New Section\n"
            
        # Add after the current cell if one is selected
        if self.current_editing_cell is not None:
            self.notebook.add_cell(NotebookCell(cell_type, default_content), self.current_editing_cell + 1)
            self.current_editing_cell += 1
        else:
            self.notebook.add_cell(NotebookCell(cell_type, default_content))
            
        self.update_editor()
        
    def delete_current_cell(self):
        print(f"Current editing cell: {self.current_editing_cell}")  # Debug output
        if self.current_editing_cell is not None and 0 <= self.current_editing_cell < len(self.notebook.cells):
            if self.notebook.delete_cell(self.current_editing_cell):
                # Reset cell selection after deletion
                if len(self.notebook.cells) > 0:
                    self.current_editing_cell = min(self.current_editing_cell, len(self.notebook.cells) - 1)
                else:
                    self.current_editing_cell = None
                self.update_editor()
                self.status_label.setText("Cell deleted")
                return
        QMessageBox.warning(self, "Warning", "Please select a cell to delete")
        self.status_label.setText("No cell selected")
        
    def run_notebook(self):
        if not self.current_file or not self.save_notebook():
            QMessageBox.warning(self, "Warning", "Save the notebook first")
            return
            
        # Open the notebook in the default Jupyter app
        try:
            if sys.platform == 'win32':
                os.startfile(self.current_file)
            elif sys.platform == 'darwin':
                subprocess.call(['open', self.current_file])
            else:
                subprocess.call(['jupyter', 'notebook', self.current_file])
            self.status_label.setText("Opened notebook in Jupyter")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Jupyter: {str(e)}")
            
    def fetch_ollama_models(self):
        """Fetch available Ollama models using subprocess directly"""
        self.status_label.setText("Fetching Ollama models...")
        self.model_combo.clear()
        
        try:
            # Use subprocess to run ollama list command
            if sys.platform == 'win32':
                proc = subprocess.Popen(['ollama', 'list'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                proc = subprocess.Popen(['ollama', 'list'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
            stdout, stderr = proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(f"Ollama command failed: {stderr.decode('utf-8')}")
                
            # Parse the output
            output = stdout.decode('utf-8')
            lines = output.strip().split('\n')
            
            # Skip header line
            if len(lines) > 1:
                models = []
                for line in lines[1:]:  # Skip header line
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        models.append(model_name)
                
                if models:
                    self.model_combo.addItems(models)
                    # Set current model if it exists in the list
                    current_index = self.model_combo.findText(self.ollama_model)
                    if current_index >= 0:
                        self.model_combo.setCurrentIndex(current_index)
                    self.status_label.setText(f"Found {len(models)} Ollama models")
                else:
                    self.model_combo.addItem("No models found")
                    self.status_label.setText("No Ollama models found")
            else:
                self.model_combo.addItem("No models found")
                self.status_label.setText("No Ollama models found")
                
        except Exception as e:
            self.status_label.setText(f"Error fetching models: {str(e)}")
            self.model_combo.addItem("Error loading models")
            
    def select_ollama_model(self):
        # Get current models from the combo box
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        if not models or models[0] == "No models found" or models[0] == "Error loading models":
            QMessageBox.warning(self, "Warning", "No Ollama models available. Please install models with 'ollama pull <model>'")
            return
            
        model, ok = QInputDialog.getItem(
            self, "Select Ollama Model", "Choose a model:", models, 0, False
        )
        
        if ok and model:
            self.ollama_model = model
            self.ollama_worker = OllamaWorker(self.ollama_model)
            self.ollama_worker.result_ready.connect(self.handle_ollama_result)
            self.ollama_worker.error_occurred.connect(self.handle_ollama_error)
            
            # Update combo box selection
            index = self.model_combo.findText(model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
                
            self.status_label.setText(f"Ollama model set to {model}")
            
    def generate_with_ollama(self, cell_type):
        selected_model = self.model_combo.currentText()
        if selected_model in ["No models found", "Error loading models"]:
            QMessageBox.warning(self, "Warning", "Please select a valid Ollama model")
            return
        
        # Handle derive mode
        if self.generation_mode == "derive":
            prompt, ok = QInputDialog.getText(
                self,
                "Generate Complete Notebook",
                "What should this notebook do?",
                text="Create a notebook that "
            )
            
            if ok and prompt:
                self.derive_mode_prompt = prompt
                self.derive_mode_in_progress = True
                
                # Clear notebook and add initial cell
                self.notebook = NotebookDocument()
                self.notebook.add_cell(NotebookCell(
                    "markdown",
                    f"# {prompt}\n\nGenerating comprehensive notebook..."
                ))
                self.update_editor()
                
                # Start phased generation
                thread = threading.Thread(
                    target=self.ollama_worker.start_generation,
                    args=(prompt, None, None, True)
                )
                thread.daemon = True
                thread.start()
                return
        
        # Single cell mode
        prompt, ok = QInputDialog.getText(
            self,
            "Generate Cell Content",
            "What would you like to generate?",
            text="Generate "
        )
        
        if ok and prompt:
            context = self.notebook.to_plain_text() if self.use_context_checkbox.isChecked() else None
            
            # Always generate both markdown and code for single cells
            self.generating_cell_index = self.current_editing_cell or len(self.notebook.cells)
            
            # Add markdown cell first
            self.notebook.add_cell(
                NotebookCell("markdown", "Generating documentation..."),
                self.generating_cell_index
            )
            
            # Add code cell
            self.notebook.add_cell(
                NotebookCell("code", "Generating code..."),
                self.generating_cell_index + 1
            )
            
            self.update_editor()
            
            # Generate both cells
            thread = threading.Thread(
                target=self.ollama_worker.start_generation,
                args=(prompt, context, "both", False)
            )
            thread.daemon = True
            thread.start()
            
    def generate_in_derive_mode(self, cell_type):
        """Handle notebook generation in derive mode"""
        if self.derive_mode_in_progress:
            self.continue_derive_mode()
            return
            
        prompt, ok = QInputDialog.getText(
            self, 
            "Derive Complete Notebook",
            "Describe the notebook you want to create:",
            text="Create a notebook that "
        )
        
        if not ok or not prompt:
            return
            
        self.derive_mode_prompt = prompt
        self.derive_mode_in_progress = True
        self.generation_queue = []
        
        # Clear or create new notebook
        self.notebook = NotebookDocument()
        self.notebook.add_cell(NotebookCell("markdown", f"# {prompt}\n\nGenerating notebook..."))
        
        # Connect to new signals
        self.ollama_worker.structure_ready.connect(self.handle_notebook_structure)
        
        # Start generation
        thread = threading.Thread(
            target=self.ollama_worker.start_generation,
            args=(prompt, None, cell_type, True)
        )
        thread.daemon = True
        thread.start()

    def handle_notebook_structure(self, structure):
        """Handle the generated notebook structure"""
        # Create initial markdown outline
        outline = f"# {structure['title']}\n\n## Sections:\n"
        for section in structure['sections']:
            outline += f"- {section['title']}\n"
        
        self.notebook.cells[0].source = outline
        self.update_editor()
        
        # Queue sections for generation
        self.generation_queue = structure['sections']
        self.current_section = 0
        
        # Start generating first section
        self.generate_next_section()

    def generate_next_section(self):
        """Generate the next section in the queue"""
        if self.current_section >= len(self.generation_queue):
            self.derive_mode_in_progress = False
            self.status_label.setText("✓ Notebook generation complete!")
            return
            
        section = self.generation_queue[self.current_section]
        self.generating_cell_index = len(self.notebook.cells)
        
        # Add section placeholder
        self.notebook.add_cell(NotebookCell("markdown", f"## {section['title']}\nGenerating..."))
        self.update_editor()
        
        # Get context of previous cells
        context = self.notebook.to_plain_text() if self.use_context_checkbox.isChecked() else None
        
        # Generate section content
        thread = threading.Thread(
            target=self.ollama_worker.start_generation,
            args=(section['title'], context, "code", True)
        )
        thread.daemon = True
        thread.start()

    def handle_ollama_result(self, result):
        if self.generating_cell_index is None:
            return

        if self.generation_mode == "derive" and self.derive_mode_in_progress:
            # Only parse if we have complete cells
            if '</md>' in result or '</code>' in result:
                # Process only the latest complete cell content
                self.parse_and_update_cells(result)
                self.current_section += 1
                self.generate_next_section()
        else:
            self.parse_and_update_cells(result)
        
        self.update_editor()

    def parse_and_update_cells(self, content):
        """Single unified method to parse and update cells"""
        new_cells = self.notebook.parse_tagged_content(content)
        if new_cells:
            # Delete the placeholder cell
            self.notebook.delete_cell(self.generating_cell_index)
            
            # Add all new cells after the current position
            for i, cell in enumerate(new_cells):
                insert_position = self.generating_cell_index + i
                self.notebook.add_cell(cell, insert_position)
            
            # Update the generating cell index to point to the last added cell
            self.generating_cell_index += len(new_cells) - 1
            
    def handle_ollama_error(self, error_msg):
        QMessageBox.critical(self, "Ollama Error", f"Error generating content: {error_msg}")
        self.status_label.setText("Ollama generation failed")
        
        # Remove the placeholder cell if there was an error
        if self.generating_cell_index is not None:
            self.notebook.delete_cell(self.generating_cell_index)
            self.generating_cell_index = None
            self.update_editor()
            
        # Reset derive mode if applicable
        if self.derive_mode_in_progress:
            self.derive_mode_in_progress = False
                
    def update_editor(self):
        # Create interactive HTML representation of the notebook
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial; 
                    margin: 0; 
                    padding: 10px;
                    background-color: {self.colors['bg_primary']};
                    color: {self.colors['text']};
                }}
                .cell {{ 
                    border: 1px solid {self.colors['cell_border']}; 
                    margin: 10px 0; 
                    padding: 10px 10px 10px 45px; 
                    position: relative;
                    border-radius: 6px;
                }}
                .cell:focus-within {{
                    border: 2px solid {self.colors['accent']};
                    box-shadow: 0 0 8px 1px rgba(255, 215, 0, 0.5);
                }}
                .cell-code {{ background-color: {self.colors['cell_code']}; }}
                .cell-markdown {{ background-color: {self.colors['cell_md']}; }}
                .cell-type {{ 
                    position: absolute; 
                    top: 5px; 
                    right: 10px; 
                    color: {self.colors['text']}; 
                    font-size: 10px;
                    user-select: none;
                    opacity: 0.7;
                }}
                .cell-run-button {{
                    position: absolute;
                    left: 8px;
                    top: 50%;
                    transform: translateY(-50%);
                    width: 25px;
                    height: 25px;
                    background-color: {self.colors['button_bg']};
                    border-radius: 50%;
                    cursor: pointer;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                .cell-run-button:hover {{ background-color: {self.colors['selected']}; }}
                .cell-run-button::after {{
                    content: '▶';
                    font-size: 12px;
                    color: {self.colors['button_text']};
                }}
                .cell-content {{ 
                    margin: 0; 
                    white-space: pre-wrap; 
                    min-height: 1.5em;
                    outline: none;
                    font-family: monospace;
                    line-height: 1.5;
                }}
                [contenteditable] {{ outline: none; }}
                
                /* Improved Markdown styling */
                .cell-markdown .cell-content {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                    line-height: 1.6;
                }}
                
                .cell-markdown h1 {{ font-size: 2em; margin: 0.67em 0; border-bottom: 1px solid {self.colors['cell_border']}; }}
                .cell-markdown h2 {{ font-size: 1.5em; margin: 0.75em 0; border-bottom: 1px solid {self.colors['cell_border']}; }}
                .cell-markdown h3 {{ font-size: 1.17em; margin: 0.83em 0; }}
                
                .cell-markdown code {{
                    background: {self.colors['cell_code']};
                    padding: 0.2em 0.4em;
                    border-radius: 3px;
                    font-family: monospace;
                }}
                
                .cell-markdown pre {{
                    background: {self.colors['cell_code']};
                    padding: 1em;
                    border-radius: 6px;
                    overflow-x: auto;
                }}
                
                .cell-markdown ul, .cell-markdown ol {{
                    padding-left: 2em;
                    margin: 1em 0;
                }}
                
                .cell-markdown blockquote {{
                    border-left: 4px solid {self.colors['accent']};
                    margin: 0;
                    padding-left: 1em;
                    color: {self.colors['text']};
                }}
            </style>
        </head>
        <body>
            <div id="notebook-container">
        """
        
        for i, cell in enumerate(self.notebook.cells):
            cell_type_class = f"cell-{cell.cell_type}"
            cell_content = "".join(cell.source)
            
            html += f"""
                <div class="cell {cell_type_class}" data-index="{i}">
                    <div class="cell-run-button" title="Run cell"></div>
                    <div class="cell-type">{cell.cell_type}</div>
                    <div class="cell-content" contenteditable="true" spellcheck="false">{cell_content}</div>
                </div>
            """
            
        html += """
            </div>
            <script>
                // Initialize selection tracking
                let currentSelectedCell = null;
                
                function selectCell(cell) {
                    // Clear previous selection visual indicator if any
                    if (currentSelectedCell) {
                        currentSelectedCell.style.boxShadow = '';
                    }
                    
                    // Set new selection
                    currentSelectedCell = cell;
                    cell.style.boxShadow = '0 0 10px rgba(255, 215, 0, 0.8)';
                    
                    // Notify Python of selection
                    const cellIndex = cell.dataset.index;
                    console.log('CELL_SELECTED:' + cellIndex);
                }

                // Initial cell selection
                document.addEventListener('DOMContentLoaded', function() {
                    const firstCell = document.querySelector('.cell');
                    if (firstCell) {
                        selectCell(firstCell);
                    }
                });

                // Make entire cell div clickable
                document.querySelectorAll('.cell').forEach(cell => {
                    cell.addEventListener('click', function(e) {
                        selectCell(this);
                        
                        // Focus content area unless clicking run button
                        if (!e.target.classList.contains('cell-run-button')) {
                            const content = this.querySelector('.cell-content');
                            if (content) {
                                content.focus();
                            }
                        }
                    });
                    
                    // Handle content focus
                    const content = cell.querySelector('.cell-content');
                    if (content) {
                        content.addEventListener('focus', function() {
                            selectCell(cell);
                        });
                    }
                });
            </script>
        </body>
        </html>
        """
        
        self.editor.setHtml(html)