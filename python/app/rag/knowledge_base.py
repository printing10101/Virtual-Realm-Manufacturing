import json
import logging
import os
import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_CHROMA_PATH = str(Path("python/data/knowledge/chroma").resolve())


class KnowledgeBase:
    """知识库管理类，基于 ChromaDB 提供知识的存储、检索和管理"""

    def __init__(self, persist_directory: str | None = None, collection_name: str = "manufacturing_knowledge"):
        self._persist_directory = persist_directory or DEFAULT_CHROMA_PATH
        self._collection_name = collection_name

        os.makedirs(self._persist_directory, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        existing = [c.name for c in self._client.list_collections()]
        if collection_name in existing:
            self.collection = self._client.get_collection(name=collection_name)
        else:
            self.collection = self._client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        loaded = self.count()
        logger.info("KnowledgeBase initialized: %d entries at %s", loaded, self._persist_directory)

    def count(self) -> int:
        return self.collection.count()

    def add_knowledge(self, document: str, metadata: dict | None = None,
                      doc_id: str | None = None) -> str:
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        if metadata is None:
            metadata = {}

        metadata.setdefault("source", "manual")
        metadata.setdefault("type", "general")

        self.collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return doc_id

    def query(self, query_text: str, n_results: int = 5) -> dict:
        if self.count() == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        return self.collection.query(query_texts=[query_text], n_results=n_results)

    def delete(self, doc_id: str):
        self.collection.delete(ids=[doc_id])

    def add_batch_knowledge(self, entries: list[dict]) -> list[str]:
        if not entries:
            return []

        doc_ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for entry in entries:
            doc_id = entry.get("doc_id") or str(uuid.uuid4())
            doc_ids.append(doc_id)
            documents.append(entry["document"])
            meta = entry.get("metadata", {})
            meta.setdefault("source", "batch")
            metadatas.append(meta)

        self.collection.add(documents=documents, metadatas=metadatas, ids=doc_ids)
        logger.info("Batch added %d knowledge entries", len(doc_ids))
        return doc_ids

    def query_by_source(self, source: str, query: str, n_results: int = 5) -> dict:
        if self.count() == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        return self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"source": source}
        )

    def get_knowledge_stats(self) -> dict:
        all_data = self.collection.get(include=["metadatas"])
        total = len(all_data["ids"])

        sources: dict[str, int] = {}
        types: dict[str, int] = {}
        categories: dict[str, int] = {}

        for meta in all_data["metadatas"]:
            src = meta.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
            typ = meta.get("type", "unknown")
            types[typ] = types.get(typ, 0) + 1
            cat = meta.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_count": total,
            "by_source": sources,
            "by_type": types,
            "by_category": categories,
        }

    def delete_by_source(self, source: str) -> int:
        all_data = self.collection.get(include=["metadatas"])
        to_delete: list[str] = []
        for i, meta in enumerate(all_data["metadatas"]):
            if meta.get("source") == source:
                to_delete.append(all_data["ids"][i])

        if to_delete:
            self.collection.delete(ids=to_delete)
            logger.info("Deleted %d entries from source '%s'", len(to_delete), source)
        return len(to_delete)

    def load_default_knowledge(self):
        entries = _get_default_knowledge()
        added = 0
        for entry in entries:
            try:
                self.add_knowledge(
                    document=entry["document"],
                    metadata=entry["metadata"],
                    doc_id=entry["id"]
                )
                added += 1
            except Exception:
                pass
        logger.info("Loaded %d default knowledge entries", added)
        return added

    def load_rag_json_knowledge(self) -> dict:
        json_path = Path("python/data/knowledge/knowledge_base.json")
        if not json_path.exists():
            raise FileNotFoundError(f"Knowledge JSON not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = data if isinstance(data, list) else data.get("entries", [])
        stats = {"success": 0, "skipped": 0, "errors": 0}

        for entry in entries:
            try:
                self.add_knowledge(
                    document=entry["document"],
                    metadata=entry["metadata"],
                    doc_id=entry["id"]
                )
                stats["success"] += 1
            except Exception:
                stats["skipped"] += 1

        return stats


def _get_default_knowledge() -> list[dict]:
    return [
        {
            "id": "default_wear_001",
            "document": "刀具磨损基本概念：刀具磨损是切削加工中刀具材料逐渐损耗的过程，主要包括前刀面磨损（月牙洼磨损）、后刀面磨损和边界磨损。后刀面磨损带宽VB是最常用的磨损衡量指标，一般规定VB=0.3mm为磨钝标准。刀具磨损分为三个阶段：初期磨损阶段（VB＜0.05mm）、正常磨损阶段（0.05≤VB＜0.2mm）、急剧磨损阶段（VB≥0.2mm）。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "磨损理论", "keywords": "刀具磨损,VB,月牙洼,后刀面,磨损阶段", "source": "default"}
        },
        {
            "id": "default_wear_002",
            "document": "Taylor刀具寿命公式：V×T^n=C，其中V为切削速度(m/min)，T为刀具寿命(min)，n为材料常数（高速钢刀具n≈0.1-0.15，硬质合金n≈0.2-0.3，陶瓷刀具n≈0.4-0.6），C为常数。根据Taylor公式，切削速度提高50%，刀具寿命将降低约70-80%。因此，在刀具磨损加速阶段，适当降低切削速度可显著延长刀具寿命。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "Taylor公式", "keywords": "Taylor公式,刀具寿命,切削速度,材料常数", "source": "default"}
        },
        {
            "id": "default_wear_003",
            "document": "影响刀具磨损的主要因素：1)切削速度——影响最大，速度越高磨损越快；2)进给量——影响次之；3)切削深度——影响最小；4)刀具材料——硬质合金耐磨性优于高速钢，涂层刀具优于未涂层；5)工件材料——硬度越高、韧性越大磨损越快；6)切削液——充分冷却可降低刀具温度，减少磨损；7)刀具几何角度——合理的前角和后角可减少摩擦。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "影响因素", "keywords": "磨损因素,切削速度,刀具材料,工件材料,切削液", "source": "default"}
        },
        {
            "id": "default_wear_004",
            "document": "刀具磨损监测方法：1)直接测量法——用显微镜或千分尺直接测量VB值，精度高但需停机；2)间接测量法——通过切削力、振动、温度、功率、声发射等信号间接判断磨损状态，可实现在线监测；3)振动监测法——利用加速度传感器采集加工振动信号，通过特征提取判断磨损状态，是工业中最常用的方法；4)功率监测法——主轴功率随刀具磨损增加而升高，但灵敏度较低。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "监测方法", "keywords": "磨损监测,振动监测,切削力,功率监测,声发射", "source": "default"}
        },
        {
            "id": "default_wear_005",
            "document": "刀具磨损的振动特征：随着刀具磨损加剧，振动信号呈现以下变化趋势：1)时域RMS值逐步增大，正常磨损阶段增速缓慢，急剧磨损阶段加速上升；2)频域中高频成分（1000Hz以上）能量占比增加；3)振动信号的峭度和偏度发生变化；4)出现与切削频率相关的谐波分量。当RMS值超过正常加工状态的2-3倍时，刀具通常已进入急剧磨损阶段。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "振动特征", "keywords": "振动特征,RMS,频域,峭度,谐波", "source": "default"}
        },
        {
            "id": "default_wear_006",
            "document": "基于机器学习的刀具磨损预测：使用机器学习方法可以建立刀具磨损预测模型，常用的方法包括：1)支持向量机(SVM)——适用于小样本分类，可区分正常/磨损状态；2)随机森林——可处理高维特征，提供特征重要性排序；3)XGBoost——梯度提升模型，在各种竞赛中表现优异；4)深度学习方法——CNN可用于原始振动信号分类，LSTM适用于时序磨损预测。特征工程是关键，需要从振动信号中提取RMS、峰度、偏度、频域特征等。",
            "metadata": {"type": "刀具磨损", "category": "基础知识", "subcategory": "机器学习", "keywords": "机器学习,SVM,随机森林,XGBoost,特征工程", "source": "default"}
        },
        {
            "id": "default_process_001",
            "document": "车削加工基本原理：车削是最基本的金属切削加工方法，工件旋转、刀具直线移动，主要用于加工内外圆柱面、端面、螺纹、锥面等回转表面。车削三要素：切削速度v(m/min)、进给量f(mm/r)、背吃刀量ap(mm)。常用设备：普通车床、数控车床、车铣复合机床。精度可达IT6-IT7，表面粗糙度Ra0.8-1.6μm。",
            "metadata": {"type": "工艺知识", "category": "车削", "subcategory": "基本原理", "keywords": "车削,回转表面,切削三要素,数控车床", "source": "default"}
        },
        {
            "id": "default_process_002",
            "document": "铣削加工基本原理：铣削是用旋转的多刃刀具对工件进行切削加工的方法，可加工平面、台阶、沟槽、成形面、齿轮等。铣削分周铣和端铣。铣削用量：铣削速度v、进给量fz(每齿)、铣削深度ap。常用设备：立式铣床、卧式铣床、数控加工中心。精度一般IT7-IT9，Ra1.6-3.2μm。五轴加工中心可用于复杂曲面加工。",
            "metadata": {"type": "工艺知识", "category": "铣削", "subcategory": "基本原理", "keywords": "铣削,多刃刀具,周铣,端铣,加工中心", "source": "default"}
        },
        {
            "id": "default_mat_001",
            "document": "45号钢材料参数：45钢是中国GB标准优质碳素结构钢，含碳量约0.45%。力学性能：抗拉强度σb≥600MPa，屈服强度σs≥355MPa，硬度≤229HB（未热处理）。热处理后可获得良好的综合力学性能。广泛用于制造轴、齿轮、连杆、螺栓等机械零件。切削加工性良好，推荐切削速度：车削100-300m/min，铣削80-200m/min。",
            "metadata": {"type": "材料知识", "category": "碳钢", "subcategory": "45钢", "keywords": "45钢,碳素结构钢,轴类零件,热处理,切削参数", "source": "default"}
        },
        {
            "id": "default_nc_001",
            "document": "常用G代码含义：G00-快速定位（非切削移动），G01-直线插补（切削进给），G02-顺时针圆弧插补，G03-逆时针圆弧插补，G04-暂停，G17-选择XY平面，G18-选择XZ平面，G19-选择YZ平面，G20-英制单位，G21-公制单位，G40-取消刀具半径补偿，G41-刀具半径左补偿，G42-刀具半径右补偿，G54-G59-工件坐标系，G90-绝对坐标编程，G91-增量坐标编程，G94-每分钟进给，G95-每转进给。M代码：M03-主轴正转，M04-主轴反转，M05-主轴停止，M08-冷却液开，M09-冷却液关，M30-程序结束并返回。",
            "metadata": {"type": "NC编程", "category": "G代码", "subcategory": "基础指令", "keywords": "G代码,M代码,数控编程,CNC,刀具补偿", "source": "default"}
        },
    ]


_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base(persist_directory: str | None = None) -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        chroma_path = persist_directory or os.environ.get("CHROMA_DB_PATH", "")
        if chroma_path:
            _knowledge_base = KnowledgeBase(persist_directory=chroma_path)
        else:
            _knowledge_base = KnowledgeBase()
    return _knowledge_base
