import type { CheckReport as Report } from '../api/types'

// The same battery for the lifetime data and for a single uploaded file: a
// new export is worth nothing until it has passed the checks the old ones
// pass. A failed check is a banner, because no figure below it can be
// trusted; a green run is a footnote, or nothing at all for the history.

export function CheckTable({ report }: { report: Report }) {
  return (
    <table className="checks">
      <thead>
        <tr>
          <th></th>
          <th>Severity</th>
          <th>Check</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {report.checks.map((c) => (
          <tr key={c.name}>
            <td className={c.passed ? '' : 'fail'}>
              {c.severity === 'INFO' ? '' : c.passed ? 'ok' : 'FAIL'}
            </td>
            <td>{c.severity}</td>
            <td>{c.name}</td>
            <td>{c.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function CheckFailureBanner({ report }: { report: Report }) {
  return (
    <div className="alert alert-error" role="alert">
      <span className="alert-icon" aria-hidden="true">
        🚨
      </span>
      <div>
        {report.n_errors} data check(s) failed — the numbers below cannot be
        trusted until this is fixed.
      </div>
    </div>
  )
}

/** Silent when green (for the history), banner + table when not. */
export function HistoryChecks({ report }: { report: Report }) {
  if (report.ok) return null
  return (
    <section className="checks-failed">
      <CheckFailureBanner report={report} />
      <CheckTable report={report} />
    </section>
  )
}
