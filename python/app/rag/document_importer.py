"""用户自定义知识导入与文档处理模块。

支持 PDF、Word (.doc, .docx)、Markdown (.md) 格式文档的导入、
智能分块、元数据提取和向量化处理。
"""
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class DocumentMetadata:
    document_name: str
    file_type: str
    file_size: int
    import_time: str
    source: str = "user_import"
    author: str = ""
    version: str = "1.0"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    chunk_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    chunk_index: int
    total_chunks: int
    metadata: dict
    start_position: int = 0
    end_position: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class DocumentExtractor:
    def extract_from_pdf(self, file_path: str) -> str:
        try:

            try:
                import pdfplumber
                return self._extract_with_pdfplumber(file_path)
            except ImportError:
                pass

            try:
                from PyPDF2 import PdfReader
                return self._extract_with_pypdf2(file_path)
            except ImportError:
                pass

            raise ImportError(
                "PDF提取需要安装 pdfplumber 或 PyPDF2。"
                "请运行: pip install pdfplumber 或 pip install PyPDF2"
            )
        except Exception as e:
            raise RuntimeError(f"PDF提取失败: {e!s}")

    def _extract_with_pdfplumber(self, file_path: str) -> str:
        import pdfplumber

        text_content = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)

        return "\n\n".join(text_content)

    def _extract_with_pypdf2(self, file_path: str) -> str:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        text_content = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)

        return "\n\n".join(text_content)

    def extract_from_word(self, file_path: str) -> str:
        try:
            from docx import Document

            doc = Document(file_path)
            text_content = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)

            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    if row_text.strip():
                        text_content.append(row_text)

            return "\n\n".join(text_content)
        except ImportError:
            raise ImportError(
                "Word提取需要安装 python-docx。请运行: pip install python-docx"
            )
        except Exception as e:
            raise RuntimeError(f"Word提取失败: {e!s}")

    def extract_from_markdown(self, file_path: str) -> str:
        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                content = f.read()

            import markdown
            html_content = markdown.markdown(content)

            clean_text = re.sub(r'<[^>]+>', '', html_content)
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

            return clean_text.strip()
        except Exception as e:
            raise RuntimeError(f"Markdown提取失败: {e!s}")

    def extract(self, file_path: str) -> str:
        file_ext = Path(file_path).suffix.lower()

        extractors = {
            '.pdf': self.extract_from_pdf,
            '.doc': self.extract_from_word,
            '.docx': self.extract_from_word,
            '.md': self.extract_from_markdown,
            '.markdown': self.extract_from_markdown
        }

        if file_ext not in extractors:
            raise ValueError(f"不支持的文件格式: {file_ext}。支持的格式: PDF, DOC, DOCX, MD")

        return extractors[file_ext](file_path)


class SmartChunker:
    def __init__(self, max_chunk_size: int = 500,
                 chunk_overlap: int = 50,
                 min_chunk_size: int = 100):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def _split_by_headings(self, text: str) -> list[tuple[str, int]]:
        heading_pattern = re.compile(r'^(#{1,6}\s+.+|第[一二三四五六七八九十\d]+[章节部分].+)$',
                                     re.MULTILINE)

        matches = list(heading_pattern.finditer(text))

        if not matches:
            return [(text, 0)]

        sections = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i < len(matches) - 1 else len(text)

            section_text = text[start:end].strip()
            sections.append((section_text, start))

        return sections

    def _split_by_paragraphs(self, text: str) -> list[str]:
        paragraphs = re.split(r'\n{2,}', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_by_sentences(self, text: str) -> list[str]:
        sentence_pattern = re.compile(r'(?<=[。！？.!?])\s*')
        sentences = sentence_pattern.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _merge_into_chunks(self, segments: list[str]) -> list[str]:
        chunks = []
        current_chunk = ""

        for segment in segments:
            if len(current_chunk) + len(segment) <= self.max_chunk_size:
                if current_chunk:
                    current_chunk += "\n" + segment
                else:
                    current_chunk = segment
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(segment) > self.max_chunk_size:
                    sentences = self._split_by_sentences(segment)
                    sub_chunk = ""
                    for sentence in sentences:
                        if len(sub_chunk) + len(sentence) <= self.max_chunk_size:
                            if sub_chunk:
                                sub_chunk += " " + sentence
                            else:
                                sub_chunk = sentence
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = sentence
                    if sub_chunk:
                        current_chunk = sub_chunk
                else:
                    current_chunk = segment

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def chunk(self, text: str, metadata: dict | None = None) -> list[DocumentChunk]:
        if not text.strip():
            return []

        sections = self._split_by_headings(text)

        all_segments = []
        for section_text, section_start in sections:
            if len(section_text) <= self.max_chunk_size:
                all_segments.append((section_text, section_start))
            else:
                paragraphs = self._split_by_paragraphs(section_text)
                current_group = ""
                group_start = section_start

                for para in paragraphs:
                    if len(current_group) + len(para) <= self.max_chunk_size:
                        if current_group:
                            current_group += "\n" + para
                        else:
                            current_group = para
                    else:
                        if current_group:
                            all_segments.append((current_group, group_start))
                        current_group = para
                        group_start = section_start + text[section_start:].find(para)

                if current_group:
                    all_segments.append((current_group, group_start))

        chunks = []
        for i, (chunk_text, start_pos) in enumerate(all_segments):
            if len(chunk_text) < self.min_chunk_size and i < len(all_segments) - 1:
                next_text, _ = all_segments[i + 1]
                merged = chunk_text + "\n" + next_text
                if len(merged) <= self.max_chunk_size:
                    all_segments[i + 1] = (merged, start_pos)
                    continue

            chunk = DocumentChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                content=chunk_text.strip(),
                chunk_index=i,
                total_chunks=0,
                metadata=metadata or {},
                start_position=start_pos,
                end_position=start_pos + len(chunk_text)
            )
            chunks.append(chunk)

        for i, chunk in enumerate(chunks):
            chunk.total_chunks = len(chunks)
            chunk.chunk_index = i

        return chunks


class DocumentVectorizer:
    def __init__(self, embedding_model=None):
        self.embedding_model = embedding_model

    def vectorize_chunk(self, chunk: DocumentChunk) -> dict:
        return {
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks
        }

    def vectorize_chunks(self, chunks: list[DocumentChunk]) -> list[dict]:
        return [self.vectorize_chunk(chunk) for chunk in chunks]


class DocumentImportService:
    def __init__(self, knowledge_base):
        self.extractor = DocumentExtractor()
        self.chunker = SmartChunker()
        self.vectorizer = DocumentVectorizer()
        self.knowledge_base = knowledge_base
        self.import_history = []

    def import_document(self, file_path: str,
                       additional_metadata: dict | None = None) -> dict:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        file_size = file_path_obj.stat().st_size
        file_type = file_path_obj.suffix.lower()
        document_name = file_path_obj.stem

        text_content = self.extractor.extract(file_path)

        if not text_content.strip():
            raise ValueError(f"文档内容为空: {file_path}")

        doc_metadata = DocumentMetadata(
            document_name=document_name,
            file_type=file_type,
            file_size=file_size,
            import_time=datetime.now().isoformat(),
            source="user_import",
            chunk_count=0
        )

        if additional_metadata:
            for key, value in additional_metadata.items():
                if hasattr(doc_metadata, key):
                    setattr(doc_metadata, key, value)

        metadata_dict = doc_metadata.to_dict()
        metadata_dict.update(additional_metadata or {})

        chunks = self.chunker.chunk(text_content, metadata_dict)

        if not chunks:
            raise ValueError("文档分块结果为空")

        vectorized_chunks = self.vectorizer.vectorize_chunks(chunks)

        imported_ids = []
        for vchunk in vectorized_chunks:
            chunk_metadata = vchunk["metadata"].copy()
            chunk_metadata["chunk_id"] = vchunk["chunk_id"]
            chunk_metadata["chunk_index"] = vchunk["chunk_index"]
            chunk_metadata["total_chunks"] = vchunk["total_chunks"]
            chunk_metadata["source_document"] = document_name

            doc_id = f"{document_name}_{vchunk['chunk_id']}"

            try:
                self.knowledge_base.add_knowledge(
                    document=vchunk["content"],
                    metadata=chunk_metadata,
                    doc_id=doc_id
                )
                imported_ids.append(doc_id)
            except Exception as e:
                print(f"导入块 {vchunk['chunk_id']} 失败: {e!s}")

        doc_metadata.chunk_count = len(imported_ids)

        import_record = {
            "document_name": document_name,
            "file_path": str(file_path),
            "file_type": file_type,
            "file_size": file_size,
            "import_time": doc_metadata.import_time,
            "chunk_count": len(imported_ids),
            "imported_ids": imported_ids,
            "status": "success" if imported_ids else "failed"
        }
        self.import_history.append(import_record)

        return {
            "document_name": document_name,
            "chunk_count": len(imported_ids),
            "imported_ids": imported_ids,
            "metadata": doc_metadata.to_dict(),
            "status": import_record["status"]
        }

    def get_import_history(self, limit: int = 50) -> list[dict]:
        return self.import_history[-limit:]

    def get_document_stats(self) -> dict:
        total_documents = len(self.import_history)
        total_chunks = sum(record["chunk_count"] for record in self.import_history)

        file_type_stats = {}
        for record in self.import_history:
            ft = record["file_type"]
            file_type_stats[ft] = file_type_stats.get(ft, 0) + 1

        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "file_type_stats": file_type_stats,
            "recent_imports": self.import_history[-5:]
        }
