import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox

import pyttsx3

DB_PATH = "lms.db"
MODULES_PATH = "modules.txt"


class Module:
    def __init__(self, title):
        self.title = title
        self.pages = []

    def add_page(self, title, content):
        self.pages.append({"title": title, "content": content})


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                ("admin", "admin123"),
            )
        conn.commit()
    finally:
        conn.close()


def verify_user(username, password, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        return row is not None and row[0] == password
    finally:
        conn.close()


def add_user(username, password, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password),
        )
        conn.commit()
        return True, "User registered successfully."
    except sqlite3.IntegrityError:
        return False, "That username already exists."
    finally:
        conn.close()


def delete_user(username, password, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        row = cursor.fetchone()
        if not row:
            return False, "Invalid username or password."
        cursor.execute("DELETE FROM users WHERE id = ?", (row[0],))
        conn.commit()
        return True, "User deleted successfully."
    finally:
        conn.close()


def load_modules(path=MODULES_PATH):
    modules = []
    current_module = None
    current_page_title = None
    current_page_lines = []

    try:
        with open(path, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.rstrip("\n")
                if line.startswith("## "):
                    if current_module and current_page_title:
                        current_module.add_page(
                            current_page_title, "\n".join(current_page_lines).strip()
                        )
                    if current_module:
                        modules.append(current_module)
                    current_module = Module(line[3:].strip())
                    current_page_title = None
                    current_page_lines = []
                elif line.startswith("### "):
                    if current_module is None:
                        current_module = Module("Untitled Module")
                    if current_page_title:
                        current_module.add_page(
                            current_page_title, "\n".join(current_page_lines).strip()
                        )
                    current_page_title = line[4:].strip()
                    current_page_lines = []
                else:
                    current_page_lines.append(line)

        if current_module and current_page_title:
            current_module.add_page(
                current_page_title, "\n".join(current_page_lines).strip()
            )
        if current_module:
            modules.append(current_module)
    except FileNotFoundError:
        return []

    return modules


class LMSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Learning Management System")
        self.geometry("900x600")
        self.resizable(True, True)

        self.tts_engine = pyttsx3.init()
        self.tts_lock = threading.Lock()

        self.modules = []
        self.current_module_index = 0
        self.current_page_index = 0

        self.login_frame = tk.Frame(self)
        self.main_frame = tk.Frame(self)

        self._build_login()
        self._build_main()

        self.login_frame.pack(fill="both", expand=True)

    def _build_login(self):
        title = tk.Label(self.login_frame, text="Sign In", font=("Arial", 20, "bold"))
        title.pack(pady=20)

        form_frame = tk.Frame(self.login_frame)
        form_frame.pack(pady=10)

        tk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky="e", pady=5)
        tk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky="e", pady=5)

        self.username_entry = tk.Entry(form_frame, width=30)
        self.password_entry = tk.Entry(form_frame, width=30, show="*")
        self.username_entry.grid(row=0, column=1, padx=10)
        self.password_entry.grid(row=1, column=1, padx=10)

        login_button = tk.Button(
            self.login_frame, text="Login", width=15, command=self._handle_login
        )
        login_button.pack(pady=15)

        action_frame = tk.Frame(self.login_frame)
        action_frame.pack(pady=5)

        tk.Button(
            action_frame, text="Register", width=12, command=self._handle_register
        ).pack(side="left", padx=5)
        tk.Button(
            action_frame, text="Delete User", width=12, command=self._handle_delete
        ).pack(side="left", padx=5)

        hint = tk.Label(
            self.login_frame,
            text="Default user: admin / admin123",
            fg="gray",
        )
        hint.pack()

    def _build_main(self):
        layout = tk.Frame(self.main_frame)
        layout.pack(fill="both", expand=True, padx=20, pady=20)

        left_panel = tk.Frame(layout)
        left_panel.pack(side="left", fill="y")

        tk.Label(left_panel, text="Modules", font=("Arial", 14, "bold")).pack(
            anchor="w"
        )
        self.module_listbox = tk.Listbox(left_panel, height=20, width=25)
        self.module_listbox.pack(fill="y", pady=10)
        self.module_listbox.bind("<<ListboxSelect>>", self._on_module_select)

        right_panel = tk.Frame(layout)
        right_panel.pack(side="left", fill="both", expand=True, padx=(20, 0))

        self.page_title_label = tk.Label(
            right_panel, text="", font=("Arial", 16, "bold")
        )
        self.page_title_label.pack(anchor="w")

        self.page_indicator_label = tk.Label(right_panel, text="")
        self.page_indicator_label.pack(anchor="w", pady=(0, 10))

        self.page_text = tk.Text(right_panel, wrap="word", height=20)
        self.page_text.pack(fill="both", expand=True)
        self.page_text.config(state="disabled")

        controls = tk.Frame(right_panel)
        controls.pack(fill="x", pady=10)

        self.prev_button = tk.Button(controls, text="Previous", command=self._prev_page)
        self.next_button = tk.Button(controls, text="Next", command=self._next_page)
        self.read_button = tk.Button(controls, text="Read Page", command=self._read_page)
        self.logout_button = tk.Button(
            controls, text="Log Out", command=self._handle_logout
        )

        self.prev_button.pack(side="left")
        self.next_button.pack(side="left", padx=10)
        self.read_button.pack(side="left")
        self.logout_button.pack(side="right")

        self._show_page()

    def _handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning("Missing Info", "Please enter username and password.")
            return

        if verify_user(username, password):
            self._load_modules()
            self.login_frame.pack_forget()
            self.main_frame.pack(fill="both", expand=True)
            self.username_entry.delete(0, tk.END)
            self.password_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def _handle_register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Missing Info", "Please enter username and password."
            )
            return

        success, message = add_user(username, password)
        if success:
            messagebox.showinfo("Registration Complete", message)
        else:
            messagebox.showerror("Registration Failed", message)

    def _handle_delete(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Missing Info", "Please enter username and password."
            )
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to delete this user?",
        )
        if not confirm:
            return

        success, message = delete_user(username, password)
        if success:
            messagebox.showinfo("User Deleted", message)
        else:
            messagebox.showerror("Delete Failed", message)

    def _load_modules(self):
        self.modules = load_modules()
        self.module_listbox.delete(0, tk.END)
        for module in self.modules:
            self.module_listbox.insert(tk.END, module.title)
        if self.modules:
            self.current_module_index = 0
            self.current_page_index = 0
            self.module_listbox.selection_set(0)
        self._show_page()

    def _handle_logout(self):
        self.main_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)
        self.modules = []
        self.module_listbox.delete(0, tk.END)
        self.current_module_index = 0
        self.current_page_index = 0
        self._show_page()

    def _on_module_select(self, event):
        selection = self.module_listbox.curselection()
        if not selection:
            return
        self.current_module_index = selection[0]
        self.current_page_index = 0
        self._show_page()

    def _show_page(self):
        if not self.modules:
            self.page_title_label.config(text="No modules loaded")
            self.page_indicator_label.config(text="")
            self._set_page_text("Add content to modules.txt to get started.")
            return

        module = self.modules[self.current_module_index]
        if not module.pages:
            self.page_title_label.config(text=module.title)
            self.page_indicator_label.config(text="No pages found")
            self._set_page_text("This module has no pages.")
            return

        page = module.pages[self.current_page_index]
        self.page_title_label.config(text=f"{module.title} - {page['title']}")
        self.page_indicator_label.config(
            text=f"Page {self.current_page_index + 1} of {len(module.pages)}"
        )
        self._set_page_text(page["content"])

        self.prev_button.config(state="normal" if self.current_page_index > 0 else "disabled")
        self.next_button.config(
            state="normal"
            if self.current_page_index < len(module.pages) - 1
            else "disabled"
        )

    def _set_page_text(self, text):
        self.page_text.config(state="normal")
        self.page_text.delete("1.0", tk.END)
        self.page_text.insert(tk.END, text)
        self.page_text.config(state="disabled")

    def _prev_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._show_page()

    def _next_page(self):
        module = self.modules[self.current_module_index]
        if self.current_page_index < len(module.pages) - 1:
            self.current_page_index += 1
            self._show_page()

    def _read_page(self):
        content = self.page_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("No Content", "There is no text to read on this page.")
            return

        def speak():
            with self.tts_lock:
                self.tts_engine.stop()
                self.tts_engine.say(content)
                self.tts_engine.runAndWait()

        threading.Thread(target=speak, daemon=True).start()


if __name__ == "__main__":
    init_db()
    app = LMSApp()
    app.mainloop()
