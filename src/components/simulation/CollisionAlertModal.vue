<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="collision-modal-overlay" @click.self="close">
        <div class="collision-modal">
          <div class="modal-header" :class="severityClass">
            <div class="header-left">
              <span class="icon">⚠</span>
              <div>
                <h3>{{ headerTitle }}</h3>
                <p class="subtitle">{{ headerSubtitle }}</p>
              </div>
            </div>
            <button class="close-btn" @click="close">&times;</button>
          </div>

          <div class="modal-body">
            <div class="summary-section">
              <div class="summary-card" v-for="card in summaryCards" :key="card.label">
                <span class="card-value">{{ card.value }}</span>
                <span class="card-label">{{ card.label }}</span>
              </div>
            </div>

            <div class="collision-list">
              <h4>碰撞事件详情</h4>
              <div
                v-for="(pos, idx) in collisionPositions"
                :key="idx"
                class="collision-item"
                @click="focusOnPosition(idx)"
              >
                <div class="collision-rank">
                  <span class="rank-number">{{ idx + 1 }}</span>
                </div>
                <div class="collision-info">
                  <div class="collision-coord">
                    <span class="coord-label">坐标</span>
                    <span class="coord-value">
                      X:{{ pos[0].toFixed(2) }} Y:{{ pos[1].toFixed(2) }} Z:{{ pos[2].toFixed(2) }}
                    </span>
                  </div>
                  <div class="collision-block" v-if="collisionSegmentIndices[idx] != null">
                    <span class="segment-label">刀位点</span>
                    <span class="segment-value">N{{ collisionSegmentIndices[idx] }}</span>
                  </div>
                </div>
                <button class="focus-btn">
                  <span>聚焦</span>
                </button>
              </div>
            </div>

            <div v-if="collisionPositions.length === 0" class="no-collision">
              <p>未检测到具体的碰撞坐标点</p>
            </div>

            <div class="model-comparison">
              <h4>碰撞前后对比</h4>
              <div class="comparison-grid">
                <div class="comparison-item before">
                  <div class="comparison-label">原始毛坯</div>
                  <div class="comparison-desc">
                    毛坯STL包围盒:
                    <span v-if="originalBbox">
                      X[{{ originalBbox.x_min?.toFixed(1) }}, {{ originalBbox.x_max?.toFixed(1) }}]
                      Y[{{ originalBbox.y_min?.toFixed(1) }}, {{ originalBbox.y_max?.toFixed(1) }}]
                      Z[{{ originalBbox.z_min?.toFixed(1) }}, {{ originalBbox.z_max?.toFixed(1) }}]
                    </span>
                    <span v-else>—</span>
                  </div>
                </div>
                <div class="comparison-item after">
                  <div class="comparison-label">仿真结果</div>
                  <div class="comparison-desc">
                    碰撞严重程度:
                    <span :class="'severity-' + collisionSeverity">
                      {{ severityLabel }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <el-button type="danger" v-if="collisionSeverity === 'critical'" @click="close">
              我知道了 - 存在严重碰撞风险
            </el-button>
            <el-button type="warning" v-else-if="collisionSeverity === 'warning'" @click="close">
              确认 - 存在潜在碰撞风险
            </el-button>
            <el-button v-else @click="close">
              关闭
            </el-button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
const props = defineProps<{
  visible: boolean
  collisionPositions: [number, number, number][]
  collisionSegmentIndices: number[]
  collisionSeverity: string
  originalBbox: Record<string, number> | null
}>()

const emit = defineEmits<{
  'close': []
  'focus-collision': [position: [number, number, number]]
}>()

const headerTitle = computed(() => {
  if (props.collisionSeverity === 'critical') return '严重碰撞警告'
  if (props.collisionSeverity === 'warning') return '碰撞风险提示'
  return '碰撞检测结果'
})

const headerSubtitle = computed(() => {
  const count = props.collisionPositions.length
  if (count === 0) return '正在进行碰撞分析...'
  return `共检测到 ${count} 个碰撞点`
})

const severityLabel = computed(() => {
  if (props.collisionSeverity === 'critical') return '严重'
  if (props.collisionSeverity === 'warning') return '警告'
  return '无风险'
})

const severityClass = computed(() => ({
  'severity-critical': props.collisionSeverity === 'critical',
  'severity-warning': props.collisionSeverity === 'warning',
  'severity-none': props.collisionSeverity === 'none',
}))

const summaryCards = computed(() => [
  {
    label: '碰撞点数',
    value: props.collisionPositions.length,
  },
  {
    label: '严重等级',
    value: severityLabel.value,
  },
  {
    label: '涉及刀位点',
    value: props.collisionSegmentIndices.length,
  },
])

function focusOnPosition(index: number): void {
  if (index < props.collisionPositions.length) {
    emit('focus-collision', props.collisionPositions[index])
  }
}

function close(): void {
  emit('close')
}
</script>

<style lang="scss" scoped>
.collision-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.collision-modal {
  width: 560px;
  max-height: 85vh;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 20px 24px;
    color: #fff;

    &.severity-critical {
      background: linear-gradient(135deg, #d32f2f, #b71c1c);
    }
    &.severity-warning {
      background: linear-gradient(135deg, #f57c00, #e65100);
    }
    &.severity-none {
      background: linear-gradient(135deg, #388e3c, #1b5e20);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 14px;

      .icon {
        font-size: 32px;
      }

      h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 700;
      }
      .subtitle {
        margin: 4px 0 0;
        font-size: 13px;
        opacity: 0.85;
      }
    }

    .close-btn {
      background: none;
      border: none;
      color: #fff;
      font-size: 28px;
      cursor: pointer;
      opacity: 0.7;
      line-height: 1;
      padding: 0 4px;

      &:hover { opacity: 1; }
    }
  }

  .modal-body {
    padding: 20px 24px;
    overflow-y: auto;
    flex: 1;

    .summary-section {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 20px;

      .summary-card {
        text-align: center;
        padding: 12px;
        background: #f5f5f5;
        border-radius: 8px;

        .card-value {
          display: block;
          font-size: 22px;
          font-weight: 700;
          color: #333;
        }
        .card-label {
          display: block;
          font-size: 11px;
          color: #888;
          margin-top: 4px;
        }
      }
    }

    .collision-list {
      h4 {
        margin: 0 0 12px;
        font-size: 14px;
        color: #333;
      }

      .collision-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        background: #fafafa;
        border: 1px solid #eee;
        border-radius: 8px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s;

        &:hover {
          background: #fff3f3;
          border-color: #ffcdd2;
        }

        .collision-rank {
          .rank-number {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #ff5252;
            color: #fff;
            font-size: 13px;
            font-weight: 600;
          }
        }

        .collision-info {
          flex: 1;
          min-width: 0;

          .collision-coord {
            margin-bottom: 2px;

            .coord-label {
              font-size: 10px;
              color: #999;
              margin-right: 6px;
            }
            .coord-value {
              font-size: 12px;
              font-family: monospace;
              color: #555;
            }
          }

          .collision-block {
            .segment-label {
              font-size: 10px;
              color: #999;
              margin-right: 6px;
            }
            .segment-value {
              font-size: 12px;
              font-weight: 600;
              color: #d32f2f;
            }
          }
        }

        .focus-btn {
          padding: 4px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          background: #fff;
          font-size: 11px;
          color: #666;
          cursor: pointer;
          transition: all 0.2s;

          &:hover {
            border-color: #ff5252;
            color: #d32f2f;
            background: #fff5f5;
          }
        }
      }
    }

    .no-collision {
      text-align: center;
      padding: 20px;
      color: #999;
      font-size: 13px;
    }

    .model-comparison {
      margin-top: 20px;

      h4 {
        margin: 0 0 12px;
        font-size: 14px;
        color: #333;
      }

      .comparison-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;

        .comparison-item {
          padding: 12px;
          border-radius: 8px;
          border: 1px solid #eee;

          &.before {
            background: #f5f5f5;
            .comparison-label { color: #888; }
          }
          &.after {
            background: #fff3e0;
            .comparison-label { color: #e65100; }
          }

          .comparison-label {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
          }
          .comparison-desc {
            font-size: 11px;
            color: #666;
            line-height: 1.5;

            .severity-critical { color: #d32f2f; font-weight: 600; }
            .severity-warning { color: #f57c00; font-weight: 600; }
            .severity-none { color: #388e3c; }
          }
        }
      }
    }
  }

  .modal-footer {
    padding: 16px 24px;
    border-top: 1px solid #eee;
    display: flex;
    justify-content: flex-end;
  }
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s ease;

  .collision-modal {
    transition: transform 0.25s ease;
  }
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;

  .collision-modal {
    transform: scale(0.95) translateY(10px);
  }
}
</style>
