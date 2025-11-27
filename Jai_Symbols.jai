#import "File";
#import "Basic";
#import "String";
#import "Compiler";
#import "IntroSort";

Symbol :: struct {
    name: string;
    type: string;
    parent: string;
    filename: string;
    line: int;
    column: int;
}

Symbols :: [..] Symbol;

// Types with no definition in Preload.jai.
PRELOAD_BUILTINS :: string.[
    "Any",
    "CPU",
    "Code",
    "IS_CROSS_COMPILING",
    "MACHINE_OPTIONS_SIZE",
    "OS",
    "TEMPORARY_STORAGE_SIZE",
    "Type",
    "bool",
    "float",
    "float32",
    "float64",
    "int",
    "s16",
    "s32",
    "s64",
    "s8",
    "string",
    "u16",
    "u32",
    "u64",
    "u8",
    "v128",
    "void",
];

EMPTY_NAME :: "-";

add_symbol :: (symbols: *Symbols, name: string, type: string, parent: string, filename: string, line: int, column: int) {
    if !filename {
        return;
    }
    // if ends_with(filename, "Preload.jai") {
    //     return;
    // }
    if line == 0 || column == 0 {
        return;
    }
    if !name {
        return;
    }
    if !is_alpha(name[0]) {
        return;
    }

    symbol := Symbol.{ name, type, parent, filename, line, column };
    // print("Adding symbol: %\n", symbol);

    array_add(symbols, symbol);
}

try_type_name :: (decl: *Code_Declaration) -> string {
    result := EMPTY_NAME;
    if decl && decl.type_inst {
        inst := decl.type_inst;

        // Chase pointers and #type directives.
        // Slightly wrong, because pointers should only be 1 level chased.
        while inst.pointer_to || inst.type_directive_target {
            if inst.pointer_to {
                inst = inst.pointer_to;
            }
            if inst.type_directive_target {
                inst = inst.type_directive_target;
            }
        }

        if inst.type_valued_expression {
            expr := inst.type_valued_expression;
            if expr.kind == .IDENT {
                ident := cast(*Code_Ident, expr);
                builtin := false;
                for PRELOAD_BUILTINS {
                    if it == ident.name {
                        builtin = true;
                        break;
                    }
                }
                if !builtin && !(ident.flags & .DEFINES_POLYMORPH_VARIABLE) {
                    result = ident.name;
                }
            }
        }
    }
    return result;
}

add_block :: (symbols: *Symbols, block: *Code_Block, parent := EMPTY_NAME) {
    for block.members {
        assert(it.kind == .DECLARATION);
        child := cast(*Code_Declaration, it);
        add_declaration(symbols, child, parent);
    }
    for block.statements {
        if it.kind == .BLOCK {
            child := cast(*Code_Block, it);
            add_block(symbols, child, parent);
        }
    }
}

add_declaration :: (symbols: *Symbols, decl: *Code_Declaration, parent := EMPTY_NAME) {
    if decl.flags & .IS_IMPORTED return; // Do not process duplicates for import links.

    // @ToDo: What are declarations with no name?
    if decl.name {
        name := decl.name;
        type := try_type_name(decl);
        filename := get_filename(decl);
        line := decl.l0;
        column := decl.c0;
        add_symbol(symbols, name, type, parent, filename, line, column);
    } else {
        // print("Found declaration wihout a name: %\n", <<decl);
        // return;
    }

    // assert(path_extension(filename).count > 0, "No path extension: %", filename);

    // print("Found declaration % in %\n", decl.name, filename);

    child_parent := ifx decl.name then decl.name else parent;

    if decl.expression {
        if decl.expression.kind == {
          case .STRUCT;
            struct_decl := cast(*Code_Struct, decl.expression);
            // print("Struct members:\n");
            if struct_decl.block {
                for struct_decl.block.members {
                    // print("Member: %\n", it.name);
                    assert(it.kind == .DECLARATION);
                    child := cast(*Code_Declaration, it);
                    add_declaration(symbols, child, child_parent);
                }
            }
            if struct_decl.constants_block {
                for struct_decl.constants_block.members {
                    // print("Constant member: %\n", it.name);
                    assert(it.kind == .DECLARATION);
                    child := cast(*Code_Declaration, it);
                    add_declaration(symbols, child, child_parent);
                }
            }
          case .ENUM;
            enum_decl := cast(*Code_Enum, decl.expression);
            // print("Enum members:\n");
            if enum_decl.block {
                for enum_decl.block.members {
                    // print("Member: %\n", it.name);
                    assert(it.kind == .DECLARATION);
                    child := cast(*Code_Declaration, it);
                    add_declaration(symbols, child, child_parent);
                }
            }
          case .PROCEDURE_HEADER;
            header_decl := cast(*Code_Procedure_Header, decl.expression);
            for header_decl.arguments {
                assert(it.kind == .DECLARATION);
                child := cast(*Code_Declaration, it);
                add_declaration(symbols, child, child_parent);
            }
          case .PROCEDURE_BODY;
            body_decl := cast(*Code_Procedure_Body, decl.expression);
            add_block(symbols, body_decl.block, child_parent);
          case;
            // print("Found other kind: %\n", decl.expression.kind);
        }
    } else {
        // print("No expression: %\n", <<decl);
    }
}

#scope_module
add :: (symbols: *Symbols, message: *Message_Typechecked) {
    for typechecked: message.declarations {
        decl := typechecked.expression;
        add_declaration(symbols, decl);
    }

    for typechecked: message.procedure_bodies {
        decl := typechecked.expression;
        add_block(symbols, decl.block, decl.header.name);
    }
}

write :: (symbols: *Symbols, filename: string) {
    sb: String_Builder;

    intro_sort(symbols.*, (a: Symbol, b: Symbol) -> int {
        result             := compare(a.name,     b.name);
        if !result { result = compare(a.filename, b.filename); }
        if !result { result = a.line - b.line; }
        if !result { result = a.column - b.column; }
        if !result { result = compare(a.parent, b.parent); }
        return result;
    });

    print_to_builder(*sb, "# .jai_symbols file. Autogenerated; edits will be ephemeral.\n");
    print_to_builder(*sb, "# .jai_symbols format:\n");
    print_to_builder(*sb, "#\n");
    print_to_builder(*sb, "# <name> <type> <parent> \"<file path>\" <line> <column>\n");
    print_to_builder(*sb, "#\n");
    print_to_builder(*sb, "# A hyphen (-) means empty. This applies when there is no parent or no non-builtin printable type.\n");
    print_to_builder(*sb, "\n");

    duplicates := 0;

    prev_symbol := Symbol.{};
    for symbols.* {
        if prev_symbol == it {
            duplicates += 1;
            continue;
        }

        print_to_builder(*sb,
                         "% % % \"%\" % %\n",
                         it.name,
                         it.type,
                         it.parent,
                         it.filename,
                         it.line,
                         it.column);
        prev_symbol = it;
    }

    if duplicates > 1 {
        // print("Jai_Symbols Warning: Generated % duplicates.\n", duplicates);
    }

    str := builder_to_string(*sb);
    write_entire_file(filename, str);
}

#scope_module
operator == :: (a: Symbol, b: Symbol) -> bool {
    result := true;
    result &&= a.name     == b.name;
    result &&= a.parent   == b.parent;
    result &&= a.filename == b.filename;
    result &&= a.line     == b.line;
    result &&= a.column   == b.column;
    return result;
}
