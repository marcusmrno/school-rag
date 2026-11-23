"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type Citation = {
  n: number;
  chunk_id: number;
  title: string;
  location: string;
  course: string;
  source_url: string | null;
  excerpt: string;
};

type Retrieved = {
  chunk_id: number;
  title: string;
  location: string;
  vector_rank: number | null;
  vector_score: number | null;
  keyword_rank: number | null;
  keyword_score: number | null;
  rrf: number;
  rerank: number | null;
};

type AskResponse = {
  answer: string;
  found: boolean;
  citations: Citation[];
  nearest: Citation[];
  debug: { retrieved: Retrieved[]; rerank_skipped: boolean };
};

const COURSES = [
  ["", "All courses"],
  ["PHIL", "Philosophy"],
  ["ENGL", "English"],
  ["CPSC", "Computer science"],
] as const;

// ponytail: mirrors the ingested corpus by hand; update it if texts are added. Each question
// retrieves its gold passage first with the live settings (RERANK_CANDIDATES=5, course filter on).
const LIBRARY = [
  {
    course: "PHIL",
    label: "Philosophy",
    texts: [
      { title: "On Liberty", by: "John Stuart Mill", question: "What is the harm principle?" },
      { title: "Utilitarianism", by: "John Stuart Mill", question: "Does Mill think all pleasures count the same, or can some be worth more than others?" },
      { title: "An Enquiry Concerning Human Understanding", by: "David Hume", question: "Why do we expect the future to resemble the past, according to Hume?" },
      { title: "Discourse on the Method", by: "René Descartes", question: "In Descartes' provisional code of conduct, how should someone act when they must choose but cannot be certain?" },
    ],
  },
  {
    course: "ENGL",
    label: "English",
    texts: [
      { title: "Frankenstein", by: "Mary Shelley", question: "In the letter that reaches Victor from home, who has died and how is the news broken to him?" },
      { title: "Heart of Darkness", by: "Joseph Conrad", question: "How does Marlow describe the river on the map that fascinated him as a boy?" },
      { title: "Strange Case of Dr Jekyll and Mr Hyde", by: "Robert Louis Stevenson", question: "How does Hyde kill the old gentleman, and who sees it happen?" },
    ],
  },
  {
    course: "CPSC",
    label: "Computer science",
    texts: [
      { title: "Strings, input/output, and branching", by: "MIT 6.100L, lecture 2", question: "Can I change one letter of a Python string in place?" },
      { title: "Iteration", by: "MIT 6.100L, lecture 3", question: "What do the arguments to range() mean, and which ones can be left out?" },
      { title: "Decomposition, abstraction, and functions", by: "MIT 6.100L, lecture 7", question: "What role does a docstring play for a function?" },
      { title: "Lambda functions, tuples, and lists", by: "MIT 6.100L, lecture 9", question: "How do I write a function that accepts any number of arguments?" },
      { title: "Dictionaries", by: "MIT 6.100L, lecture 14", question: "What happens when I look up a key that is not in a dictionary?" },
      { title: "Python classes", by: "MIT 6.100L, lecture 17", question: "How is a method different from an ordinary function, and what is its first parameter?" },
    ],
  },
];

// same marker shapes generate/answer.py accepts: [2] or [1, 3]
const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

// ponytail: tiny stoplist, enough to keep "what"/"does" from lighting up every excerpt
const STOP = new Set(
  "what when where which while with does doing done have from that this they them their there then than about into your just like more most some such only also very would could should will shall".split(" "),
);

const rankCell = (
  rank: number | null,
  score: number | null,
  format: (score: number) => string,
) => (rank === null || score === null ? "–" : `${rank} (${format(score)})`);

function questionTerms(question: string): string[] {
  const words = question.toLowerCase().match(/[a-z]{4,}/g) ?? [];
  return [...new Set(words.filter((w) => !STOP.has(w)))];
}

function highlight(text: string, terms: string[]): ReactNode[] {
  if (terms.length === 0) return [text];
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`\\b(?:${escaped.join("|")})\\w*`, "gi");
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    out.push(text.slice(last, m.index), <mark key={m.index}>{m[0]}</mark>);
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [course, setCourse] = useState("");
  const [loading, setLoading] = useState(false);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [asked, setAsked] = useState("");
  const [active, setActive] = useState<number | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const libraryRef = useRef<HTMLDetailsElement>(null);

  // wake the API and database while the visitor types; say so if it's slow
  useEffect(() => {
    const slow = setTimeout(() => setWaking(true), 2500);
    fetch("/api/health")
      .catch(() => {})
      .finally(() => {
        clearTimeout(slow);
        setWaking(false);
      });
  }, []);

  async function ask(q: string, c: string) {
    if (loading || !q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActive(null);
    setAsked(q);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q, course: c || null }),
      });
      const body = await res.json();
      if (!res.ok) {
        // 429 and 503 send a string; 422 sends a list of validation objects
        setError(
          typeof body.detail === "string"
            ? body.detail
            : "That question couldn't be read. Keep it under 500 characters and try again.",
        );
      } else {
        setResult(body as AskResponse);
      }
    } catch {
      setError("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  function tryExample(q: string, c: string) {
    setQuestion(q);
    setCourse(c);
    setLibraryOpen(false);
    ask(q, c);
  }

  function showLibrary() {
    setLibraryOpen(true);
    requestAnimationFrame(() => libraryRef.current?.scrollIntoView({ block: "start" }));
  }

  const library = (
    <div className="library">
      {LIBRARY.map((group) => (
        <section key={group.course} aria-labelledby={`lib-${group.course}`}>
          <h3 id={`lib-${group.course}`}>
            <span className="dot" style={{ background: `var(--${group.course})` }} aria-hidden="true" />
            {group.label}
          </h3>
          <ul>
            {group.texts.map((t) => (
              <li key={t.title}>
                <span className="lib-title">{t.title}</span>
                <span className="lib-by">{t.by}</span>
                <button type="button" className="lib-q" onClick={() => tryExample(t.question, group.course)}>
                  {t.question}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );

  const terms = questionTerms(asked);
  const cited = new Set(result?.citations.map((c) => c.chunk_id));

  const cite = (n: number, key: string) => (
    <button
      key={key}
      type="button"
      className={`cite${active === n ? " on" : ""}`}
      aria-label={`Source ${n}`}
      onMouseEnter={() => setActive(n)}
      onMouseLeave={() => setActive(null)}
      onFocus={() => setActive(n)}
      onBlur={() => setActive(null)}
    >
      {n}
    </button>
  );

  const renderAnswer = (answer: string) =>
    answer.split(/\n\s*\n/).map((para, p) => {
      const parts: ReactNode[] = [];
      let last = 0;
      for (const m of para.matchAll(MARKER)) {
        // keep the marker on one line with the word before it and the punctuation after it
        const [, head, word, space] = para.slice(last, m.index).match(/^([\s\S]*?)(\S*)(\s*)$/)!;
        last = m.index + m[0].length;
        const punct = para.slice(last).match(/^[.,;:!?)]+/)?.[0] ?? "";
        last += punct.length;
        parts.push(
          head,
          <span key={`${p}-${m.index}`} className="cites">
            {word}
            {space && " "}
            {m[1].split(/\s*,\s*/).map((n, i) => cite(Number(n), `${p}-${m.index}-${i}`))}
            {punct}
          </span>,
        );
      }
      parts.push(para.slice(last));
      return <p key={p}>{parts}</p>;
    });

  const note = (c: Citation, linked: boolean) => (
    <div
      key={c.n}
      className={`note${linked && active === c.n ? " on" : ""}`}
      onMouseEnter={linked ? () => setActive(c.n) : undefined}
      onMouseLeave={linked ? () => setActive(null) : undefined}
    >
      <div className="note-head">
        <span className="num">{c.n}</span>
        <span className="src">{c.title}</span>
      </div>
      <div className="loc">
        <span className="dot" style={{ background: `var(--${c.course})` }} aria-hidden="true" />
        {c.location}
      </div>
      <p className="quote">{highlight(c.excerpt, terms)}</p>
      {c.source_url && (
        <a className="open" href={c.source_url} target="_blank" rel="noreferrer">
          View the source text
        </a>
      )}
    </div>
  );

  return (
    <main>
      <header>
        <h1>CourseLens</h1>
        <p className="tagline">Ask the course readings. Every answer shows its sources.</p>
      </header>

      <div className="courses" role="group" aria-label="Course">
        {COURSES.map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={course === value}
            onClick={() => setCourse(value)}
          >
            {value && <span className="dot" style={{ background: `var(--${value})` }} aria-hidden="true" />}
            {label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question, course);
        }}
      >
        <textarea
          aria-label="Your question"
          placeholder="What does Mill mean by the tyranny of the majority?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
          maxLength={500}
          required
          rows={2}
        />
        <button className="ask" type="submit">
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>
      {(result || error) && (
        <details
          ref={libraryRef}
          className="covers"
          open={libraryOpen}
          onToggle={(e) => setLibraryOpen(e.currentTarget.open)}
        >
          <summary>What the readings cover</summary>
          {library}
        </details>
      )}
      {waking && (
        <p className="notice" role="status">
          Starting the server. The first question after a quiet spell can take about a minute.
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!result && !loading && !error && (
        <section className="result start" aria-labelledby="start-heading">
          <h2 id="start-heading">What you can ask about</h2>
          <p className="lede">
            Answers come from these texts and lectures. Pick a question to try one, or ask your own.
          </p>
          {library}
        </section>
      )}

      {loading && (
        <section className="result waiting" role="status">
          <span className="sweep">Reading the course material…</span>
          <p className="sub">Searching the readings and writing an answer. This usually takes about 6 seconds.</p>
        </section>
      )}

      {result && result.found && (
        <section className="result">
          <div className="reading">
            <div className="answer">{renderAnswer(result.answer)}</div>
            <aside className="margin" aria-label="Sources">
              <h2>Sources used in this answer</h2>
              {result.citations.map((c) => note(c, true))}
            </aside>
          </div>
          {debugPanel(result, cited)}
        </section>
      )}

      {result && !result.found && (
        <section className="result miss">
          <h2>The readings don&apos;t cover this</h2>
          <p>
            Nothing in the course material answers this question.
            {result.nearest.length > 0 && " These passages came closest, in case one helps."}{" "}
            <button type="button" className="linkish" onClick={showLibrary}>
              See what the readings cover
            </button>
          </p>
          {result.nearest.map((c) => note(c, false))}
          {debugPanel(result, cited)}
        </section>
      )}

      <footer>
        Answers come only from public-domain and openly licensed course texts. Built with hybrid
        search in Postgres, a local reranker, and Claude.{" "}
        <a href="https://github.com/marcusmrno/school-rag">Source code on GitHub</a>
      </footer>
    </main>
  );
}

function debugPanel(result: AskResponse, cited: Set<number>) {
  if (result.debug.retrieved.length === 0) return null;
  return (
    <details>
      <summary>How these sources were chosen</summary>
      <p className="how">
        Each passage was found by meaning (vector search), by matching words (keyword search), or
        both. The two rankings are merged with reciprocal rank fusion, so a passage ranked high in
        either list rises to the top. A reranker then reads the question beside each top passage and
        rescores it, and the best 5 go to the model, unless even the best one scores too low to be
        worth asking.{result.found && " Highlighted rows are the passages the answer cites."}
      </p>
      {result.debug.rerank_skipped && (
        <p className="how">The reranker was unavailable, so these are in merged order.</p>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Passage</th>
              <th scope="col" className="n">By meaning</th>
              <th scope="col" className="n">By words</th>
              <th scope="col" className="n">Merged</th>
              <th scope="col" className="n">Reranker</th>
            </tr>
          </thead>
          <tbody>
            {result.debug.retrieved.map((r) => (
              <tr key={r.chunk_id} className={cited.has(r.chunk_id) ? "cited" : undefined}>
                <td>
                  {r.title}, {r.location}
                </td>
                <td className="n">{rankCell(r.vector_rank, r.vector_score, (s) => s.toFixed(2))}</td>
                <td className="n">{rankCell(r.keyword_rank, r.keyword_score, (s) => s.toPrecision(2))}</td>
                <td className="n">{r.rrf.toFixed(4)}</td>
                <td className="n">{r.rerank === null ? "–" : r.rerank.toPrecision(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
