import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ProjectMeta } from '@/types/persistence'
import { getProjects, createProject, deleteProject } from '@/services/project'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<ProjectMeta[]>([])
  const currentProject = ref<ProjectMeta | null>(null)

  const loadProjects = async () => {
    try {
      projects.value = await getProjects()
    } catch (error) {
      console.error('Failed to load projects:', error)
    }
  }

  const createProjectFn = async (name: string, desc: string) => {
    const project = await createProject(name, desc)
    projects.value.push(project)
    return project
  }

  const deleteProjectFn = async (id: string) => {
    await deleteProject(id)
    projects.value = projects.value.filter(p => p.id !== id)
    if (currentProject.value?.id === id) {
      currentProject.value = null
    }
  }

  const selectProject = (project: ProjectMeta) => {
    currentProject.value = project
  }

  return {
    projects,
    currentProject,
    loadProjects,
    createProject: createProjectFn,
    deleteProject: deleteProjectFn,
    selectProject
  }
})
