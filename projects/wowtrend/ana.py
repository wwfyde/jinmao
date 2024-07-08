import json
from collections import defaultdict
from pathlib import Path

def load_data(file_path):
    if Path(file_path).is_file():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def process_data(input_file, output_file):
    data = load_data(input_file)

    # 创建一个新的数据结构：{brand: {time: [articles]}}
    processed_data = defaultdict(lambda: defaultdict(list))

    for brand, categories in data.items():
        for time_period, articles in categories.items():
            for article in articles:
                processed_data[brand][time_period].append(article)

    save_data(output_file, processed_data)

if __name__ == "__main__":
    input_file = 'articles.json'  # 现有的JSON文件
    output_file = 'processed_articles.json'  # 处理后的JSON文件
    process_data(input_file, output_file)
