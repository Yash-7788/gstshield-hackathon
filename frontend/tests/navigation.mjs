export async function openSection(page, name) {
  const nav = page.getByRole("navigation", {
    name: "Workspace sections",
    exact: true,
  });
  const link = nav.getByRole("link", { name, exact: true });
  if (!(await link.isVisible()))
    await nav.getByRole("button", { name: "More tools", exact: true }).click();
  await link.click({ timeout: 15000 });
}
