import json
from collections import Counter

import matplotlib.pyplot as plt

# 读取JSON文件
with open("aime/stats_output.json", "r") as file:
    data = json.load(file)

# 初始化计数器
field_counter = Counter()
subfield_counter = Counter()

# 遍历数据并统计field和subfield
for year, year_data in data.items():
    for experiment in year_data["experiments"]:
        field = experiment["attributes"]["field"]
        subfield = experiment["attributes"]["subfield"]
        field_counter[field] += 1
        subfield_counter[subfield] += 1

# 打印统计结果
print("Field Counts:")
for field, count in field_counter.items():
    print(f"{field}: {count}")

print("\nSubfield Counts:")
for subfield, count in subfield_counter.items():
    print(f"{subfield}: {count}")


# 可视化统计结果
def plot_counter(counter, title):
    labels, values = zip(*counter.items())
    plt.figure(figsize=(10, 5))
    plt.bar(labels, values)
    plt.title(title)
    plt.xticks(rotation=90)
    plt.show()


plot_counter(field_counter, "Field Counts")
plot_counter(subfield_counter, "Subfield Counts")
