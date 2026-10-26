# eda

eda is a personal project aimed at bringing most of the stages of the VLSI design workflow into a single desktop application.

The current version provides a python/Tkinter interface for writing verilog RTL and testbenches, compiling and simulating designs with icarus verilog, generating .VCD waveform files, and inspecting simulation results using GTKWave.

## Current Features
- Separate RTL and testbench editors
- Icarus Verilog compilation and simulation
- Console output and error reporting
- Automatic VCD waveform generation
- GTKWave integration
- Save and reopen projects

## Planned Features
- Yosys synthesis and technology mapping
- Sky130 PDK integration
- Static timing analysis
- Floorplanning and physical design
- Layout inspection using KLayout

## Requirements
- Python 3
- Icarus Verilog
- GTKWave

Additional dependencies will be required as further design-flow stages are integrated.

## Status
Early-stage development. Simulation and waveform inspection are working; synthesis and physical-design integration are planned.

This project is intended for learning, experimentation, and gradual development into an integrated open-source EDA workflow.
