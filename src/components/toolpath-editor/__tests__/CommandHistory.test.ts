import { describe, it, expect, beforeEach } from 'vitest'
import { CommandHistory } from '../commands/CommandHistory'
import { BaseCommand, type Command } from '../commands/BaseCommand'
import type { EditableToolpathSegment } from '../types/editor'

function makeSegment(id: string): EditableToolpathSegment {
  return {
    id,
    type: 'linear',
    startPoint: [0, 0, 0],
    endPoint: [10, 10, 0],
    feedRate: 500,
    spindleSpeed: 8000,
    toolId: 1,
    blockNumber: 1,
    gCode: 'G01 X10 Y10',
    isDeleted: false,
  }
}

class TestCommand extends BaseCommand {
  private action: string
  constructor(segments: EditableToolpathSegment[], onUpdate: () => void, action: string) {
    super(segments, onUpdate)
    this.action = action
  }
  execute(): void {
    this.segments.push(makeSegment(`test-${this.action}`))
    this.onUpdate()
  }
  undo(): void {
    this.segments.pop()
    this.onUpdate()
  }
  getDescription(): string {
    return `Test: ${this.action}`
  }
}

describe('CommandHistory', () => {
  let history: CommandHistory
  let segments: EditableToolpathSegment[]
  let updateCount: number

  beforeEach(() => {
    history = new CommandHistory(50)
    segments = []
    updateCount = 0
  })

  function onUpdate() {
    updateCount++
  }

  describe('execute', () => {
    it('should execute command and push to undo stack', () => {
      const cmd = new TestCommand(segments, onUpdate, 'add1')
      history.execute(cmd)

      expect(segments.length).toBe(1)
      expect(segments[0].id).toBe('test-add1')
      expect(history.canUndo()).toBe(true)
      expect(history.canRedo()).toBe(false)
      expect(updateCount).toBe(1)
    })

    it('should clear redo stack on new execute', () => {
      const cmd1 = new TestCommand(segments, onUpdate, 'add1')
      history.execute(cmd1)
      history.undo()

      const cmd2 = new TestCommand(segments, onUpdate, 'add2')
      history.execute(cmd2)

      expect(history.canRedo()).toBe(false)
    })
  })

  describe('undo', () => {
    it('should undo last executed command', () => {
      const cmd = new TestCommand(segments, onUpdate, 'add1')
      history.execute(cmd)

      const result = history.undo()
      expect(result).toBe(true)
      expect(segments.length).toBe(0)
      expect(history.canUndo()).toBe(false)
      expect(history.canRedo()).toBe(true)
      expect(updateCount).toBe(2)
    })

    it('should return false when undo stack is empty', () => {
      const result = history.undo()
      expect(result).toBe(false)
    })
  })

  describe('redo', () => {
    it('should redo after undo', () => {
      const cmd = new TestCommand(segments, onUpdate, 'add1')
      history.execute(cmd)
      history.undo()

      const result = history.redo()
      expect(result).toBe(true)
      expect(segments.length).toBe(1)
      expect(history.canUndo()).toBe(true)
      expect(history.canRedo()).toBe(false)
      expect(updateCount).toBe(3)
    })

    it('should return false when redo stack is empty', () => {
      const result = history.redo()
      expect(result).toBe(false)
    })
  })

  describe('max size', () => {
    it('should discard oldest commands when exceeding max size', () => {
      const smallHistory = new CommandHistory(3)
      for (let i = 0; i < 5; i++) {
        const cmd = new TestCommand(segments, onUpdate, `add${i}`)
        smallHistory.execute(cmd)
      }

      expect(smallHistory.getUndoCount()).toBe(3)
      expect(segments.length).toBe(5)

      for (let i = 0; i < 3; i++) {
        smallHistory.undo()
      }

      expect(segments.length).toBe(2)
      expect(smallHistory.canUndo()).toBe(false)
    })
  })

  describe('getDescriptions', () => {
    it('should list undo stack descriptions', () => {
      const cmd1 = new TestCommand(segments, onUpdate, 'cmd1')
      const cmd2 = new TestCommand(segments, onUpdate, 'cmd2')
      history.execute(cmd1)
      history.execute(cmd2)

      const descs = history.getUndoDescriptions()
      expect(descs).toEqual(['Test: cmd1', 'Test: cmd2'])
    })
  })

  describe('clear', () => {
    it('should clear all stacks', () => {
      const cmd = new TestCommand(segments, onUpdate, 'add1')
      history.execute(cmd)
      history.clear()

      expect(history.canUndo()).toBe(false)
      expect(history.canRedo()).toBe(false)
      expect(history.getUndoCount()).toBe(0)
    })
  })
})
