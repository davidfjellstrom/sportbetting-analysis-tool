import type { LabelledKey, SliceRow } from '../api/types'
import { UNKNOWN, fixed, integer, signed, tableMoney } from '../format'
import { Help } from './Help'

export function SliceTable({
  rows,
  dimension,
  currency,
}: {
  rows: SliceRow[]
  /** What the rows are grouped by, as the API labels it. */
  dimension: LabelledKey
  currency: string
}) {
  return (
    <div className="table-scroll">
      <table className="slices">
        <thead>
          <tr>
            <th>
              {dimension.label} {dimension.help && <Help text={dimension.help} />}
            </th>
            <th className="num">Bets</th>
            <th className="num">Matches</th>
            <th className="num">
              Bets / match{' '}
              <Help text="Average number of bets per match. Bets on the same match tend to win or lose together, so a high number means the group has less to say than its bet count suggests." />
            </th>
            <th className="num">Turnover ({currency})</th>
            <th className="num">P/L ({currency})</th>
            <th className="num">
              ROI % <Help text="Profit or loss as a share of the amount staked." />
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.slice}>
              <td>{r.slice}</td>
              <td className="num">{r.bets === null ? UNKNOWN : integer(r.bets)}</td>
              <td className="num">{integer(r.fixtures)}</td>
              <td className="num">
                {r.bets_per_fixture === null ? UNKNOWN : fixed(r.bets_per_fixture, 2)}
              </td>
              <td className="num">{tableMoney(r.turnover, currency)}</td>
              <td className="num">{tableMoney(r.pl, currency)}</td>
              <td className="num">{signed(r.roi_pct, 2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
