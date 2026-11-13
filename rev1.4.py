# EDA2
#
# kushagra srivastava (hostilebaker on github)
#
# integrated vlsi platform rev 1.3 (27/10/2026) (start date:-17/06/2026)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# a very barebones platform that integrates all the main steps of vlsi
# design flow into a single executable (provided the user has the required tools installed)
#
# based on the **sky130 130nm open source pdk**
#
# -> revs 0 -> 1 contained a simple gui with no working buttons or any functionality
# -> rev 1.1 is the same gui with minimal changes, but now integrates icarus verilog compiler
# -> rev 1.2 added gtk wave but messed up the file saving logic where it wants me to save the program when clicking run
#    reverted this part back to the original rev 1.1, added a new automatic waveform generation support without requiring
#    me to save the file itself
# -> rev 1.3 added the feature to open the latest waveform directly when i click gtk wave, and also lets me select another
#    .vcd waveform file if the generated waveform is not the one i want to see, also added a check for the presence of gtkwave in the system path
import json, os, re, shutil, subprocess, tempfile, tkinter as tk, zipfile, threading, queue
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
title = "integrated asic platform rev1.21 (13/11/2026)"
filetype = ".eda2" # fix this in later revs, might get confused
var1 = " "
var2 = " "
arial = "Arial"
class eda(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(title)
        self.geometry("1100x720")
        self.minsize(850, 560)
        self.PP = self.verilog_editor = self.testbench_editor = self.OC = None
        # Keep the application, shared dependencies, and projects under one EDA folder.
        script_dir = Path(__file__).resolve().parent
        self.app_dir = script_dir if script_dir.name.lower() == "eda" else script_dir / "EDA"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.dependencies_dir = self.app_dir / "dependencies"
        self.projects_dir = self.app_dir / "projects"
        self.dependencies_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.app_dir / "settings.json"
        self.project_dir = None
        self.waveform_path = None
        self.gtkwave_path = self.load_gtkwave_path()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        # Tool locations are resolved from the EDA2 dependencies folder or the
        # user's existing Desktop installation. No shell command is built from paths.
        self.oss_cad_suite = None
        self.yosys_running = False
        self.yosys_queue = queue.Queue()
        self.projectpage()
    def default_waveform_path(self):
        # Waveforms always belong to the active project's simulation directory.
        return self.project_dir / "simulation" / "waveform.vcd" if self.project_dir else None
    def create_project_structure(self, root):
        for folder in (
            "verilog", "simulation", "synthesis/reports", "schematic",
            "constraints", "sta", "floorplan", "placement", "routing",
            "layout", "logs"
        ):
            (root / folder).mkdir(parents=True, exist_ok=True)
        design_path = root / "verilog" / "design.v"
        testbench_path = root / "verilog" / "testbench.v"
        if not design_path.exists():
            design_path.write_text("", encoding="utf-8")
        if not testbench_path.exists():
            testbench_path.write_text("", encoding="utf-8")

    def start_project_workspace(self, project_dir):
        # Projects are real folders; no temporary extraction or repacking is used.
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.waveform_path = self.project_dir / "simulation" / "waveform.vcd"

    def sync_editors_to_project(self):
        if self.project_dir is None:
            return
        verilog_dir = self.project_dir / "verilog"
        verilog_dir.mkdir(parents=True, exist_ok=True)
        # A project-page transition can destroy editor widgets while callbacks
        # are still unwinding. Never call Tcl on a destroyed Text widget.
        try:
            if self.verilog_editor is not None and self.verilog_editor.winfo_exists():
                (verilog_dir / "design.v").write_text(
                    self.verilog_editor.get("1.0", "end-1c"), encoding="utf-8"
                )
            if self.testbench_editor is not None and self.testbench_editor.winfo_exists():
                (verilog_dir / "testbench.v").write_text(
                    self.testbench_editor.get("1.0", "end-1c"), encoding="utf-8"
                )
        except tk.TclError:
            # The widget was destroyed between the existence check and get().
            # The project files remain intact; callers save before switching.
            return

    def pack_project(self):
        # Kept under its old method name so existing button/tool callbacks remain intact.
        # The .eda2 file is a small JSON project descriptor, not an archive.
        if self.PP is None or self.project_dir is None:
            return False
        self.sync_editors_to_project()
        metadata = {
            "format": "EDA2",
            "format_version": 3,
            "project_name": self.project_dir.name,
            "project_directory": self.project_dir.name,
            "entry_point": self.PP.name
        }
        self.PP.parent.mkdir(parents=True, exist_ok=True)
        self.PP.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return True

    def close_app(self):
        if self.PP is not None and self.project_dir is not None:
            if messagebox.askyesno("save project", "Save the current Verilog files and project metadata before closing?"):
                try:
                    self.pack_project()
                except (OSError, tk.TclError) as e:
                    messagebox.showerror("save failed", str(e))
                    return
        self.destroy()
    def delete(self):
        for child in self.winfo_children():
            child.destroy()
        # Clear references so later save/close callbacks cannot use dead widgets.
        self.verilog_editor = None
        self.testbench_editor = None
        self.OC = None
    def projectpage(self):
        self.delete()
        box = tk.Frame(self, padx=32, pady=32)
        box.pack(fill="both", expand=True)
        tk.Label(box, text="integrated asic platform rev1.3 (2/11/2026)", font=(arial, 20)).pack(pady=(90, 8))
        tk.Label(box, text="rev1.3-> verilog + gui + gtkwave + yosys synthesis + schematic", font=(arial, 16)).pack(pady=(0, 32))
        tk.Button(box, text="new project", font=(arial, 14), width=24, height=3, command=self.newproject).pack(pady=5)
        tk.Button(box, text="open existing project", font=(arial, 14), width=24, height=3, command=self.openexistingproject).pack(pady=5)
    def newproject(self):
        filepath = filedialog.asksaveasfilename(
            title="create EDA2 project", defaultextension=filetype,
            initialdir=str(self.projects_dir), initialfile=f"new_project{filetype}",
            filetypes=[("EDA2 project", f"*{filetype}")]
        )
        if not filepath:
            return
        # Save the currently open project before changing the active project paths.
        try:
            if self.PP is not None and self.project_dir is not None:
                self.pack_project()
        except (OSError, tk.TclError) as e:
            messagebox.showerror("save failed", str(e))
            return
        requested_path = Path(filepath).resolve()
        project_name = requested_path.stem
        if not project_name or project_name in (".", ".."):
            messagebox.showerror("invalid project name", "Enter a valid project name.")
            return
        project_dir = self.projects_dir / project_name
        if project_dir.exists() and any(project_dir.iterdir()):
            messagebox.showerror(
                "project already exists",
                f'The project folder already exists:\n{project_dir}\n\nOpen that project instead of creating it again.'
            )
            return
        self.project_dir = project_dir
        self.PP = project_dir / f"{project_name}{filetype}"
        self.start_project_workspace(project_dir)
        self.create_project_structure(self.project_dir)
        self.waveform_path = self.default_waveform_path()
        self.showeditor("", "")
        try:
            self.pack_project()
            self.consoleprint(f"Created project folder: {self.project_dir}\n")
            self.consoleprint(f"Project file: {self.PP}\n")
        except OSError as e:
            messagebox.showerror("project creation failed", str(e))

    def openexistingproject(self):
        filepath = filedialog.askopenfilename(
            title="open project", initialdir=str(self.projects_dir),
            filetypes=[("EDA2 project", f"*{filetype}"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        selected_path = Path(filepath).resolve()
        try:
            if not selected_path.is_file() or selected_path.suffix.lower() != filetype:
                raise ValueError("Select a valid .eda2 project file.")

            # Save the old project while its editor widgets and paths are still active.
            if self.PP is not None and self.project_dir is not None:
                self.pack_project()

            # Legacy ZIP-based projects are imported into a same-named project folder.
            if zipfile.is_zipfile(selected_path):
                project_dir = self.projects_dir / selected_path.stem
                project_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(selected_path, "r") as archive:
                    root_resolved = project_dir.resolve()
                    for member in archive.infolist():
                        target = (project_dir / member.filename).resolve()
                        if root_resolved not in target.parents and target != root_resolved:
                            raise ValueError("Project archive contains an unsafe file path.")
                    archive.extractall(project_dir)
                self.project_dir = project_dir
                self.PP = project_dir / f"{project_dir.name}{filetype}"
                self.start_project_workspace(project_dir)
                self.create_project_structure(project_dir)
                design_path = project_dir / "verilog" / "design.v"
                testbench_path = project_dir / "verilog" / "testbench.v"
                vcode = design_path.read_text(encoding="utf-8") if design_path.is_file() else ""
                tbcode = testbench_path.read_text(encoding="utf-8") if testbench_path.is_file() else ""
            else:
                project_dir = selected_path.parent
                self.project_dir = project_dir
                self.PP = selected_path
                self.start_project_workspace(project_dir)
                self.create_project_structure(project_dir)
                try:
                    data = json.loads(selected_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"The selected .eda2 file is not valid project metadata: {exc}") from exc
                # Support older standalone JSON project files as well as the new project descriptor.
                if "verilog" in data or "testbench" in data:
                    (project_dir / "verilog" / "design.v").write_text(data.get("verilog", ""), encoding="utf-8")
                    (project_dir / "verilog" / "testbench.v").write_text(data.get("testbench", ""), encoding="utf-8")
                vcode = (project_dir / "verilog" / "design.v").read_text(encoding="utf-8")
                tbcode = (project_dir / "verilog" / "testbench.v").read_text(encoding="utf-8")
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError, tk.TclError) as e:
            self.project_dir = None
            self.PP = None
            messagebox.showerror("open failed", f"Could not open EDA2 project: {e}")
            return
        self.waveform_path = self.default_waveform_path()
        self.showeditor(vcode, tbcode)
        # Save metadata only after the new project's editors are installed.
        try:
            self.pack_project()
        except (OSError, tk.TclError) as e:
            messagebox.showerror("save failed", str(e))
            return
        self.consoleprint(f"Opened project folder: {self.project_dir}\n")
        self.consoleprint(f"Project file: {self.PP}\n")

    def saveproject(self):
        if self.PP is None or self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        try:
            if self.pack_project():
                self.consoleprint(f"Saved project: {self.PP}\n")
        except OSError as e:
            messagebox.showerror("save failed", f"Could not save project: {e}")
    def showeditor(self, vcode, tbcode):
        self.delete()
        toolbar = tk.Frame(self, padx=10, pady=8, bg="#f2f2f2")
        toolbar.pack(side="top", fill="x")
        tk.Label(toolbar, text=self.projectlabel(), bg="#f2f2f2", font=(arial, 11, "bold")).pack(side="left")
        for text, command in [
            ("verilog", self.confirm_verilog),
            ("synthesis", self.confirm_synthesis),
            ("RTL", self.generate_rtl_schematic),
            ("gate level", self.generate_gate_level_schematic),
            ("floorplan", self.confirm_floorplan),
            ("STA", self.confirm_sta),
            ("klayout", self.confirm_klayout),
            ("GTKWave", self.open_waveform)
        ]:
            tk.Button(toolbar, text=text, font=(arial, 9), command=command).pack(side="left", padx=(10, 0))
        for text, command in [("home", self.homeconfirm), ("save", self.saveproject), ("run", self.runproject)]:
            tk.Button(toolbar, text=text, font=(arial, 9), command=command).pack(side="right", padx=(6, 0))
        editorbox = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6)
        editorbox.pack(expand=True, fill="both")
        verilogbox, testbenchbox = self.editorpanel(editorbox, "verilog"), self.editorpanel(editorbox, "testbench")
        self.verilog_editor, self.testbench_editor = verilogbox["editor"], testbenchbox["editor"]
        self.verilog_editor.insert("1.0", vcode)
        self.testbench_editor.insert("1.0", tbcode)
        editorbox.add(verilogbox["frame"], minsize=320)
        editorbox.add(testbenchbox["frame"], minsize=320)
        consolebox = tk.Frame(self)
        consolebox.pack(side="bottom", fill="both")
        tk.Label(consolebox, text="output console", anchor="w", padx=8, font=(arial, 9)).pack(fill="x")
        self.OC = tk.Text(consolebox, height=9, bg="#111111", fg="#eeeeee", insertbackground="#eeeeee", wrap="word", font=(arial, 10))
        self.OC.pack(fill="both")
    def editorpanel(self, parent, labeltext):
        frame = tk.Frame(parent)
        tk.Label(frame, text=labeltext, anchor="w", padx=8, pady=4, font=(arial, 9)).pack(fill="x")
        editorframe = tk.Frame(frame)
        editorframe.pack(expand=True, fill="both")
        scrollbar = tk.Scrollbar(editorframe)
        scrollbar.pack(side="right", fill="y")
        editor = tk.Text(editorframe, undo=True, wrap="none", font=(arial, 11), yscrollcommand=scrollbar.set)
        editor.pack(side="left", expand=True, fill="both")
        scrollbar.config(command=editor.yview)
        return {"frame": frame, "editor": editor}
    def projectlabel(self):
        return f"project- {self.PP.name}" if self.PP else "project- untitled"
    def find_oss_cad_suite(self):
        """Find the OSS CAD Suite only inside EDA2/dependencies."""
        if not self.dependencies_dir.is_dir():
            return None
        for current_root, _, filenames in os.walk(self.dependencies_dir):
            if "yosys.exe" in {name.casefold() for name in filenames}:
                executable = Path(current_root) / "yosys.exe"
                if executable.parent.name.casefold() == "bin":
                    return executable.parent.parent
        return None

    def tool_environment(self):
        """Return a child-process environment using tools under EDA/dependencies."""
        env = os.environ.copy()
        tool_dirs = []

        if self.dependencies_dir.is_dir():
            for current_root, _, filenames in os.walk(self.dependencies_dir):
                names = {name.casefold() for name in filenames}
                if {"iverilog.exe", "vvp.exe"} & names or "dot.exe" in names:
                    tool_dirs.append(current_root)

        suite = self.find_oss_cad_suite()
        if suite is not None:
            self.oss_cad_suite = suite
            for candidate in (suite / "bin", suite / "lib", suite / "mingw64" / "bin", suite):
                if candidate.is_dir():
                    tool_dirs.append(str(candidate))

        # Remove duplicates while preserving order.
        unique_dirs = []
        seen = set()
        for directory in tool_dirs:
            value = str(Path(directory).resolve())
            key = os.path.normcase(value)
            if key not in seen:
                seen.add(key)
                unique_dirs.append(value)
        existing = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(unique_dirs + ([existing] if existing else []))
        return env, unique_dirs, suite

    def find_icarus_executable(self, name, env_dirs):
        executable = name + (".exe" if os.name == "nt" else "")
        for directory in env_dirs:
            candidate = Path(directory) / executable
            if candidate.is_file():
                return str(candidate)
        return shutil.which(name)

    def runproject(self):
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        self.consoleprint("compiling Verilog from active project\n")
        try:
            self.sync_editors_to_project()
            simulation_dir = self.project_dir / "simulation"
            simulation_dir.mkdir(parents=True, exist_ok=True)
            verilogpath = self.project_dir / "verilog" / "design.v"
            testbenchpath = self.project_dir / "verilog" / "testbench.v"
            outputpath = simulation_dir / "output.vvp"
            vcode = verilogpath.read_text(encoding="utf-8")
            tbcode = testbenchpath.read_text(encoding="utf-8")
            self.waveform_path.parent.mkdir(parents=True, exist_ok=True)
            self.waveform_path.unlink(missing_ok=True)
            dumpfile_pattern = r'\$dumpfile\s*\(\s*"[^"]+"\s*\)'
            dumpfile_call = f'$dumpfile("{self.waveform_path.as_posix()}")'
            if re.search(dumpfile_pattern, tbcode):
                tbcode = re.sub(dumpfile_pattern, dumpfile_call, tbcode, count=1)
            else:
                module_match = re.search(r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_]\w*)\b", tbcode)
                if module_match is None:
                    self.consoleprint("could not identify a testbench module for waveform generation\n")
                    self.consoleprint("add a testbench module so EDA2 can inject waveform commands\n")
                    return
                endmodule_match = re.search(r"\bendmodule\b", tbcode[module_match.end():])
                if endmodule_match is None:
                    self.consoleprint("could not find endmodule in testbench\n")
                    return
                insert_pos = module_match.end() + endmodule_match.start()
                module_name = module_match.group(1)
                waveform_code = f'\ninitial begin\n    $dumpfile("{self.waveform_path.as_posix()}");\n'
                if not re.search(r"\$dumpvars\s*\(", tbcode):
                    waveform_code += f"    $dumpvars(0, {module_name});\n"
                waveform_code += "end\n\n"
                tbcode = tbcode[:insert_pos] + waveform_code + tbcode[insert_pos:]
            if not re.search(r"\$dumpvars\s*\(", tbcode):
                module_match = re.search(r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_]\w*)\b", tbcode)
                if module_match:
                    module_name = module_match.group(1)
                    endmodule_match = re.search(r"\bendmodule\b", tbcode[module_match.end():])
                    if endmodule_match:
                        insert_pos = module_match.end() + endmodule_match.start()
                        tbcode = tbcode[:insert_pos] + f"\ninitial begin\n    $dumpvars(0, {module_name});\nend\n\n" + tbcode[insert_pos:]
            # Use a generated simulation copy; the user's testbench source remains unchanged.
            simulation_tb = simulation_dir / "testbench_runtime.v"
            simulation_tb.write_text(tbcode, encoding="utf-8")
            env, tool_dirs, suite_root = self.tool_environment()
            compiler = self.find_icarus_executable("iverilog", tool_dirs)
            simulator = self.find_icarus_executable("vvp", tool_dirs)
            self.consoleprint("Tool PATH entries for this run:\n")
            for directory in tool_dirs:
                self.consoleprint(f"  {directory}\n")
            if compiler is None or simulator is None:
                self.consoleprint("Icarus Verilog was not found. Checked Desktop/eda2dependencies/icarus/iverilog/bin, EDA2/dependencies/icarus, and OSS CAD Suite.\n")
                messagebox.showerror(
                    "Icarus Verilog not found",
                    "Could not find iverilog.exe and vvp.exe.\n\n"
                    "Expected Desktop/eda2dependencies/icarus/iverilog/bin, dependencies/icarus/bin, or the OSS CAD Suite bin folder.\n"
                    "Check that both executables exist in the same installation."
                )
                return
            compileresult = self.commandrun(
                [compiler, "-g2012", "-o", str(outputpath), str(simulation_tb), str(verilogpath)],
                cwd=simulation_dir, env=env
            )
            if compileresult is None or compileresult.returncode != 0:
                self.consoleprint("compilation failed\n")
                if compileresult is not None:
                    self.processoutput(compileresult)
                self.pack_project()
                return
            self.consoleprint("compilation successful, running simulation\n")
            simresult = self.commandrun([simulator, str(outputpath)], cwd=simulation_dir, env=env)
            if simresult is None:
                return
            self.processoutput(simresult)
            if self.waveform_path.is_file():
                self.consoleprint(f"waveform generated inside project: simulation/waveform.vcd\n")
            else:
                self.consoleprint("simulation did not generate a waveform file; check the testbench\n")
            self.consoleprint("simulation successful\n" if simresult.returncode == 0 else "simulation failed\n")
            self.pack_project()
        except OSError as e:
            self.consoleprint(f"simulation error: {e}\n")
    def commandrun(self, command, cwd=None, env=None):
        try:
            return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
        except FileNotFoundError:
            self.consoleprint(f"could not find {command[0]}, make sure it is installed and added to PATH\n")
            return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="")
        except OSError as e:
            self.consoleprint(f"could not execute {command[0]}: {e}\n")
            return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="")
    def load_gtkwave_path(self):
        """Load the previously selected GTKWave executable, if it still exists."""
        try:
            if self.settings_path.is_file():
                settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
                saved_path = settings.get("gtkwave_path")
                if saved_path:
                    executable = Path(saved_path)
                    if executable.is_file():
                        return executable
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return None

    def save_gtkwave_path(self):
        """Remember the selected GTKWave executable for future EDA2 launches."""
        try:
            settings = {}
            if self.settings_path.is_file():
                try:
                    settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    settings = {}
            settings["gtkwave_path"] = str(self.gtkwave_path) if self.gtkwave_path else ""
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        except OSError as e:
            self.consoleprint(f"could not save GTKWave location: {e}\\n")

    def find_gtkwave_executable(self):
        """Find GTKWave anywhere inside EDA2/dependencies, then check PATH."""
        executable_name = "gtkwave.exe" if os.name == "nt" else "gtkwave"

        # Search the complete dependencies tree. GTKWave archives often contain
        # several nested folders, e.g. gtkwave/gtkwave64/bin/gtkwave.exe.
        if self.dependencies_dir.is_dir():
            for current_root, _, filenames in os.walk(self.dependencies_dir):
                for filename in filenames:
                    if filename.casefold() == executable_name.casefold():
                        candidate = Path(current_root) / filename
                        if candidate.is_file():
                            return candidate

        located = shutil.which("gtkwave.exe" if os.name == "nt" else "gtkwave")
        return Path(located) if located else None

    def launch_gtkwave(self, waveform):
        """Launch GTKWave with its own folder on PATH so bundled DLLs can be found."""
        if self.gtkwave_path is None or not self.gtkwave_path.is_file():
            self.gtkwave_path = self.find_gtkwave_executable()

        if self.gtkwave_path is None:
            executable = filedialog.askopenfilename(
                title="select GTKWave executable",
                initialdir=str(self.dependencies_dir),
                filetypes=[
                    ("GTKWave executable", "gtkwave.exe"),
                    ("Executable files", "*.exe"),
                    ("All Files", "*.*")
                ]
            )
            if not executable:
                self.consoleprint("GTKWave executable was not selected\\n")
                return False

            selected_path = Path(executable).resolve()
            if selected_path.name.casefold() not in ("gtkwave.exe", "gtkwave"):
                messagebox.showerror(
                    "invalid GTKWave executable",
                    "Please select gtkwave.exe, not a shortcut or another executable."
                )
                return False

            self.gtkwave_path = selected_path
            self.save_gtkwave_path()

        env = os.environ.copy()
        executable_dir = str(self.gtkwave_path.parent)
        env["PATH"] = executable_dir + os.pathsep + env.get("PATH", "")

        try:
            subprocess.Popen(
                [str(self.gtkwave_path), str(waveform)],
                cwd=executable_dir,
                env=env
            )
            self.consoleprint(f"opened waveform {waveform} with {self.gtkwave_path}\\n")
            return True
        except OSError as e:
            messagebox.showerror("GTKWave launch failed", str(e))
            self.consoleprint(f"GTKWave launch failed: {e}\\n")
            return False

    def open_waveform(self):
        # Use the latest generated waveform by default; allow selecting another VCD if needed.
        if self.waveform_path is not None and self.waveform_path.is_file():
            waveform = self.waveform_path
        else:
            filepath = filedialog.askopenfilename(
                title="open waveform file",
                initialdir=str(self.waveform_path.parent if self.waveform_path else Path.home()),
                filetypes=[("VCD Waveforms", "*.vcd"), ("All Files", "*.*")]
            )
            if not filepath:
                return
            waveform = Path(filepath)

        self.launch_gtkwave(waveform)

    def processoutput(self, result):
        if result.stdout:
            self.consoleprint(result.stdout)
        if result.stderr:
            self.consoleprint(result.stderr)
    def consoleprint(self, text):
        if self.OC is not None and self.OC.winfo_exists():
            self.OC.insert("end", text)
            self.OC.see("end")
    def homeconfirm(self):
        if not messagebox.askyesno("return home", "Return to start page? The current project files and .eda2 descriptor will be saved."):
            return
        try:
            if self.PP is not None:
                self.pack_project()
        except (OSError, tk.TclError) as e:
            messagebox.showerror("save failed", str(e))
            return
        self.project_dir = None
        self.PP = None
        self.waveform_path = None
        self.projectpage()
    def detect_top_modules(self, verilog_code):
        # Basic heuristic: declared modules not instantiated by another module are likely tops.
        module_pattern = re.compile(
            r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_$][A-Za-z0-9_$]*)",
            re.MULTILINE
        )
        modules = module_pattern.findall(verilog_code)
        if not modules:
            return []
        clean_code = re.sub(r"/\*.*?\*/", " ", verilog_code, flags=re.DOTALL)
        clean_code = re.sub(r"//[^\n]*", " ", clean_code)
        # Remove module declarations and headers before searching for instantiations.
        clean_code = re.sub(
            r"\bmodule\s+(?:automatic\s+|static\s+)?[A-Za-z_$][A-Za-z0-9_$]*"
            r"(?:\s*#\s*\(.*?\))?\s*\([^;]*?\)\s*;",
            " ",
            clean_code,
            flags=re.DOTALL
        )
        instantiated = set()
        for name in modules:
            pattern = re.compile(
                r"\b" + re.escape(name) +
                r"\s*(?:#\s*\(.*?\)\s*)?[A-Za-z_$][A-Za-z0-9_$]*\s*\(",
                re.DOTALL
            )
            if pattern.search(clean_code):
                instantiated.add(name)
        tops = [name for name in modules if name not in instantiated]
        return tops or modules
    def run_yosys(self):
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        if self.yosys_running:
            messagebox.showinfo("synthesis running", "Yosys synthesis is already running for this project.")
            return

        vcode = self.verilog_editor.get("1.0", "end-1c").strip()
        if not vcode:
            messagebox.showwarning("no Verilog RTL", "Enter your design RTL before running Yosys.")
            return
        tops = self.detect_top_modules(vcode)
        if not tops:
            messagebox.showerror("top module not found", "Could not find a Verilog module declaration.")
            return
        default_top = tops[0]
        prompt = (
            f"Possible top modules: {', '.join(tops)}\nEnter the top-module name:"
            if len(tops) > 1
            else f"Detected top module: {default_top}\nEnter a different name to override, or leave unchanged:"
        )
        top = simpledialog.askstring("Top module", prompt, initialvalue=default_top, parent=self)
        if top is None:
            self.consoleprint("Yosys synthesis cancelled.\n")
            return
        top = top.strip()
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", top):
            messagebox.showerror("invalid top module", "Enter a valid Verilog module identifier.")
            return
        if not re.search(r"\bmodule\s+(?:automatic\s+|static\s+)?" + re.escape(top) + r"\b", vcode):
            messagebox.showerror("module not found", f'The RTL does not declare a module named "{top}".')
            return

        env, tool_dirs, suite_root = self.tool_environment()
        if suite_root is None:
            selected = filedialog.askopenfilename(
                title="Locate yosys.exe", initialdir=str(self.dependencies_dir),
                filetypes=[("Yosys executable", "yosys.exe"), ("Executable files", "*.exe"), ("All files", "*.*")]
            )
            if not selected:
                self.consoleprint("Yosys not started: yosys.exe was not selected.\n")
                return
            yosys_exe = Path(selected).resolve()
            suite_root = yosys_exe.parent.parent
            for candidate in (suite_root / "bin", suite_root / "lib", suite_root / "mingw64" / "bin", suite_root):
                if candidate.is_dir() and str(candidate.resolve()) not in tool_dirs:
                    tool_dirs.append(str(candidate.resolve()))
            env["PATH"] = os.pathsep.join(tool_dirs + [env.get("PATH", "")])
        else:
            yosys_exe = suite_root / "bin" / "yosys.exe"
        if not yosys_exe.is_file():
            messagebox.showerror("Yosys executable not found", f"Could not find yosys.exe at {yosys_exe}")
            return

        self.sync_editors_to_project()
        project_dir = self.project_dir
        source_path = project_dir / "verilog" / "design.v"
        output_dir = project_dir / "synthesis"
        schematic_dir = project_dir / "schematic"
        output_dir.mkdir(parents=True, exist_ok=True)
        schematic_dir.mkdir(parents=True, exist_ok=True)
        netlist_path = output_dir / "synthesized.v"
        script_path = output_dir / "run_synthesis.ys"
        json_path = output_dir / "synthesized.json"
        rtl_json_path = output_dir / "rtl.json"
        top_module_path = output_dir / "top_module.txt"
        top_module_path.write_text(top, encoding="utf-8")

        def yosys_path(path):
            return path.resolve().as_posix().replace('"', '\\"')

        yosys_script = (
            f'read_verilog "{yosys_path(source_path)}"\n'
            f'hierarchy -check -top {top}\n'
            # Preserve a pre-mapping RTL-oriented representation for the RTL viewer.
            # This is intentionally exported before synth performs gate-level lowering.
            'proc\n'
            'opt\n'
            f'write_json "{yosys_path(rtl_json_path)}"\n'
            f'synth -top {top}\n'
            'stat\n'
            f'write_verilog -noattr "{yosys_path(netlist_path)}"\n'
            f'write_json "{yosys_path(json_path)}"\n'
        )
        try:
            script_path.write_text(yosys_script, encoding="utf-8")
            launcher_path = output_dir / "run_yosys.cmd"
            environment_bat = suite_root / "environment.bat"
            if os.name == "nt" and environment_bat.is_file():
                launcher_path.write_text(
                    "@echo off\r\n"
                    f'call "{environment_bat}"\r\n'
                    "if errorlevel 1 exit /b %errorlevel%\r\n"
                    f'cd /d "{schematic_dir}"\r\n'
                    "if errorlevel 1 exit /b %errorlevel%\r\n"
                    f'"{yosys_exe}" -s "{script_path}"\r\n'
                    "exit /b %errorlevel%\r\n",
                    encoding="utf-8"
                )
                yosys_command = ["cmd.exe", "/d", "/c", str(launcher_path)]
            else:
                yosys_command = [str(yosys_exe), "-s", str(script_path)]

            self.yosys_running = True
            self.consoleprint(f"Starting Yosys synthesis in background for top module: {top}\n")
            self.consoleprint("EDA2 remains usable while Yosys synthesis runs.\n")
            self.consoleprint(f"Yosys script: {script_path}\n")

            def worker():
                try:
                    yosys_result = subprocess.run(
                        yosys_command, cwd=schematic_dir, env=env,
                        capture_output=True, text=True
                    )
                    self.yosys_queue.put(("yosys", yosys_result.stdout, yosys_result.stderr, yosys_result.returncode))
                    if yosys_result.returncode != 0:
                        self.yosys_queue.put(("done", False, f"Yosys exited with code {yosys_result.returncode}."))
                        return
                    if not netlist_path.is_file():
                        self.yosys_queue.put(("done", False, "Yosys returned success but synthesized.v is missing."))
                        return
                    if not json_path.is_file():
                        self.yosys_queue.put(("done", False, "Yosys returned success but synthesized.json is missing."))
                        return
                    if not rtl_json_path.is_file():
                        self.yosys_queue.put(("done", False, "Yosys returned success but rtl.json is missing."))
                        return

                    self.yosys_queue.put(("done", True, "Synthesis completed. RTL and gate-level JSON files are ready for schematic generation."))
                except Exception as exc:
                    self.yosys_queue.put(("done", False, f"Background synthesis error: {exc}"))

            threading.Thread(target=worker, daemon=True).start()
            self.after(100, self.poll_yosys_queue)
        except OSError as exc:
            self.yosys_running = False
            self.consoleprint(f"could not start Yosys: {exc}\n")

    def poll_yosys_queue(self):
        """Transfer background-process output to Tkinter on the GUI thread."""
        try:
            while True:
                item = self.yosys_queue.get_nowait()
                if item[0] == "yosys":
                    stage, stdout, stderr, returncode = item
                    if stdout:
                        self.consoleprint(stdout)
                    if stderr:
                        self.consoleprint(stderr)
                    if stage == "yosys" and returncode == 0:
                        self.consoleprint("Yosys completed: synthesized.v and synthesized.json generated.\n")
                elif item[0] == "stage":
                    self.consoleprint(item[1] + "\n")
                elif item[0] == "done":
                    success, detail = item[1], item[2]
                    self.yosys_running = False
                    self.consoleprint(detail + "\n")
                    if success:
                        self.consoleprint("Outputs: synthesis/rtl.json, synthesis/synthesized.v, synthesis/synthesized.json\n")
                        try:
                            self.pack_project()
                        except OSError as exc:
                            self.consoleprint(f"Could not save project metadata: {exc}\n")
                    else:
                        self.consoleprint("Synthesis workflow failed; see the stage-specific output above.\n")
                    return
        except queue.Empty:
            pass
        if self.yosys_running:
            self.after(100, self.poll_yosys_queue)

    def find_json_top_module(self, json_path):
        """Find the top module from Yosys JSON metadata or module instantiations."""
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            modules = data.get("modules", {})
            marked_tops = []
            for name, module in modules.items():
                top_value = module.get("attributes", {}).get("top")
                if top_value not in (None, "0", "00000000000000000000000000000000", 0, False):
                    marked_tops.append(name)
            if len(marked_tops) == 1:
                return marked_tops[0]

            instantiated = set()
            module_names = set(modules)
            for module in modules.values():
                for cell in module.get("cells", {}).values():
                    cell_type = cell.get("type")
                    if cell_type in module_names:
                        instantiated.add(cell_type)
            roots = [name for name in modules if name not in instantiated]
            if len(roots) == 1:
                return roots[0]
            if len(marked_tops) > 1:
                return marked_tops[0]
            if len(roots) > 1:
                return None
            return next(iter(modules), None)
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            return None

    def generate_rtl_schematic(self):
        self.generate_hierarchical_rtl_schematic()

    def build_hierarchical_rtl_dot(self, json_path, top):
        """Build a conventional RTL block diagram with named port anchors."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        modules = data.get("modules", {})
        if top not in modules:
            raise ValueError(f"Top module '{top}' is not present in rtl.json.")
        module = modules[top]
        module_names = set(modules)
        cells = module.get("cells", {})
        instances = {}
        primitive_cells = []
        for cell_name, cell in cells.items():
            if cell.get("type") in module_names:
                instances[cell_name] = cell
            else:
                primitive_cells.append((cell_name, cell))

        def esc(value):
            return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;"))

        def ident(value):
            return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", str(value))

        def port_ident(value):
            return "p_" + re.sub(r"[^A-Za-z0-9_]", "_", str(value))

        def signal_color(name):
            # Monochrome engineering schematic: all nets use black strokes.
            return "#000000"

        lines = [
            "digraph RTL {",
            '  graph [rankdir=LR, bgcolor="white", pad="0.30", nodesep="0.48", ranksep="0.90", '
            'splines=ortho, concentrate=true, overlap=false, outputorder=edgesfirst, fontname="Arial", '
            f'label="{esc(top)}", labelloc=t, fontsize=18];',
            '  node [shape=plain, fontname="Arial", fontsize=10];',
            '  edge [fontname="Arial", fontsize=9, arrowsize=0.65, penwidth=1.25];'
        ]

        # External interface is kept on the left/right edges of the drawing.
        top_ports = {}
        input_nodes, output_nodes = [], []
        for port_name, port in module.get("ports", {}).items():
            bits = tuple(str(bit) for bit in port.get("bits", []))
            direction = port.get("direction", "inout")
            width = len(bits)
            suffix = f" [{width-1}:0]" if width > 1 else ""
            node_id = ident("topport_" + port_name)
            color = "#000000"
            fill = "#ffffff"
            label = (f'<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="6" COLOR="{color}">'
                     f'<TR><TD BGCOLOR="{fill}"><B>{esc(port_name + suffix)}</B></TD></TR></TABLE>')
            lines.append(f'  {node_id} [label=<{label}>];')
            top_ports[port_name] = (node_id, bits, direction)
            (input_nodes if direction == "input" else output_nodes).append(node_id)

        # Module instances are proper rectangular blocks. Each port has its own
        # Graphviz port anchor, so wires attach at the correct side of the block.
        instance_ports = {}
        for instance_name, cell in instances.items():
            node_id = ident(instance_name)
            directions = cell.get("port_directions", {})
            connections = cell.get("connections", {})
            in_rows, out_rows = [], []
            for port_name in sorted(connections):
                direction = directions.get(port_name, "inout")
                bits = connections[port_name]
                width = len(bits)
                suffix = f" [{width-1}:0]" if width > 1 else ""
                anchor = port_ident(port_name)
                color = "#000000"
                row = (f'<TR><TD PORT="{anchor}" ALIGN="LEFT">'
                       f'<FONT COLOR="{color}">{"▶" if direction == "input" else "◀" if direction == "output" else "◆"}</FONT> '
                       f'{esc(port_name + suffix)}</TD></TR>')
                (in_rows if direction == "input" else out_rows).append(row)
                instance_ports[(instance_name, port_name)] = (node_id, anchor, direction)
            port_table = (
                '<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="5" CELLSPACING="0" COLOR="#000000">'
                f'<TR><TD COLSPAN="1" BGCOLOR="#ffffff"><B>{esc(instance_name)}</B><BR/>'
                f'<FONT POINT-SIZE="9">{esc(cell.get("type", "module"))}</FONT></TD></TR>'
                + "".join(in_rows + out_rows) + '</TABLE>'
            )
            lines.append(f'  {node_id} [label=<{port_table}>];')

        # The JSON may contain top-level RTL primitives alongside module instances.
        # Keep them visible as a clearly identified logic region rather than
        # inventing internal functional blocks that are not present in the JSON.
        logic_node = None
        if primitive_cells:
            logic_node = "top_level_logic"
            logic_table = (
                '<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="8" COLOR="#000000">'
                '<TR><TD BGCOLOR="#ffffff"><B>Top-level RTL logic</B></TD></TR>'
                f'<TR><TD><FONT POINT-SIZE="9">{len(primitive_cells)} primitive cells</FONT></TD></TR>'
                '</TABLE>'
            )
            lines.append(f'  {logic_node} [label=<{logic_table}>];')

        # Resolve bit drivers and sinks to actual module ports.
        drivers, sinks = {}, {}
        for port_name, (node_id, bits, direction) in top_ports.items():
            target = drivers if direction == "input" else sinks if direction == "output" else None
            if target is not None:
                for bit in bits:
                    target.setdefault(bit, []).append((node_id, None, port_name))
        for instance_name, cell in instances.items():
            for port_name, bits in cell.get("connections", {}).items():
                node_id, anchor, direction = instance_ports[(instance_name, port_name)]
                target = sinks if direction == "input" else drivers if direction == "output" else None
                if target is not None:
                    for bit in bits:
                        target.setdefault(str(bit), []).append((node_id, anchor, port_name))

        # Aggregate primitive logic connections at the boundary of the logic block.
        # It is deliberately shown as one region; the gate-level button expands cells.
        if logic_node:
            for _, cell in primitive_cells:
                for port_name, bits in cell.get("connections", {}).items():
                    direction = cell.get("port_directions", {}).get(port_name)
                    target = sinks if direction == "input" else drivers if direction == "output" else None
                    if target is not None:
                        for bit in bits:
                            target.setdefault(str(bit), []).append((logic_node, None, port_name))

        bit_names = {}
        for net_name, net in module.get("netnames", {}).items():
            if net_name.startswith("$"):
                continue
            for bit in net.get("bits", []):
                bit_names.setdefault(str(bit), net_name)

        grouped = {}
        for bit, source_list in drivers.items():
            for src_node, src_port, src_name in source_list:
                for dst_node, dst_port, dst_name in sinks.get(bit, []):
                    if src_node == dst_node:
                        continue
                    key = (src_node, src_port, dst_node, dst_port)
                    grouped.setdefault(key, set())
                    label = bit_names.get(bit)
                    if label:
                        grouped[key].add(label)

        # Fan-out nets (especially clocks and reset) share one junction rather
        # than drawing several independent long wires from the same input pin.
        by_source = {}
        for (src_node, src_port, dst_node, dst_port), names in grouped.items():
            by_source.setdefault((src_node, src_port), []).append((dst_node, dst_port, names))

        for source_index, ((src_node, src_port), destinations) in enumerate(by_source.items()):
            source = f'{src_node}:{src_port}:e' if src_port else src_node
            source_names = set()
            for _, _, names in destinations:
                source_names.update(names)
            color = signal_color(" ".join(source_names)) if source_names else "#000000"
            fanout = len(destinations) > 1 and src_node.startswith("n_topport_")
            if fanout:
                junction = f"fanout_{source_index}"
                lines.append(f'  {junction} [shape=point, width=0.07, height=0.07, label="", color="{color}", fillcolor="{color}", style=filled];')
                lines.append(f'  {source} -> {junction} [color="{color}", penwidth=1.45, arrowhead=none];')
                source = junction
            for dst_node, dst_port, names in destinations:
                clean_names = sorted(names)
                label = ", ".join(clean_names[:2])
                if len(clean_names) > 2:
                    label += f" +{len(clean_names)-2} nets"
                dst = f'{dst_node}:{dst_port}:w' if dst_port else dst_node
                attrs = [f'color="{color}"', f'fontcolor="{color}"']
                if label and (not fanout or dst_node == destinations[0][0]):
                    attrs.append(f'xlabel="{esc(label)}"')
                lines.append(f'  {source} -> {dst} [{", ".join(attrs)}];')

        # Guide the layout into a conventional left-to-right datapath instead
        # of letting Graphviz place blocks solely by whichever net has most edges.
        # These ranks describe the actual top-level module instances in this RTL.
        stage_one = [ident(name) for name in ("u_lfsr", "u_chaos", "top_level_logic")
                     if name in instances or name == "top_level_logic" and logic_node]
        stage_two = [ident("u_alu")] if "u_alu" in instances else []
        stage_three = [ident("u_pwm")] if "u_pwm" in instances else []
        for stage in (stage_one, stage_two, stage_three):
            if len(stage) > 1:
                lines.append('  { rank=same; ' + "; ".join(stage) + '; }')
        # Invisible ordering constraints establish the intended signal-flow direction.
        if stage_one and stage_two:
            for source in stage_one:
                lines.append(f'  {source} -> {stage_two[0]} [style=invis, weight=8];')
        if stage_two and stage_three:
            lines.append(f'  {stage_two[0]} -> {stage_three[0]} [style=invis, weight=8];')
        lines.append("}")
        return "\n".join(lines)

    def generate_hierarchical_rtl_schematic(self):
        """Render the RTL hierarchy as module blocks, not a flattened cell tangle."""
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        if self.yosys_running:
            messagebox.showinfo("EDA tool running", "A Yosys/Graphviz operation is already running. Please wait for it to finish.")
            return
        json_path = self.project_dir / "synthesis" / "rtl.json"
        if not json_path.is_file():
            messagebox.showerror("RTL JSON not found", f"Could not find {json_path}. Run synthesis first.")
            return
        top = self.find_json_top_module(json_path)
        top_file = self.project_dir / "synthesis" / "top_module.txt"
        if top_file.is_file():
            try:
                saved_top = top_file.read_text(encoding="utf-8").strip()
                if saved_top:
                    top = saved_top
            except OSError:
                pass
        if not top:
            messagebox.showerror("Top module not identified", "EDA2 could not identify a unique top module in rtl.json.")
            return
        env, tool_dirs, suite_root = self.tool_environment()
        graphviz_exe = self.find_icarus_executable("dot", tool_dirs)
        if graphviz_exe is None:
            messagebox.showerror("Graphviz not found", "Could not find dot.exe under EDA/dependencies.")
            return
        schematic_dir = self.project_dir / "schematic"
        schematic_dir.mkdir(parents=True, exist_ok=True)
        dot_path = schematic_dir / "rtl_schematic.dot"
        svg_path = schematic_dir / "rtl_schematic.svg"
        try:
            dot_path.write_text(self.build_hierarchical_rtl_dot(json_path, top), encoding="utf-8")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("RTL schematic error", f"Could not build the hierarchical RTL diagram: {exc}")
            return
        self.yosys_running = True
        self.consoleprint(f"Generating hierarchical RTL schematic from {json_path.name}...\n")
        self.consoleprint(f"Top module: {top}\n")

        def worker():
            try:
                result = subprocess.run([graphviz_exe, "-Tsvg", str(dot_path), "-o", str(svg_path)], cwd=schematic_dir, env=env, capture_output=True, text=True)
                self.yosys_queue.put(("graphviz", result.stdout, result.stderr, result.returncode))
                if result.returncode != 0 or not svg_path.is_file() or svg_path.stat().st_size == 0:
                    self.yosys_queue.put(("done", False, "Graphviz failed to create the hierarchical RTL schematic."))
                else:
                    self.yosys_queue.put(("done", True, "Hierarchical RTL schematic created: schematic/rtl_schematic.svg"))
            except Exception as exc:
                self.yosys_queue.put(("done", False, f"RTL schematic generation error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self.poll_yosys_queue)

    def build_gate_level_dot(self, json_path, top):
        """Build a monochrome, pin-accurate cell schematic from Yosys JSON."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        modules = data.get("modules", {})
        if top not in modules:
            raise ValueError(f"Top module '{top}' is not present in {json_path.name}.")
        module = modules[top]
        cells = module.get("cells", {})

        def esc(value):
            return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;"))

        def safe(value):
            return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", str(value))

        lines = [
            "digraph GATE_LEVEL {",
            ' graph [rankdir=LR, bgcolor="white", pad="0.25", nodesep="0.28", ranksep="0.65", '
            'splines=ortho, concentrate=false, overlap=false, outputorder=edgesfirst, '
            'fontname="Arial", labelloc=t, fontsize=18, label="' + esc(top) + '"];',
            ' node [shape=plain, fontname="Arial", fontsize=9];',
            ' edge [color="black", fontcolor="black", fontname="Arial", fontsize=7, '
            'penwidth=1.0, arrowsize=0.55];'
        ]

        # Give every top-level port a real connection anchor.
        top_ports = {}
        for pname, port in module.get("ports", {}).items():
            bits = [str(b) for b in port.get("bits", [])]
            direction = port.get("direction", "input")
            suffix = f" [{len(bits)-1}:0]" if len(bits) > 1 else ""
            node = safe("top_" + pname)
            port_id = safe("anchor_" + pname)
            table = (f'<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="5" COLOR="black">'
                     f'<TR><TD PORT="{port_id}"><B>{esc(pname + suffix)}</B></TD></TR></TABLE>')
            lines.append(f' {node} [label=<{table}>];')
            top_ports[pname] = (node, port_id, direction, bits)

        # Each standard/generic cell is a separate rectangular symbol with named pins.
        cell_pins = {}
        for cname, cell in cells.items():
            node = safe("cell_" + cname)
            directions = cell.get("port_directions", {})
            connections = cell.get("connections", {})
            rows = []
            for pname in sorted(connections):
                direction = directions.get(pname, "inout")
                bits = connections[pname]
                width = len(bits)
                suffix = f" [{width-1}:0]" if width > 1 else ""
                anchor = safe("pin_" + pname)
                prefix = "◀" if direction == "output" else "▶" if direction == "input" else "◆"
                rows.append(f'<TR><TD PORT="{anchor}" ALIGN="LEFT">{prefix} {esc(pname + suffix)}</TD></TR>')
                cell_pins[(cname, pname)] = (node, anchor, direction, [str(b) for b in bits])
            cell_type = cell.get("type", "cell")
            table = ('<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="4" CELLSPACING="0" COLOR="black">'
                     f'<TR><TD BGCOLOR="white"><B>{esc(cell_type)}</B></TD></TR>'
                     + ''.join(rows) + '</TABLE>')
            lines.append(f' {node} [label=<{table}>];')

        # Collapse bit-level connections into bus edges between matching cell pins.
        # This keeps wide datapaths readable and avoids hundreds of redundant wires.
        bit_names = {}
        for net_name, net in module.get("netnames", {}).items():
            # Ignore Yosys-generated source-location names; they make unreadable wire labels.
            if (len(net_name) > 36 or "/" in net_name or "\\" in net_name
                    or ":" in net_name or net_name.startswith("$")):
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.$\[\]]*", net_name):
                continue
            net_bits = net.get("bits", [])
            for index, bit in enumerate(net_bits):
                bit_names.setdefault(str(bit), net_name if len(net_bits) == 1 else f"{net_name}[{index}]")

        drivers, sinks = {}, {}
        for pname, (node, anchor, direction, bits) in top_ports.items():
            target = drivers if direction == "input" else sinks if direction == "output" else None
            if target is not None:
                for bit in bits:
                    target.setdefault(bit, []).append((node, anchor, pname))

        for (cname, pname), (node, anchor, direction, bits) in cell_pins.items():
            target = drivers if direction == "output" else sinks if direction == "input" else None
            if target is not None:
                for bit in bits:
                    target.setdefault(bit, []).append((node, anchor, pname))

        grouped_edges = {}
        for bit in set(drivers) & set(sinks):
            for src_node, src_pin, _ in drivers[bit]:
                for dst_node, dst_pin, _ in sinks[bit]:
                    if src_node == dst_node:
                        continue
                    key = (src_node, src_pin, dst_node, dst_pin)
                    grouped_edges.setdefault(key, set()).add(bit_names.get(bit, ""))

        for (src_node, src_pin, dst_node, dst_pin), labels in grouped_edges.items():
            src = f"{src_node}:{src_pin}:e" if src_pin else src_node
            dst = f"{dst_node}:{dst_pin}:w" if dst_pin else dst_node
            clean_labels = sorted(label for label in labels if label)
            if len(clean_labels) == 1:
                label = clean_labels[0]
            elif len(clean_labels) > 1:
                label = f"{len(clean_labels)}-bit bus"
            else:
                label = ""
            label_attr = f', xlabel="{esc(label)}"' if label else ""
            lines.append(f" {src} -> {dst} [arrowhead=normal{label_attr}];")

        # Put primary inputs/outputs at the outside edges of the cell network.
        input_ids = [safe("top_" + n) for n, (_, _, d, _) in top_ports.items() if d == "input"]
        output_ids = [safe("top_" + n) for n, (_, _, d, _) in top_ports.items() if d == "output"]
        if input_ids:
            lines.append('{ rank=source; ' + '; '.join(input_ids) + '; }')
        if output_ids:
            lines.append('{ rank=sink; ' + '; '.join(output_ids) + '; }')
        lines.append('}')
        return "\n".join(lines)

    def generate_gate_level_schematic(self):
        """Render every cell from synthesized.json in a monochrome schematic."""
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        if self.yosys_running:
            messagebox.showinfo("EDA tool running", "A Yosys/Graphviz operation is already running. Please wait for it to finish.")
            return
        json_path = self.project_dir / "synthesis" / "synthesized.json"
        if not json_path.is_file():
            messagebox.showerror("Gate-level JSON not found", f"Could not find {json_path}. Run synthesis first.")
            return
        top = self.find_json_top_module(json_path)
        top_file = self.project_dir / "synthesis" / "top_module.txt"
        if top_file.is_file():
            try:
                top = top_file.read_text(encoding="utf-8").strip() or top
            except OSError:
                pass
        if not top:
            messagebox.showerror("Top module not identified", "EDA2 could not identify a unique top module in synthesized.json.")
            return
        env, tool_dirs, suite_root = self.tool_environment()
        graphviz_exe = self.find_icarus_executable("dot", tool_dirs)
        if graphviz_exe is None:
            messagebox.showerror("Graphviz not found", "Could not find dot.exe under EDA/dependencies.")
            return
        schematic_dir = self.project_dir / "schematic"
        schematic_dir.mkdir(parents=True, exist_ok=True)
        dot_path = schematic_dir / "gate_level_schematic.dot"
        svg_path = schematic_dir / "gate_level_schematic.svg"
        try:
            dot_path.write_text(self.build_gate_level_dot(json_path, top), encoding="utf-8")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Gate-level schematic error", f"Could not build the cell schematic: {exc}")
            return
        self.yosys_running = True
        self.consoleprint(f"Generating monochrome gate-level schematic from {json_path.name}...\n")
        self.consoleprint(f"Top module: {top}\n")
        self.consoleprint("Every cell is shown individually; wires and symbols are black on white.\n")

        def worker():
            try:
                result = subprocess.run([graphviz_exe, "-Tsvg", str(dot_path), "-o", str(svg_path)],
                                        cwd=schematic_dir, env=env, capture_output=True, text=True)
                self.yosys_queue.put(("graphviz", result.stdout, result.stderr, result.returncode))
                if result.returncode != 0 or not svg_path.is_file() or svg_path.stat().st_size == 0:
                    self.yosys_queue.put(("done", False, "Graphviz failed to create the gate-level schematic."))
                else:
                    self.yosys_queue.put(("done", True, "Monochrome gate-level schematic created: schematic/gate_level_schematic.svg"))
            except Exception as exc:
                self.yosys_queue.put(("done", False, f"Gate-level schematic generation error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self.poll_yosys_queue)

    def generate_json_schematic(self, schematic_type):
        """Render an existing Yosys JSON file through Yosys show and Graphviz."""
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
            return
        if self.yosys_running:
            messagebox.showinfo("EDA tool running", "A Yosys operation is already running. Please wait for it to finish.")
            return

        output_dir = self.project_dir / "synthesis"
        if schematic_type == "rtl":
            json_path = output_dir / "rtl.json"
            name = "rtl_schematic"
            description = "RTL"
        else:
            json_path = output_dir / "synthesized.json"
            name = "gate_level_schematic"
            description = "gate-level"

        if not json_path.is_file():
            messagebox.showerror(
                f"{description} JSON not found",
                f"Could not find {json_path.name} in the project's synthesis folder. Run synthesis first."
            )
            return

        top_module_path = output_dir / "top_module.txt"
        top = None
        if top_module_path.is_file():
            try:
                top = top_module_path.read_text(encoding="utf-8").strip()
            except OSError:
                top = None
        if not top:
            top = self.find_json_top_module(json_path)
        if not top:
            messagebox.showerror(
                "top module not identified",
                f"EDA2 could not identify a unique top module in {json_path.name}."
            )
            return

        env, tool_dirs, suite_root = self.tool_environment()
        if suite_root is None:
            messagebox.showerror("Yosys not found", "Could not find the OSS CAD Suite under EDA/dependencies.")
            return
        yosys_exe = suite_root / "bin" / "yosys.exe"
        if not yosys_exe.is_file():
            messagebox.showerror("Yosys not found", f"Could not find yosys.exe at {yosys_exe}")
            return
        graphviz_exe = self.find_icarus_executable("dot", tool_dirs)
        if graphviz_exe is None:
            messagebox.showerror("Graphviz not found", "Could not find dot.exe under EDA/dependencies.")
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        schematic_dir = self.project_dir / "schematic"
        schematic_dir.mkdir(parents=True, exist_ok=True)
        dot_path = schematic_dir / f"{name}.dot"
        svg_path = schematic_dir / f"{name}.svg"
        script_path = output_dir / f"{name}.ys"
        json_yosys_path = json_path.resolve().as_posix().replace('"', '\\"')
        script_path.write_text(
            f'read_json "{json_yosys_path}"\n'
            f'hierarchy -check -top {top}\n'
            f'show -format dot -prefix {name} {top}\n',
            encoding="utf-8"
        )

        launcher_path = output_dir / f"run_{name}.cmd"
        environment_bat = suite_root / "environment.bat"
        if os.name == "nt" and environment_bat.is_file():
            launcher_path.write_text(
                "@echo off\r\n"
                f'call "{environment_bat}"\r\n'
                "if errorlevel 1 exit /b %errorlevel%\r\n"
                f'cd /d "{schematic_dir}"\r\n'
                "if errorlevel 1 exit /b %errorlevel%\r\n"
                f'"{yosys_exe}" -s "{script_path}"\r\n'
                "exit /b %errorlevel%\r\n",
                encoding="utf-8"
            )
            yosys_command = ["cmd.exe", "/d", "/c", str(launcher_path)]
        else:
            yosys_command = [str(yosys_exe), "-s", str(script_path)]

        self.yosys_running = True
        self.consoleprint(f"Generating {description} schematic from existing {json_path.name}...\n")
        self.consoleprint(f"Top module: {top}\n")

        def worker():
            try:
                yosys_result = subprocess.run(
                    yosys_command, cwd=schematic_dir, env=env,
                    capture_output=True, text=True
                )
                self.yosys_queue.put(("yosys", yosys_result.stdout, yosys_result.stderr, yosys_result.returncode))
                if yosys_result.returncode != 0:
                    self.yosys_queue.put(("done", False, f"Yosys failed while creating {description} DOT ({yosys_result.returncode})."))
                    return
                if not dot_path.is_file() or dot_path.stat().st_size == 0:
                    self.yosys_queue.put(("done", False, f"Yosys did not create a valid {dot_path.name}."))
                    return
                graphviz_result = subprocess.run(
                    [graphviz_exe, "-Tsvg", str(dot_path), "-o", str(svg_path)],
                    cwd=schematic_dir, env=env, capture_output=True, text=True
                )
                self.yosys_queue.put(("graphviz", graphviz_result.stdout, graphviz_result.stderr, graphviz_result.returncode))
                if graphviz_result.returncode != 0 or not svg_path.is_file() or svg_path.stat().st_size == 0:
                    self.yosys_queue.put(("done", False, f"Graphviz failed to create {svg_path.name}."))
                    return
                self.yosys_queue.put(("done", True, f"{description} schematic created: schematic/{svg_path.name}"))
            except Exception as exc:
                self.yosys_queue.put(("done", False, f"{description} schematic generation error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self.poll_yosys_queue)

    def confirm_verilog(self): pass
    def confirm_floorplan(self): pass
    def confirm_synthesis(self):
        self.run_yosys()
    def confirm_sta(self): pass
    def confirm_klayout(self): pass
if __name__ == "__main__":
    app = eda()
    app.mainloop()
