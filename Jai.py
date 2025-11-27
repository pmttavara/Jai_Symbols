import N10X

def get_word(line, index):
    if index >= len(line):
       index = len(line)

    if index < 0:
       index = 0

    start = end = index

    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_'):
        start -= 1

    while end < len(line) and (line[end].isalnum() or line[end] == '_'):
        end += 1

    return line[start:end], start

def JAI_GotoSymbolDefinition():
    line = N10X.Editor.GetCurrentLine()
    current_file = N10X.Editor.GetCurrentFilename()
    current_pos = N10X.Editor.GetCursorPos()
    word, word_start = get_word(line, current_pos[0])
    symbols_path = ""
    if len(word) != 0:
        for file in N10X.Editor.GetWorkspaceFiles():
            if file.endswith(".build/.jai_symbols"):
                symbols_path = file
                break

    results = []

    if len(symbols_path) != 0:
        try:
            with open(symbols_path, 'r', encoding='utf-8') as file:
                for line_number, line in enumerate(file, start=1):
                    if line.startswith(word) and len(line) > len(word) and line[len(word)] == ' ':
                        quotation_split_line = line.split('"')

                        decl    = quotation_split_line[0].strip().split(' ')
                        pos_str = quotation_split_line[2].strip().split(' ')

                        name   = decl[0]
                        type   = decl[1]
                        parent = decl[2]

                        filename = quotation_split_line[1]

                        line   = int(pos_str[0]) - 1
                        column = int(pos_str[1]) - 1
                        pos    = (column, line)

                        result = {}
                        result["name"]     = name
                        result["type"]     = type
                        result["parent"]   = parent
                        result["filename"] = filename
                        result["pos"]      = pos

                        results.append(result)
        except FileNotFoundError:
            N10X.Editor.LogTo10XOutput("Couldn't open .jai_symbols!")
        except IOError:
            N10X.Editor.LogTo10XOutput("Error reading .jai_symbols!")

    result_i = 0
    current = (current_file, current_pos)
    for i in range(len(results) - 1, -1, -1):
        result = (results[i]["filename"], results[i]["pos"])
        if result[0] == current[0] and result[1][0] == current[1][0] and result[1][1] == current[1][1]:
            result_i = (i + 1) % len(results)
            break

    if result_i < len(results):
        # We found a JaiTags definition; jump to it.
        N10X.Editor.OpenFile(results[result_i]["filename"])
        N10X.Editor.SetCursorPos(results[result_i]["pos"])
    else:
        # Gracefully fallback to GotoSymbolDefinition.
        N10X.Editor.ExecuteCommand("GotoSymbolDefinition")
