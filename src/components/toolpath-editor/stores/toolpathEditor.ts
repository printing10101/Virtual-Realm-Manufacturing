import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { EditableToolpathSegment, GCodeController } from '../types/editor'
import { CommandHistory } from '../commands/CommandHistory'
import { DeleteSegmentCommand } from '../commands/DeleteSegmentCommand'
import { ModifyFeedRateCommand } from '../commands/ModifyFeedRateCommand'
import { parseGCodeText, exportGCodeText, validateGCodeExport } from '../composables/useGCodeParser'
import type { ToolpathSegmentData } from '@/types'

export const useToolpathEditorStore = defineStore('toolpathEditor', () => {
  const segments = ref<EditableToolpathSegment[]>([])
  const originalSegments = ref<EditableToolpathSegment[]>([])
  const selectedSegmentId = ref<string | null>(null)
  const hoveredSegmentId = ref<string | null>(null)

  const history = new CommandHistory(50)
  const undoCount = ref(0)
  const redoCount = ref(0)
  const canUndo = ref(false)
  const canRedo = ref(false)

  function _syncHistoryState(): void {
    undoCount.value = history.getUndoCount()
    redoCount.value = history.getRedoCount()
    canUndo.value = history.canUndo()
    canRedo.value = history.canRedo()
  }

  const activeSegments = computed(() => segments.value.filter((s) => !s.isDeleted))

  const isDirty = computed(() => {
    if (segments.value.length !== originalSegments.value.length) return true
    return JSON.stringify(segments.value) !== JSON.stringify(originalSegments.value)
  })

  function loadSegments(data: ToolpathSegmentData[]): void {
    const converted: EditableToolpathSegment[] = data.map((seg, i) => ({
      id: `seg-${i}-${Date.now()}`,
      type: seg.type,
      startPoint: [...seg.start_point] as [number, number, number],
      endPoint: [...seg.end_point] as [number, number, number],
      feedRate: 500,
      spindleSpeed: 8000,
      toolId: 1,
      blockNumber: seg.block_number,
      gCode: seg.g_code,
      isDeleted: false,
    }))
    segments.value = converted
    originalSegments.value = JSON.parse(JSON.stringify(converted))
    history.clear()
    _syncHistoryState()
    selectedSegmentId.value = null
    hoveredSegmentId.value = null
  }

  function loadGCode(gcodeText: string): { success: boolean; message: string } {
    try {
      const parsed = parseGCodeText(gcodeText)
      if (parsed.length === 0) {
        return { success: false, message: 'No valid G-code commands found' }
      }
      segments.value = parsed
      originalSegments.value = JSON.parse(JSON.stringify(parsed))
      history.clear()
      _syncHistoryState()
      selectedSegmentId.value = null
      hoveredSegmentId.value = null
      return { success: true, message: `Loaded ${parsed.length} segments` }
    } catch (e: any) {
      return { success: false, message: e.message || 'Failed to parse G-code' }
    }
  }

  function deleteSegment(segmentId: string): void {
    const onUpdate = () => {}
    const cmd = new DeleteSegmentCommand(segments.value, onUpdate, segmentId)
    history.execute(cmd)
    _syncHistoryState()
  }

  function modifyFeedRate(segmentId: string, newFeedRate: number): void {
    const onUpdate = () => {}
    const cmd = new ModifyFeedRateCommand(segments.value, onUpdate, segmentId, newFeedRate)
    history.execute(cmd)
    _syncHistoryState()
  }

  function undo(): void {
    history.undo()
    _syncHistoryState()
  }

  function redo(): void {
    history.redo()
    _syncHistoryState()
  }

  function exportGCode(controller: GCodeController = 'fanuc', programNumber: number = 1): {
    gcode: string
    validation: ReturnType<typeof validateGCodeExport>
  } {
    const validation = validateGCodeExport(segments.value)
    const gcode = exportGCodeText(segments.value, controller, programNumber)
    return { gcode, validation }
  }

  function reset(): void {
    segments.value = []
    originalSegments.value = []
    selectedSegmentId.value = null
    hoveredSegmentId.value = null
    history.clear()
    _syncHistoryState()
  }

  return {
    segments,
    originalSegments,
    selectedSegmentId,
    hoveredSegmentId,
    activeSegments,
    isDirty,
    canUndo,
    canRedo,
    undoCount,
    redoCount,
    loadSegments,
    loadGCode,
    deleteSegment,
    modifyFeedRate,
    undo,
    redo,
    exportGCode,
    reset,
  }
})
