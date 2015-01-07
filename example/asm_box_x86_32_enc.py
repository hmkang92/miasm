#! /usr/bin/env python
from pdb import pm

from elfesteem import pe_init

from miasm2.core import asmbloc
from miasm2.core.cpu import parse_ast
from miasm2.arch.x86.arch import mn_x86, base_expr
from miasm2.core import parse_asm
import miasm2.expression.expression as m2_expr

pe = pe_init.PE()
s_text = pe.SHList.add_section(name="text", addr=0x1000, rawsize=0x1000)
s_iat = pe.SHList.add_section(name="iat", rawsize=0x100)
new_dll = [({"name": "USER32.dll",
             "firstthunk": s_iat.addr}, ["MessageBoxA"])]
pe.DirImport.add_dlldesc(new_dll)
s_myimp = pe.SHList.add_section(name="myimp", rawsize=len(pe.DirImport))
pe.DirImport.set_rva(s_myimp.addr)

reg_and_id = dict(mn_x86.regs.all_regs_ids_byname)


def my_ast_int2expr(a):
    return m2_expr.ExprInt32(a)


def my_ast_id2expr(t):
    return reg_and_id.get(t, m2_expr.ExprId(t, size=32))

my_var_parser = parse_ast(my_ast_id2expr, my_ast_int2expr)
base_expr.setParseAction(my_var_parser)

blocs, symbol_pool = parse_asm.parse_txt(mn_x86, 32, '''
main:
    CALL cipher_code
    CALL msgbox_encrypted_start
    CALL cipher_code
    RET

cipher_code:
    PUSH EBP
    MOV  EBP, ESP

    LEA  ESI, DWORD PTR [msgbox_encrypted_start]
    LEA  EDI, DWORD PTR [msgbox_encrypted_stop]

loop:
    XOR  BYTE PTR [ESI], 0x42
    INC  ESI
    CMP  ESI, EDI
    JBE  loop

    MOV  ESP, EBP
    POP  EBP
    RET

msgbox_encrypted_start:
    PUSH 0
    PUSH title
    PUSH msg
    PUSH 0
    CALL DWORD PTR [ MessageBoxA ]
    RET
.dontsplit
msgbox_encrypted_stop:
.long 0

title:
.string "Hello!"
msg:
.string "World!"
''')


# fix shellcode addr
symbol_pool.set_offset(symbol_pool.getby_name("main"), pe.rva2virt(s_text.addr))
symbol_pool.set_offset(symbol_pool.getby_name_create(
    "MessageBoxA"), pe.DirImport.get_funcvirt('MessageBoxA'))
pe.Opthdr.AddressOfEntryPoint = s_text.addr

for b in blocs[0]:
    print b

print "symbols"
print symbol_pool

resolved_b, patches = asmbloc.asm_resolve_final(
    mn_x86, blocs[0], symbol_pool)
print patches

ad_start = symbol_pool.getby_name_create("msgbox_encrypted_start").offset
ad_stop = symbol_pool.getby_name_create("msgbox_encrypted_stop").offset

# cipher code
new_patches = dict(patches)
for ad, val in patches.items():
    if ad_start <= ad < ad_stop:
        new_patches[ad] = "".join([chr(ord(x) ^ 0x42) for x in val])

for offset, raw in new_patches.items():
    pe.virt[offset] = raw

open('box_x86_32_enc.bin', 'wb').write(str(pe))
