#!/usr/bin/env python3
"""
RAG知识库数据集成脚本
将 docs/RAG知识库.json 中的数据导入到 ChromaDB 向量数据库
"""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import chromadb
from chromadb.config import Settings


def load_json_knowledge(json_path: str) -> dict:
    """加载 JSON 知识库文件"""
    print(f"正在加载 JSON 文件: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def validate_json_data(data: dict) -> tuple:
    """验证 JSON 数据的完整性和结构"""
    if 'metadata' not in data:
        raise ValueError("JSON 文件缺少 metadata 字段")
    if 'knowledge_base' not in data:
        raise ValueError("JSON 文件缺少 knowledge_base 字段")
    
    kb_entries = data['knowledge_base']
    total_entries = data['metadata'].get('total_entries', 0)
    
    print(f"JSON 元数据:")
    print(f"  - 版本: {data['metadata'].get('version', '未知')}")
    print(f"  - 项目: {data['metadata'].get('project', '未知')}")
    print(f"  - 预期条目数: {total_entries}")
    print(f"  - 实际条目数: {len(kb_entries)}")
    
    if len(kb_entries) != total_entries:
        print(f"  [WARN] 警告: 实际条目数与预期不一致")
    
    # 验证每条知识的必需字段
    required_fields = {'id', 'category', 'subcategory', 'text'}
    missing_count = 0
    
    for i, entry in enumerate(kb_entries):
        missing = required_fields - set(entry.keys())
        if missing:
            print(f"  [WARN] 条目 {i+1} (ID: {entry.get('id', '未知')}) 缺少字段: {missing}")
            missing_count += 1
    
    if missing_count > 0:
        print(f"  [WARN] 共有 {missing_count} 条知识缺少必需字段")
    else:
        print(f"  [OK] 所有知识条目字段完整")
    
    return data['metadata'], kb_entries


def transform_entries(entries: List[Dict]) -> Dict[str, List]:
    """批量转换 JSON 知识条目为 ChromaDB 期望的格式"""
    ids = []
    documents = []
    metadatas = []
    
    for entry in entries:
        ids.append(entry['id'])
        documents.append(entry['text'])
        metadatas.append({
            'category': entry.get('category', '未分类'),
            'subcategory': entry.get('subcategory', ''),
            'tags': json.dumps(entry.get('tags', [])),
            'source': 'RAG知识库.json',
            'json_version': '2.0.0'
        })
    
    return {
        'ids': ids,
        'documents': documents,
        'metadatas': metadatas
    }


def integrate_knowledge_base(json_path: str, chroma_dir: str = "./chroma_db"):
    """集成知识库的主函数"""
    print("=" * 60)
    print("灵境制造V4 - RAG知识库数据集成工具")
    print("=" * 60)
    print()
    
    # 1. 加载 JSON 数据
    data = load_json_knowledge(json_path)
    
    # 2. 验证数据
    metadata, entries = validate_json_data(data)
    print()
    
    # 3. 初始化 ChromaDB 客户端
    print(f"正在初始化 ChromaDB 知识库 (持久化目录: {chroma_dir})")
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name="manufacturing_knowledge",
        metadata={"description": "制造工艺知识库"}
    )
    
    initial_count = collection.count()
    print(f"当前知识库条目数: {initial_count}")
    print()
    
    # 4. 批量转换数据
    print("正在转换数据格式...")
    batch_data = transform_entries(entries)
    print(f"已转换 {len(batch_data['ids'])} 条知识")
    print()
    
    # 5. 批量导入数据（分批处理避免内存问题）
    print("开始导入知识条目...")
    batch_size = 100
    total_entries = len(batch_data['ids'])
    success_count = 0
    error_count = 0
    
    for i in range(0, total_entries, batch_size):
        end_idx = min(i + batch_size, total_entries)
        batch = {
            'ids': batch_data['ids'][i:end_idx],
            'documents': batch_data['documents'][i:end_idx],
            'metadatas': batch_data['metadatas'][i:end_idx]
        }
        
        try:
            collection.add(
                ids=batch['ids'],
                documents=batch['documents'],
                metadatas=batch['metadatas']
            )
            success_count += len(batch['ids'])
            print(f"  进度: {end_idx}/{total_entries} 条已导入")
        except Exception as e:
            error_count += len(batch['ids'])
            print(f"  [ERROR] 批次 {i//batch_size + 1} 导入失败: {str(e)}")
            # 尝试逐条导入该批次
            print(f"  正在尝试逐条导入该批次...")
            for j in range(len(batch['ids'])):
                try:
                    collection.add(
                        ids=[batch['ids'][j]],
                        documents=[batch['documents'][j]],
                        metadatas=[batch['metadatas'][j]]
                    )
                    success_count += 1
                    error_count -= 1
                except Exception as e2:
                    print(f"    [ERROR] 条目 {batch['ids'][j]} 导入失败: {str(e2)}")
    
    print()
    
    # 6. 验证导入结果
    final_count = collection.count()
    added_count = final_count - initial_count
    
    print("=" * 60)
    print("集成结果统计:")
    print(f"  - 初始知识库条目: {initial_count}")
    print(f"  - 成功导入: {success_count}")
    print(f"  - 导入失败: {error_count}")
    print(f"  - 新增条目: {added_count}")
    print(f"  - 最终知识库条目: {final_count}")
    print("=" * 60)
    
    if error_count == 0:
        print("[OK] 所有知识条目已成功导入！")
    else:
        print(f"[WARN] 有 {error_count} 条知识导入失败，请检查日志")
    
    # 7. 测试检索功能
    print()
    print("正在测试检索功能...")
    test_queries = [
        "45钢车削参数",
        "铝合金铣削",
        "钻头选择"
    ]
    
    for query in test_queries:
        print(f"\n测试查询: '{query}'")
        try:
            results = collection.query(
                query_texts=[query],
                n_results=3
            )
            if results['documents'][0]:
                print(f"  [OK] 检索到 {len(results['documents'][0])} 条结果")
                for i, (doc, meta, dist, doc_id) in enumerate(zip(
                    results['documents'][0], 
                    results['metadatas'][0], 
                    results['distances'][0],
                    results['ids'][0]
                )):
                    print(f"  {i+1}. [ID: {doc_id}] {doc[:80]}... (距离: {dist:.4f})")
            else:
                print(f"  [WARN] 未找到相关结果")
        except Exception as e:
            print(f"  [ERROR] 查询失败: {str(e)}")
    
    print()
    print("=" * 60)
    print("数据集成完成！")
    print("=" * 60)
    
    return {
        'initial_count': initial_count,
        'success_count': success_count,
        'error_count': error_count,
        'final_count': final_count
    }


if __name__ == "__main__":
    # 默认路径
    json_path = project_root.parent / "docs" / "RAG知识库.json"
    
    # 支持命令行参数
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    
    if not json_path.exists():
        print(f"[ERROR] 找不到文件 {json_path}")
        sys.exit(1)
    
    chroma_dir = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
    
    try:
        result = integrate_knowledge_base(str(json_path), chroma_dir)
        sys.exit(0 if result['error_count'] == 0 else 1)
    except Exception as e:
        print(f"[ERROR] 集成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
