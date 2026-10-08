import { useState } from "react";
import type { Context } from "./shared";
import { useResource, useCommand, LoadState, date } from "./shared";
import {
  productPath,
  selection,
  teamRoles,
  presetTeamRoles,
  roleNames,
} from "./product";
import type { Member, Portal } from "./product";

type Update = {
  id: string;
  username: string;
  role: string;
  note: string;
  created_at: number;
};
export default function TeamWorkspace({
  c,
  workingRole,
  approvedPortal,
}: {
  c: Context;
  workingRole?: string;
  approvedPortal?: Portal;
}) {
  const team = useResource<{ members: Member[]; account_limit: number }>(
    c.api,
    productPath(c, "team"),
    15000,
  );
  const portalRequest = useResource<Portal>(
    c.api,
    approvedPortal ? null : productPath(c, "portal"),
  );
  const portal = { data: approvedPortal || portalRequest.data };
  const updates = useResource<{ updates: Update[] }>(
    c.api,
    productPath(c, `contributions?${selection(c)}`),
    15000,
  );
  const [view, setView] = useState("all");
  const [rosterOpen, setRosterOpen] = useState(false);
  const action = useCommand();
  return (
    <>
      <details
        className="panel team-roster"
        open={rosterOpen}
        onToggle={(e) => setRosterOpen(e.currentTarget.open)}
      >
        <summary>People and access</summary>
        <p>
          Several people can hold the same role. Everyone in this workspace can
          see shared progress. Only the owner manages accounts.
        </p>
        <LoadState {...team} empty={!team.data} />
        {team.data && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Role</th>
                  <th>Access</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {team.data.members.map((m) => (
                  <tr key={m.id}>
                    <td>
                      {m.display_name}
                      <small> · {m.username}</small>
                    </td>
                    <td>
                      {m.roles.map((r) => roleNames[r] || r).join(", ")}
                      {c.workspace.role === "OWNER" &&
                        m.membership_role !== "OWNER" && (
                          <EditRoles
                            key={`${m.id}:${m.version}`}
                            c={c}
                            member={m}
                            reload={team.reload}
                          />
                        )}
                      {c.workspace.role === "OWNER" &&
                        m.membership_role !== "OWNER" && (
                          <ChangePassword
                            key={`password:${m.id}:${m.version}`}
                            c={c}
                            member={m}
                            reload={team.reload}
                          />
                        )}
                    </td>
                    <td>
                      {m.membership_role === "OWNER"
                        ? "Owner oversight"
                        : "Assigned role only"}
                    </td>
                    <td>
                      {m.active ? "Active" : "Disabled"}
                      {c.workspace.role === "OWNER" &&
                        m.membership_role !== "OWNER" && (
                          <button
                            className="secondary"
                            disabled={action.busy}
                            onClick={() =>
                              void action.run(
                                () =>
                                  c.api.command(
                                    productPath(c, `team/members/${m.id}`),
                                    {
                                      expected_version: m.version,
                                      roles: m.roles,
                                      active: !m.active,
                                    },
                                    "PATCH",
                                  ),
                                team.reload,
                              )
                            }
                          >
                            {m.active ? "Disable" : "Enable"}
                          </button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
      {c.workspace.role === "OWNER" && (
        <CreateMember
          c={c}
          reload={() => {
            setRosterOpen(true);
            team.reload();
          }}
        />
      )}
      <section className="team-handoffs">
        <h2 id="team-updates">Shared work updates</h2>
        <div className="handoff-columns">
          <div className="handoff-compose">
            <label>
              See another role's context
              <select value={view} onChange={(e) => setView(e.target.value)}>
                <option value="all">All roles</option>
                {Array.from(
                  new Set(
                    team.data?.members
                      .filter((m) => m.active)
                      .flatMap((m) => m.roles)
                      .filter((r) => r !== "OWNER") || teamRoles,
                  ),
                ).map((r) => (
                  <option value={r} key={r}>
                    {roleNames[r]}
                  </option>
                ))}
              </select>
            </label>
            {portal.data &&
              !portal.data.owner &&
              portal.data.roles.some(
                (r) => r !== "OBSERVER" && r !== "ROLE_SETUP_REQUIRED",
              ) && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = e.currentTarget;
                    const f = new FormData(form);
                    void action.run(
                      () =>
                        c.api.command(productPath(c, "contributions"), {
                          registration_id: c.registration.id,
                          period: c.period,
                          role: f.get("role"),
                          note: f.get("note"),
                        }),
                      () => {
                        updates.reload();
                        form.reset();
                      },
                    );
                  }}
                >
                  <input
                    type="hidden"
                    name="role"
                    value={workingRole || portal.data.roles[0]}
                  />
                  <p>
                    Posting as {roleNames[workingRole || portal.data.roles[0]]}
                  </p>
                  <label>
                    What changed, and what does the next person need?
                    <textarea
                      name="note"
                      required
                      minLength={1}
                      maxLength={2000}
                    />
                  </label>
                  <button disabled={action.busy}>Share update</button>
                </form>
              )}
            {action.feedback}
          </div>
          <div className="handoff-history">
            <span className="eyebrow">From your team</span>
            <LoadState {...updates} empty={!updates.data} />
            {updates.data?.updates
              .filter((u) => view === "all" || u.role === view)
              .map((u) => (
                <article className="panel" key={u.id}>
                  <strong>
                    {u.username} · {roleNames[u.role] || u.role}
                  </strong>
                  <p>{u.note}</p>
                  <small>{date(u.created_at)}</small>
                </article>
              ))}
            {updates.data &&
              !updates.data.updates.some(
                (u) => view === "all" || u.role === view,
              ) && (
                <p className="empty-history">
                  No updates in this view yet. A shared note will appear here
                  with its author and time.
                </p>
              )}
          </div>
        </div>
      </section>
    </>
  );
}
type TeamDraft = {
  id: string;
  display_name: string;
  role: string;
  username: string;
  password: string;
};
function CreateMember({ c, reload }: { c: Context; reload: () => void }) {
  const action = useCommand();
  const person = (): TeamDraft => ({
    id: crypto.randomUUID(),
    display_name: "",
    role: "CA",
    username: "",
    password: "",
  });
  const [people, setPeople] = useState<TeamDraft[]>(() => [person()]);
  const [stage, setStage] = useState<"people" | "accounts">("people");
  const [open, setOpen] = useState(false);
  const update = (id: string, field: keyof TeamDraft, value: string) => {
    setPeople((rows) =>
      rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
    );
  };
  return (
    <details
      className="panel team-formation"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Create your team</summary>
      <p>
        First add people and one role each. Then create their sign-in accounts.
        Several people can share a role.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (stage === "people") {
            setStage("accounts");
            return;
          }
          void action.run(
            () =>
              c.api.command(productPath(c, "team/setup"), {
                members: people.map((row) => ({
                  display_name: row.display_name.trim(),
                  roles: [row.role],
                  username: row.username.trim(),
                  password: row.password,
                })),
              }),
            () => {
              setPeople([person()]);
              setStage("people");
              setOpen(false);
              reload();
            },
          );
        }}
      >
        <div className="team-formation-list">
          {people.map((row, index) => (
            <fieldset key={row.id} className="team-person">
              <legend>
                {stage === "people"
                  ? `Person ${index + 1}`
                  : `${row.display_name} · ${roleNames[row.role]}`}
              </legend>
              {stage === "people" ? (
                <div className="form-grid">
                  <label>
                    Person's name
                    <input
                      value={row.display_name}
                      onChange={(e) =>
                        update(row.id, "display_name", e.target.value)
                      }
                      required
                      maxLength={100}
                      disabled={action.busy}
                    />
                  </label>
                  <label>
                    Assigned role
                    <select
                      value={row.role}
                      onChange={(e) => update(row.id, "role", e.target.value)}
                      disabled={action.busy}
                    >
                      {presetTeamRoles.map((role) => (
                        <option key={role} value={role}>
                          {roleNames[role]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ) : (
                <div className="form-grid">
                  <label>
                    Username
                    <input
                      value={row.username}
                      onChange={(e) =>
                        update(row.id, "username", e.target.value)
                      }
                      autoComplete="off"
                      required
                      minLength={1}
                      maxLength={64}

                      disabled={action.busy}
                    />
                    <small>
                      Choose any unique username. Sign-in ignores letter case.
                    </small>
                  </label>
                  <label>
                    Password for {row.display_name}
                    <input
                      type="password"
                      value={row.password}
                      onChange={(e) =>
                        update(row.id, "password", e.target.value)
                      }
                      autoComplete="new-password"
                      required
                      minLength={1}
                      maxLength={128}
                      disabled={action.busy}
                    />
                    <small>
                      Choose this person’s password. It can differ from others
                      with the same role.
                    </small>
                  </label>
                </div>
              )}
              {stage === "people" && people.length > 1 && (
                <button
                  type="button"
                  className="text-button"
                  disabled={action.busy}
                  onClick={() =>
                    setPeople((rows) =>
                      rows.filter((entry) => entry.id !== row.id),
                    )
                  }
                >
                  Remove this person
                </button>
              )}
            </fieldset>
          ))}
        </div>
        <div className="toolbar">
          {stage === "people" ? (
            <button
              type="button"
              className="secondary"
              disabled={action.busy || people.length >= 100}
              onClick={() => setPeople((rows) => [...rows, person()])}
            >
              Add another person
            </button>
          ) : (
            <button
              type="button"
              className="secondary"
              disabled={action.busy}
              onClick={() => setStage("people")}
            >
              Back to people and roles
            </button>
          )}
          <button disabled={action.busy}>
            {action.busy
              ? "Registering team…"
              : stage === "people"
                ? "Next: sign-in accounts"
                : "Register team accounts"}
          </button>
        </div>
        {stage === "accounts" && (
          <p className="caption">
            Accounts become available together after registration succeeds.
            People who are not registered cannot sign in. The configured local
            account limit still applies.
          </p>
        )}
        {action.feedback}
      </form>
    </details>
  );
}

function EditRoles({
  c,
  member,
  reload,
}: {
  c: Context;
  member: Member;
  reload: () => void;
}) {
  const [roles, setRoles] = useState(member.roles);
  const action = useCommand();
  return (
    <details>
      <summary>Change assigned role</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(
            () =>
              c.api.command(
                productPath(c, `team/members/${member.id}`),
                {
                  expected_version: member.version,
                  roles,
                  active: member.active,
                },
                "PATCH",
              ),
            reload,
          );
        }}
      >
        <fieldset>
          <legend>Assigned role for {member.display_name}</legend>
          {presetTeamRoles.map((r) => (
            <label className="check" key={r}>
              <input
                type="radio"
                name="assigned_role"
                checked={roles.includes(r)}
                onChange={() => setRoles([r])}
              />
              {roleNames[r]}
            </label>
          ))}
        </fieldset>
        <button disabled={action.busy || !roles.length}>Save role</button>
        {action.feedback}
      </form>
    </details>
  );
}

function ChangePassword({
  c,
  member,
  reload,
}: {
  c: Context;
  member: Member;
  reload: () => void;
}) {
  const action = useCommand();
  return (
    <details>
      <summary>Set this person's password</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const data = new FormData(form);
          void action.run(
            () =>
              c.api.command(
                productPath(c, `team/members/${member.id}/password`),
                {
                  expected_version: member.version,
                  password: data.get("password"),
                },
              ),
            () => {
              form.reset();
              reload();
            },
          );
        }}
      >
        <label>
          New password for {member.display_name}
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={1}
            maxLength={128}
            disabled={action.busy}
          />
        </label>
        <p className="caption">
          Only this account changes. Existing sessions for this person are
          signed out.
        </p>
        <button disabled={action.busy}>Update password</button>
        {action.feedback}
      </form>
    </details>
  );
}
