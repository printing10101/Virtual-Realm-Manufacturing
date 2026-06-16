import { describe, it, expect } from 'vitest'
import { exampleProjects, getCategories, getDifficulties, getAllTags } from '../src/examples/data'
import type { ExampleProject, ExampleCategory, ExampleDifficulty } from '../src/examples/types'

describe('Example Gallery Data', () => {
  it('应该提供至少10个示例工程', () => {
    expect(exampleProjects.length).toBeGreaterThanOrEqual(10)
  })

  it('每个示例工程都应该包含必需的字段', () => {
    exampleProjects.forEach((project: ExampleProject) => {
      expect(project.id).toBeDefined()
      expect(project.name).toBeDefined()
      expect(project.description).toBeDefined()
      expect(project.details).toBeDefined()
      expect(project.category).toBeDefined()
      expect(project.difficulty).toBeDefined()
      expect(project.tags).toBeDefined()
      expect(project.tags.length).toBeGreaterThan(0)
      expect(project.code).toBeDefined()
      expect(project.language).toBeDefined()
      expect(project.useCases).toBeDefined()
      expect(project.useCases.length).toBeGreaterThan(0)
      expect(project.createdAt).toBeDefined()
      expect(project.updatedAt).toBeDefined()
      expect(project.downloadCount).toBeDefined()
    })
  })

  it('示例工程的ID应该是唯一的', () => {
    const ids = exampleProjects.map(p => p.id)
    const uniqueIds = new Set(ids)
    expect(uniqueIds.size).toBe(ids.length)
  })

  it('示例工程的名称应该是唯一的', () => {
    const names = exampleProjects.map(p => p.name)
    const uniqueNames = new Set(names)
    expect(uniqueNames.size).toBe(names.length)
  })

  it('应该覆盖所有分类', () => {
    const categories = new Set(exampleProjects.map(p => p.category))
    expect(categories.has('basic')).toBe(true)
    expect(categories.has('modeling')).toBe(true)
    expect(categories.has('toolpath')).toBe(true)
    expect(categories.has('simulation')).toBe(true)
    expect(categories.has('ai')).toBe(true)
    expect(categories.has('advanced')).toBe(true)
  })

  it('应该覆盖所有难度级别', () => {
    const difficulties = new Set(exampleProjects.map(p => p.difficulty))
    expect(difficulties.has('beginner')).toBe(true)
    expect(difficulties.has('intermediate')).toBe(true)
    expect(difficulties.has('advanced')).toBe(true)
  })

  it('每个分类应该至少有一个示例', () => {
    const categories: ExampleCategory[] = ['basic', 'modeling', 'toolpath', 'simulation', 'ai', 'advanced']
    
    categories.forEach(category => {
      const count = exampleProjects.filter(p => p.category === category).length
      expect(count).toBeGreaterThan(0)
    })
  })

  it('每个难度级别应该至少有一个示例', () => {
    const difficulties: ExampleDifficulty[] = ['beginner', 'intermediate', 'advanced']
    
    difficulties.forEach(difficulty => {
      const count = exampleProjects.filter(p => p.difficulty === difficulty).length
      expect(count).toBeGreaterThan(0)
    })
  })

  it('代码示例应该是有效的字符串', () => {
    exampleProjects.forEach(project => {
      expect(typeof project.code).toBe('string')
      expect(project.code.length).toBeGreaterThan(0)
    })
  })

  it('详细说明应该包含Markdown格式', () => {
    exampleProjects.forEach(project => {
      expect(typeof project.details).toBe('string')
      expect(project.details.length).toBeGreaterThan(0)
      // 检查是否包含Markdown标记
      expect(project.details).toMatch(/[#*`]/)
    })
  })

  it('使用场景应该是字符串数组', () => {
    exampleProjects.forEach(project => {
      expect(Array.isArray(project.useCases)).toBe(true)
      project.useCases.forEach(useCase => {
        expect(typeof useCase).toBe('string')
        expect(useCase.length).toBeGreaterThan(0)
      })
    })
  })

  it('标签应该是字符串数组', () => {
    exampleProjects.forEach(project => {
      expect(Array.isArray(project.tags)).toBe(true)
      project.tags.forEach(tag => {
        expect(typeof tag).toBe('string')
        expect(tag.length).toBeGreaterThan(0)
      })
    })
  })

  it('日期格式应该是有效的', () => {
    exampleProjects.forEach(project => {
      const createdAt = new Date(project.createdAt)
      const updatedAt = new Date(project.updatedAt)
      
      expect(createdAt.toString()).not.toBe('Invalid Date')
      expect(updatedAt.toString()).not.toBe('Invalid Date')
      expect(updatedAt.getTime()).toBeGreaterThanOrEqual(createdAt.getTime())
    })
  })

  it('下载次数应该是非负数', () => {
    exampleProjects.forEach(project => {
      expect(project.downloadCount).toBeGreaterThanOrEqual(0)
      expect(Number.isInteger(project.downloadCount)).toBe(true)
    })
  })

  it('应该提供分类列表', () => {
    const categories = getCategories()
    expect(Array.isArray(categories)).toBe(true)
    expect(categories.length).toBeGreaterThan(0)
    
    categories.forEach(cat => {
      expect(cat.value).toBeDefined()
      expect(cat.label).toBeDefined()
      expect(typeof cat.value).toBe('string')
      expect(typeof cat.label).toBe('string')
    })

    // 应该包含"全部分类"选项
    expect(categories.find(c => c.value === 'all')).toBeDefined()
  })

  it('应该提供难度级别列表', () => {
    const difficulties = getDifficulties()
    expect(Array.isArray(difficulties)).toBe(true)
    expect(difficulties.length).toBeGreaterThan(0)
    
    difficulties.forEach(diff => {
      expect(diff.value).toBeDefined()
      expect(diff.label).toBeDefined()
      expect(typeof diff.value).toBe('string')
      expect(typeof diff.label).toBe('string')
    })

    // 应该包含"全部难度"选项
    expect(difficulties.find(d => d.value === 'all')).toBeDefined()
  })

  it('应该提供所有标签列表', () => {
    const tags = getAllTags()
    expect(Array.isArray(tags)).toBe(true)
    expect(tags.length).toBeGreaterThan(0)
    
    tags.forEach(tag => {
      expect(typeof tag).toBe('string')
      expect(tag.length).toBeGreaterThan(0)
    })

    // 标签应该是唯一的
    const uniqueTags = new Set(tags)
    expect(uniqueTags.size).toBe(tags.length)

    // 标签应该是排序的
    const sortedTags = [...tags].sort()
    expect(tags).toEqual(sortedTags)
  })

  it('所有标签都应该在标签列表中', () => {
    const allTags = getAllTags()
    
    exampleProjects.forEach(project => {
      project.tags.forEach(tag => {
        expect(allTags).toContain(tag)
      })
    })
  })

  it('示例工程应该包含实际业务场景', () => {
    // 检查是否包含常见的制造业场景
    const scenarios = [
      '铣削',
      '车削',
      '仿真',
      'AI',
      '装配',
      '工具路径',
      '3D打印',
      '参数化'
    ]

    const allText = exampleProjects
      .map(p => `${p.name} ${p.description} ${p.tags.join(' ')}`)
      .join(' ')

    scenarios.forEach(scenario => {
      expect(allText).toContain(scenario)
    })
  })

  it('代码示例应该包含注释', () => {
    exampleProjects.forEach(project => {
      // 检查是否包含注释（// 或 # 或 /*）
      const hasComment = /\/\/|#|\/\*/.test(project.code)
      expect(hasComment).toBe(true)
    })
  })

  it('代码示例应该包含实际的可执行代码', () => {
    exampleProjects.forEach(project => {
      // 检查是否包含函数调用、变量声明等
      const hasCode = /(const|let|var|function|=>|\.|\()/i.test(project.code)
      expect(hasCode).toBe(true)
    })
  })

  it('基础示例应该适合初学者', () => {
    const basicExamples = exampleProjects.filter(p => p.category === 'basic')
    
    basicExamples.forEach(example => {
      // 基础示例的难度应该是入门级
      expect(example.difficulty).toBe('beginner')
    })
  })

  it('高级示例应该包含复杂功能', () => {
    const advancedExamples = exampleProjects.filter(p => p.difficulty === 'advanced')
    
    advancedExamples.forEach(example => {
      // 高级示例的代码应该更长
      expect(example.code.length).toBeGreaterThan(500)
      // 应该有多个使用场景
      expect(example.useCases.length).toBeGreaterThanOrEqual(3)
    })
  })

  it('工具路径示例应该包含CNC相关内容', () => {
    const toolpathExamples = exampleProjects.filter(p => p.category === 'toolpath')
    
    toolpathExamples.forEach(example => {
      const hasCNCContent = /G代码|CNC|铣削|刀具|切削/.test(
        `${example.name} ${example.description} ${example.tags.join(' ')}`
      )
      expect(hasCNCContent).toBe(true)
    })
  })

  it('AI示例应该包含人工智能相关内容', () => {
    const aiExamples = exampleProjects.filter(p => p.category === 'ai')
    
    aiExamples.forEach(example => {
      const hasAIContent = /AI|人工智能|识别|自动化|智能/.test(
        `${example.name} ${example.description} ${example.tags.join(' ')}`
      )
      expect(hasAIContent).toBe(true)
    })
  })

  it('仿真示例应该包含物理模拟相关内容', () => {
    const simulationExamples = exampleProjects.filter(p => p.category === 'simulation')
    
    simulationExamples.forEach(example => {
      const hasSimulationContent = /仿真|模拟|热力|切削力|颤振/.test(
        `${example.name} ${example.description} ${example.tags.join(' ')}`
      )
      expect(hasSimulationContent).toBe(true)
    })
  })
})
