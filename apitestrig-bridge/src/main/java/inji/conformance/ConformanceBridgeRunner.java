package inji.conformance;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

import org.testng.ITestResult;
import org.testng.TestNG;
import org.testng.ITestListener;

import io.mosip.testrig.apirig.testrunner.BaseTestCase;
import io.mosip.testrig.apirig.utils.ConfigManager;

/**
 * Runs one conformance TestNG suite (certify, verify or combined) and gates the build
 * on the outcome.
 *
 * Usage:
 *   java ... inji.conformance.ConformanceBridgeRunner --component certify|verify|combined \
 *        --results path/to/conformance-results.json [--min-pass-rate 100]
 *
 * Exit code 0 = benchmark met, 1 = benchmark failed or run could not be trusted.
 * A machine-readable summary is written to testng-report/gate-summary.json.
 *
 * This runner sets the system properties and BaseTestCase fields that MOSIP's
 * EmailableReport listener expects (report name, output dir, module/environment
 * labels) so the generated HTML report looks like a normal api-testrig report.
 * It does not do the rig's MOSIP-environment setup (Keycloak users, PMS, health
 * check), which the conformance bridge does not need.
 */
public final class ConformanceBridgeRunner {

    private static final String BENCHMARK_POLICY_TEXT = "project policy (the problem statement requires "
            + "benchmark gating but defines no numeric benchmark): every executed conformance module must "
            + "pass. By default a module passes with result PASSED, or with result WARNING while "
            + "benchmark.allowWarnings=true (flagged in the report for manual review); with "
            + "benchmark.allowWarnings=false only a literal PASSED passes. FAILED, REVIEW, missing or "
            + "unknown results, and an empty result set, fail the gate.";

    private ConformanceBridgeRunner() {
    }

    /** Counts TestNG outcomes for the benchmark gate. */
    static final class CountingListener implements ITestListener {
        int passed;
        int failed;
        int skipped;
        final List<String> failedNames = new ArrayList<>();

        @Override
        public void onTestSuccess(ITestResult result) {
            passed++;
        }

        @Override
        public void onTestFailure(ITestResult result) {
            failed++;
            Object name = result.getAttribute("TestCaseName");
            failedNames.add(name != null ? name.toString() : result.getMethod().getMethodName());
        }

        @Override
        public void onTestSkipped(ITestResult result) {
            skipped++;
        }
    }

    public static void main(String[] args) throws Exception {
        String component = null;
        String results = null;
        double minPassRate = 100.0;
        long maxResultAgeMinutes = 60;
        String expectRunId = null;
        for (int i = 0; i < args.length - 1; i++) {
            switch (args[i]) {
                case "--component" -> component = args[++i];
                case "--results" -> results = args[++i];
                case "--min-pass-rate" -> minPassRate = Double.parseDouble(args[++i]);
                case "--max-result-age-minutes" -> maxResultAgeMinutes = Long.parseLong(args[++i]);
                case "--expect-run-id" -> expectRunId = args[++i];
                default -> {
                }
            }
        }
        if (component == null || results == null
                || !(component.equals("certify") || component.equals("verify") || component.equals("combined"))) {
            System.err.println("[ERROR] usage: ConformanceBridgeRunner --component certify|verify|combined "
                    + "--results <conformance-results.json> [--min-pass-rate <0-100>]");
            System.exit(2);
        }

        // Freshness gate: only gate on results the current orchestration just produced.
        // The runner stamps every output with run.id and run.started_at and writes the
        // file atomically; a file without a fresh timestamp is refused, so a stale file
        // left over from an older or interrupted run can never satisfy the benchmark.
        if (!Files.exists(Path.of(results))) {
            System.out.println("[GATE] FAIL - results file " + results + " does not exist. "
                    + "Run scripts/conformance_runner.py first and gate on its fresh output.");
            writeGateSummary(component, results, 0, new CountingListener(), 0.0, minPassRate, false);
            System.exit(1);
        }
        String runId = null;
        String runStartedAt = null;
        try {
            org.json.JSONObject root = new org.json.JSONObject(
                    Files.readString(Path.of(results), java.nio.charset.StandardCharsets.UTF_8));
            org.json.JSONObject run = root.optJSONObject("run");
            if (run != null) {
                runId = run.optString("id", null);
                runStartedAt = run.optString("started_at", null);
            }
        } catch (Exception e) {
            // leave runId/runStartedAt null; the freshness check below fails closed
        }
        if (expectRunId != null && !expectRunId.equals(runId)) {
            System.out.println("[GATE] FAIL - results file " + results + " belongs to run id " + runId
                    + ", not the expected run " + expectRunId + ". Refusing to gate on another run's output.");
            writeGateSummary(component, results, 0, new CountingListener(), 0.0, minPassRate, false);
            System.exit(1);
        }
        if (runStartedAt == null) {
            System.out.println("[GATE] FAIL - results file " + results + " has no run.started_at "
                    + "timestamp. Freshness cannot be verified, so the file is not trusted for "
                    + "gating. Re-run scripts/conformance_runner.py and gate on its fresh output.");
            writeGateSummary(component, results, 0, new CountingListener(), 0.0, minPassRate, false);
            System.exit(1);
        }
        try {
            long ageMinutes = java.time.Duration.between(Instant.parse(runStartedAt), Instant.now()).toMinutes();
            if (ageMinutes > maxResultAgeMinutes) {
                System.out.println("[GATE] FAIL - results file " + results + " is " + ageMinutes
                        + " minutes old (run id " + runId + ", started " + runStartedAt + "), older than the "
                        + "--max-result-age-minutes " + maxResultAgeMinutes + " limit. Re-run "
                        + "scripts/conformance_runner.py and gate on its fresh output.");
                writeGateSummary(component, results, 0, new CountingListener(), 0.0, minPassRate, false);
                System.exit(1);
            }
            System.out.println("[INFO] Results file freshness OK: run id " + runId + ", started "
                    + runStartedAt + " (" + ageMinutes + " min ago, limit " + maxResultAgeMinutes + ").");
        } catch (java.time.format.DateTimeParseException e) {
            System.out.println("[GATE] FAIL - results file " + results + " has an unparseable "
                    + "run.started_at ('" + runStartedAt + "'). Freshness cannot be verified.");
            writeGateSummary(component, results, 0, new CountingListener(), 0.0, minPassRate, false);
            System.exit(1);
        }

        System.setProperty("conformance.results", results);
        System.setProperty("conformance.component", component);
        System.setProperty("testng.outpur.dir", "testng-report"); // property name typo matches apitest-commons
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd-HH-mm"));
        System.setProperty("emailable.report2.name",
                "inji-conformance-" + component + "-" + timestamp + "-report.html");
        System.setProperty("modules", "conformance-" + component);
        // EmailableReport 1.4.0 requires an env.endpoint host with at least two dots (label only).
        System.setProperty("env.endpoint", "conformance.local.run");
        System.setProperty("env.user", "conformance");

        // Keep generated report copies inside testng-report instead of the working directory.
        ConfigManager.init(java.util.Map.of("mountPathForReport", "testng-report"));

        // Labels MOSIP's EmailableReport expects; harmless stand-ins, no MOSIP environment needed.
        BaseTestCase.environment = "local";
        BaseTestCase.testLevel = "conformance";
        BaseTestCase.currentModule = "conformance-" + component;

        String suiteResource = "/testNgXmlFiles/" + switch (component) {
            case "certify" -> "conformanceCertifyMasterTestSuite.xml";
            case "verify" -> "conformanceVerifyMasterTestSuite.xml";
            default -> "conformanceCombinedMasterTestSuite.xml";
        };
        Path suiteFile = extractResource(suiteResource);

        TestNG testng = new TestNG();
        testng.setTestSuites(List.of(suiteFile.toString()));
        testng.setOutputDirectory("testng-report");
        CountingListener counter = new CountingListener();
        testng.addListener((ITestListener) counter);

        System.out.println("[INFO] Running " + component + " conformance suite through TestNG "
                + "with MOSIP EmailableReport listener. Results: " + Path.of(results).toAbsolutePath());
        testng.run();

        int executed = counter.passed + counter.failed + counter.skipped;
        double passRate = executed == 0 ? 0.0 : (100.0 * counter.passed) / executed;
        boolean gatePassed = executed > 0 && counter.failed == 0 && counter.skipped == 0
                && passRate >= minPassRate;

        System.out.println("[GATE] component=" + component + " executed=" + executed + " passed=" + counter.passed
                + " failed=" + counter.failed + " skipped=" + counter.skipped
                + String.format(" passRate=%.1f%% minPassRate=%.1f%%", passRate, minPassRate));
        System.out.println("[GATE] benchmark policy: " + BENCHMARK_POLICY_TEXT);
        if (!counter.failedNames.isEmpty()) {
            System.out.println("[GATE] failing modules:");
            counter.failedNames.forEach(name -> System.out.println("[GATE]   - " + name));
        }

        writeGateSummary(component, results, executed, counter, passRate, minPassRate, gatePassed);

        if (gatePassed) {
            System.out.println("[GATE] PASS - conformance benchmark met for " + component + ".");
            System.exit(0);
        }
        System.out.println("[GATE] FAIL - conformance benchmark NOT met for " + component
                + ". Failing the build so a regression cannot ship.");
        System.exit(1);
    }

    private static Path extractResource(String resource) throws IOException {
        try (InputStream in = ConformanceBridgeRunner.class.getResourceAsStream(resource)) {
            if (in == null) {
                throw new IOException("suite resource not found on classpath: " + resource);
            }
            Path temp = Files.createTempFile("conformance-suite-", ".xml");
            Files.copy(in, temp, StandardCopyOption.REPLACE_EXISTING);
            temp.toFile().deleteOnExit();
            return temp;
        }
    }

    private static void writeGateSummary(String component, String results, int executed,
            CountingListener counter, double passRate, double minPassRate, boolean gatePassed) throws IOException {
        Files.createDirectories(Path.of("testng-report"));
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        json.append("  \"component\": \"").append(component).append("\",\n");
        json.append("  \"resultsFile\": \"").append(results.replace("\\", "\\\\")).append("\",\n");
        json.append("  \"benchmark\": \"").append(BENCHMARK_POLICY_TEXT.replace("\"", "'")).append("\",\n");
        json.append("  \"minPassRatePercent\": ").append(minPassRate).append(",\n");
        json.append("  \"executed\": ").append(executed).append(",\n");
        json.append("  \"passed\": ").append(counter.passed).append(",\n");
        json.append("  \"failed\": ").append(counter.failed).append(",\n");
        json.append("  \"skipped\": ").append(counter.skipped).append(",\n");
        json.append(String.format("  \"passRatePercent\": %.1f,\n", passRate));
        json.append("  \"gatePassed\": ").append(gatePassed).append("\n");
        json.append("}\n");
        Files.writeString(Path.of("testng-report", "gate-summary.json"), json.toString());
    }
}
