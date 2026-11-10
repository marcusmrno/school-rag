"use client";

import { useState } from "react";

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
};

type AskResponse = {
  answer: string;
  found: boolean;
  citations: Citation[];
  nearest: Citation[];
  debug: { retrieved: Retrieved[] };
};

const rankCell = (
  rank: number | null,
  score: number | null,
  format: (score: number) => string,
) => (rank === null || score === null ? "–" : `${rank} (${format(score)})`);

export default function Home() {
  const [question, setQuestion] = useState("");
  const [course, setCourse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question, course: course || null }),
      });
      const body = await res.json();
      if (!res.ok) {
        // 503 sends a string; 422 sends a list of validation objects
        setError(
          typeof body.detail === "string"
            ? body.detail
            : "Please check your question.",
        );
      } else {
        setResult(body as AskResponse);
      }
    } catch {
      setError("Could not reach the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>CourseLens</h1>
      <form onSubmit={ask}>
        <textarea
          aria-label="Question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          required
          rows={3}
          cols={60}
        />
        <br />
        <select
          aria-label="Course"
          value={course} onChange={(e) => setCourse(e.target.value)}>
          <option value="">All</option>
          <option value="PHIL">PHIL</option>
          <option value="ENGL">ENGL</option>
          <option value="CPSC">CPSC</option>
        </select>{" "}
        <button type="submit" disabled={loading}>
          Ask
        </button>
      </form>

      {loading && <p role="status">Thinking…</p>}
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p>{result.answer}</p>
          {result.found && (
            <ul>
              {result.citations.map((c) => (
                <li key={c.n}>
                  [{c.n}] {c.title}, {c.location}
                  <br />
                  {c.excerpt}
                  {c.source_url && (
                    <>
                      {" "}
                      <a href={c.source_url}>source</a>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!result.found && result.nearest.length > 0 && (
            <>
              <h2>Closest sources I found</h2>
              <ul>
                {result.nearest.map((c) => (
                  <li key={c.n}>
                    {c.title}, {c.location}
                    <br />
                    {c.excerpt}
                    {c.source_url && (
                      <>
                        {" "}
                        <a href={c.source_url}>source</a>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
          {result.debug.retrieved.length > 0 && (
            <details>
              <summary>Why these sources?</summary>
              <p>
                Each passage was found by meaning (vector search), by matching
                words (keyword search), or both. The two rankings are merged with
                reciprocal rank fusion (RRF): a passage ranked high in either list
                rises to the top, and the top 5 are sent to the model.
              </p>
              <table style={{ borderSpacing: "1rem 0.25rem" }}>
                <caption>Retrieved passages</caption>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Source</th>
                    <th scope="col">Vector</th>
                    <th scope="col">Keyword</th>
                    <th scope="col">RRF</th>
                    <th scope="col">Cited</th>
                  </tr>
                </thead>
                <tbody>
                  {result.debug.retrieved.map((r, i) => (
                    <tr key={r.chunk_id}>
                      <td>{i + 1}</td>
                      <td>
                        {r.title}, {r.location}
                      </td>
                      <td>
                        {rankCell(r.vector_rank, r.vector_score, (s) =>
                          s.toFixed(2),
                        )}
                      </td>
                      <td>
                        {rankCell(r.keyword_rank, r.keyword_score, (s) =>
                          s.toPrecision(2),
                        )}
                      </td>
                      <td>{r.rrf.toFixed(4)}</td>
                      <td>
                        {result.citations.some((c) => c.chunk_id === r.chunk_id)
                          ? "✓"
                          : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </>
      )}
    </main>
  );
}
