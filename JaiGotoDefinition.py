import N10X
import os
import re
from functools import cmp_to_key

import time
import sys

print_perf = False

def compare_results(a, b):
    if a["filename"] != b["filename"]: return -1 if a["filename"] < b["filename"] else 1 # file
    if a["pos"][1]   != b["pos"][1]:   return       a["pos"][1]   - b["pos"][1]          # Y (line)
    if a["pos"][0]   != b["pos"][0]:   return       a["pos"][0]   - b["pos"][0]          # X (column)
    if a["parent"]   != b["parent"]:   return -1 if a["parent"]   < b["parent"]   else 1 # parent
    if a["type"]     != b["type"]:     return -1 if a["type"]     < b["type"]     else 1 # type
    if a["kind"]     != b["kind"]:     return -1 if a["kind"]     < b["kind"]     else 1 # kind

    return 0

def get_word(line: str, index: int):
    begin = time.perf_counter()

    if index >= len(line):
       index = len(line)

    if index < 0:
       index = 0

    start = end = index

    # @Todo: This lexing is pretty hacky. Is there a way to simplify it?
    if line[:start].strip().endswith("\\"):
        while start > 0 and (line[start - 1] == '\\' or line[start - 1] == ' '):
            start -= 1
        while end < len(line) and (line[end] == '\\' or line[end] == ' '):
            end += 1

    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_' or line[start - 1] == '\\'):
        start -= 1
        seeker = start - 1
        while seeker > 0 and line[seeker - 1] == ' ':
            seeker -= 1
        if seeker > 0 and line[seeker - 1] == '\\':
            start = seeker

    while end < len(line) and (line[end].isalnum() or line[end] == '_' or line[end] == '\\'):
        if end < len(line) and line[end] == '\\':
            end += 1
            while end < len(line) and (line[end].isalnum() or line[end] == ' '):
                end += 1
        else:
            end += 1

    slice = line[start:end]
    slice = "".join([part.strip() for part in slice.split('\\')]);
    # N10X.Editor.LogTo10XOutput(f"Word is {slice}!\n")

    end = time.perf_counter()
    if print_perf: N10X.Editor.LogTo10XOutput(f"{sys._getframe().f_code.co_name}: {int((end - begin) * 1000000)} us\n") # @Perf

    return slice

def jai_decl_regex(varname: str):
    interspersed = r"".join(re.escape(ch) + r"(\\ *)*" for ch in varname)
    result = re.compile(rf"(?<![A-Za-z0-9_])({interspersed}) *:")

    return result

def JAI_GotoSymbolDefinition(dir: int):
    begin = time.perf_counter()

    line = N10X.Editor.GetCurrentLine()
    current_file = N10X.Editor.GetCurrentFilename()
    current_pos = N10X.Editor.GetCursorPos()
    word = get_word(line, current_pos[0])

    search_results = [] # textual search results
    symbol_results = [] # Jai_Symbols.jai module's symbol results
    all_results    = [] # combined unique results

    files_to_search = {} # all unique files in either the workspace or the Jai_Symbols.jai symbol results

    loc_to_symbol = {} # maps locations to symbols, so textual search can disconfirm stale symbol results

    symbols_path = ""
    if len(word) != 0:
        open_filename = N10X.Editor.GetCurrentFilename()
        if open_filename != "":
            files_to_search[open_filename] = open_filename

        for filename in N10X.Editor.GetWorkspaceFiles():
            if symbols_path == "":
                filedir = os.path.dirname(filename)
                possible_symbols_path = filedir + "/.build/.jai_symbols"
                if os.path.isfile(possible_symbols_path):
                    symbols_path = possible_symbols_path
                    # N10X.Editor.LogTo10XOutput(f"Found symbols at {symbols_path}!\n")

            if filename.endswith(".jai"):
                files_to_search[filename] = filename

    if len(symbols_path) != 0:
        try:
            with open(symbols_path, 'r', encoding='utf-8') as file:
                for line_number, line in enumerate(file, start=1):
                    if line.startswith(word) and len(line) > len(word) and line[len(word)] == ' ':
                        quotation_split_line = line.split('"')

                        decl    = quotation_split_line[0].strip().split(' ')
                        pos_str = quotation_split_line[2].strip().split(' ')

                        filename = quotation_split_line[1]
                        pos = (int(pos_str[1]) - 1, int(pos_str[0]) - 1)
                        loc = (filename, pos)

                        result = {}
                        result["kind"]     = "symbol"
                        result["type"]     = decl[1]
                        result["parent"]   = decl[2]
                        result["filename"] = filename
                        result["pos"]      = pos

                        files_to_search[filename] = filename
                        loc_to_symbol[loc] = result

        except FileNotFoundError:
            N10X.Editor.LogTo10XOutput("Couldn't open .jai_symbols!\n")
        except IOError:
            N10X.Editor.LogTo10XOutput("Error reading .jai_symbols!\n")

    regex = jai_decl_regex(word)

    for filename in files_to_search:
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                file_begin = time.perf_counter()

                for line_number, line in enumerate(file, start=1):
                    index_of_first_char = line.find(word[0])
                    index_of_colon      = line[index_of_first_char:].find(":")

                    if index_of_first_char >= 0 and index_of_colon >= 0: # skip obviously fruitless lines
                        # N10X.Editor.LogTo10XOutput(f"Fruitful line!\n")
                        for match in regex.finditer(line):
                            pos = (match.start(1), line_number - 1)
                            loc = (filename, pos)

                            result = {}
                            result["kind"]     = "search"
                            result["type"]     = "-"
                            result["parent"]   = "-"
                            result["filename"] = filename
                            result["pos"]      = pos

                            search_results.append(result)
                            if loc in loc_to_symbol:
                                symbol_results.append(loc_to_symbol[loc])

                file_end = time.perf_counter()
                if print_perf: N10X.Editor.LogTo10XOutput(f"{filename}: {int((file_end - file_begin) * 1000000)} us\n") # @Perf

        except FileNotFoundError:
            N10X.Editor.LogTo10XOutput(f"Couldn't open {filename}!\n")
        except IOError:
            N10X.Editor.LogTo10XOutput(f"Error reading {filename}!\n")

    # add symbol results first to take priority, then search results. this ensures type/parent is preserved
    unique_locs = {}
    for result in symbol_results:
        loc = (result["filename"], result["pos"])
        if loc not in unique_locs:
            all_results.append(result)
            unique_locs[loc] = loc

    for result in search_results:
        loc = (result["filename"], result["pos"])
        if loc not in unique_locs:
            all_results.append(result)
            unique_locs[loc] = loc

    sort_begin = time.perf_counter()
    all_results = sorted(all_results, key=cmp_to_key(compare_results))
    sort_end = time.perf_counter()
    if print_perf: N10X.Editor.LogTo10XOutput(f"sort: {int((sort_end - sort_begin) * 1000000)} us\n") # @Perf

    result_i = 0
    current = (current_file, current_pos)
    for i in range(len(all_results)):
        result = (all_results[i]["filename"], all_results[i]["pos"])

        if result[0] == current[0] and result[1][0] <= current[1][0] and result[1][1] <= current[1][1]:
            result_i = i

        if result == current:
            result_i = (i + dir) % len(all_results)
            break

    if result_i < len(all_results):
        # We found a definition; jump to it.
        N10X.Editor.OpenFile(all_results[result_i]["filename"])
        N10X.Editor.SetCursorPos(all_results[result_i]["pos"])
    else:
        # Gracefully fallback to GotoSymbolDefinition.
        N10X.Editor.ExecuteCommand("GotoSymbolDefinition")

    end = time.perf_counter()
    if print_perf: N10X.Editor.LogTo10XOutput(f"{sys._getframe().f_code.co_name}: {int((end - begin) * 1000000)} us\n") # @Perf
    if print_perf: N10X.Editor.LogTo10XOutput(f"\n")

def JAI_GotoNextSymbolDefinition():
    JAI_GotoSymbolDefinition(+1)

def JAI_GotoPrevSymbolDefinition():
    JAI_GotoSymbolDefinition(-1)
