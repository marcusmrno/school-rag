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

type AskResponse = {
  answer: string;
  found: boolean;
  citations: Citation[];
};

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
        </>
      )}
    </main>
  );
}
