import { describe, expect, it } from 'vitest'
import { fixed, integer, money, percent, signed, tableMoney } from './format'

describe('money', () => {
  it('matches the Python app for every currency form', () => {
    expect(money(1234.4, 'EUR')).toBe('€1,234')
    expect(money(1234.4, 'GBP')).toBe('£1,234')
    expect(money(1234.4, 'USD')).toBe('$1,234')
    expect(money(218, 'SEK')).toBe('218 kr')
    expect(money(102480.2, 'units')).toBe('102,480 u')
    expect(money(5, 'CHF')).toBe('5 CHF')
  })
  it('carries an explicit sign on P/L', () => {
    expect(money(1204, 'EUR', 0, true)).toBe('+€1,204')
    expect(money(-1204, 'EUR', 0, true)).toBe('-€1,204')
    expect(money(0, 'units', 0, true)).toBe('+0 u')
    expect(money(-3.5, 'SEK', 2, true)).toBe('-3.50 kr')
  })
  it('does not sign a plain amount', () => {
    expect(money(-12, 'units')).toBe('-12 u')
  })
})

describe('number formats', () => {
  it('fixed rounds half to even like Python', () => {
    expect(fixed(2.5)).toBe('2')
    expect(fixed(3.5)).toBe('4')
    expect(fixed(1234567.891, 2)).toBe('1,234,567.89')
  })
  it('signed always shows a sign', () => {
    expect(signed(4.031, 2)).toBe('+4.03')
    expect(signed(-0.004, 2)).toBe('-0.00')
    expect(signed(0)).toBe('+0')
  })
  it('integer and percent', () => {
    expect(integer(131713)).toBe('131,713')
    expect(percent(0.8661)).toBe('86.6%')
    expect(percent(0.456, 1)).toBe('45.6%')
  })
})

describe('tableMoney', () => {
  it('shows two decimals, with the euro sign for EUR', () => {
    expect(tableMoney(1234.567, 'EUR')).toBe('€1,234.57')
    expect(tableMoney(-5, 'EUR')).toBe('-€5.00')
    expect(tableMoney(1692.41528, 'units')).toBe('1,692.42')
    expect(tableMoney(-59.085, 'units')).toBe('-59.08')
    expect(tableMoney(1692.41528, 'SEK')).toBe('1,692.42')
  })
})
