import os
import sys
import subprocess
import platform
import re
import shutil
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# --- ФИКС БАГА С ПУТЯМИ ---
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(TOOL_DIR)

MINDUSTRY_VERSION = "v159.7"
BRAND_HJSON = "Создано с помощью Mindustry Mod Creator by EvilCorporation"
BRAND_JAVA = "Создано с поддержкой Mindustry Mod Creator by EvilCorporation"
DATA_DIR = os.path.join(TOOL_DIR, "creator_data")
LIBS_DIR = os.path.join(DATA_DIR, "libs")

LOCAL_GIT = os.path.join(DATA_DIR, "git", "cmd", "git.exe")
GIT_CMD = LOCAL_GIT if os.path.exists(LOCAL_GIT) else "git"

CONTENT_TYPES = {
    "Item (Предмет)": "content/items",
    "Block (Блок)": "content/blocks",
    "Liquid (Жидкость)": "content/liquids",
    "Unit (Юнит)": "content/units"
}

class ModCreatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Mindustry Mod Creator - {MINDUSTRY_VERSION}")
        self.root.geometry("950x700")
        self.gradle_cmd = "gradlew.bat" if platform.system() == "Windows" else "./gradlew"
        
        self.is_java_mod = os.path.exists("build.gradle") or os.path.exists("src")
        
        if not os.path.exists("mod.hjson") and not os.path.exists("mod.json"):
            with open("mod.hjson", "w", encoding="utf-8") as f:
                f.write(f'name: "new-mod"\ndisplayName: "New Mod"\nauthor: "Unknown"\ndescription: ""\nversion: "1.0"\nminGameVersion: "{MINDUSTRY_VERSION.replace("v", "")}"\n')
        
        self.setup_ui()

    def setup_ui(self):
        status_text = "Проект: " + ("Java Мод ☕" if self.is_java_mod else "HJSON Мод 📝")
        status_label = ttk.Label(self.root, text=status_text, font=("Arial", 12, "bold"), foreground="blue")
        status_label.pack(pady=5)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        self.tab_create = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_create, text="1. Создать файл")
        self.setup_create_tab()

        self.tab_edit = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_edit, text="2. Редактор HJSON")
        self.setup_editor_tab()

        if self.is_java_mod:
            self.tab_gradle = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_gradle, text="3. Сборка (Gradle)")
            self.setup_gradle_tab()
        else:
            self.tab_convert = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_convert, text="3. Конвертация/Экспорт")
            self.setup_convert_tab()

        self.tab_git = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_git, text="4. Git и Экспорт")
        self.setup_git_tab()

    # ==================== 1. ВКЛАДКА СОЗДАНИЯ ====================
    def setup_create_tab(self):
        frame = self.tab_create
        ttk.Label(frame, text="Создание нового файла контента", font=("Arial", 14, "bold")).pack(pady=20)
        
        ttk.Label(frame, text="Тип контента:").pack(anchor='w', padx=50)
        self.type_var = tk.StringVar(value=list(CONTENT_TYPES.keys())[0])
        type_combo = ttk.Combobox(frame, textvariable=self.type_var, values=list(CONTENT_TYPES.keys()), state="readonly")
        type_combo.pack(fill='x', padx=50, pady=5)
        
        ttk.Label(frame, text="Имя файла (на английском, без пробелов):").pack(anchor='w', padx=50, pady=(15,0))
        self.filename_var = tk.StringVar(value="my-new-block")
        ttk.Entry(frame, textvariable=self.filename_var).pack(fill='x', padx=50, pady=5)
        
        ttk.Button(frame, text="📄 Создать файл", command=self.create_new_file).pack(pady=20)

    def create_new_file(self):
        ctype = self.type_var.get()
        name = self.filename_var.get().strip().replace(" ", "-").lower()
        if not name:
            messagebox.showerror("Ошибка", "Введите имя файла!")
            return
            
        folder = CONTENT_TYPES[ctype]
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{name}.hjson")
        
        if os.path.exists(path):
            if not messagebox.askyesno("Файл существует", "Перезаписать файл?"):
                return
                
        if "Block" in ctype:
            content = f"name: \"{name}\"\ntype: \"GenericCrafter\"\nsize: 1\nhealth: 100"
        elif "Item" in ctype:
            content = f"name: \"{name}\"\ncolor: \"ffaa00\"\nhardness: 1\ncost: 1"
        else:
            content = f"name: \"{name}\""

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        messagebox.showinfo("Успех", f"Создан файл: {path}")
        self.refresh_tree()
        self.filename_var.set("my-new-block")

    # ==================== 2. ВКЛАДКА РЕДАКТОРА ====================
    def setup_editor_tab(self):
        paned = ttk.PanedWindow(self.tab_edit, orient='horizontal')
        paned.pack(fill='both', expand=True)

        left_frame = ttk.Frame(paned, width=250)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Файлы проекта:").pack(anchor='w')
        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(fill='both', expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)
        
        ttk.Button(left_frame, text="🔄 Обновить дерево", command=self.refresh_tree).pack(fill='x', pady=5)

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=4)
        
        self.current_file_path = None
        self.file_label = ttk.Label(right_frame, text="Файл не выбран", font=("Arial", 10, "bold"))
        self.file_label.pack(anchor='w', pady=5)

        ctrl_frame = ttk.Frame(right_frame)
        ctrl_frame.pack(fill='x', pady=5)
        ttk.Button(ctrl_frame, text="+ Добавить строку", command=self.add_edit_row).pack(side='left')
        ttk.Button(ctrl_frame, text="💾 Сохранить изменения", command=self.save_edited_file).pack(side='left', padx=10)

        self.canvas = tk.Canvas(right_frame)
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.refresh_tree()

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for folder in ["content", "."]:
            if os.path.exists(folder):
                node = self.tree.insert("", "end", text=folder if folder != "." else "Корень", open=True)
                self.populate_tree(node, folder)
                
    def populate_tree(self, parent, path):
        try:
            for item in os.listdir(path):
                if item in ['.git', 'build', '__pycache__', '.gradle', 'creator_data', 'mod_tool.py', 'libs']:
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    node = self.tree.insert(parent, "end", text=item, open=False)
                    self.populate_tree(node, full_path)
                elif item.endswith(".hjson") or item.endswith(".json"):
                    self.tree.insert(parent, "end", text=item, values=[full_path])
        except PermissionError:
            pass

    def on_file_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item = self.tree.item(selected[0])
        if item.get('values'):
            file_path = item['values'][0]
            self.load_file_to_editor(file_path)

    def load_file_to_editor(self, file_path):
        self.current_file_path = file_path
        self.file_label.config(text=f"Файл: {file_path}")
        
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip().rstrip(',') # Убираем запятые на конце
            if not line or line in ["{", "}"]: continue
            
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                
                has_quotes = val.startswith('"') and val.endswith('"')
                if has_quotes:
                    val = val[1:-1]
                    
                self.add_edit_row(key, val, has_quotes)

    def add_edit_row(self, key="", value="", has_quotes=False):
        row = ttk.Frame(self.scrollable_frame)
        row.pack(fill='x', pady=2)
        
        key_entry = ttk.Entry(row, width=25)
        key_entry.insert(0, key)
        key_entry.pack(side='left', padx=2)
        
        val_entry = ttk.Entry(row, width=40)
        val_entry.insert(0, value)
        val_entry.pack(side='left', padx=2)
        
        # СОЗДАЕМ ПЕРЕМЕННУЮ И ПРИВЯЗЫВАЕМ К ЧЕКБОКСУ
        quote_var = tk.BooleanVar(value=has_quotes)
        quote_chk = ttk.Checkbutton(row, text="В кавычках", variable=quote_var)
        quote_chk.pack(side='left', padx=5)
        
        # Сохраняем ссылку на переменную внутри самого виджета
        quote_chk.var = quote_var
        
        def delete_row():
            row.destroy()
            
        del_btn = ttk.Button(row, text="❌", width=3, command=delete_row)
        del_btn.pack(side='left', padx=2)

    def save_edited_file(self):
        if not self.current_file_path:
            messagebox.showwarning("Внимание", "Файл не выбран!")
            return
            
        with open(self.current_file_path, "r", encoding="utf-8") as f:
            original = f.read()
            is_object = "{" in original

        lines = []
        if is_object:
            lines.append("{\n")
            
        for row in self.scrollable_frame.winfo_children():
            entries = row.winfo_children()
            if len(entries) < 3: continue
            
            key = entries[0].get().strip()
            val = entries[1].get().strip()
            
            # ЧИТАЕМ ЗНАЧЕНИЕ ИЗ ПРИВЯЗАННОЙ ПЕРЕМЕННОЙ
            quote_var = getattr(entries[2], 'var', None)
            quotes = quote_var.get() if quote_var else False
            
            if not key: continue
            
            if quotes:
                val_str = f'"{val}"'
            else:
                val_str = val
                
            lines.append(f"  {key}: {val_str}\n")
            
        if is_object:
            lines.append("}")
            
        with open(self.current_file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        messagebox.showinfo("Успех", f"Файл сохранен: {self.current_file_path}")
        self.load_file_to_editor(self.current_file_path)

    # ==================== 3. КОНВЕРТАЦИЯ / GRADLE ====================
    def setup_convert_tab(self):
        frame = self.tab_convert
        ttk.Label(frame, text="Конвертация и Экспорт", font=("Arial", 14, "bold")).pack(pady=20)
        ttk.Button(frame, text="📦 Упаковать в ZIP (с меткой)", command=self.zip_and_brand).pack(pady=10)
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=20)
        ttk.Label(frame, text="Конвертировать HJSON в Java-Мод (Offline)").pack()
        ttk.Button(frame, text="⚙️ Создать Java Проект", command=self.convert_to_java).pack(pady=10)

    def convert_to_java(self):
        try:
            if os.path.exists(os.path.join(DATA_DIR, "wrapper")):
                shutil.copytree(os.path.join(DATA_DIR, "wrapper"), ".", dirs_exist_ok=True)
            
            wrapper_props = os.path.join("gradle", "wrapper", "gradle-wrapper.properties")
            if os.path.exists(os.path.dirname(wrapper_props)):
                local_zip = os.path.join(DATA_DIR, "gradle-8.5-bin.zip").replace("\\", "/")
                with open(wrapper_props, "w") as f:
                    f.write(f"distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\ndistributionUrl=file\\:///{local_zip}\n")

            os.makedirs("libs", exist_ok=True)
            for jar in ["core.jar", "arc-core.jar"]:
                if os.path.exists(os.path.join(LIBS_DIR, jar)):
                    shutil.copy(os.path.join(LIBS_DIR, jar), "libs")

            build_gradle_content = f"""
apply plugin: "java"
version '1.0'
sourceCompatibility = 17
targetCompatibility = 17

repositories {{
    flatDir {{ dirs 'libs' }}
}}

dependencies {{
    implementation name: 'core'
    implementation name: 'arc-core'
}}

jar {{
    archiveFileName = "my-mod.jar"
    from {{ configurations.runtimeClasspath.collect {{ it.isDirectory() ? it : zipTree(it) }} }}
}}
"""
            with open("build.gradle", "w", encoding="utf-8") as f:
                f.write(build_gradle_content)
            
            os.makedirs("src/main/java/mymod", exist_ok=True)
            with open("src/main/java/mymod/MyMod.java", "w", encoding="utf-8") as f:
                f.write("package mymod;\nimport mindustry.mod.Mod;\npublic class MyMod extends Mod {\n @Override\n public void loadContent() { }\n}")
            
            with open("mod.hjson", "a", encoding="utf-8") as f:
                f.write(f'\nmain: "mymod.MyMod"\njava: true\nminGameVersion: "{MINDUSTRY_VERSION.replace("v", "")}"\n')
            
            self.apply_branding()
            messagebox.showinfo("Успех", "Проект сконвертирован! Перезапустите программу.")
            self.is_java_mod = True
            self.root.destroy() 
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def setup_gradle_tab(self):
        frame = self.tab_gradle
        ttk.Button(frame, text="🔨 Собрать мод (build)", command=lambda: self.run_gradle("build")).pack(pady=10)
        ttk.Button(frame, text="🧹 Очистить (clean)", command=lambda: self.run_gradle("clean")).pack(pady=5)
        self.log_text = scrolledtext.ScrolledText(frame, height=20, state='disabled')
        self.log_text.pack(fill='both', expand=True, pady=5)

    def run_gradle(self, args):
        self.apply_branding()
        cmd = [self.gradle_cmd] + args.split()
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"\n> {' '.join(cmd)}\n")
        self.log_text.config(state='disabled')
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, line)
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
                self.root.update()
            process.wait()
            messagebox.showinfo("Gradle", "Сборка завершена!")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ==================== 4. GIT И МАРКИРОВКА ====================
    def apply_branding(self):
        mod_file = "mod.hjson" if os.path.exists("mod.hjson") else "mod.json"
        if not os.path.exists(mod_file): return
        with open(mod_file, "r", encoding="utf-8") as f: content = f.read()
        brand_text = BRAND_JAVA if self.is_java_mod else BRAND_HJSON
        desc_pattern = r'(description\s*:\s*)(["\']?)(.*?)\2(?=\n|$)'
        if re.search(desc_pattern, content):
            def repl(m):
                curr = m.group(3)
                return f'{m.group(1)}"{curr} | {brand_text}"' if brand_text not in curr else m.group(0)
            content = re.sub(desc_pattern, repl, content)
        else:
            content += f'\ndescription: "{brand_text}"\n'
        with open(mod_file, "w", encoding="utf-8") as f: f.write(content)

    def setup_git_tab(self):
        frame = self.tab_git
        ttk.Label(frame, text="Настройки Git (использует локальный Portable Git)", font=("Arial", 10, "bold")).pack(anchor='w', pady=10)
        
        ttk.Label(frame, text="Ваше Имя (user.name):").pack(anchor='w', pady=2)
        self.git_name_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.git_name_var).pack(fill='x', pady=2)
        
        ttk.Label(frame, text="Ваша Почта (user.email):").pack(anchor='w', pady=2)
        self.git_email_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.git_email_var).pack(fill='x', pady=2)
        
        ttk.Label(frame, text="URL Репозитория (origin):").pack(anchor='w', pady=2)
        self.git_url_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.git_url_var).pack(fill='x', pady=2)
        
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)
        
        ttk.Button(frame, text="🐙 Инициализировать и закоммитить", command=self.git_commit).pack(fill='x', pady=5)
        ttk.Button(frame, text="🚀 Отправить в удаленный репозиторий (Push)", command=self.git_push).pack(fill='x', pady=5)
        
        ttk.Label(frame, text="Лог Git:").pack(anchor='w', pady=5)
        self.git_log = scrolledtext.ScrolledText(frame, height=10, state='disabled')
        self.git_log.pack(fill='both', expand=True, pady=5)

    def run_git(self, args):
        cmd = [GIT_CMD] + args
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.git_log.config(state='normal')
            self.git_log.insert(tk.END, f"> {' '.join(cmd)}\n{process.stdout}{process.stderr}\n")
            self.git_log.see(tk.END)
            self.git_log.config(state='disabled')
            return process.returncode == 0
        except Exception as e:
            messagebox.showerror("Ошибка Git", str(e))
            return False

    def git_commit(self):
        name = self.git_name_var.get().strip()
        email = self.git_email_var.get().strip()
        if name: self.run_git(["config", "user.name", name])
        if email: self.run_git(["config", "user.email", email])
        
        if not os.path.exists(".git"):
            self.run_git(["init"])
            self.run_git(["branch", "-M", "main"])
            with open(".gitignore", "w", encoding="utf-8") as f:
                f.write(".gradle/\nbuild/\n.idea/\n*.iml\n.DS_Store\nThumbs.db\ncreator_data/\nmod_tool.py\n*.zip\n")
        
        self.apply_branding()
        self.run_git(["add", "."])
        success = self.run_git(["commit", "-m", "Update mod via Mindustry Mod Creator"])
        if success: messagebox.showinfo("Git", "Коммит создан успешно!")

    def git_push(self):
        url = self.git_url_var.get().strip()
        if not url:
            messagebox.showwarning("Git", "Введите URL репозитория!")
            return
        if not os.path.exists(".git"):
            messagebox.showwarning("Git", "Сначала сделайте коммит!")
            return
            
        self.run_git(["remote", "remove", "origin"])
        self.run_git(["remote", "add", "origin", url])
        
        if messagebox.askyesno("Git Push", "Отправить изменения на сервер?"):
            success = self.run_git(["push", "-u", "origin", "main"])
            if success: messagebox.showinfo("Git", "Успешно отправлено!")

    def zip_and_brand(self):
        self.apply_branding()
        zip_name = "my-mod.zip"
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk("."):
                dirs[:] = [d for d in dirs if d not in ['.git', 'build', '__pycache__', '.gradle', 'creator_data']]
                for file in files:
                    if file in [zip_name, "mod_tool.py"] or file.endswith(".jar"): continue
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), "."))
        messagebox.showinfo("Успех", f"Мод упакован в {zip_name}!")

if __name__ == "__main__":
    root = tk.Tk()
    app = ModCreatorApp(root)
    root.mainloop()
