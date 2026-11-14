/* RISC-V GCC 链接脚本（可选）。入口 _start，全部放进 8 KB RAM。
 * mini_asm 不用本文件：它按出现顺序从地址 0 往下排。
 *
 * [给你看的对照] 刚学 Python 的话：
 *   链接脚本告诉 GCC「代码放哪、栈在哪」。mini_asm.py 自己从地址 0 往下排，不读本文件。
 *   ENTRY(_start)     程序从名叫 _start 的标签开始，≈ if __name__ == "__main__"
 *   ORIGIN / LENGTH   RAM 从 0 开始、长 8K，和 socmap.py 的 RAM_BASE / RAM_BYTES 一致
 */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    ram (rwx) : ORIGIN = 0x00000000, LENGTH = 8K
}

SECTIONS
{
    .text : {
        *(.text.start)     /* 若把复位向量单独成节，保证最先 */
        *(.text*)
    } > ram

    .rodata : { *(.rodata*) } > ram
    .data : { *(.data*) } > ram
    .bss : { *(.bss*) *(COMMON) } > ram

    _end = .;
    PROVIDE(_sp = 0x2000); /* 与 STACK_TOP 一致 */
}
