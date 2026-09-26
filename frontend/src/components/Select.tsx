import { useEffect, useId, useRef, useState } from 'react'

export interface SelectOption {
  value: string
  label: string
}

/**
 * A dropdown styled to match the rest of the app, in place of a native
 * `<select>`. The element itself can be styled, but its open popup cannot —
 * Chrome on macOS renders it as a plain grey system list no matter what CSS
 * is applied, and other browsers each do their own thing. This follows the
 * ARIA "listbox button" pattern: the trigger owns focus and keyboard
 * handling throughout, `aria-activedescendant` tracks the highlighted
 * option, and the popup itself is never focused.
 */
export function Select({
  value,
  onChange,
  options,
  placeholder = 'Choose an option',
  ariaLabel,
  disabled,
  variant = 'default',
}: {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  ariaLabel?: string
  disabled?: boolean
  variant?: 'default' | 'inline'
}) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const rootRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listboxId = useId()

  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    function onDocMouseDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [open])

  function openList() {
    const idx = options.findIndex((o) => o.value === value)
    setActiveIndex(idx >= 0 ? idx : 0)
    setOpen(true)
  }

  useEffect(() => {
    if (open && activeIndex >= 0) {
      listRef.current
        ?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`)
        ?.scrollIntoView({ block: 'nearest' })
    }
  }, [open, activeIndex])

  function commit(index: number) {
    const option = options[index]
    if (option) onChange(option.value)
    setOpen(false)
  }

  function onTriggerKeyDown(e: React.KeyboardEvent) {
    if (disabled || options.length === 0) return
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        if (!open) openList()
        else setActiveIndex((i) => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        if (!open) openList()
        else setActiveIndex((i) => Math.max(i - 1, 0))
        break
      case 'Home':
        if (open) {
          e.preventDefault()
          setActiveIndex(0)
        }
        break
      case 'End':
        if (open) {
          e.preventDefault()
          setActiveIndex(options.length - 1)
        }
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (!open) openList()
        else commit(activeIndex)
        break
      case 'Escape':
        if (open) {
          e.preventDefault()
          setOpen(false)
        }
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  return (
    <div className={variant === 'inline' ? 'select-root select-inline' : 'select-root'} ref={rootRef}>
      <button
        type="button"
        className="select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={
          open && activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined
        }
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onTriggerKeyDown}
      >
        <span className={selected ? 'select-value' : 'select-placeholder'}>
          {selected ? selected.label : placeholder}
        </span>
        <span className="select-chevron" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <ul
          className="select-list"
          role="listbox"
          id={listboxId}
          ref={listRef}
          // Leaving the options with the mouse closes the list, as a menu does.
          onMouseLeave={() => setOpen(false)}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${listboxId}-opt-${i}`}
              data-index={i}
              role="option"
              aria-selected={o.value === value}
              className={
                'select-option' +
                (i === activeIndex ? ' active' : '') +
                (o.value === value ? ' selected' : '')
              }
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => commit(i)}
            >
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
