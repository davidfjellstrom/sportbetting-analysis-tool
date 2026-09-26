import { describe, expect, it } from 'vitest'
import { fixed, formatMonth, integer, money, percent, signed, tableMoney } from './format'

describe('money', () => {
  it('formats every currency form', () => {
    expect(money(1234.4, 'EUR')).toBe('€1,234')
    expect(money(1234.4, 'GBP')).toBe('£1,234')
    expect(money(1234.4, 'USD')).toBe('$1,234')
    expect(money(218, 'SEK')).toBe('218 kr')
    expect(money(102480.2, 'units')).toBe('102,480.20 u')
    expect(money(5, 'CHF')).toBe('5 CHF')
  })
  it('carries an explicit sign on P/L', () => {
    expect(money(1204, 'EUR', true)).toBe('+€1,204')
    expect(money(-1204, 'EUR', true)).toBe('-€1,204')
    expect(money(0, 'units', true)).toBe('+0.00 u')
    expect(money(-3.5, 'SEK', true)).toBe('-4 kr')
  })
  it('keeps two decimals on units, so a large unit is not rounded away', () => {
    expect(money(-98 / 10, 'units', true)).toBe('-9.80 u')
  })
  it('does not sign a plain amount', () => {
    expect(money(-12, 'units')).toBe('-12.00 u')
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

describe('formatMonth', () => {
  it('names the month and year', () => {
    expect(formatMonth('2022-11-04')).toBe('November 2022')
    expect(formatMonth('2026-09-05')).toBe('September 2026')
    expect(formatMonth(null)).toBe('?')
  })
})
