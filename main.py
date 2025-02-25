#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from cryptography.fernet import Fernet
import os
import logging
import re
import json

# Generate or load encryption key
def get_or_create_key():
    key_file = 'key.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
    return key

key = get_or_create_key()
cipher_suite = Fernet(key)

class StickyNoteWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Sticky Notes")
        self.unsaved_changes = False
        self.is_shaded = False
        self.mode = "text"  # Track current mode
        self.cells = {}  # Store cell entries for calc mode
        self.formulas = {}  # Store formulas for calc mode
        self.cell_dependencies = {}  # Track which cells depend on which other cells
        self.active_formula_cell = None  # Track cell being edited
        self.updating_cell = False  # Prevent recursive updates
        self.is_displaying_formula = False  # Track if we're showing formula text or value
        logging.info(f"Initial unsaved_changes: {self.unsaved_changes}")
        self.set_default_size(400, 300)

        # Create a header bar
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.props.title = "New Note"
        header_bar.get_style_context().add_class("titlebar")
        header_bar.get_style_context().add_class("default-decoration")
        self.set_titlebar(header_bar)

        # Add windowshade button to the header bar
        shade_button = Gtk.Button()
        shade_image = Gtk.Image.new_from_icon_name("view-restore-symbolic", Gtk.IconSize.BUTTON)
        shade_button.add(shade_image)
        shade_button.set_tooltip_text("Toggle Windowshade")
        shade_button.connect("clicked", self.on_shade_clicked)
        header_bar.pack_end(shade_button)

        # Add a button to the header bar
        note_manager_button = Gtk.Button()
        note_manager_image = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.BUTTON)
        note_manager_button.add(note_manager_image)
        note_manager_button.set_tooltip_text("Manage Notes")
        note_manager_button.get_style_context().add_class("suggested-action")
        note_manager_button.connect("clicked", self.on_note_manager_clicked)
        header_bar.pack_start(note_manager_button)

        # Add mode toggle button
        mode_button = Gtk.Button()
        self.mode_image = Gtk.Image.new_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)
        mode_button.add(self.mode_image)
        mode_button.set_tooltip_text("Switch to Calc Mode")
        mode_button.connect("clicked", self.on_mode_toggle)
        header_bar.pack_start(mode_button)

        # Store main content in a box for windowshade
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_vexpand(True)
        self.content_box.set_valign(Gtk.Align.FILL)
        super().add(self.content_box)

        # Create scrolled window for text view
        self.text_scroll = Gtk.ScrolledWindow()
        self.text_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.text_scroll.set_vexpand(True)
        self.text_scroll.set_valign(Gtk.Align.FILL)
        
        # Create text view with styling
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(10)
        self.text_view.set_right_margin(10)
        self.text_view.set_top_margin(10)
        self.text_view.set_bottom_margin(10)
        self.text_view.get_style_context().add_class("view")
        self.text_view.set_vexpand(True)
        self.text_view.set_valign(Gtk.Align.FILL)
        self.text_scroll.add(self.text_view)
        
        # Initially show text view
        self.content_box.add(self.text_scroll)

        # Create grid for calc mode
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(1)
        self.grid.set_row_spacing(1)
        self.grid.set_margin_start(10)
        self.grid.set_margin_end(10)
        self.grid.set_margin_top(10)
        self.grid.set_margin_bottom(10)
        self.grid.set_vexpand(True)  # Make grid expand vertically
        self.grid.set_valign(Gtk.Align.FILL)  # Fill available space
        self.grid.set_hexpand(True)  # Make grid expand horizontally
        self.grid.set_halign(Gtk.Align.FILL)  # Fill available space

        # Add column headers (A-T)
        for col in range(20):
            label = Gtk.Label(label=chr(65 + col))
            label.get_style_context().add_class("column-header")
            self.grid.attach(label, col + 1, 0, 1, 1)

        # Add row headers (1-50)
        for row in range(50):
            label = Gtk.Label(label=str(row + 1))
            label.get_style_context().add_class("row-header")
            self.grid.attach(label, 0, row + 1, 1, 1)

        # Add cells
        for row in range(50):
            for col in range(20):
                entry = Gtk.Entry()
                entry.set_width_chars(10)
                entry.connect('changed', self.on_cell_changed, row, col)
                entry.connect('key-press-event', self.on_cell_key_press, row, col)
                entry.connect('button-press-event', self.on_cell_clicked, row, col)
                entry.connect('focus-out-event', self.on_cell_focus_out, row, col)
                entry.connect('focus-in-event', self.on_cell_focus_in, row, col)
                self.cells[(row, col)] = entry
                self.grid.attach(entry, col + 1, row + 1, 1, 1)

        # Create grid scrolled window but don't add it yet
        self.grid_scroll = Gtk.ScrolledWindow()
        self.grid_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.grid_scroll.add(self.grid)
        self.grid_scroll.set_vexpand(True)  # Make scrolled window expand vertically
        self.grid_scroll.set_valign(Gtk.Align.FILL)  # Fill available space
        self.grid_scroll.set_hexpand(True)  # Make scrolled window expand horizontally 
        self.grid_scroll.set_halign(Gtk.Align.FILL)  # Fill available space

        # Set up CSS styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .titlebar { 
                background: linear-gradient(to bottom, #4a90d9, #357abd);
                font-size: 14pt;
                font-weight: 300;  
                color: #1a1a1a;    
            }
            .titlebar button { 
                color: white; 
                min-width: 24px;
                min-height: 24px;
                background: transparent;
                border: none;
                border-radius: 12px;
                transition: all 250ms ease-in-out;
            }
            .titlebar button:hover { 
                background: rgba(255, 255, 255, 0.2);
            }
            .titlebar button image { 
                color: white;
                -gtk-icon-effect: none;
                background: transparent;
            }
            .titlebar button:hover image {
                color: rgba(255, 255, 255, 0.9);
            }
            .delete-button {
                background: transparent;
                border: none;
                padding: 4px;
                border-radius: 12px;
                transition: all 250ms ease-in-out;
            }
            .delete-button:hover {
                background: rgba(255, 0, 0, 0.1);
            }
            .delete-button image {
                color: #ff0000;
                background: transparent;
            }
            .view { font-family: Sans; font-size: 12pt; }
            .new-note-button { 
                background: #4a90d9;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                transition: all 250ms ease-in-out;
            }
            .new-note-button:hover { 
                background: #5aa0e9;
            }
            .suggested-action { 
                background: #2ecc71; 
                color: white;
                padding: 8px 16px;   
                border-radius: 4px;
            }
            .column-header {
                font-weight: bold;
            }
            .row-header {
                font-weight: bold;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Connect events
        self.text_view.get_buffer().connect("changed", self.on_text_changed)
        self.connect("delete-event", self.on_delete_event)
        logging.info("Connected delete-event signal")
        self.start_new_note()

    def on_text_changed(self, buffer):
        logging.info("on_text_changed triggered")
        self.unsaved_changes = True
        logging.info(f"unsaved_changes set to {self.unsaved_changes}")
        logging.info("on_text_changed successfully triggered and unsaved_changes set")
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, False)
        encrypted_content = cipher_suite.encrypt(content.encode())
        logging.info(f"Encrypted content: {encrypted_content}")

    def get_note_preview(self):
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, False)
        # Strip whitespace and replace newlines with spaces
        content = ' '.join(content.strip().splitlines())
        return content[:23] if content else ""

    def update_title(self, name=None):
        header_bar = self.get_titlebar()
        if name:
            header_bar.props.title = name
        else:
            header_bar.props.title = "New Note"

    def on_delete_event(self, widget, event):
        logging.info("on_delete_event triggered")
        logging.info(f"unsaved_changes: {self.unsaved_changes}")
        if self.unsaved_changes:
            # Check for content in current mode
            has_content = False
            if self.mode == 'text':
                buffer = self.text_view.get_buffer()
                start, end = buffer.get_bounds()
                content = buffer.get_text(start, end, False).strip()
                has_content = bool(content)
            else:  # calc mode
                # Check if any cell has content
                has_content = any(entry.get_text().strip() for entry in self.cells.values())
                
            if has_content:
                dialog = Gtk.Dialog(
                    transient_for=self,
                    flags=0,
                    title="Save changes?"
                )
                
                # Style dialog header bar
                header_bar = dialog.get_header_bar()
                if header_bar:
                    header_bar.get_style_context().add_class("titlebar")
                
                dialog.add_buttons(
                    Gtk.STOCK_YES, Gtk.ResponseType.YES,
                    Gtk.STOCK_NO, Gtk.ResponseType.NO,
                    Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL
                )
                
                # Add dialog content
                content_area = dialog.get_content_area()
                content_area.set_margin_start(10)
                content_area.set_margin_end(10)
                content_area.set_margin_top(10)
                content_area.set_margin_bottom(10)
                content_area.set_spacing(10)
                
                label = Gtk.Label(label="Do you want to save your changes?")
                content_area.add(label)
                
                entry = Gtk.Entry()
                suggested_name = self.get_note_preview() if self.mode == 'text' else "Spreadsheet"
                entry.set_text(suggested_name)
                entry.set_placeholder_text("Enter save name")
                entry.set_activates_default(True)  # Make Enter trigger default response
                content_area.add(entry)
                
                # Style the buttons
                dialog.set_default_response(Gtk.ResponseType.YES)  # Make Yes the default
                for button in dialog.get_action_area().get_children():
                    if dialog.get_response_for_widget(button) == Gtk.ResponseType.YES:
                        button.get_style_context().add_class("suggested-action")
                    elif dialog.get_response_for_widget(button) == Gtk.ResponseType.NO:
                        button.get_style_context().add_class("destructive-action")
                
                dialog.show_all()
                response = dialog.run()
                if response == Gtk.ResponseType.YES:
                    save_name = entry.get_text()
                    if save_name:
                        note_data = {
                            'mode': self.mode,
                            'text_content': '',
                            'calc_data': {
                                'cells': {},
                                'formulas': {}
                            }
                        }

                        # Save text content if in text mode
                        if self.mode == 'text':
                            buffer = self.text_view.get_buffer()
                            start, end = buffer.get_bounds()
                            note_data['text_content'] = buffer.get_text(start, end, False)

                        # Save calc data if in calc mode
                        if self.mode == 'calc':
                            for (row, col), entry in self.cells.items():
                                cell_value = entry.get_text()
                                if cell_value:  # Only save non-empty cells
                                    note_data['calc_data']['cells'][f"{row},{col}"] = cell_value
                            
                            # Save formulas
                            note_data['calc_data']['formulas'] = {
                                f"{row},{col}": formula 
                                for (row, col), formula in self.formulas.items()
                            }

                        # Convert to JSON and encrypt
                        json_data = json.dumps(note_data)
                        encrypted_content = cipher_suite.encrypt(json_data.encode())
                        with open(f'{save_name}.enc', 'wb') as f:
                            f.write(encrypted_content)
                        self.update_title(save_name)
                    else:
                        self.save_note()
                elif response == Gtk.ResponseType.CANCEL:
                    dialog.destroy()
                    return True
                dialog.destroy()
        Gtk.main_quit()
        return False

    def save_note(self):
        # Create a dictionary to store both text and calc data
        note_data = {
            'mode': self.mode,
            'text_content': '',
            'calc_data': {
                'cells': {},
                'formulas': {}
            }
        }

        # Save text content
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        note_data['text_content'] = buffer.get_text(start, end, False)

        # Save calc data
        for (row, col), entry in self.cells.items():
            cell_value = entry.get_text()
            if cell_value:  # Only save non-empty cells
                note_data['calc_data']['cells'][(row, col)] = cell_value
        
        # Save formulas
        note_data['calc_data']['formulas'] = {
            f"{row},{col}": formula 
            for (row, col), formula in self.formulas.items()
        }

        if note_data['text_content'] or note_data['calc_data']['cells']:
            # Convert to JSON and encrypt
            json_data = json.dumps(note_data)
            encrypted_content = cipher_suite.encrypt(json_data.encode())
            with open('.note.enc', 'wb') as f:
                f.write(encrypted_content)
            self.unsaved_changes = False
            self.update_title()

    def load_note(self):
        if os.path.exists('.note.enc'):
            try:
                with open('.note.enc', 'rb') as f:
                    encrypted_content = f.read()
                decrypted_content = cipher_suite.decrypt(encrypted_content).decode()
                
                # Try to parse as JSON (new format)
                try:
                    note_data = json.loads(decrypted_content)
                    self._load_note_data(note_data)
                except json.JSONDecodeError:
                    # Old format - just text content
                    buffer = self.text_view.get_buffer()
                    buffer.set_text(decrypted_content)
                    # Switch to text mode if needed
                    if self.mode != 'text':
                        self.mode = 'text'
                        self.content_box.remove(self.grid_scroll)
                        self.content_box.add(self.text_scroll)
                        self.text_scroll.show_all()
                        self.mode_image.set_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)

            except Exception as e:
                print(f"Load error: {e}")
                buffer = self.text_view.get_buffer()
                buffer.set_text("")

    def _load_note_data(self, note_data):
        """Helper method to load note data in the new format"""
        # Load text content
        buffer = self.text_view.get_buffer()
        buffer.set_text(note_data.get('text_content', ''))

        # Load calc data
        cells_data = note_data.get('calc_data', {}).get('cells', {})
        formulas_data = note_data.get('calc_data', {}).get('formulas', {})

        # Clear existing data
        for entry in self.cells.values():
            entry.set_text('')
        self.formulas.clear()

        # Load cell values
        for cell_pos, value in cells_data.items():
            row, col = map(int, cell_pos.split(','))
            if (row, col) in self.cells:
                self.cells[(row, col)].set_text(value)

        # Load formulas
        for cell_pos, formula in formulas_data.items():
            row, col = map(int, cell_pos.split(','))
            if (row, col) in self.cells:
                self.formulas[(row, col)] = formula
                # Update cell with evaluated formula
                result = self.evaluate_formula(formula, (row, col))
                self.cells[(row, col)].set_text(result)

        # Switch to the saved mode
        saved_mode = note_data.get('mode', 'text')
        if saved_mode != self.mode:
            self.mode = saved_mode
            if saved_mode == 'calc':
                self.content_box.remove(self.text_scroll)
                self.content_box.add(self.grid_scroll)
                self.grid_scroll.show_all()
                self.mode_image.set_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON)
            else:
                self.content_box.remove(self.grid_scroll)
                self.content_box.add(self.text_scroll)
                self.text_scroll.show_all()
                self.mode_image.set_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)

    def start_new_note(self):
        buffer = self.text_view.get_buffer()
        buffer.set_text("")
        self.unsaved_changes = False
        logging.info("Started a new note")

    def on_note_manager_clicked(self, button):
        dialog = NoteManagerDialog(self)
        dialog.show()

    def on_shade_clicked(self, button):
        self.is_shaded = not self.is_shaded
        if self.is_shaded:
            self.content_box.hide()
            self.resize(400, 1)  # Collapse to just the header bar
            button.get_image().set_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        else:
            self.content_box.show()
            self.resize(400, 300)  # Restore default size
            button.get_image().set_from_icon_name("view-restore-symbolic", Gtk.IconSize.BUTTON)

    def on_mode_toggle(self, button):
        if self.mode == "text":
            # Switch to calc mode
            self.mode = "calc"
            self.mode_image.set_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON)
            button.set_tooltip_text("Switch to Text Mode")
            
            # Switch views
            self.content_box.remove(self.text_scroll)
            self.content_box.add(self.grid_scroll)
            self.grid_scroll.show_all()
        else:
            # Switch to text mode
            self.mode = "text"
            self.mode_image.set_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)
            button.set_tooltip_text("Switch to Calc Mode")
            
            # Switch views
            self.content_box.remove(self.grid_scroll)
            self.content_box.add(self.text_scroll)
            self.text_scroll.show_all()

    def on_cell_focus_out(self, entry, event, row, col):
        """Handle cell focus out"""
        if (row, col) in self.formulas:
            self.updating_cell = True
            result = self.evaluate_formula(self.formulas[(row, col)], (row, col))
            entry.set_text(result)
            self.set_numeric_alignment(entry, result)
            self.updating_cell = False
            self.is_displaying_formula = False
        self.active_formula_cell = None
        return False

    def cell_to_ref(self, row, col):
        """Convert row, col to cell reference (e.g., 0,0 -> A1)"""
        return f"{chr(65 + col)}{row + 1}"

    def ref_to_cell(self, ref):
        """Convert cell reference to row, col (e.g., A1 -> 0,0)"""
        if not ref or len(ref) < 2:
            return None
        col = ord(ref[0].upper()) - 65
        try:
            row = int(ref[1:]) - 1
            if 0 <= row < 50 and 0 <= col < 20:
                return (row, col)
        except ValueError:
            pass
        return None

    def evaluate_formula(self, formula, current_cell):
        """Evaluate a formula, handling basic arithmetic and cell references"""
        if not formula.startswith('='):
            return formula
        
        formula = formula[1:]  # Remove '='
        try:
            # Replace cell references with their values
            cell_refs = re.findall(r'[A-T][1-9][0-9]?', formula)
            for ref in cell_refs:
                cell_pos = self.ref_to_cell(ref)
                if cell_pos:
                    row, col = cell_pos
                    if (row, col) == current_cell:  # Prevent circular reference
                        raise ValueError("Circular reference detected")
                    cell_value = self.cells[(row, col)].get_text()
                    if cell_value.startswith('='):  # Handle nested formulas
                        cell_value = self.evaluate_formula(cell_value, (row, col))
                    formula = formula.replace(ref, cell_value)
            
            # Evaluate the resulting expression
            result = eval(formula)
            return str(result)
        except Exception as e:
            logging.error(f"Formula evaluation error: {e}")
            return "#ERROR"

    def on_cell_changed(self, entry, row, col):
        """Handle cell content changes"""
        if self.updating_cell:  # Prevent recursive updates
            return

        cell_value = entry.get_text()
        if cell_value:
            self.unsaved_changes = True
        
        # Update active_formula_cell when a cell starts with = and has focus
        if cell_value.startswith('=') and entry.is_focus():
            self.active_formula_cell = (row, col)
            # Update dependencies when formula changes
            self.update_dependencies(row, col, cell_value)
            self.formulas[(row, col)] = cell_value
        
        # Set alignment based on content
        self.set_numeric_alignment(entry, cell_value)
            
        if cell_value.startswith('='):
            # Only evaluate when editing is complete (Enter pressed or focus lost)
            if not entry.is_focus():
                self.updating_cell = True
                result = self.evaluate_formula(cell_value, (row, col))
                entry.set_text(result)
                # Set alignment for the result
                self.set_numeric_alignment(entry, result)
                self.updating_cell = False
        else:
            if (row, col) in self.formulas:
                del self.formulas[(row, col)]
            # Update cells that depend on this cell
            self.update_dependent_cells(row, col)

    def on_cell_key_press(self, entry, event, row, col):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            # Move focus to cell below on Enter
            if row < 49:  # Not last row
                self.cells[(row + 1, col)].grab_focus()
            return True
        elif event.keyval == Gdk.KEY_Tab:
            # Move focus to next cell on Tab
            if col < 19:  # Not last column
                self.cells[(row, col + 1)].grab_focus()
            elif row < 49:  # Move to first column of next row
                self.cells[(row + 1, 0)].grab_focus()
            return True
        elif event.keyval == Gdk.KEY_Up:
            if row > 0:  # Not first row
                self.cells[(row - 1, col)].grab_focus()
            return True
        elif event.keyval == Gdk.KEY_Down:
            if row < 49:  # Not last row
                self.cells[(row + 1, col)].grab_focus()
            return True
        elif event.keyval == Gdk.KEY_Left:
            if col > 0:  # Not first column
                self.cells[(row, col - 1)].grab_focus()
            return True
        elif event.keyval == Gdk.KEY_Right:
            if col < 19:  # Not last column
                self.cells[(row, col + 1)].grab_focus()
            return True
        return False

    def on_cell_clicked(self, entry, event, row, col):
        """Handle cell clicks"""
        if event.type == Gdk.EventType.BUTTON_PRESS:
            # If we're editing a formula and clicked another cell, insert cell reference
            if self.active_formula_cell and self.active_formula_cell != (row, col):
                active_row, active_col = self.active_formula_cell
                active_entry = self.cells[self.active_formula_cell]
                formula = active_entry.get_text()
                cell_ref = self.cell_to_ref(row, col)
                
                # Insert cell reference at cursor position
                position = active_entry.get_position()
                formula = formula[:position] + cell_ref + formula[position:]
                active_entry.set_text(formula)
                active_entry.set_position(position + len(cell_ref))
                return True
            
            # Show formula if cell has one
            elif (row, col) in self.formulas and not self.is_displaying_formula:
                self.updating_cell = True
                self.is_displaying_formula = True
                entry.set_text(self.formulas[(row, col)])
                entry.set_alignment(0.0)  # Left align formulas
                self.updating_cell = False
                # Set cursor at end of formula
                entry.set_position(-1)
                return True
        return False

    def on_cell_focus_in(self, entry, event, row, col):
        """Handle cell focus in - show formula if cell has one"""
        if (row, col) in self.formulas and not self.is_displaying_formula:
            self.updating_cell = True
            self.is_displaying_formula = True
            entry.set_text(self.formulas[(row, col)])
            entry.set_alignment(0.0)  # Left align formulas
            self.updating_cell = False
            # Set cursor at end of formula
            entry.set_position(-1)
        return False

    def find_dependencies(self, formula):
        """Extract all cell references from a formula and return them as a list of (row, col) tuples"""
        if not formula.startswith('='):
            return []
        cell_refs = re.findall(r'[A-T][1-9][0-9]?', formula)
        dependencies = []
        for ref in cell_refs:
            cell_pos = self.ref_to_cell(ref)
            if cell_pos:
                dependencies.append(cell_pos)
        return dependencies

    def update_dependencies(self, row, col, formula):
        """Update the cell_dependencies dictionary with new dependencies"""
        # Remove this cell from all dependency lists
        for deps in self.cell_dependencies.values():
            if (row, col) in deps:
                deps.remove((row, col))
        
        # Find new dependencies
        dependencies = self.find_dependencies(formula)
        
        # Add this cell to the dependency lists of its dependencies
        for dep_row, dep_col in dependencies:
            if (dep_row, dep_col) not in self.cell_dependencies:
                self.cell_dependencies[(dep_row, dep_col)] = []
            if (row, col) not in self.cell_dependencies[(dep_row, dep_col)]:
                self.cell_dependencies[(dep_row, dep_col)].append((row, col))

    def set_numeric_alignment(self, entry, value):
        """Set entry alignment based on whether the value is numeric"""
        try:
            float(value)
            entry.set_alignment(1.0)  # Right align for numbers
        except ValueError:
            entry.set_alignment(0.0)  # Left align for text

    def update_dependent_cells(self, row, col):
        """Update all cells that depend on the cell at (row, col)"""
        if (row, col) not in self.cell_dependencies:
            return
            
        # Get all cells that depend on this cell
        dependent_cells = self.cell_dependencies[(row, col)][:]  # Create a copy to avoid modification issues
        
        # Update each dependent cell
        for dep_row, dep_col in dependent_cells:
            # Only update if it still has a formula
            if (dep_row, dep_col) in self.formulas:
                self.updating_cell = True
                formula = self.formulas[(dep_row, dep_col)]
                result = self.evaluate_formula(formula, (dep_row, dep_col))
                self.cells[(dep_row, dep_col)].set_text(result)
                # Ensure numeric results are right-aligned
                self.set_numeric_alignment(self.cells[(dep_row, dep_col)], result)
                self.updating_cell = False
                # Recursively update cells that depend on this dependent cell
                self.update_dependent_cells(dep_row, dep_col)

class NoteManagerDialog(Gtk.Window):
    def __init__(self, parent):
        super().__init__(title="Note Manager")
        self.parent = parent
        self.set_default_size(400, 600)
        self.set_transient_for(parent)  # Make it stay on top of parent
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)  # Keep dialog appearance
        
        # Create main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)
        
        # Add header bar with styling
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.props.title = "Note Manager"
        header_bar.get_style_context().add_class("titlebar")
        self.set_titlebar(header_bar)
        
        # Create box for vertical layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_homogeneous(False)
        vbox.set_vexpand(True)
        vbox.set_valign(Gtk.Align.FILL)
        main_box.pack_start(vbox, True, True, 0)
        
        # Add New Note button at the top
        new_note_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        new_note_box.set_margin_top(10)
        new_note_box.set_margin_bottom(10)
        new_note_box.set_margin_start(10)
        new_note_box.set_margin_end(10)
        new_note_box.set_halign(Gtk.Align.END)  # Align to right
        
        new_note_button = Gtk.Button()
        new_note_button.set_label("New Note")
        new_note_button.get_style_context().add_class("new-note-button")  
        new_note_button.connect('clicked', self.on_new_note_clicked)
        new_note_box.pack_end(new_note_button, False, False, 0)
        
        vbox.pack_start(new_note_box, False, False, 0)
        
        # Create list box for notes with styling
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_valign(Gtk.Align.FILL)
        
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.set_margin_top(10)
        self.list_box.set_margin_bottom(10)
        self.list_box.set_margin_start(10)
        self.list_box.set_margin_end(10)
        scrolled.add(self.list_box)
        
        vbox.pack_start(scrolled, True, True, 0)
        
        # Connect delete event
        self.connect("delete-event", self.on_delete_event)
        
        self.refresh_notes()
        self.show_all()

    def refresh_notes(self):
        # Clear existing items
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        
        # List all .enc files
        for file in os.listdir('.'):
            if file.endswith('.enc') and not file.startswith('.'):
                row = Gtk.ListBoxRow()
                row.set_margin_top(5)
                row.set_margin_bottom(5)
                
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                hbox.set_margin_start(10)
                hbox.set_margin_end(10)
                hbox.set_margin_top(10)
                hbox.set_margin_bottom(10)
                
                # Note name as button
                name = file[:-4]  # Remove .enc
                name_button = Gtk.Button(label=name)
                name_button.get_style_context().add_class("flat")
                name_button.set_halign(Gtk.Align.START)
                name_button.connect('clicked', self.on_open_clicked, file)
                hbox.pack_start(name_button, True, True, 0)
                
                # Delete button
                delete_button = Gtk.Button()
                delete_image = Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
                delete_button.add(delete_image)
                delete_button.get_style_context().add_class("delete-button")
                delete_button.connect('clicked', self.on_delete_clicked, file)
                hbox.pack_end(delete_button, False, False, 0)
                
                row.add(hbox)
                self.list_box.add(row)
        
        self.show_all()
    
    def on_open_clicked(self, button, filename):
        with open(filename, 'rb') as f:
            encrypted_content = f.read()
        decrypted_content = cipher_suite.decrypt(encrypted_content).decode()
        
        # Try to parse as JSON (new format)
        try:
            note_data = json.loads(decrypted_content)
            self.parent._load_note_data(note_data)
        except json.JSONDecodeError:
            # Old format - just text content
            buffer = self.parent.text_view.get_buffer()
            buffer.set_text(decrypted_content)
            # Switch to text mode if needed
            if self.parent.mode != 'text':
                self.parent.mode = 'text'
                self.parent.content_box.remove(self.parent.grid_scroll)
                self.parent.content_box.add(self.parent.text_scroll)
                self.parent.text_scroll.show_all()
                self.parent.mode_image.set_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)

        self.parent.update_title(filename[:-4])  # Remove .enc
        self.destroy()
    
    def on_delete_clicked(self, button, filename):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Delete Note?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        dialog.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            os.remove(filename)
            self.refresh_notes()
        dialog.destroy()
    
    def on_new_note_clicked(self, button):
        win = StickyNoteWindow()
        win.show_all()

    def on_delete_event(self, widget, event):
        self.destroy()
        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    win = StickyNoteWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
