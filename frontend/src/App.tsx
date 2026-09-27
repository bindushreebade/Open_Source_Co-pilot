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
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);

  const analyzeIssue = async () => {
    setEvents([]);
    setRunning(true);

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

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (true) {
        const { value, done } =
          await reader.read();

        if (done) break;

        buffer += decoder.decode(value, {
          stream: true,
        });

        const chunks = buffer.split("\n\n");

        buffer = chunks.pop() || "";

        for (const chunk of chunks) {
          if (!chunk.startsWith("data:")) {
            continue;
          }

          const json = chunk.replace(
            /^data:\s*/,
            ""
          );

          try {
            const event: AgentEvent =
              JSON.parse(json);

            setEvents((previous) => [
              ...previous,
              event,
            ]);

            if (event.type === "done") {
              setRunning(false);
            }
          } catch (error) {
            console.error(
              "Invalid SSE event:",
              json
            );
          }
        }
      }
    } catch (error) {
      setEvents((previous) => [
        ...previous,
        {
          type: "error",
          message: String(error),
        },
      ]);
    } finally {
      setRunning(false);
    }
  };

  // ==========================================================
  // Latest live events
  // ==========================================================

  const latestTestProgress = [...events]
    .reverse()
    .find(
      (event) =>
        event.type === "test_progress"
    );

  const latestTestStarted = [...events]
    .reverse()
    .find(
      (event) =>
        event.type === "test_started"
    );

  const latestRepair = [...events]
    .reverse()
    .find(
      (event) =>
        event.type === "repair_started"
    );

  const latestTestResult = [...events]
    .reverse()
    .find(
      (event) =>
        event.type === "test_result"
    );

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>

        {/* ================================================== */}
        {/* HEADER */}
        {/* ================================================== */}

        <div style={headerStyle}>
          <h1>🤖 Open Source Copilot</h1>

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
                setRepository(e.target.value)
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
                setIssueNumber(e.target.value)
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
              opacity: running ? 0.6 : 1,
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

          <div style={panelHeaderStyle}>
            <h2>Agent Activity</h2>

            {running && (
              <div style={liveIndicatorStyle}>
                <span>●</span> LIVE
              </div>
            )}
          </div>

          {events.length === 0 && (
            <p style={emptyStyle}>
              Agent activity will appear here...
            </p>
          )}

          {/* ================================================= */}
          {/* REPAIR STATUS */}
          {/* ================================================= */}

          {latestRepair && running && (
            <div style={repairCardStyle}>

              <div style={repairTitleStyle}>
                🔧 Repair Attempt{" "}
                {latestRepair.repair_attempt}
                {" / "}
                {latestRepair.repair_attempts}
              </div>

              <div style={repairMessageStyle}>
                {latestRepair.message}
              </div>

            </div>
          )}

          {/* ================================================= */}
          {/* TEST PROGRESS */}
          {/* ================================================= */}

          {latestTestProgress && (
            <TestProgressCard
              event={latestTestProgress}
              repairAttempt={
                latestTestStarted?.repair_attempt ?? 0
              }
            />
          )}

          {/* ================================================= */}
          {/* NORMAL EVENTS */}
          {/* ================================================= */}

          {events
            .filter(
              (event) =>
                event.type !==
                  "test_progress" &&
                event.type !==
                  "test_result" &&
                event.type !==
                  "test_started" &&
                event.type !==
                  "repair_started" &&
                event.type !== "done"
            )
            .map((event, index) => (
              <EventCard
                key={index}
                event={event}
              />
            ))}

          {/* ================================================= */}
          {/* TEST RESULT */}
          {/* ================================================= */}

          {latestTestResult && (
            <EventCard
              event={latestTestResult}
            />
          )}

        </div>
      </div>
    </div>
  );
}

/* ========================================================== */
/* TEST PROGRESS */
/* ========================================================== */

function TestProgressCard({
  event,
  repairAttempt,
}: {
  event: AgentEvent;
  repairAttempt: number;
}) {
  const completed =
    event.completed ?? 0;

  const total =
    event.total ?? 0;

  const percent = Math.min(
    event.percent ?? 0,
    100
  );

  return (
    <div style={progressCardStyle}>

      <div style={progressHeaderStyle}>

        <div style={progressTitleStyle}>
          🧪{" "}
          {repairAttempt > 0
            ? `Running Tests — Repair ${repairAttempt}`
            : "Running Tests"}
        </div>

        <div style={progressPercentStyle}>
          {percent.toFixed(1)}%
        </div>

      </div>

      <div style={progressNumbersStyle}>
        <span>
          {completed.toLocaleString()}
          {" / "}
          {total
            ? total.toLocaleString()
            : "?"}
        </span>

        <span>
          {total
            ? `${total.toLocaleString()} tests`
            : "Tests"}
        </span>
      </div>

      <div style={progressTrackStyle}>
        <div
          style={{
            ...progressFillStyle,
            width: `${percent}%`,
          }}
        />
      </div>

      <div style={progressMessageStyle}>
        {event.message ||
          "Running test suite..."}
      </div>

    </div>
  );
}

/* ========================================================== */
/* EVENT CARD */
/* ========================================================== */

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

  if (event.type === "analysis") {
    return (
      <div style={cardStyle}>

        <h3>
          🧠 Root Cause Analysis
        </h3>

        <div style={sectionStyle}>
          <strong>
            Root Cause
          </strong>

          <p>
            {event.root_cause}
          </p>
        </div>

        <div style={sectionStyle}>
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

  if (event.type === "patch") {
    return (
      <div style={cardStyle}>

        <h3>
          {event.repair_attempt
            ? `🔧 Repair Patch — Attempt ${event.repair_attempt}`
            : "🛠️ Patch Generated"}
        </h3>

        <p>
          <strong>File:</strong>{" "}
          <code>{event.file}</code>
        </p>

        <div style={diffBox}>

          <div style={removedCodeStyle}>
            - {event.old_text}
          </div>

          <div style={addedCodeStyle}>
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
  // TEST RESULT
  // ----------------------------------------------------------

  if (event.type === "test_result") {

    const summary =
      typeof event.summary === "object"
        ? event.summary
        : null;

    const passed =
      summary?.passed ?? 0;

    const failed =
      summary?.failed ?? 0;

    const skipped =
      summary?.skipped ?? 0;

    const didNotRun =
      summary?.did_not_run ?? 0;

    const passedAll =
      event.status === "passed";

    return (
      <div
        style={{
          ...cardStyle,
          border: passedAll
            ? "1px solid #22c55e"
            : "1px solid #ef4444",
        }}
      >

        <div style={testResultHeaderStyle}>
          <h3>
            🧪 Test Results
          </h3>

          <span
            style={{
              ...statusBadgeStyle,
              background: passedAll
                ? "#14532d"
                : "#7f1d1d",
            }}
          >
            {passedAll
              ? "PASSED"
              : "FAILED"}
          </span>
        </div>

        <div style={statsGridStyle}>

          <Stat
            label="Passed"
            value={passed}
            icon="✅"
          />

          <Stat
            label="Failed"
            value={failed}
            icon="❌"
          />

          <Stat
            label="Skipped"
            value={skipped}
            icon="⏭️"
          />

          <Stat
            label="Did Not Run"
            value={didNotRun}
            icon="⚪"
          />

        </div>

        <div style={resultDetailsStyle}>
          <div>
            <strong>
              Exit Code:
            </strong>{" "}
            {event.exit_code}
          </div>

          {event.repair_attempt !==
            undefined && (
            <div>
              🔧 Repair attempt:{" "}
              {event.repair_attempt}
            </div>
          )}
        </div>

      </div>
    );
  }

  // ----------------------------------------------------------
  // FINAL
  // ----------------------------------------------------------

  if (event.type === "final") {

    const verified =
      event.status === "verified";

    return (
      <div
        style={{
          ...cardStyle,
          border: verified
            ? "1px solid #22c55e"
            : "1px solid #f59e0b",
          background: verified
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
          {event.repair_attempts ?? 0}
        </p>

      </div>
    );
  }

  // ----------------------------------------------------------
  // ERROR
  // ----------------------------------------------------------

  if (event.type === "error") {
    return (
      <div
        style={{
          ...cardStyle,
          border:
            "1px solid #ef4444",
          color: "#fecaca",
        }}
      >
        ❌ {event.message}
      </div>
    );
  }

  return null;
}

/* ========================================================== */
/* STAT */
/* ========================================================== */

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: string;
}) {
  return (
    <div style={statStyle}>

      <div style={statLabelStyle}>
        {icon} {label}
      </div>

      <div style={statValueStyle}>
        {value.toLocaleString()}
      </div>

    </div>
  );
}

/* ========================================================== */
/* STYLES */
/* ========================================================== */

const pageStyle = {
  minHeight: "100vh",
  background:
    "linear-gradient(135deg, #020617, #0f172a)",
  color: "#e2e8f0",
  padding: "40px 20px",
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
  flexDirection: "column" as const,
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
  padding: "13px 22px",
  background: "#2563eb",
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
  alignItems: "center",
};

const liveIndicatorStyle = {
  color: "#60a5fa",
  fontFamily: "monospace",
  fontSize: "13px",
};

const emptyStyle = {
  color: "#64748b",
};

const logStyle = {
  padding: "7px 0",
  color: "#cbd5e1",
  fontFamily: "monospace",
  fontSize: "14px",
};

const cardStyle = {
  background: "#0f172a",
  border:
    "1px solid #334155",
  borderRadius: "10px",
  padding: "20px",
  marginTop: "15px",
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
  alignItems: "center",
};

const progressTitleStyle = {
  fontSize: "18px",
  fontWeight: 600,
};

const progressPercentStyle = {
  fontFamily: "monospace",
  fontSize: "20px",
  fontWeight: 700,
};

const progressNumbersStyle = {
  marginTop: "14px",
  display: "flex",
  justifyContent:
    "space-between",
  color: "#94a3b8",
  fontFamily: "monospace",
};

const progressTrackStyle = {
  width: "100%",
  height: "14px",
  background: "#1e293b",
  borderRadius: "999px",
  overflow: "hidden" as const,
  marginTop: "10px",
};

const progressFillStyle = {
  height: "100%",
  background:
    "linear-gradient(90deg, #2563eb, #22c55e)",
  borderRadius: "999px",
  transition:
    "width 0.25s ease",
};

const progressMessageStyle = {
  marginTop: "11px",
  fontFamily: "monospace",
  fontSize: "13px",
  color: "#64748b",
  whiteSpace:
    "nowrap" as const,
  overflow: "hidden",
  textOverflow:
    "ellipsis",
};

const repairCardStyle = {
  marginTop: "15px",
  padding: "18px 20px",
  background:
    "linear-gradient(135deg, #172554, #1e293b)",
  border:
    "1px solid #3b82f6",
  borderRadius: "10px",
  fontFamily: "monospace",
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
  background: "#020617",
  borderRadius: "8px",
  padding: "15px",
  marginTop: "15px",
  fontFamily: "monospace",
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

const testResultHeaderStyle = {
  display: "flex",
  justifyContent:
    "space-between",
  alignItems: "center",
};

const statusBadgeStyle = {
  padding: "5px 10px",
  borderRadius: "999px",
  fontFamily: "monospace",
  fontSize: "12px",
  fontWeight: 700,
};

const statsGridStyle = {
  display: "grid",
  gridTemplateColumns:
    "repeat(4, 1fr)",
  gap: "12px",
  marginTop: "18px",
};

const statStyle = {
  padding: "15px",
  background: "#020617",
  borderRadius: "8px",
  border:
    "1px solid #1e293b",
};

const statLabelStyle = {
  color: "#94a3b8",
  fontSize: "13px",
};

const statValueStyle = {
  marginTop: "8px",
  fontSize: "22px",
  fontWeight: 700,
  fontFamily: "monospace",
};

const resultDetailsStyle = {
  marginTop: "18px",
  color: "#94a3b8",
  display: "flex",
  gap: "25px",
  flexWrap: "wrap" as const,
};

export default App;