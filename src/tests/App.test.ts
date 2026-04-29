import { describe, it, expect } from 'vitest'
import App from '../App.vue'

describe('App.vue', () => {
  it('can be imported', () => {
    expect(App).toBeDefined()
  })
  
  it('has a template', () => {
    expect(App.template || App.render).toBeDefined()
  })
})
