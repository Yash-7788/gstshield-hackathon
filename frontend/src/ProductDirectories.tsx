import { useState } from "react";
import type { Context } from "./shared";
import { useResource, LoadState, label } from "./shared";
import { productPath, selection } from "./product";
type Scheme = {
  id: string;
  name: string;
  purpose: string;
  source: string;
  conditions: string[];
  interest: string;
  limit: string;
  status: string;
  missing_data: string[];
};
export function Schemes({ c }: { c: Context }) {
  const [open, setOpen] = useState(false);
  const result = useResource<{ checked_on: string; schemes: Scheme[] }>(
    c.api,
    open ? productPath(c, `schemes?${selection(c)}`) : null,
  );
  return (
    <details className="panel" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Government finance schemes to discuss with your lender</summary>
      {open && (
        <>
          <p>
            A directory of possible routes, not an approval or guaranteed
            interest rate.
          </p>
          <LoadState {...result} empty={!result.data} />
          {result.data && (
            <>
              <p>
                Sources checked: {result.data.checked_on}. Recheck current terms
                before applying.
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Scheme</th>
                      <th>What it offers</th>
                      <th>Conditions and limits</th>
                      <th>What is still needed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.schemes.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <a href={s.source} target="_blank" rel="noreferrer">
                            {s.name}
                          </a>
                        </td>
                        <td>
                          {s.purpose}
                          <p>{s.interest}</p>
                        </td>
                        <td>
                          {s.limit}
                          <ul>
                            {s.conditions.map((x) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ul>
                        </td>
                        <td>
                          {label(s.status)}
                          <ul>
                            {s.missing_data.map((x) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </details>
  );
}
export function Competitors({ c }: { c: Context }) {
  const [open, setOpen] = useState(false);
  const data = useResource<{
    framing: string;
    columns: string[];
    rows: Record<string, string>[];
    status: string;
  }>(c.api, open ? productPath(c, "competitors") : null);
  return (
    <details className="panel" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>What connects this workflow?</summary>
      {open && (
        <>
          <LoadState {...data} empty={!data.data} />
          {data.data && (
            <>
              <p>{data.data.framing}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Capability</th>
                      {data.data.columns.map((x) => (
                        <th key={x}>{x}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.data.rows.map((row) => (
                      <tr key={row.capability}>
                        <td>{row.capability}</td>
                        {data.data!.columns.map((x) => (
                          <td key={x}>
                            {row[x] === "OWNER_TO_FILL"
                              ? "Facts to verify"
                              : row[x]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>{data.data.status}</p>
            </>
          )}
        </>
      )}
    </details>
  );
}
