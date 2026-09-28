import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import userEvent from '@testing-library/user-event'
import React, { useState } from 'react'

// Example of good testing practices - testing behavior, not implementation

// Helper to generate dynamic test content
const generateContent = () => ({
  message: `Message ${Math.floor(Math.random() * 1000)}`,
  count: Math.floor(Math.random() * 100),
  items: Array.from({ length: Math.floor(Math.random() * 10) + 1 }, (_, i) => `Item ${i + 1}`)
})

// Example component that demonstrates testable patterns
const ExampleComponent = ({ initialCount = 0 }: { initialCount?: number }) => {
  const [count, setCount] = useState(initialCount)
  const [message, setMessage] = useState('')

  return (
    <div>
      <h1>Counter: {count}</h1>
      <button onClick={() => setCount(count + 1)}>Increment</button>
      <button onClick={() => setCount(count - 1)}>Decrement</button>
      <button onClick={() => setCount(0)}>Reset</button>

      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Enter a message"
      />

      {message && <p data-testid="message-display">{message}</p>}

      {count > 0 && (
        <div data-testid="positive-indicator">Count is positive</div>
      )}

      {count < 0 && (
        <div data-testid="negative-indicator">Count is negative</div>
      )}
    </div>
  )
}

describe('Testing Best Practices Examples', () => {
  it('demonstrates component behavior testing', async () => {
    const user = userEvent.setup()
    const initialCount = Math.floor(Math.random() * 10)

    render(<ExampleComponent initialCount={initialCount} />)

    // Test behavior, not specific values
    expect(screen.getByText(`Counter: ${initialCount}`)).toBeInTheDocument()

    const incrementButton = screen.getByText('Increment')
    await user.click(incrementButton)

    // Test that the counter increased
    expect(screen.getByText(`Counter: ${initialCount + 1}`)).toBeInTheDocument()
  })

  it('demonstrates user interaction patterns', async () => {
    const user = userEvent.setup()
    render(<ExampleComponent />)

    // Test user input behavior
    const input = screen.getByPlaceholderText('Enter a message')
    const testMessage = `Test message ${Math.random()}`

    await user.type(input, testMessage)

    // Should display the entered message
    expect(screen.getByTestId('message-display')).toHaveTextContent(testMessage)
  })

  it('demonstrates conditional rendering testing', async () => {
    const user = userEvent.setup()
    render(<ExampleComponent initialCount={0} />)

    // Initially no indicators
    expect(screen.queryByTestId('positive-indicator')).not.toBeInTheDocument()
    expect(screen.queryByTestId('negative-indicator')).not.toBeInTheDocument()

    // Make count positive
    await user.click(screen.getByText('Increment'))
    expect(screen.getByTestId('positive-indicator')).toBeInTheDocument()
    expect(screen.queryByTestId('negative-indicator')).not.toBeInTheDocument()

    // Make count negative
    await user.click(screen.getByText('Reset'))
    await user.click(screen.getByText('Decrement'))
    expect(screen.queryByTestId('positive-indicator')).not.toBeInTheDocument()
    expect(screen.getByTestId('negative-indicator')).toBeInTheDocument()
  })

  it('demonstrates property-based testing patterns', () => {
    // Test with various random initial values
    const testCases = Array.from({ length: 5 }, () => Math.floor(Math.random() * 100) - 50)

    testCases.forEach(initialCount => {
      const { unmount } = render(<ExampleComponent initialCount={initialCount} />)

      // Should always display the current count
      expect(screen.getByText(`Counter: ${initialCount}`)).toBeInTheDocument()

      // Should show appropriate indicators
      if (initialCount > 0) {
        expect(screen.getByTestId('positive-indicator')).toBeInTheDocument()
      } else if (initialCount < 0) {
        expect(screen.getByTestId('negative-indicator')).toBeInTheDocument()
      }

      unmount() // Clean up between test cases
    })
  })

  it('demonstrates dynamic test data usage', () => {
    const testData = generateContent()

    // Use generated data but test behavior patterns
    expect(testData.message).toBeTruthy()
    expect(typeof testData.message).toBe('string')
    expect(testData.count).toBeGreaterThanOrEqual(0)
    expect(testData.items.length).toBeGreaterThan(0)
    expect(Array.isArray(testData.items)).toBe(true)
  })

  it('demonstrates error boundary patterns', () => {
    // Test that components handle edge cases gracefully
    const edgeCases = [
      { initialCount: Number.MAX_SAFE_INTEGER },
      { initialCount: Number.MIN_SAFE_INTEGER },
      { initialCount: 0 }
    ]

    edgeCases.forEach(({ initialCount }) => {
      expect(() => {
        render(<ExampleComponent initialCount={initialCount} />)
      }).not.toThrow()
    })
  })
})
