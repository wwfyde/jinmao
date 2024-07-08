import json

with open("meetings-0704.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    print(type(data))
