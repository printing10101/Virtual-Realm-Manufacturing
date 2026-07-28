import { BaseCommand } from './BaseCommand'
import type { EditableToolpathSegment } from '../types/editor'

export class ModifyFeedRateCommand extends BaseCommand {
  private segmentId: string
  private oldFeedRate: number
  private newFeedRate: number
  private targetIndex: number = -1

  constructor(
    segments: EditableToolpathSegment[],
    onUpdate: () => void,
    segmentId: string,
    newFeedRate: number,
  ) {
    super(segments, onUpdate)
    this.segmentId = segmentId
    this.newFeedRate = newFeedRate
    this.oldFeedRate = 0
  }

  execute(): void {
    this.targetIndex = this.segments.findIndex((s) => s.id === this.segmentId)
    if (this.targetIndex === -1) return
    this.oldFeedRate = this.segments[this.targetIndex].feedRate
    this.segments[this.targetIndex].feedRate = this.newFeedRate
    this.onUpdate()
  }

  undo(): void {
    if (this.targetIndex === -1) return
    this.segments[this.targetIndex].feedRate = this.oldFeedRate
    this.onUpdate()
  }

  getDescription(): string {
    return `Feed rate: ${this.oldFeedRate} → ${this.newFeedRate}`
  }
}
