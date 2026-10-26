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
# -> rev 0 -> 1 contained a simple gui with no working buttons or any functionality
# -> rev 1.1 is the same gui with minimal changes, but now integrates icarus verilog compiler
# -> rev 1.2 added gtk wave but messed up the file saving logic where it wants me to save the program when clicking run
#    reverted this part back to the original rev 1.1, added a new automatic waveform generation support without requiring
#    me to save the file itself
# -> rev 1.3 added the feature to open the latest waveform directly when i click gtk wave, and also lets me select another
#    .vcd waveform file if the generated waveform is not the one i want to see, also added a check for the presence of gtkwave in the system path

import json, re, subprocess, tempfile, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


title = "integrated vlsi platform rev1.3 (27/10/2026)"
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
        self.waveform_path = self.default_waveform_path()
        self.gtkwave_path = None
        self.projectpage()

    def default_waveform_path(self):
        # Keep generated waveforms beside the EDA2 script unless a project is saved.
        return Path(__file__).resolve().parent / "waveform.vcd"

    def delete(self):
        for child in self.winfo_children():
            child.destroy()
        self.OC = None

    def projectpage(self):
        self.delete()
        box = tk.Frame(self, padx=32, pady=32)
        box.pack(fill="both", expand=True)
        tk.Label(box, text="integrated vlsi platform rev1.3 (27/10/2026)", font=(arial, 20)).pack(pady=(90, 8))
        tk.Label(box, text="rev1.3-> verilog + self written code for gui", font=(arial, 16)).pack(pady=(0, 32))
        tk.Button(box, text="new project", font=(arial, 14), width=24, height=3, command=self.newproject).pack(pady=5)
        tk.Button(box, text="open existing project", font=(arial, 14), width=24, height=3, command=self.openexistingproject).pack(pady=5)

    def newproject(self):
        self.PP = None
        self.waveform_path = self.default_waveform_path()
        self.showeditor(var1, var2)

    def openexistingproject(self):
        filepath = filedialog.askopenfilename(title="open project", filetypes=[("integrated vlsi platform rev1.3 (27/10/2026)", f"*{filetype}"), ("JSON Files", "*.json"), ("All Files", "*.*")])
        if not filepath:
            return
        try:
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            vcode, tbcode = data.get("verilog", ""), data.get("testbench", "")
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("open failed", f"error code {e}")
            return
        self.PP = Path(filepath)
        self.waveform_path = self.PP.parent / "waveform.vcd"
        self.showeditor(vcode, tbcode)
        self.consoleprint(f"opened {filepath}\n")

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

    def saveproject(self):
        if self.PP is None:
            filepath = filedialog.asksaveasfilename(title="save project", defaultextension=filetype, filetypes=[("integrated vlsi platform rev1.3 (27/10/2026)", f"*{filetype}"), ("JSON Files", "*.json"), ("All Files", "*.*")])
            if not filepath:
                return
            self.PP = Path(filepath)
            self.waveform_path = self.PP.parent / "waveform.vcd"
        try:
            self.PP.write_text(json.dumps({"version": 1.3, "verilog": self.verilog_editor.get("1.0", "end-1c"), "testbench": self.testbench_editor.get("1.0", "end-1c")}, indent=2), encoding="utf-8")
        except OSError as e:
            messagebox.showerror("save failed", f"error code {e}")
            return
        self.consoleprint(f"saved {self.PP}\n")

    def runproject(self):
        self.consoleprint("compiling verilog\n")

        try:
            with tempfile.TemporaryDirectory(prefix="eda2_") as tempdir:
                temppath = Path(tempdir)
                verilogpath = temppath / "design.v"
                testbenchpath = temppath / "testbench.v"
                outputpath = temppath / "output.vvp"

                vcode = self.verilog_editor.get("1.0", "end-1c")
                tbcode = self.testbench_editor.get("1.0", "end-1c")

                self.waveform_path.parent.mkdir(parents=True, exist_ok=True)
                self.waveform_path.unlink(missing_ok=True)

                # Ensure the testbench writes its VCD directly to the persistent waveform path.
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

                verilogpath.write_text(vcode, encoding="utf-8")
                testbenchpath.write_text(tbcode, encoding="utf-8")

                compileresult = self.commandrun(
                    ["iverilog", "-g2012", "-o", str(outputpath), str(testbenchpath), str(verilogpath)],
                    cwd=temppath
                )

                if compileresult is None or compileresult.returncode != 0:
                    self.consoleprint("compilation failed\n")
                    if compileresult is not None:
                        self.processoutput(compileresult)
                    return

                self.consoleprint("compilation successful, running simulation\n")
                simresult = self.commandrun(["vvp", str(outputpath)], cwd=temppath)

                if simresult is None:
                    return

                self.processoutput(simresult)
                if self.waveform_path.is_file():
                    self.consoleprint(f"waveform generated: {self.waveform_path}\n")
                else:
                    self.consoleprint("simulation did not generate a waveform file; check the testbench\n")

                self.consoleprint("simulation successful\n" if simresult.returncode == 0 else "simulation failed\n")

        except OSError as e:
            self.consoleprint(f"simulation error: {e}\n")

    def commandrun(self, command, cwd=None):
        try:
            return subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        except FileNotFoundError:
            self.consoleprint(f"could not find {command[0]}, make sure it is installed and added to PATH\n")
            return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="")
        except OSError as e:
            self.consoleprint(f"could not execute {command[0]}: {e}\n")
            return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="")

    def open_waveform(self):
        #use the latest generated waveform by default; allow selecting another vcd file if needed
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

        command = [str(self.gtkwave_path), str(waveform)] if self.gtkwave_path else ["gtkwave", str(waveform)]
        try:
            subprocess.Popen(command)
            self.consoleprint(f"opened waveform {waveform}\n")
        except FileNotFoundError:
            messagebox.showinfo(
                "gtkwave executable not found",
                "could not find GTKWave on PATH. select gtkwave.exe in the dialog."
            )
            executable = filedialog.askopenfilename(
                title="locate gtkwave.exe",
                filetypes=[("GTKWave executable", "gtkwave.exe"), ("Executable files", "*.exe"), ("All Files", "*.*")]
            )
            if not executable:
                self.consoleprint("gtkwave executable was not selected\n")
                return
            self.gtkwave_path = Path(executable)
            try:
                subprocess.Popen([str(self.gtkwave_path), str(waveform)])
                self.consoleprint(f"opened waveform {waveform}\n")
            except OSError as e:
                messagebox.showerror("gtkwave launch failed", str(e))
        except OSError as e:
            messagebox.showerror("gtkwave launch failed", str(e))

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
        if messagebox.askyesno("return home", "return to start page? unsaved changes will be lost if not saved"):
            self.projectpage()

    def confirm_verilog(self): pass
    def confirm_floorplan(self): pass
    def confirm_synthesis(self): pass
    def confirm_yosys(self): pass
    def confirm_sta(self): pass
    def confirm_klayout(self): pass

if __name__ == "__main__":
    app = eda()
    app.mainloop()
