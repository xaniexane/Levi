import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { GENRE_CATEGORIES, GENRES, labelGenre } from "@/lib/levi/genres";
import { leviComplete } from "@/lib/levi/ai";
import { companionSystem } from "@/lib/levi/prompt";
import { fabricStory, localRevise } from "@/lib/levi/local";
import { craftParagraph, nextCraftBeat, PREMIUM_CASCADE } from "@/lib/levi/craft";
import { mintCharacter } from "@/lib/levi/characters";
import { catalystAllowed, shelfSummary, useLevi } from "@/lib/levi/store";

const MODES = ["void", "interrogation", "reframe", "noir", "horror", "spiral", "compress"] as const;

export function WriteView() {
  const stories = useLevi((s) => s.stories);
  const activeId = useLevi((s) => s.activeStoryId);
  const addStory = useLevi((s) => s.addStory);
  const updateStory = useLevi((s) => s.updateStory);
  const addGraphChar = useLevi((s) => s.addGraphChar);
  const persona = useLevi((s) => s.persona);
  const name = useLevi((s) => s.name);
  const goal = useLevi((s) => s.goal);
  const story = stories.find((s) => s.id === activeId) ?? stories[0];
  const [genre, setGenre] = useState("systems_horror");
  const [cat, setCat] = useState<(typeof GENRE_CATEGORIES)[number]["id"]>("signature_lattice");
  const [premise, setPremise] = useState("");
  const [busy, setBusy] = useState(false);

  const inCat = useMemo(() => GENRES.filter((g) => g.category === cat), [cat]);

  async function create() {
    if (!premise.trim() || busy) return;
    setBusy(true);
    const local = fabricStory(genre, premise.trim());
    try {
      if (!catalystAllowed()) {
        addStory({
          title: local.title,
          genre,
          premise: premise.trim(),
          body: local.body,
          characters: local.characters,
        });
        setPremise("");
        return;
      }
      const result = await leviComplete({
        data: {
          maxTokens: 1100,
          messages: [
            {
              role: "system",
              content:
                companionSystem({ name, goal, persona, shelf: shelfSummary(), mode: "write" }) +
                `\nReturn markdown with title, genre, cast, these beats in order: ${PREMIUM_CASCADE.join(" → ")}, and a 2-paragraph in-medias-res opening. Stay inside the named genre. No emoji.`,
            },
            {
              role: "user",
              content: `Write a story in ${genre} about: ${premise.trim()}`,
            },
          ],
        },
      });
      const body = result.ok && result.text ? result.text : local.body;
      addStory({
        title: extractTitle(body, local.title),
        genre,
        premise: premise.trim(),
        body,
        characters: local.characters,
      });
      setPremise("");
    } catch {
      addStory({
        title: local.title,
        genre,
        premise: premise.trim(),
        body: local.body,
        characters: local.characters,
      });
      setPremise("");
    } finally {
      setBusy(false);
    }
  }

  async function apply(kind: "expand" | "modify", extra: string) {
    if (!story || busy) return;
    setBusy(true);
    const beat = nextCraftBeat(story.modes.length);
    const lead = story.characters[0]?.name ?? "The lead";
    const wound = story.characters[0]?.need ?? "the unnamed cost";
    try {
      if (!catalystAllowed()) {
        updateStory(story.id, {
          body: `${story.body}\n\n${kind === "expand" ? craftParagraph(lead, beat, story.genre, wound) : localRevise(story.body, kind, extra)}`,
          modes: [...story.modes, `${kind}:${extra}`],
        });
        return;
      }
      const result = await leviComplete({
        data: {
          maxTokens: 900,
          messages: [
            {
              role: "system",
              content: companionSystem({
                name,
                goal,
                persona,
                shelf: shelfSummary(),
                mode: "write",
              }),
            },
            {
              role: "user",
              content: `${kind === "expand" ? "Expand the next cascade beat" : "Modify"} this ${story.genre} story.\nBeat: ${beat}\nInstruction: ${extra}\n\n${story.body.slice(0, 4000)}\n\nReturn the full updated markdown.`,
            },
          ],
        },
      });
      const next =
        result.ok && result.text
          ? result.text
          : `${story.body}\n\n${craftParagraph(lead, beat, story.genre, wound)}`;
      updateStory(story.id, {
        body: next,
        modes: [...story.modes, `${kind}:${extra}`],
      });
    } catch {
      updateStory(story.id, {
        body: `${story.body}\n\n${kind === "expand" ? craftParagraph(lead, beat, story.genre, wound) : localRevise(story.body, kind, extra)}`,
        modes: [...story.modes, `${kind}:${extra}`],
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-5 py-8">
      <p className="text-xs tracking-kicker text-muted uppercase">Write</p>
      <h1 className="mt-2 font-display text-4xl">Story fabric</h1>
      <p className="mt-2 text-sm text-muted">
        {GENRES.length} genres. Premium cascade. Characters mint into the graph.
      </p>

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <div className="flex gap-1.5 overflow-x-auto pb-2">
          {GENRE_CATEGORIES.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                setCat(c.id);
                const first = GENRES.find((g) => g.category === c.id);
                if (first) setGenre(first.id);
              }}
              className={`h-8 shrink-0 rounded-full px-3 text-xs ${
                cat === c.id ? "bg-accent text-accent-fg" : "bg-elevated text-muted"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <label className="mt-3 block text-xs text-muted">Genre</label>
        <select
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
          className="mt-1 h-11 w-full rounded-md border border-border bg-elevated px-3 text-sm text-fg"
        >
          {inCat.map((g) => (
            <option key={g.id} value={g.id}>
              {labelGenre(g.id)}
            </option>
          ))}
        </select>
        <label className="mt-3 block text-xs text-muted">Premise</label>
        <Textarea
          className="mt-1"
          rows={3}
          value={premise}
          onChange={(e) => setPremise(e.target.value)}
          placeholder="A city that bills people for dreams they have not had yet"
        />
        <Button
          className="mt-3 w-full"
          disabled={busy || !premise.trim()}
          onClick={() => void create()}
        >
          {busy ? "Composing…" : "Create story"}
        </Button>
      </div>

      {story && (
        <article className="mt-8">
          <h2 className="font-display text-2xl">{story.title}</h2>
          <p className="mt-1 text-xs text-muted">{labelGenre(story.genre)}</p>
          {story.characters.length > 0 && (
            <ul className="mt-4 grid gap-2 sm:grid-cols-3">
              {story.characters.map((c) => (
                <li key={c.name} className="rounded-md border border-border bg-surface px-3 py-2">
                  <div className="text-sm font-medium">{c.name}</div>
                  <div className="text-micro text-muted">{c.archetype}</div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap gap-1.5">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void apply("expand", "next beat")}
            >
              Next beat
            </Button>
            {MODES.map((m) => (
              <Button
                key={m}
                size="sm"
                variant="quiet"
                disabled={busy}
                onClick={() => void apply("modify", m)}
              >
                {m}
              </Button>
            ))}
            <Button
              size="sm"
              variant="quiet"
              onClick={() => addGraphChar(mintCharacter(story.title + story.premise))}
            >
              Mint to graph
            </Button>
          </div>
          <div className="mt-6 whitespace-pre-wrap text-sm leading-relaxed text-fg/90">
            {story.body}
          </div>
        </article>
      )}

      {stories.length > 1 && (
        <ul className="mt-10 space-y-2">
          {stories.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => useLevi.setState({ activeStoryId: s.id })}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-elevated ${
                  s.id === story?.id ? "border-border-strong bg-elevated" : "border-border"
                }`}
              >
                {s.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function extractTitle(body: string, fallback: string) {
  const m = body.match(/^#\s+(.+)$/m);
  return (m?.[1] || fallback).slice(0, 80);
}
