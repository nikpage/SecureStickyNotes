#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from cryptography.fernet import Fernet
import os
import logging

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
        note_manager_image = Gtk.Image.new_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON)
        note_manager_button.add(note_manager_image)
        note_manager_button.set_tooltip_text("Manage Notes")
        note_manager_button.get_style_context().add_class("suggested-action")
        note_manager_button.connect("clicked", self.on_note_manager_clicked)
        header_bar.pack_start(note_manager_button)

        # Store main content in a box for windowshade
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_vexpand(True)
        self.content_box.set_valign(Gtk.Align.FILL)
        super().add(self.content_box)

        # Create a text view with styling
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(10)
        self.text_view.set_right_margin(10)
        self.text_view.set_top_margin(10)
        self.text_view.set_bottom_margin(10)
        self.text_view.get_style_context().add_class("view")
        self.text_view.set_vexpand(True)
        self.text_view.set_valign(Gtk.Align.FILL)
        
        # Add scrolled window for text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.text_view)
        scrolled.set_vexpand(True)
        scrolled.set_valign(Gtk.Align.FILL)
        self.content_box.add(scrolled)

        # Set up CSS styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .view { font-family: Sans; font-size: 12pt; }
            .titlebar { background: linear-gradient(to bottom, #4a90d9, #357abd); }
            .titlebar button { color: white; }
            .suggested-action { background: #2ecc71; color: white; }
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
            # Only show save dialog if there's actual content
            buffer = self.text_view.get_buffer()
            start, end = buffer.get_bounds()
            content = buffer.get_text(start, end, False).strip()
            if not content:
                return False

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
            suggested_name = self.get_note_preview()
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
                    buffer = self.text_view.get_buffer()
                    start, end = buffer.get_bounds()
                    content = buffer.get_text(start, end, False)
                    encrypted_content = cipher_suite.encrypt(content.encode())
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
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, False)
        if content:
            encrypted_content = cipher_suite.encrypt(content.encode())
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
                buffer = self.text_view.get_buffer()
                buffer.set_text(decrypted_content)
            except Exception as e:
                print(f"Decryption error: {e}")
                buffer = self.text_view.get_buffer()
                buffer.set_text("")

    def start_new_note(self):
        buffer = self.text_view.get_buffer()
        buffer.set_text("")
        self.unsaved_changes = False
        logging.info("Started a new note")

    def on_note_manager_clicked(self, button):
        dialog = NoteManagerDialog(self)
        dialog.run()
        dialog.destroy()

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

class NoteManagerDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Note Manager", transient_for=parent)
        self.parent = parent
        self.set_default_size(400, 600)
        
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
        
        # Add to dialog's content area
        content_area = self.get_content_area()
        content_area.add(vbox)
        content_area.set_vexpand(True)
        content_area.set_valign(Gtk.Align.FILL)
        
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
                delete_button.get_style_context().add_class("destructive-action")
                delete_button.connect('clicked', self.on_delete_clicked, file)
                hbox.pack_end(delete_button, False, False, 0)
                
                row.add(hbox)
                self.list_box.add(row)
        
        self.show_all()
    
    def on_open_clicked(self, button, filename):
        with open(filename, 'rb') as f:
            encrypted_content = f.read()
        decrypted_content = cipher_suite.decrypt(encrypted_content).decode()
        self.parent.text_view.get_buffer().set_text(decrypted_content)
        self.parent.update_title(filename[:-4])  # Remove .enc
        self.destroy()
    
    def on_delete_clicked(self, button, filename):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete {filename}?"
        )
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            os.remove(filename)
            self.refresh_notes()
        dialog.destroy()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    win = StickyNoteWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
