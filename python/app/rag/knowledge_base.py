import chromadb
from chromadb.config import Settings
from typing import Optional
import uuid
import json
from datetime import datetime
from pathlib import Path


class KnowledgeBase:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="manufacturing_knowledge",
            metadata={"description": "制造工艺知识库"}
        )

    def add_knowledge(self, document: str, metadata: dict = None, doc_id: str = None) -> str:
        if doc_id is None:
            doc_id = str(uuid.uuid4())

        if metadata is None:
            metadata = {}
        
        metadata["created_at"] = datetime.now().isoformat()
        metadata["doc_id"] = doc_id

        self.collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return doc_id

    def query(self, query_text: str, n_results: int = 5) -> dict:
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return {
            "documents": results["documents"][0],
            "metadatas": results["metadatas"][0],
            "distances": results["distances"][0],
            "ids": results["ids"][0]
        }

    def delete(self, doc_id: str):
        self.collection.delete(ids=[doc_id])

    def count(self) -> int:
        return self.collection.count()

    def load_default_knowledge(self):
        default_knowledge = [
            {
                "id": "turning_basic",
                "document": "车削加工基础：车削是最基本的金属切削加工方法，主要用于加工回转体表面。车削可以加工外圆、内孔、端面、螺纹等。切削用量包括切削速度v(m/min)、进给量f(mm/r)和背吃刀量ap(mm)。",
                "metadata": {"type": "车削", "category": "加工工艺"}
            },
            {
                "id": "milling_basic",
                "document": "铣削加工基础：铣削是利用铣刀在铣床上进行切削加工的方法，主要用于加工平面、沟槽、台阶、齿轮等。铣削分为顺铣和逆铣两种方式。铣削用量包括切削速度v(m/min)、每齿进给量fz(mm/z)、背吃刀量ap(mm)和侧吃刀量ae(mm)。",
                "metadata": {"type": "铣削", "category": "加工工艺"}
            },
            {
                "id": "drilling_basic",
                "document": "钻孔加工基础：钻孔是利用钻头在实体材料上加工孔的方法。常用钻头为麻花钻，直径范围一般为0.5-80mm。钻孔时需注意冷却液的使用、钻头的选择和切削参数的确定。钻孔用量包括切削速度v(m/min)和进给量f(mm/r)。",
                "metadata": {"type": "钻孔", "category": "加工工艺"}
            },
            {
                "id": "grinding_basic",
                "document": "磨削加工基础：磨削是利用砂轮对工件表面进行精加工的方法，可以获得较高的尺寸精度和较低的表面粗糙度。磨削分为外圆磨、内圆磨、平面磨等。磨削用量包括砂轮速度vs(m/s)、工件速度vw(m/min)、径向进给量fr(mm)和轴向进给量fa(mm)。",
                "metadata": {"type": "磨削", "category": "加工工艺"}
            },
            {
                "id": "steel_45_properties",
                "document": "45钢材料参数：45钢是中国GB标准的中碳结构钢，相当于美国AISI 1045钢。其化学成分：C 0.42-0.50%，Si 0.17-0.37%，Mn 0.50-0.80%。抗拉强度≥600MPa，屈服强度≥355MPa，硬度HB≤197。适用于制造强度要求较高的零件，如轴、齿轮、连杆等。",
                "metadata": {"type": "材料", "category": "45钢"}
            },
            {
                "id": "aluminum_6061_properties",
                "document": "6061铝合金参数：6061铝合金是Al-Mg-Si系可热处理强化铝合金。化学成分：Mg 0.8-1.2%，Si 0.4-0.8%，Cu 0.15-0.4%。T6状态抗拉强度≥310MPa，屈服强度≥276MPa，延伸率≥12%，硬度HB≥95。具有良好的可焊性、耐腐蚀性和加工性能，适用于航空航天、汽车零部件等领域。",
                "metadata": {"type": "材料", "category": "6061铝合金"}
            },
            {
                "id": "surface_roughness",
                "document": "表面粗糙度等级：表面粗糙度Ra(μm)常用等级：Ra 0.025(镜面)、Ra 0.05(超精)、Ra 0.1(精密磨)、Ra 0.2(精磨)、Ra 0.4(精车/精铣)、Ra 0.8(半精车)、Ra 1.6(粗车/粗铣)、Ra 3.2(钻孔)、Ra 6.3(粗加工)、Ra 12.5(毛坯面)、Ra 25(铸造面)。",
                "metadata": {"type": "标准", "category": "表面粗糙度"}
            },
            {
                "id": "it_tolerance",
                "document": "IT公差等级：ISO公差等级IT01-IT18共20个等级。常用等级：IT6(精密配合)、IT7(一般精密配合)、IT8(中等精度)、IT9(较低精度)、IT10-IT11(粗糙配合)、IT12-IT14(非配合尺寸)。IT6-IT8用于重要配合尺寸，IT9-IT11用于一般尺寸，IT12-IT14用于自由尺寸。",
                "metadata": {"type": "标准", "category": "公差等级"}
            },
            {
                "id": "gcode_basic",
                "document": "G代码基础：G代码是数控编程中的准备功能代码。常用G代码：G00(快速定位)、G01(直线插补)、G02(顺时针圆弧插补)、G03(逆时针圆弧插补)、G04(暂停)、G17/G18/G19(选择XY/XZ/YZ平面)、G20/G21(英制/公制)、G40/G41/G42(刀具半径补偿)、G54-G59(工件坐标系)、G90/G91(绝对/增量编程)。",
                "metadata": {"type": "NC代码", "category": "G代码"}
            },
            {
                "id": "mcode_basic",
                "document": "M代码基础：M代码是数控编程中的辅助功能代码。常用M代码：M00(程序暂停)、M01(选择暂停)、M02/M30(程序结束)、M03(主轴正转)、M04(主轴反转)、M05(主轴停止)、M06(换刀)、M08(切削液开)、M09(切削液关)、M10/M11(夹紧/松开)。",
                "metadata": {"type": "NC代码", "category": "M代码"}
            }
        ]

        for item in default_knowledge:
            try:
                self.add_knowledge(
                    document=item["document"],
                    metadata=item["metadata"],
                    doc_id=item["id"]
                )
            except Exception:
                pass

    def load_rag_json_knowledge(self, json_path: str = None) -> dict:
        if json_path is None:
            project_root = Path(__file__).parent.parent.parent.parent
            json_path = project_root / "docs" / "RAG知识库.json"
        
        json_path = str(json_path)
        
        if not Path(json_path).exists():
            raise FileNotFoundError(f"找不到 RAG 知识库 JSON 文件: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        entries = data.get('knowledge_base', [])
        stats = {'total': len(entries), 'success': 0, 'skipped': 0, 'errors': 0}
        
        for entry in entries:
            try:
                doc_id = entry.get('id', str(uuid.uuid4()))
                text = entry.get('text', '')
                category = entry.get('category', '未分类')
                subcategory = entry.get('subcategory', '')
                tags = entry.get('tags', [])
                
                metadata = {
                    'category': category,
                    'subcategory': subcategory,
                    'tags': json.dumps(tags),
                    'source': 'RAG知识库.json',
                    'version': data.get('metadata', {}).get('version', '1.0')
                }
                
                try:
                    self.add_knowledge(
                        document=text,
                        metadata=metadata,
                        doc_id=doc_id
                    )
                    stats['success'] += 1
                except Exception:
                    stats['skipped'] += 1
                    
            except Exception:
                stats['errors'] += 1
        
        return stats


_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base(persist_dir: str = "./chroma_db") -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(persist_dir=persist_dir)
    return _knowledge_base
