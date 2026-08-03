import re

path = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\src\views\TaskBoard.vue"
src = open(path, 'r', encoding='utf-8').read()

# 1) Add import
src = src.replace(
    "import { useTasksStore, type TaskInfo } from '@/stores/tasks'",
    "import { useTasksStore, type TaskInfo } from '@/stores/tasks'\nimport TaskCard from '@/components/task_board/TaskCard.vue'",
    1
)

# 2) Replace kanban inline card (the full div block) with <TaskCard>
# Strategy: find the outer div that starts the card and replace it with component
old_card_start = '              <div\n                v-for="task in column.items"\n                :key="task.job_id"\n                class="task-card"\n                :class="`priority-${mapPriority(task)}`"\n                @click="openDetail(task)"\n              >'
old_card_end = '              </div>\n              <div\n                v-if="column.items.length === 0"'

idx_start = src.index(old_card_start)
idx_end = src.index(old_card_end, idx_start)

new_card = '''              <TaskCard
                v-for="task in column.items"
                :key="task.job_id"
                :task="task"
                :param-desc="getParamDesc(task)"
                :priority="mapPriority(task)"
                @click="openDetail(task)"
              />
'''

src = src[:idx_start] + new_card + src[idx_end:]

open(path, 'w', encoding='utf-8').write(src)
print(f"OK, replaced {idx_end - idx_start} chars")
