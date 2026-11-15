# 可选：有 RISC-V GCC 时把 C 固件编成 hex。
# 默认工作流不依赖本 Makefile，请用：
#   python fw/python/mini_asm.py fw/asm/e2e_mvm.S
#
# 若 mret/csrw 报未知指令，确认工具链支持 zicsr；本文件已用 rv32i_zicsr。
#
# [给你看的对照] 刚学 Python 的话：
#   这是「有交叉编译器才用」的配方。日常请走 mini_asm.py，不必装 GCC。
#   PREFIX ?= ...   默认参数；CC = $(PREFIX)gcc 是字符串拼接，得到 riscv32-unknown-elf-gcc

PREFIX ?= riscv32-unknown-elf-
CC      = $(PREFIX)gcc
OBJCOPY = $(PREFIX)objcopy
CFLAGS  = -march=rv32i_zicsr -mabi=ilp32 -Os -nostdlib -ffreestanding -Iinclude
LDFLAGS = -T linker/link.ld -nostdlib -Wl,-e,_start

all: ../fw/hex/e2e_from_c.hex

../fw/hex/e2e_from_c.hex: src/start.S src/main.c
	$(CC) $(CFLAGS) $(LDFLAGS) src/start.S src/main.c -o /tmp/e2e.elf
	$(OBJCOPY) -O verilog /tmp/e2e.elf $@

.PHONY: all
