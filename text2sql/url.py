import json

def clean_jsonl(input_file, output_file):
    kept_count = 0
    removed_count = 0

    print(f"开始清洗数据：{input_file} -> {output_file}")

    with open(input_file, 'r', encoding='utf-8') as fin, \
         open(output_file, 'w', encoding='utf-8') as fout:
        
        for line in fin:
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # 核心逻辑：判断 details 是否存在且列表不为空
                # data.get('details') 确保该字段存在，len > 0 确保列表有内容
                if data.get('details') and len(data['details']) > 0:
                    fout.write(json.dumps(data, ensure_ascii=False) + '\n')
                    kept_count += 1
                else:
                    # 如果 details 为空，则跳过写入（即“删除”该条数据）
                    removed_count += 1
                    
            except json.JSONDecodeError:
                print("跳过损坏的 JSON 行")
                continue

    print("-" * 30)
    print(f"处理完成！")
    print(f"成功保留条目: {kept_count}")
    print(f"已删除条目: {removed_count}")
    print(f"最终结果已保存至: {output_file}")

if __name__ == "__main__":
    # 原文件名和清洗后的文件名
    clean_jsonl('carbon_data_final.jsonl', 'carbon_data_cleaned.jsonl')