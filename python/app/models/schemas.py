from pydantic import BaseModel, Field


class KnowledgeAddRequest(BaseModel):
    document: str = Field(..., description="知识文档内容")
    metadata: dict | None = Field(default=None, description="元数据")
    doc_id: str | None = Field(default=None, description="文档ID（为空则自动生成）")


class KnowledgeDeleteRequest(BaseModel):
    doc_id: str = Field(..., description="要删除的文档ID")


class KnowledgeQueryRequest(BaseModel):
    query_text: str = Field(..., description="查询文本")
    n_results: int = Field(default=5, description="返回结果数量", ge=1, le=20)
