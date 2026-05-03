#!/usr/bin/env python3
"""
简单的 RAG 知识库数据集成脚本
直接导入 JSON 数据到 ChromaDB
"""

import sys
import os
from pathlib import Path

# 切换到 python 目录
python_dir = Path(__file__).parent.parent
os.chdir(python_dir)
sys.path.insert(0, str(python_dir))

# 设置环境变量以启用离线模式
os.environ['CHROMA_CLI_TELEMETRY'] = 'False'

import json
import uuid
import chromadb


def main():
    json_path = python_dir.parent / "docs" / "RAG知识库.json"
    chroma_dir = os.path.join(python_dir, "chroma_db")
    
    print("=" * 60)
    print("灵境制造V4 - RAG知识库数据集成工具")
    print("=" * 60)
    print()
    
    if not json_path.exists():
        print(f"[ERROR] 找不到文件: {json_path}")
        return 1
    
    print(f"步骤 1/5: 加载 JSON 文件...")
    print(f"  文件路径: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metadata = data.get('metadata', {})
    entries = data.get('knowledge_base', [])
    
    print(f"  版本: {metadata.get('version', '未知')}")
    print(f"  总条目数: {len(entries)}")
    print()
    
    print("步骤 2/5: 验证数据完整性...")
    
    required_fields = {'id', 'category', 'subcategory', 'text'}
    missing_count = 0
    for i, entry in enumerate(entries):
        missing = required_fields - set(entry.keys())
        if missing:
            print(f"  [WARN] 条目 {i+1} (ID: {entry.get('id', '未知')}) 缺少字段: {missing}")
            missing_count += 1
    
    if missing_count > 0:
        print(f"  [WARN] 共有 {missing_count} 条知识缺少必需字段")
    else:
        print(f"  [OK] 所有知识条目字段完整")
    print()
    
    print(f"步骤 3/5: 初始化 ChromaDB 知识库...")
    print(f"  持久化目录: {chroma_dir}")
    
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name="manufacturing_knowledge",
        metadata={"description": "制造工艺知识库"}
    )
    
    initial_count = collection.count()
    print(f"  当前知识库条目数: {initial_count}")
    print()
    
    print(f"步骤 4/5: 导入知识条目到 ChromaDB...")
    
    batch_size = 50
    total_entries = len(entries)
    success_count = 0
    skipped_count = 0
    error_count = 0
    
    ids = []
    documents = []
    metadatas = []
    
    for entry in entries:
        try:
            doc_id = entry.get('id', str(uuid.uuid4()))
            text = entry.get('text', '')
            category = entry.get('category', '未分类')
            subcategory = entry.get('subcategory', '')
            tags = entry.get('tags', [])
            
            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                'category': category,
                'subcategory': subcategory,
                'tags': json.dumps(tags),
                'source': 'RAG知识库.json',
                'version': metadata.get('version', '1.0')
            })
        except Exception as e:
            error_count += 1
            print(f"  [WARN] 转换条目 {entry.get('id', '未知')} 失败: {str(e)}")
    
    for i in range(0, len(ids), batch_size):
        end_idx = min(i + batch_size, len(ids))
        batch_ids = ids[i:end_idx]
        batch_docs = documents[i:end_idx]
        batch_meta = metadatas[i:end_idx]
        
        try:
            existing = collection.get(ids=batch_ids, include=[])
            existing_ids = set(existing['ids'])
            
            new_ids = [bid for bid in batch_ids if bid not in existing_ids]
            new_docs = [d for bid, d in zip(batch_ids, batch_docs) if bid not in existing_ids]
            new_meta = [m for bid, m in zip(batch_ids, batch_meta) if bid not in existing_ids]
            
            if new_ids:
                collection.add(
                    ids=new_ids,
                    documents=new_docs,
                    metadatas=new_meta
                )
            
            success_count += len(batch_ids)
            print(f"  进度: {end_idx}/{total_entries} 条已处理")
        except Exception as e:
            error_count += len(batch_ids)
            print(f"  [ERROR] 批次 {i//batch_size + 1} 导入失败: {str(e)}")
    
    print()
    
    final_count = collection.count()
    
    print(f"步骤 5/5: 验证导入结果...")
    print(f"  初始知识库条目: {initial_count}")
    print(f"  成功导入: {success_count}")
    print(f"  跳过: {skipped_count}")
    print(f"  错误: {error_count}")
    print(f"  最终知识库条目: {final_count}")
    print()
    
    if error_count == 0:
        print("[OK] 所有知识条目已成功导入!")
    else:
        print(f"[WARN] 有 {error_count} 条知识导入失败")
    
    print()
    print("=" * 60)
    print("数据集成完成!")
    print("=" * 60)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    try:
        result = main()
        sys.exit(result)
    except Exception as e:
        print(f"[ERROR] 集成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
