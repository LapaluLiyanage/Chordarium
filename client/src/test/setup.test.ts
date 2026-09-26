import { expect, it } from 'vitest'

it('provides DOM matchers and requestAnimationFrame', () => {
  document.body.innerHTML = '<p>hi</p>'
  expect(document.querySelector('p')).toHaveTextContent('hi')
  expect(typeof requestAnimationFrame).toBe('function')
})
