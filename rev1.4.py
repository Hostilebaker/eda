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
import json, os, re, shutil, subprocess, tempfile, tkinter as tk, zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
title = "integrated asic platform rev1.4 (12/11/2026)"
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
        if self.project_dir is None or self.verilog_editor is None or self.testbench_editor is None:
            return
        verilog_dir = self.project_dir / "verilog"
        verilog_dir.mkdir(parents=True, exist_ok=True)
        (verilog_dir / "design.v").write_text(self.verilog_editor.get("1.0", "end-1c"), encoding="utf-8")
        (verilog_dir / "testbench.v").write_text(self.testbench_editor.get("1.0", "end-1c"), encoding="utf-8")

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
                except OSError as e:
                    messagebox.showerror("save failed", str(e))
                    return
        self.destroy()
    def delete(self):
        for child in self.winfo_children():
            child.destroy()
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
                self.pack_project()
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
                self.pack_project()
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as e:
            self.project_dir = None
            self.PP = None
            messagebox.showerror("open failed", f"Could not open EDA2 project: {e}")
            return
        self.waveform_path = self.default_waveform_path()
        self.showeditor(vcode, tbcode)
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
        for text, command in [("verilog", self.confirm_verilog), ("synthesis", self.confirm_synthesis), ("floorplan", self.confirm_floorplan), ("yosys", self.confirm_yosys), ("STA", self.confirm_sta), ("klayout", self.confirm_klayout), ("GTKWave", self.open_waveform)]:
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
        """Find the OSS CAD Suite root without relying on the process PATH."""
        app_dir = Path(__file__).resolve().parent
        desktop = Path.home() / "Desktop"
        search_roots = [
            self.dependencies_dir / "yosys",
            self.dependencies_dir,
            app_dir / "yosys",
            desktop / "eda2 dependencies" / "yosys",
            desktop / "yosys",
        ]
        for root in search_roots:
            if (root / "bin" / "yosys.exe").is_file():
                return root
            if root.is_dir():
                for candidate in root.glob("oss-cad-suite*/oss-cad-suite"):
                    if (candidate / "bin" / "yosys.exe").is_file():
                        return candidate
                # Also support a directly extracted suite folder.
                for candidate in root.glob("oss-cad-suite*"):
                    if (candidate / "bin" / "yosys.exe").is_file():
                        return candidate
        return None

    def tool_environment(self):
        """Return a child-process environment with EDA2's bundled tools on PATH."""
        env = os.environ.copy()
        app_dir = Path(__file__).resolve().parent
        desktop = Path.home() / "Desktop"
        tool_dirs = []

        # Standalone Icarus installation used on this machine.
        # The actual path is: Desktop\eda2dependencies\icarus\iverilog\bin
        icarus_bases = (
            self.dependencies_dir / "icarus",
            self.dependencies_dir / "iverilog",
            self.dependencies_dir / "icarus" / "iverilog",
            app_dir / "icarus",
            desktop / "eda2dependencies" / "icarus" / "iverilog",
            desktop / "eda2 dependencies" / "icarus" / "iverilog",
            desktop / "eda2 dependencies" / "icarus",
        )
        for base in icarus_bases:
            for candidate in (base / "bin", base):
                if candidate.is_dir():
                    tool_dirs.append(candidate)

        suite = self.find_oss_cad_suite()
        if suite is not None:
            self.oss_cad_suite = suite
            for candidate in (suite / "bin", suite / "lib", suite / "mingw64" / "bin", suite):
                if candidate.is_dir():
                    tool_dirs.append(candidate)

        # Remove duplicates while preserving order. Windows PATH entries with
        # spaces are valid as-is; quoting PATH entries would be incorrect.
        unique_dirs = []
        seen = set()
        for directory in tool_dirs:
            value = str(directory.resolve())
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
        except OSError as e:
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
    def find_graphviz_executable(self):
        """Find Graphviz dot.exe in EDA2 dependencies or on PATH."""
        executable_name = "dot.exe" if os.name == "nt" else "dot"
        if self.dependencies_dir.is_dir():
            for current_root, _, filenames in os.walk(self.dependencies_dir):
                for filename in filenames:
                    if filename.casefold() == executable_name.casefold():
                        candidate = Path(current_root) / filename
                        if candidate.is_file():
                            return candidate
        located = shutil.which(executable_name)
        return Path(located) if located else None

    def run_yosys(self):
        if self.project_dir is None:
            messagebox.showwarning("no project", "Create or open an EDA2 project first.")
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
        top = simpledialog.askstring(
            "Top module", prompt, initialvalue=default_top, parent=self
        )
        if top is None:
            self.consoleprint("Yosys synthesis cancelled.\n")
            return
        top = top.strip()
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", top):
            messagebox.showerror("invalid top module", "Enter a valid Verilog module identifier.")
            return
        if not re.search(
            r"\bmodule\s+(?:automatic\s+|static\s+)?" + re.escape(top) + r"\b",
            vcode
        ):
            messagebox.showerror("module not found", f'The RTL does not declare a module named "{top}".')
            return

        env, tool_dirs, suite_root = self.tool_environment()
        if suite_root is None:
            selected = filedialog.askopenfilename(
                title="Locate yosys.exe",
                initialdir=str(self.dependencies_dir),
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

        dot_exe = self.find_graphviz_executable()
        if dot_exe is None:
            selected = filedialog.askopenfilename(
                title="Locate Graphviz dot.exe",
                initialdir=str(self.dependencies_dir),
                filetypes=[("Graphviz dot executable", "dot.exe"), ("Executable files", "*.exe"), ("All files", "*.*")]
            )
            if not selected:
                self.consoleprint("Synthesis cancelled: Graphviz dot.exe was not selected.\n")
                return
            dot_exe = Path(selected).resolve()
            if dot_exe.name.casefold() not in ("dot.exe", "dot"):
                messagebox.showerror("invalid Graphviz executable", "Select Graphviz dot.exe, not another executable.")
                return

        self.sync_editors_to_project()
        source_path = self.project_dir / "verilog" / "design.v"
        output_dir = self.project_dir / "synthesis"
        schematic_dir = self.project_dir / "schematic"
        output_dir.mkdir(parents=True, exist_ok=True)
        schematic_dir.mkdir(parents=True, exist_ok=True)

        netlist_path = output_dir / "synthesized.v"
        script_path = output_dir / "run_synthesis.ys"
        dot_path = schematic_dir / "schematic.dot"
        svg_path = schematic_dir / "schematic.svg"

        # Yosys accepts forward-slash paths on Windows. Keep the generated
        # script in the project so the exact synthesis flow can be inspected.
        def yosys_path(path):
            return path.resolve().as_posix().replace('"', '\\"')

        yosys_script = (
            f'read_verilog "{yosys_path(source_path)}"\n'
            f'hierarchy -check -top {top}\n'
            f'synth -top {top}\n'
            'stat\n'
            f'write_verilog -noattr "{yosys_path(netlist_path)}"\n'
            f'show -format dot -prefix "{yosys_path(dot_path.with_suffix(""))}" {top}\n'
        )
        try:
            script_path.write_text(yosys_script, encoding="utf-8")
            self.consoleprint(f"Starting generic Yosys synthesis for top module: {top}\n")
            self.consoleprint(f"Yosys script: {script_path}\n")

            environment_bat = suite_root / "environment.bat"
            if os.name == "nt" and environment_bat.is_file():
                # Run the suite environment setup and Yosys from a generated
                # .cmd wrapper. This avoids cmd.exe /s /c quote parsing issues
                # when the EDA installation path contains spaces.
                launcher_path = output_dir / "run_yosys.cmd"
                launcher_path.write_text(
                    "@echo off\r\n"
                    f'call "{environment_bat}"\r\n'
                    "if errorlevel 1 exit /b %errorlevel%\r\n"
                    f'"{yosys_exe}" -s "{script_path}"\r\n'
                    "exit /b %errorlevel%\r\n",
                    encoding="utf-8"
                )
                result = subprocess.run(
                    ["cmd.exe", "/d", "/c", str(launcher_path)],
                    cwd=self.project_dir, env=env,
                    capture_output=True, text=True
                )
            else:
                # Non-Windows fallback, or a suite installation without environment.bat.
                result = subprocess.run(
                    [str(yosys_exe), "-s", str(script_path)],
                    cwd=self.project_dir, env=env,
                    capture_output=True, text=True
                )
            self.processoutput(result)
            if result.returncode != 0:
                self.consoleprint(f"Yosys synthesis failed (exit code {result.returncode}).\n")
                return
            if not netlist_path.is_file():
                self.consoleprint("Yosys exited successfully but did not create synthesized.v.\n")
                return
            if not dot_path.is_file():
                self.consoleprint("Yosys created the netlist but did not create schematic.dot.\n")
                return

            self.consoleprint("Yosys synthesis successful. Netlist saved: synthesis/synthesized.v\n")
            self.consoleprint("Schematic DOT saved: schematic/schematic.dot\n")
            dot_result = subprocess.run(
                [str(dot_exe), "-Tsvg", str(dot_path), "-o", str(svg_path)],
                cwd=schematic_dir, env=env,
                capture_output=True, text=True
            )
            self.processoutput(dot_result)
            if dot_result.returncode != 0 or not svg_path.is_file():
                self.consoleprint(f"Graphviz conversion failed (exit code {dot_result.returncode}).\n")
                return

            self.consoleprint("Graphviz conversion successful. SVG saved: schematic/schematic.svg\n")
            self.pack_project()
        except OSError as e:
            self.consoleprint(f"could not run Yosys/Graphviz: {e}\n")

    def confirm_verilog(self): pass
    def confirm_floorplan(self): pass
    def confirm_synthesis(self):
        self.run_yosys()
    def confirm_yosys(self):
        self.run_yosys()
    def confirm_sta(self): pass
    def confirm_klayout(self): pass
if __name__ == "__main__":
    app = eda()
    app.mainloop()
