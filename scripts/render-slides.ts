// Compatibility entry point for QMDs now stored in decks/<name>/slides.qmd.
import * as path from "stdlib/path";

const projectDir = path.resolve(path.dirname(path.fromFileUrl(import.meta.url)), "..");
if (Deno.args.length === 0) {
  console.error("Usage: quarto run scripts/render-slides.ts decks/<name>/slides.qmd");
  Deno.exit(2);
}
for (const input of Deno.args) {
  const source = path.resolve(input);
  const deck = path.basename(path.dirname(source));
  const expected = path.join(projectDir, "decks", deck, "slides.qmd");
  if (source !== expected) {
    console.error(`Use the deck source: decks/<name>/slides.qmd (received ${input})`);
    Deno.exit(2);
  }
  const command = new Deno.Command("uv", {
    args: ["run", "scripts/slides.py", "build", deck],
    cwd: projectDir,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  const status = await command.spawn().status;
  if (!status.success) Deno.exit(status.code);
}
