 `timescale 1ns / 1ps

module test_v (
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [1:0] mode,
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output reg valid,
    output reg [3:0] state,
    output reg [7:0] accumulator,
    output reg [3:0] counter,
    output reg overflow
);

    reg [7:0] registers [0:3];
    reg [7:0] alu_a, alu_b;
    reg [8:0] alu_result;
    reg [7:0] memory [0:15];
    reg [3:0] address;
    integer i;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state       <= 0;
            data_out    <= 0;
            valid       <= 0;
            accumulator <= 0;
            counter     <= 0;
            overflow    <= 0;
            address     <= 0;
            alu_a       <= 0;
            alu_b       <= 0;
            alu_result  <= 0;

            for (i = 0; i < 4; i = i + 1)
                registers[i] <= 0;

            for (i = 0; i < 16; i = i + 1)
                memory[i] <= 0;
        end else begin
            valid <= 0;

            if (enable) begin
                case (state)
                    0: begin
                        alu_a <= data_in;
                        alu_b <= registers[counter[1:0]];
                        state <= 1;
                    end

                    1: begin
                        case (mode)
                            0: alu_result <= {1'b0, alu_a} + {1'b0, alu_b};
                            1: alu_result <= {1'b0, alu_a} - {1'b0, alu_b};
                            2: alu_result <= {1'b0, alu_a ^ alu_b};
                            3: alu_result <= {1'b0, alu_a} << 1;
                        endcase
                        state <= 2;
                    end

                    2: begin
                        accumulator <= alu_result[7:0];
                        overflow <= alu_result[8];
                        registers[counter[1:0]] <= alu_result[7:0];
                        address <= counter;
                        state <= 3;
                    end

                    3: begin
                        memory[address] <= accumulator;
                        data_out <= memory[address];
                        valid <= 1;
                        counter <= counter + 1'b1;
                        state <= 0;
                    end

                    default: state <= 0;
                endcase
            end
        end
    end

endmodule
