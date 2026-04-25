from playwright.sync_api import sync_playwright
import json
import time
import random

def load_urls(file_path='urls.txt'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def save_result(data):
    with open('carbon_data_final.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')

def scrape_all():
    urls = load_urls()
    print(f"共加载到 {len(urls)} 个 URL，准备开始抓取...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda msg: print(f"浏览器日志: {msg.text}"))

        for index, url in enumerate(urls):
            try:
                print(f"[{index+1}/{len(urls)}] 正在抓取: {url}")
                page.goto(url, wait_until="networkidle")
                
                # 等待核心元素加载
                page.wait_for_selector("#shown-item-name", state="attached", timeout=10000)
                
                # 注入 JS 执行抓取
                result = page.evaluate("""
    () => {
        try {
            // 辅助函数：通过 XPath 找到包含关键字的元素，并获取其文本
            const getVal = (label) => {
                // XPath 逻辑：查找包含指定文字的元素
                const xpath = `//*[contains(text(), '${label}')]`;
                const node = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                
                if (!node) return "未找到";
                
                // 获取该节点所在的完整容器文本，或者它的下一个兄弟节点
                // 通常这类网站的布局是 <div>标签</div><div>值</div> 或 <div>标签:值</div>
                const text = node.parentElement.innerText || node.innerText;
                
                // 清理数据
                return text.replace(label, '').replace(/[:：]/g, '').trim();
            };

            // 抓取逻辑
            const metadata = {
                functional_unit: getVal("功能单元"),
                boundary: getVal("核算边界"),
                representative_tech: getVal("技术代表性"),
                region: getVal("地域代表性"),
                source: getVal("数据来源"),
                date: getVal("数据时间")
            };

            const nameEl = document.querySelector('#shown-item-name');
            const name = nameEl ? nameEl.innerText.trim() : "未知产品";
            
            // 提取图表数据
            const dom = document.querySelector('[_echarts_instance_]');
            let details = [];
            if (dom) {
                const chart = echarts.getInstanceByDom(dom);
                if (chart) {
                    const option = chart.getOption();
                    const stages = option.yAxis[0].data;
                    const values = option.series[0].data;
                    details = stages.map((s, i) => ({
                        stage: s,
                        emission: values[i] && values[i].value !== undefined ? values[i].value : (values[i] || 0)
                    }));
                }
            }

            return { product: name, metadata: metadata, details: details };
        } catch(e) { 
            console.log("XPath 抓取错误: " + e.message);
            return null; 
        }
    }
""")
                
                # 确保这里和上面 page.evaluate 这一行对齐
                if result:
                    save_result(result)
                    print(f" -> 成功: {result['product']}")
                else:
                    print(f" -> 警告: 页面解析返回空值")
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"抓取发生异常 {url}: {e}")
        
        browser.close()
    
    print("\n全部完成！数据已保存为 carbon_data_final.jsonl")

if __name__ == "__main__":
    scrape_all()