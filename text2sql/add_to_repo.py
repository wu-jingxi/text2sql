import json
import sqlite3

def ingest_to_db(jsonl_file, db_name='carbon.db'):
    # 连接数据库
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # 1. 创建表结构 (使用外键关联)
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            unit TEXT,
            boundary TEXT,
            tech TEXT,
            region TEXT,
            source TEXT,
            date TEXT
        );
        CREATE TABLE IF NOT EXISTS emissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            stage TEXT,
            emission REAL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
    ''')

    # 2. 读取并插入数据
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                meta = data.get('metadata', {})
                
                # 使用 INSERT OR IGNORE 避免重复插入相同产品
                cursor.execute('''INSERT OR IGNORE INTO products (name, unit, boundary, tech, region, source, date) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                               (data['product'], meta.get('functional_unit'), meta.get('boundary'), 
                                meta.get('representative_tech'), meta.get('region'), meta.get('source'), meta.get('date')))
                
                # 获取产品ID (无论是刚插入的还是已存在的)
                cursor.execute('SELECT id FROM products WHERE name = ?', (data['product'],))
                product_id = cursor.fetchone()[0]
                
                # 插入 emission 数据 (先清除旧数据以保证幂等性)
                cursor.execute('DELETE FROM emissions WHERE product_id = ?', (product_id,))
                for item in data.get('details', []):
                    cursor.execute('INSERT INTO emissions (product_id, stage, emission) VALUES (?, ?, ?)', 
                                   (product_id, item['stage'], item['emission']))
            except Exception as e:
                print(f"插入数据出错: {e}")

    conn.commit()
    conn.close()
    print("数据库入库完成！")

if __name__ == "__main__":
    ingest_to_db('carbon_data_cleaned.jsonl')