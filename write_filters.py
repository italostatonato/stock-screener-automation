content = open("filters_content.txt", "r", encoding="utf-8").read()
with open("src/filters.py", "w", encoding="utf-8") as f:
    f.write(content)
print("filters.py reescrito com sucesso, encoding UTF-8 garantido.")