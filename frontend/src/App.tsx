import { useState } from "react";

type AgentEvent = {
  type: string;
  message?: string;

  completed?: number;
  total?: number;
  percent?: number;

  root_cause?: string;
  explanation?: string;

  file?: string;
  old_text?: string;
  new_text?: string;

  success?: boolean;
  status?: string;
  exit_code?: number;

  summary?: string | Record<string, number>;

  repair_attempt?: number;
  repair_attempts?: number;
};

function App() {
  const [repository, setRepository] = useState("");
  const [issueNumber, setIssueNumber] = useState("");

  // Permanent/historical events only.
  const [events, setEvents] = useState<AgentEvent[]>([]);

  const [running, setRunning] = useState(false);

  // ------------------------------------------------------------
  // LIVE TEST STATE
  // ------------------------------------------------------------

  const [testStarted, setTestStarted] =
    useState<AgentEvent | null>(null);

  const [testProgress, setTestProgress] =
    useState<AgentEvent | null>(null);

  const [testResult, setTestResult] =
    useState<AgentEvent | null>(null);

  const [repairStarted, setRepairStarted] =
    useState<AgentEvent | null>(null);

  // ============================================================
  // RUN AGENT
  // ============================================================

  const analyzeIssue = async () => {
    setEvents([]);

    setRunning(true);

    // Reset live test state
    setTestStarted(null);
    setTestProgress(null);
    setTestResult(null);
    setRepairStarted(null);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/analyze-stream",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            repository,
            issue_number: Number(issueNumber),
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Server error: ${response.status}`
        );
      }

      if (!response.body) {
        throw new Error(
          "Streaming is not supported by the browser."
        );
      }

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder();

      let buffer = "";

      while (true) {
        const { value, done } =
          await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(
          value,
          {
            stream: true,
          }
        );

        const chunks =
          buffer.split("\n\n");

        buffer =
          chunks.pop() || "";

        for (const chunk of chunks) {
          if (!chunk.startsWith("data:")) {
            continue;
          }

          const json =
            chunk.replace(
              /^data:\s*/,
              ""
            );

          try {
            const event: AgentEvent =
              JSON.parse(json);

            // ==================================================
            // IMPORTANT:
            //
            // Do NOT put test_progress into events.
            //
            // We update ONE progress state instead.
            // ==================================================

            if (
              event.type ===
              "test_started"
            ) {
              setTestStarted(event);

              // New test run means old result
              // should disappear.
              setTestResult(null);

              // Reset progress for this run.
              setTestProgress(null);

              continue;
            }

            if (
              event.type ===
              "test_progress"
            ) {
              setTestProgress(event);
              continue;
            }

            if (
              event.type ===
              "test_result"
            ) {
              setTestResult(event);
              continue;
            }

            if (
              event.type ===
              "repair_started"
            ) {
              setRepairStarted(event);
              continue;
            }

            if (event.type === "done") {
              setRunning(false);
              continue;
            }

            // Everything else is a normal
            // historical event.
            setEvents(
              (previous) => [
                ...previous,
                event,
              ]
            );
          } catch (error) {
            console.error(
              "Invalid SSE event:",
              json
            );
          }
        }
      }
    } catch (error) {
      setEvents(
        (previous) => [
          ...previous,
          {
            type: "error",
            message: String(error),
          },
        ]
      );
    } finally {
      setRunning(false);
    }
  };

  // ============================================================
  // DERIVED TEST STATE
  // ============================================================

  const isTesting =
    testStarted !== null &&
    testResult === null;

  const currentRepairAttempt =
    testStarted?.repair_attempt ??
    testProgress?.repair_attempt ??
    0;

  // ============================================================
  // UI
  // ============================================================

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>

        {/* ================================================== */}
        {/* HEADER */}
        {/* ================================================== */}

        <div style={headerStyle}>
          <h1>
            🤖 Open Source Copilot
          </h1>

          <p>
            AI-powered GitHub issue
            investigation, patching and
            automated testing
          </p>
        </div>

        {/* ================================================== */}
        {/* INPUT */}
        {/* ================================================== */}

        <div style={inputPanelStyle}>

          <div style={inputGroupStyle}>
            <label>
              GitHub Repository
            </label>

            <input
              type="text"
              placeholder="neomjs/neo"
              value={repository}
              onChange={(e) =>
                setRepository(
                  e.target.value
                )
              }
              style={inputStyle}
            />
          </div>

          <div style={inputGroupStyle}>
            <label>
              Issue Number
            </label>

            <input
              type="number"
              placeholder="19143"
              value={issueNumber}
              onChange={(e) =>
                setIssueNumber(
                  e.target.value
                )
              }
              style={{
                ...inputStyle,
                width: "140px",
              }}
            />
          </div>

          <button
            onClick={analyzeIssue}
            disabled={running}
            style={{
              ...buttonStyle,
              opacity: running
                ? 0.6
                : 1,
            }}
          >
            {running
              ? "🤖 Agent Running..."
              : "🔍 Analyze Issue"}
          </button>

        </div>

        {/* ================================================== */}
        {/* ACTIVITY */}
        {/* ================================================== */}

        <div style={panelStyle}>

          <div
            style={panelHeaderStyle}
          >
            <h2>
              Agent Activity
            </h2>

            {running && (
              <div
                style={
                  liveIndicatorStyle
                }
              >
                <span>●</span>{" "}
                LIVE
              </div>
            )}
          </div>

          {events.length === 0 &&
            !testStarted &&
            !testResult && (
              <p style={emptyStyle}>
                Agent activity will
                appear here...
              </p>
            )}

          {/* ================================================= */}
          {/* REPAIR STATUS */}
          {/* ================================================= */}

          {repairStarted &&
            running && (
              <div
                style={
                  repairCardStyle
                }
              >
                <div
                  style={
                    repairTitleStyle
                  }
                >
                  🔧 Repair Attempt{" "}
                  {
                    repairStarted.repair_attempt
                  }
                  {" / "}
                  {
                    repairStarted.repair_attempts
                  }
                </div>

                <div
                  style={
                    repairMessageStyle
                  }
                >
                  {
                    repairStarted.message
                  }
                </div>
              </div>
            )}

          {/* ================================================= */}
          {/* LIVE TEST CARD */}
          {/* ================================================= */}

          

          {/* ================================================= */}
          {/* NORMAL EVENTS */}
          {/* ================================================= */}

          {events.map(
            (event, index) => (
              <EventCard
                key={index}
                event={event}
              />
            )
          )}

          {testStarted && (
            <LiveTestCard
              started={testStarted}
              progress={
                testProgress
              }
              result={testResult}
              running={isTesting}
              repairAttempt={
                currentRepairAttempt
              }
            />
          )}

          {/* ================================================= */}
          {/* FINAL TEST RESULT */}
          {/* ================================================= */}

          {testResult &&
            !testStarted && (
              <EventCard
                event={testResult}
              />
            )}

        </div>
      </div>
    </div>
  );
}

// ============================================================
// LIVE TEST CARD
// ============================================================

function LiveTestCard({
  started,
  progress,
  result,
  running,
  repairAttempt,
}: {
  started: AgentEvent;
  progress: AgentEvent | null;
  result: AgentEvent | null;
  running: boolean;
  repairAttempt: number;
}) {
  // ----------------------------------------------------------
  // TEST RESULT AVAILABLE
  // ----------------------------------------------------------

  if (result) {
    const summary =
      typeof result.summary === "object"
        ? result.summary
        : null;

    const passed = summary?.passed ?? 0;
    const failed = summary?.failed ?? 0;
    const skipped = summary?.skipped ?? 0;
    const didNotRun = summary?.did_not_run ?? 0;

    const passedAll = result.status === "passed";

    return (
      <div
        style={{
          ...progressCardStyle,

          border: passedAll
            ? "1px solid #22c55e"
            : "1px solid #ef4444",

          boxShadow: passedAll
            ? "0 0 25px rgba(34,197,94,0.12)"
            : "0 0 25px rgba(239,68,68,0.12)",
        }}
      >
        <div style={progressHeaderStyle}>
          <div style={progressTitleStyle}>
            {passedAll
              ? "✅ Test Cases Passed"
              : "❌ Test Cases Failed"}
          </div>

          <div style={progressPercentStyle}>
            {passedAll ? "100%" : "FAILED"}
          </div>
        </div>

        {/* Summary */}
        <div style={testCaseSummaryStyle}>
          <div>
            <span style={testCaseNumberStyle}>
              {passed.toLocaleString()}
            </span>

            <span style={testCaseLabelStyle}>
              test cases passed
            </span>
          </div>

          <div>
            <span
              style={{
                ...testCaseNumberStyle,
                color: "#f87171",
              }}
            >
              {failed.toLocaleString()}
            </span>

            <span style={testCaseLabelStyle}>
              test cases failed
            </span>
          </div>

          <div>
            <span
              style={{
                ...testCaseNumberStyle,
                color: "#fbbf24",
              }}
            >
              {skipped.toLocaleString()}
            </span>

            <span style={testCaseLabelStyle}>
              test cases skipped
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={progressTrackStyle}>
          <div
            style={{
              ...progressFillStyle,

              width: passedAll
                ? "100%"
                : `${progress?.percent ?? 0}%`,

              background: passedAll
                ? "#22c55e"
                : "#ef4444",
            }}
          />
        </div>

        <div style={progressMessageStyle}>
          {passedAll
            ? "All test cases completed successfully."
            : `${failed.toLocaleString()} test cases failed.`}
        </div>

        {/* Detailed stats */}
        <div style={testResultMiniGridStyle}>
          <MiniStat
            label="Passed"
            value={passed}
            icon="✅"
          />

          <MiniStat
            label="Failed"
            value={failed}
            icon="❌"
          />

          <MiniStat
            label="Skipped"
            value={skipped}
            icon="⏭️"
          />

          <MiniStat
            label="Did Not Run"
            value={didNotRun}
            icon="⚪"
          />
        </div>

        <div style={resultDetailsStyle}>
          <div>
            <strong>Exit Code:</strong>{" "}
            {result.exit_code}
          </div>

          <div>
            🔧 Repair attempt:{" "}
            {result.repair_attempt ?? 0}
          </div>
        </div>
      </div>
    );
  }

  // ----------------------------------------------------------
  // LIVE PROGRESS
  // ----------------------------------------------------------

  const completed =
    progress?.completed ?? 0;

  const total =
    progress?.total ?? 0;

  const percent = Math.min(
    progress?.percent ?? 0,
    100
  );

  const title =
    repairAttempt > 0
      ? `Running Tests — Repair ${repairAttempt}`
      : "Running Tests";

  return (
    <div
      style={
        progressCardStyle
      }
    >

      <div
        style={
          progressHeaderStyle
        }
      >
        <div
          style={
            progressTitleStyle
          }
        >
          🧪 {title}
        </div>

        <div
          style={
            progressPercentStyle
          }
        >
          {progress
            ? `${percent.toFixed(1)}%`
            : "Starting..."}
        </div>
      </div>

      {/* -------------------------------------------------- */}
      {/* NUMBERS */}
      {/* -------------------------------------------------- */}

      <div
        style={
          progressNumbersStyle
        }
      >
        <span>
          {progress
            ? `${completed.toLocaleString()} / ${
                total
                  ? total.toLocaleString()
                  : "?"
              }`
            : "Preparing test suite..."}
        </span>

        <span>
          {total
            ? `${total.toLocaleString()} tests`
            : "Docker sandbox"}
        </span>
      </div>

      {/* -------------------------------------------------- */}
      {/* PROGRESS BAR */}
      {/* -------------------------------------------------- */}

      <div
        style={
          progressTrackStyle
        }
      >
        <div
          style={{
            ...progressFillStyle,

            width: progress
              ? `${percent}%`
              : "3%",

            animation:
              progress
                ? undefined
                : "pulse 1.5s infinite",
          }}
        />
      </div>

      {/* -------------------------------------------------- */}
      {/* CURRENT MESSAGE */}
      {/* -------------------------------------------------- */}

      <div
        style={
          progressMessageStyle
        }
      >
        {progress?.message ||
          started.message ||
          "Starting test suite..."}
      </div>

      {/* -------------------------------------------------- */}
      {/* STATUS */}
      {/* -------------------------------------------------- */}

      <div
        style={
          runningStatusStyle
        }
      >
        <span
          style={
            runningDotStyle
          }
        >
          ●
        </span>

        {progress
          ? "Tests are running inside Docker sandbox..."
          : "Preparing Docker sandbox and starting tests..."}
      </div>
    </div>
  );
}

// ============================================================
// NORMAL EVENT CARD
// ============================================================

function EventCard({
  event,
}: {
  event: AgentEvent;
}) {

  // ----------------------------------------------------------
  // LOG
  // ----------------------------------------------------------

  if (event.type === "log") {
    return (
      <div style={logStyle}>
        {event.message}
      </div>
    );
  }

  // ----------------------------------------------------------
  // ANALYSIS
  // ----------------------------------------------------------

  if (
    event.type ===
    "analysis"
  ) {
    return (
      <div style={cardStyle}>

        <h3>
          🧠 Root Cause Analysis
        </h3>

        <div
          style={sectionStyle}
        >
          <strong>
            Root Cause
          </strong>

          <p>
            {event.root_cause}
          </p>
        </div>

        <div
          style={sectionStyle}
        >
          <strong>
            Explanation
          </strong>

          <p>
            {event.explanation}
          </p>
        </div>

      </div>
    );
  }

  // ----------------------------------------------------------
  // PATCH
  // ----------------------------------------------------------

  if (
    event.type ===
    "patch"
  ) {
    return (
      <div style={cardStyle}>

        <h3>
          {event.repair_attempt
            ? `🔧 Repair Patch — Attempt ${event.repair_attempt}`
            : "🛠️ Patch Generated"}
        </h3>

        <p>
          <strong>
            File:
          </strong>{" "}
          <code>
            {event.file}
          </code>
        </p>

        <div
          style={diffBox}
        >
          <div
            style={
              removedCodeStyle
            }
          >
            - {event.old_text}
          </div>

          <div
            style={
              addedCodeStyle
            }
          >
            + {event.new_text}
          </div>
        </div>

        <p>
          {event.success
            ? "✅ Patch applied successfully"
            : "❌ Patch failed"}
        </p>

      </div>
    );
  }

  // ----------------------------------------------------------
  // FINAL
  // ----------------------------------------------------------

  if (
    event.type ===
    "final"
  ) {
    const verified =
      event.status ===
      "verified";

    return (
      <div
        style={{
          ...cardStyle,

          border:
            verified
              ? "1px solid #22c55e"
              : "1px solid #f59e0b",

          background:
            verified
              ? "#052e16"
              : "#1c1917",
        }}
      >

        <h2>
          {verified
            ? "🎉 Fix Verified"
            : "⚠️ Agent Finished"}
        </h2>

        <p>
          <strong>
            Status:
          </strong>{" "}
          {event.status}
        </p>

        <p>
          <strong>
            Repair attempts:
          </strong>{" "}
          {event.repair_attempts ??
            0}
        </p>

      </div>
    );
  }

  // ----------------------------------------------------------
  // ERROR
  // ----------------------------------------------------------

  if (
    event.type ===
    "error"
  ) {
    return (
      <div
        style={{
          ...cardStyle,

          border:
            "1px solid #ef4444",

          color:
            "#fecaca",
        }}
      >
        ❌ {event.message}
      </div>
    );
  }

  return null;
}

// ============================================================
// MINI STAT
// ============================================================

function MiniStat({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: string;
}) {
  return (
    <div
      style={miniStatStyle}
    >
      <div
        style={
          miniStatLabelStyle
        }
      >
        {icon} {label}
      </div>

      <div
        style={
          miniStatValueStyle
        }
      >
        {value.toLocaleString()}
      </div>
    </div>
  );
}

// ============================================================
// STYLES
// ============================================================

const pageStyle = {
  minHeight: "100vh",

  background:
    "linear-gradient(135deg, #020617, #0f172a)",

  color: "#e2e8f0",

  padding:
    "40px 20px",

  fontFamily:
    "Inter, Arial, sans-serif",
};

const containerStyle = {
  maxWidth: "1100px",
  margin: "0 auto",
};

const headerStyle = {
  marginBottom: "30px",
};

const inputPanelStyle = {
  display: "flex",

  gap: "18px",

  alignItems: "end",

  flexWrap: "wrap" as const,

  padding: "22px",

  background: "#020617",

  border:
    "1px solid #334155",

  borderRadius: "12px",
};

const inputGroupStyle = {
  display: "flex",

  flexDirection:
    "column" as const,
};

const inputStyle = {
  padding: "12px",

  width: "280px",

  marginTop: "7px",

  background: "#0f172a",

  color: "white",

  border:
    "1px solid #475569",

  borderRadius: "8px",

  outline: "none",
};

const buttonStyle = {
  padding:
    "13px 22px",

  background:
    "#2563eb",

  color: "white",

  border: "none",

  borderRadius: "8px",

  cursor: "pointer",

  fontWeight: 600,
};

const panelStyle = {
  marginTop: "30px",

  background: "#020617",

  borderRadius: "12px",

  padding: "25px",

  border:
    "1px solid #334155",
};

const panelHeaderStyle = {
  display: "flex",

  justifyContent:
    "space-between",

  alignItems:
    "center",
};

const liveIndicatorStyle = {
  color: "#60a5fa",

  fontFamily:
    "monospace",

  fontSize: "13px",
};

const emptyStyle = {
  color: "#64748b",
};

const logStyle = {
  padding:
    "7px 0",

  color: "#cbd5e1",

  fontFamily:
    "monospace",

  fontSize: "14px",
};

const cardStyle = {
  background:
    "#0f172a",

  border:
    "1px solid #334155",

  borderRadius:
    "10px",

  padding:
    "20px",

  marginTop:
    "15px",
};

const progressCardStyle = {
  marginTop: "20px",

  padding: "22px",

  background:
    "linear-gradient(135deg, #0f172a, #111827)",

  border:
    "1px solid #2563eb",

  borderRadius: "12px",

  boxShadow:
    "0 0 25px rgba(37,99,235,0.12)",
};

const progressHeaderStyle = {
  display: "flex",

  justifyContent:
    "space-between",

  alignItems:
    "center",
};

const progressTitleStyle = {
  fontSize: "18px",

  fontWeight: 600,
};

const progressPercentStyle = {
  fontFamily:
    "monospace",

  fontSize: "20px",

  fontWeight: 700,
};

const progressNumbersStyle = {
  marginTop: "14px",

  display: "flex",

  justifyContent:
    "space-between",

  gap: "15px",

  color: "#94a3b8",

  fontFamily:
    "monospace",

  flexWrap:
    "wrap" as const,
};

const progressTrackStyle = {
  width: "100%",

  height: "14px",

  background:
    "#1e293b",

  borderRadius:
    "999px",

  overflow:
    "hidden" as const,

  marginTop: "10px",
};

const progressFillStyle = {
  height: "100%",

  background:
    "linear-gradient(90deg, #2563eb, #22c55e)",

  borderRadius:
    "999px",

  transition:
    "width 0.25s ease",
};

const progressMessageStyle = {
  marginTop: "11px",

  fontFamily:
    "monospace",

  fontSize: "13px",

  color: "#64748b",

  whiteSpace:
    "nowrap" as const,

  overflow:
    "hidden",

  textOverflow:
    "ellipsis",
};

const runningStatusStyle = {
  marginTop: "14px",

  display: "flex",

  alignItems: "center",

  gap: "8px",

  color: "#94a3b8",

  fontSize: "13px",
};

const runningDotStyle = {
  color: "#22c55e",

  fontSize: "10px",
};

const repairCardStyle = {
  marginTop: "15px",

  padding:
    "18px 20px",

  background:
    "linear-gradient(135deg, #172554, #1e293b)",

  border:
    "1px solid #3b82f6",

  borderRadius:
    "10px",

  fontFamily:
    "monospace",
};

const repairTitleStyle = {
  fontSize: "17px",

  fontWeight: 600,

  color: "#dbeafe",
};

const repairMessageStyle = {
  marginTop: "8px",

  color: "#bfdbfe",
};

const sectionStyle = {
  marginTop: "12px",

  lineHeight: "1.6",
};

const diffBox = {
  background:
    "#020617",

  borderRadius:
    "8px",

  padding: "15px",

  marginTop: "15px",

  fontFamily:
    "monospace",

  whiteSpace:
    "pre-wrap" as const,

  overflowX:
    "auto" as const,
};

const removedCodeStyle = {
  color: "#f87171",
};

const addedCodeStyle = {
  color: "#4ade80",

  marginTop: "6px",
};

const testResultMiniGridStyle = {
  display: "grid",

  gridTemplateColumns:
    "repeat(4, 1fr)",

  gap: "10px",

  marginTop: "18px",
};

const miniStatStyle = {
  padding: "12px",

  background:
    "#020617",

  borderRadius:
    "8px",

  border:
    "1px solid #1e293b",
};

const miniStatLabelStyle = {
  color: "#94a3b8",

  fontSize: "12px",
};

const miniStatValueStyle = {
  marginTop: "5px",

  fontSize: "19px",

  fontWeight: 700,

  fontFamily:
    "monospace",
};

const testCaseSummaryStyle = {
  display: "grid",

  gridTemplateColumns:
    "repeat(3, 1fr)",

  gap: "20px",

  marginTop: "20px",

  padding: "16px",

  background: "#020617",

  borderRadius: "10px",

  border:
    "1px solid #1e293b",
};

const testCaseNumberStyle = {
  display: "block",

  fontSize: "24px",

  fontWeight: 700,

  fontFamily: "monospace",

  color: "#e2e8f0",
};

const testCaseLabelStyle = {
  display: "block",

  marginTop: "5px",

  color: "#94a3b8",

  fontSize: "13px",
};

const resultDetailsStyle = {
  marginTop: "18px",

  color: "#94a3b8",

  display: "flex",

  gap: "25px",

  flexWrap:
    "wrap" as const,
};

export default App;