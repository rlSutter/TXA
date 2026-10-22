"""txc - the TXA cross-compiler (Python), the reference the TI workbench matches.

Modules: lexer (source text to tokens), parser (tokens to an AST), ast (the
node classes), sema (meaning: symbols, objects, actions, the grammar
tables, every check), codegen (bytecode, then link: the story image),
opcodes (the VM's instruction set and the image's header: the one
definition), dump (the canonical text forms the workbench's tests compare),
txvm (the reference VM).  compile_file(path, libpath, title, release,
date) in codegen goes from a source file to a story image.
"""
