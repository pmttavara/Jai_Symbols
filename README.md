# (WIP) Go-to-definition for `.jai` in 10x Editor

**WORK IN PROGRESS.** Inspired by, and adapted from, Raphael Luba's [`jai-ctags`](https://github.com/rluba/jai-ctags).

## Installation and usage

- Put `Jai_Symbols.jai` in your modules folder.
- In your project's metaprogram, call `add()` for `.TYPECHECKED` messages. Once the build is done, call `write(*symbols, ".build/.jai_symbols")`. The Python extension only searches for `.build/.jai_symbols`.
- Put `JaiGotoDefinition.py` in `%AppData%/10x/PythonScripts`.
- In the 10x menu bar > `Settings` > `Key Bindings...`, replace your key binding for `GotoSymbolDefinition` with `JAI_GotoNextSymbolDefinition`.
- (Optional) In the 10x menu bar > `Settings` > `Key Bindings...`, add a new key binding for `JAI_GotoPrevSymbolDefinition` (e.g., Alt-Shift-G to complement Alt-G).
- (Optional) put `jai_symbols.10x_syntax` in `%AppData%/10x/Settings/SyntaxHighlighting`.

## Necessary improvements

- Member resolution: in the Python extension, parse `a.b.c.d` and recursively narrow the candidates list
    - determine the possible types of `a` from the search results: `T1`, `T2`, etc.
    - when searching the possible declarations of `b`, prune those candidates that are not children of `T1`, `T2`, etc.
    - recursively repeat this process for all possible declarations of `c`, `d`, etc.
    - if this does not resolve to a single declaration, then fall back to the regular cycling behaviour, to avoid making the command stateful

## Example metaprogram
```jai
#import "Compiler";

Jai_Symbols :: #import "Jai_Symbols";

build :: () {
    set_build_options_dc(.{do_output = false, write_added_strings = false});

    w := compiler_create_workspace();
    options := get_build_options(w);

    options.write_added_strings = false;
    options.text_output_flags = 0;

    options.output_executable_name = "main";
    options.output_path = ".";
    set_build_options(options, w);

    compiler_begin_intercept(w);

    add_build_file("main.jai", w);

    jai_symbols: Jai_Symbols.Symbols;
    while true {
        message := compiler_wait_for_message();
        if message.kind == {
          case .TYPECHECKED;
            Jai_Symbols.add(*jai_symbols, cast(*Message_Typechecked, message));

          case .COMPLETE;
            break;
        }
    }

    if jai_symbols.count { Jai_Symbols.write(*jai_symbols, ".build/.jai_symbols"); }
}

#run build();
```

## Potential improvements

- Advanced scope awareness
    - Compute and output the declaration/liveness scopes for definitions and match against those in the extension
    - Compute and output block-comment/line-comment ranges so the extension ignores those during textual search
        - Alternative: Lex files before searching them (difficult due to code that may not compile)

