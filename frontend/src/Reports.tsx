import { useEffect, useRef, useState } from "react";

import type { Schemas } from "./contracts";

import {
  Badge,
  Field,
  Facts,
  LoadState,
  Notice,
  date,
  path,
  useCommand,
  useResource,
  values,
  writable,
} from "./shared";

import type { Context } from "./shared";

export default function Reports({ c }: { c: Context }) {
  const [cursor, setCursor] = useState("");
  const [id, setId] = useState("");
  const [kind, setKind] =
    useState<Schemas["ArtifactCreate"]["kind"]>("RECONCILIATION_PDF");
  const [historical, setHistorical] = useState(false);
  const action = useCommand();
  const downloadScope = useRef(new AbortController());
  useEffect(() => {
    downloadScope.current = new AbortController();
    return () => downloadScope.current.abort();
  }, []);

  const list = useResource<Schemas["ArtifactListData"]>(
    c.api,
    path(
      c,
      `artifacts?limit=20&registration_id=${c.registration.id}&period=${c.period}${cursor ? `&cursor=${cursor}` : ""}`,
    ),
  );

  const endpoint =
    kind === "RECONCILIATION_PDF"
      ? "runs"
      : kind === "EVIDENCE_PDF"
        ? "cases"
        : kind === "PROPOSAL_CSV"
          ? "proposals"
          : "imports";

  const [sourceCursor, setSourceCursor] = useState("");

  const sources = useResource<{
    runs?: Schemas["RunData"][];
    cases?: Schemas["CaseData"][];
    proposals?: Schemas["ProposalData"][];
    imports?: Schemas["ImportData"][];
    next_cursor: string | null;
  }>(
    c.api,
    path(
      c,
      `${endpoint}?registration_id=${c.registration.id}&period=${c.period}&limit=20${sourceCursor ? `&cursor=${sourceCursor}` : ""}`,
    ),
  );

  const candidates = sources.data
    ? sources.data[endpoint as "runs"] ||
      sources.data.cases ||
      sources.data.proposals ||
      sources.data.imports ||
      []
    : [];

  const detail = useResource<Schemas["ArtifactData"]>(
    c.api,
    id ? path(c, `artifacts/${id}`) : null,
    true,
  );
  const item = detail.data;

  return (
    <>
      <p>
        Generate private reports from frozen recorded evidence. Reports are not
        filed returns or guaranteed credit recovery.
      </p>
      {writable(c) && (
        <details>
          <summary>Generate a report</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const v = values(e.currentTarget);
              const source = candidates.find((x) => x.id === v.source);
              if (!source) return;
              void action.run(
                () =>
                  c.api.command<Schemas["ArtifactData"]>(path(c, "artifacts"), {
                    kind,
                    source_id: source.id,
                    expected_version: source.version,
                    selected_result_ids: v.results
                      ? v.results
                          .split(",")
                          .map((x) => x.trim())
                          .filter(Boolean)
                      : [],
                  }),
                (data) => {
                  setId(data.id);
                  list.reload();
                  setHistorical(false);
                },
              );
            }}
          >
            <label>
              Report kind
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as typeof kind);
                  setSourceCursor("");
                }}
              >
                <option value="RECONCILIATION_PDF">Reconciliation PDF</option>
                <option value="EVIDENCE_PDF">Evidence case PDF</option>
                <option value="PROPOSAL_CSV">
                  Approved payment proposal CSV
                </option>
                <option value="ROW_ERRORS_CSV">Source row errors CSV</option>
              </select>
            </label>
            <LoadState {...sources} empty={false} />
            <label>
              Recorded source
              <select name="source" required>
                <option value="">Choose source</option>
                {candidates.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.id.slice(0, 8)} · {x.state}
                  </option>
                ))}
              </select>
            </label>
            {kind === "RECONCILIATION_PDF" && (
              <Field name="results" maxLength={8000}>
                Optional result IDs, comma separated (default first 200 rows)
              </Field>
            )}
            <div className="controls">
              <button
                type="button"
                disabled={!sourceCursor}
                onClick={() => setSourceCursor("")}
              >
                First report sources
              </button>
              <button
                type="button"
                disabled={!sources.data?.next_cursor}
                onClick={() => setSourceCursor(sources.data!.next_cursor!)}
              >
                Next report sources
              </button>
            </div>
            <button
              disabled={action.busy || sources.loading || !candidates.length}
            >
              Generate private report
            </button>
          </form>
        </details>
      )}

      <button className="secondary" onClick={list.reload}>
        Refresh reports
      </button>
      <LoadState {...list} empty={!list.data?.artifacts.length} />
      {list.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Private reports table"
          >
            <table>
              <thead>
                <tr>
                  <th>Report</th>
                  <th>State</th>
                  <th>Expires</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {list.data.artifacts.map((x) => (
                  <tr key={x.id}>
                    <td>
                      {x.kind} · {x.id.slice(0, 8)}
                    </td>
                    <td>
                      <Badge value={x.state} />
                    </td>
                    <td>{date(x.expires_at)}</td>
                    <td>
                      <button
                        onClick={() => {
                          setId(x.id);
                          setHistorical(false);
                        }}
                      >
                        Open report
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="controls">
            <button disabled={!cursor} onClick={() => setCursor("")}>
              First reports
            </button>
            <button
              disabled={!list.data.next_cursor}
              onClick={() => setCursor(list.data!.next_cursor!)}
            >
              Next reports
            </button>
          </div>
        </>
      )}

      <details>
        <summary>Find a report by its saved ID</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setId(values(e.currentTarget).id);
            setHistorical(false);
          }}
        >
          <Field
            name="id"
            required
            maxLength={36}
            pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
          >
            Report ID
          </Field>
          <button>Find report</button>
        </form>
      </details>
      <LoadState {...detail} empty={false} />
      {item && (
        <article>
          <h2>{item.kind.replaceAll("_", " ")}</h2>
          <Badge value={item.state} />
          <button className="secondary" onClick={detail.reload}>
            Refresh report status
          </button>
          <Badge value={item.provenance} />
          <Facts
            values={{
              report_id: item.id,
              source_id: item.source_id,
              size_bytes: item.size_bytes,
              expires: date(item.expires_at),
              error_code: item.error_code,
            }}
          />
          {!item.sources_current && (
            <Notice error>
              Source evidence changed. This is a historical snapshot.
            </Notice>
          )}
          {!item.sources_current && item.kind !== "PROPOSAL_CSV" && (
            <label className="check">
              <input
                type="checkbox"
                checked={historical}
                onChange={(e) => setHistorical(e.target.checked)}
              />
              I explicitly want the historical evidence report
            </label>
          )}
          <button
            disabled={
              action.busy ||
              detail.loading ||
              item.state !== "READY" ||
              (!item.sources_current &&
                (!historical || item.kind === "PROPOSAL_CSV"))
            }
            onClick={() =>
              void action.run(
                () =>
                  c.api.download(
                    path(
                      c,
                      `artifacts/${item.id}/download${historical ? "?historical=true" : ""}`,
                    ),
                    item.filename,
                    downloadScope.current.signal,
                  ),
                undefined,
                "Download prepared.",
              )
            }
          >
            Download private report
          </button>
        </article>
      )}

      {c.workspace.role === "OWNER" && (
        <details>
          <summary>Remove expired report content</summary>
          <p>
            This removes expired generated content only. It retains recorded
            evidence and report history.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(
                () =>
                  c.api.command(path(c, "artifacts/cleanup"), {
                    expired_only: true,
                  }),
                () => {
                  detail.reload();
                  list.reload();
                },
              );
            }}
          >
            <label className="check">
              <input type="checkbox" required />
              Confirm cleanup of expired generated content
            </label>
            <button disabled={action.busy}>Clean expired reports</button>
          </form>
        </details>
      )}
      {action.feedback}
    </>
  );
}
