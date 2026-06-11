#!/usr/bin/env python3
"""批量替换 step_parser.py 中的 except Exception 为具体异常类型"""
import re
from pathlib import Path

TARGET = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app\step_import\step_parser.py")

text = TARGET.read_text(encoding="utf-8")

# Pattern 1: shape attribute access with default fallback - simple assignment
# try: X = shape.Y()  except Exception: X = default
# Match these and replace with specific exception types
patterns = [
    # Pattern: bbox default 0
    (r'        except Exception:\n            bbox = BoundingBox\(0, 0, 0\)',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as geom_err:\n'
     '            # CadQuery 包围盒计算失败时回退为零包围盒，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to compute BoundingBox for shape: %s",\n'
     '                geom_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            bbox = BoundingBox(0, 0, 0)'),
    # Pattern: volume default
    (r'        except Exception:\n            volume = 0\.0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as vol_err:\n'
     '            # CadQuery 体积计算失败时回退为 0.0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to compute shape Volume: %s",\n'
     '                vol_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            volume = 0.0'),
    # Pattern: surface_area default
    (r'        except Exception:\n            surface_area = 0\.0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as area_err:\n'
     '            # CadQuery 表面积计算失败时回退为 0.0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to compute shape Area: %s",\n'
     '                area_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            surface_area = 0.0'),
    # Pattern: center default
    (r'        except Exception:\n            center = \(0\.0, 0\.0, 0\.0\)',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as com_err:\n'
     '            # CadQuery 重心计算失败时回退到原点，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to compute shape Center: %s",\n'
     '                com_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            center = (0.0, 0.0, 0.0)'),
    # Pattern: face_count
    (r'        except Exception:\n            face_count = 0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as face_err:\n'
     '            # CadQuery 面枚举失败时回退为 0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate shape Faces: %s",\n'
     '                face_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            face_count = 0'),
    # Pattern: vertex_count
    (r'        except Exception:\n            vertex_count = 0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as vert_err:\n'
     '            # CadQuery 顶点枚举失败时回退为 0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate shape Vertices: %s",\n'
     '                vert_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            vertex_count = 0'),
    # Pattern: edge_count
    (r'        except Exception:\n            edge_count = 0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as edge_err:\n'
     '            # CadQuery 边枚举失败时回退为 0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate shape Edges: %s",\n'
     '                edge_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            edge_count = 0'),
    # Pattern: shell_count
    (r'        except Exception:\n            shell_count = 0',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as shell_err:\n'
     '            # CadQuery 壳枚举失败时回退为 0，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate shape Shells: %s",\n'
     '                shell_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            shell_count = 0'),
    # Pattern: solid_count + entity_count
    (r'        except Exception:\n            solid_count = 0\n            entity_count = 1',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as sol_err:\n'
     '            # CadQuery 实体枚举失败时回退为单个实体，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate shape Solids: %s",\n'
     '                sol_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            solid_count = 0\n'
     '            entity_count = 1'),
    # Pattern: solids = []
    (r'        except Exception:\n            solids = \[\]',
     '        except (AttributeError, RuntimeError, ValueError, TypeError) as sol_err:\n'
     '            # 装配体实体枚举失败时按单实体处理，记录以便排查\n'
     '            logger.debug(\n'
     '                "Failed to enumerate assembly solids: %s",\n'
     '                sol_err,\n'
     '                exc_info=True,\n'
     '            )\n'
     '            solids = []'),
    # Pattern: e_faces = 0
    (r'            except Exception:\n                e_faces = 0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as face_err:\n'
     '                # 装配体面枚举失败时回退为 0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to enumerate entity faces: %s",\n'
     '                    face_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                e_faces = 0'),
    # Pattern: e_verts = 0
    (r'            except Exception:\n                e_verts = 0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as vert_err:\n'
     '                # 装配体顶点枚举失败时回退为 0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to enumerate entity vertices: %s",\n'
     '                    vert_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                e_verts = 0'),
    # Pattern: e_vol = 0.0
    (r'            except Exception:\n                e_vol = 0\.0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as vol_err:\n'
     '                # 装配体体积计算失败时回退为 0.0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute entity Volume: %s",\n'
     '                    vol_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                e_vol = 0.0'),
    # Pattern: e_area = 0.0
    (r'            except Exception:\n                e_area = 0\.0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as area_err:\n'
     '                # 装配体表面积计算失败时回退为 0.0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute entity Area: %s",\n'
     '                    area_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                e_area = 0.0'),
    # Pattern: e_center = (0.0, 0.0, 0.0)
    (r'            except Exception:\n                e_center = \(0\.0, 0\.0, 0\.0\)',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as com_err:\n'
     '                # 装配体重心计算失败时回退为原点，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute entity Center: %s",\n'
     '                    com_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                e_center = (0.0, 0.0, 0.0)'),
    # Pattern: entity_bbox = BoundingBox(0, 0, 0)
    (r'            except Exception:\n                entity_bbox = BoundingBox\(0, 0, 0\)',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as bb_err:\n'
     '                # 装配体包围盒计算失败时回退为零包围盒，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute entity BoundingBox: %s",\n'
     '                    bb_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                entity_bbox = BoundingBox(0, 0, 0)'),
    # Pattern: face_count = 0 (16 spaces, in _extract_entities)
    (r'            except Exception:\n                face_count = 0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as face_err:\n'
     '                # 单实体面枚举失败时回退为 0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to enumerate single-entity faces: %s",\n'
     '                    face_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                face_count = 0'),
    # Pattern: vertex_count = 0 (16 spaces)
    (r'            except Exception:\n                vertex_count = 0',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as vert_err:\n'
     '                # 单实体顶点枚举失败时回退为 0，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to enumerate single-entity vertices: %s",\n'
     '                    vert_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                vertex_count = 0'),
    # Pattern: bbox (16 spaces) - in _extract_entities
    (r'            except Exception:\n                bbox = BoundingBox\(0, 0, 0\)',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as bb_err:\n'
     '                # 单实体包围盒计算失败时回退为零包围盒，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute single-entity BoundingBox: %s",\n'
     '                    bb_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                bbox = BoundingBox(0, 0, 0)'),
    # Pattern: center (16 spaces)
    (r'            except Exception:\n                center = \(0\.0, 0\.0, 0\.0\)',
     '            except (AttributeError, RuntimeError, ValueError, TypeError) as com_err:\n'
     '                # 单实体重心计算失败时回退为原点，记录以便排查\n'
     '                logger.debug(\n'
     '                    "Failed to compute single-entity Center: %s",\n'
     '                    com_err,\n'
     '                    exc_info=True,\n'
     '                )\n'
     '                center = (0.0, 0.0, 0.0)'),
]

count = 0
for pat, repl in patterns:
    new_text, n = re.subn(pat, repl, text)
    if n > 0:
        text = new_text
        count += n
        print(f"Replaced {n} occurrences of pattern: {pat[:60]}...")

TARGET.write_text(text, encoding="utf-8")
print(f"\n=== Total replacements: {count} ===")
